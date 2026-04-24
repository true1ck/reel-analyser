#!/usr/bin/env python3
"""
Migration script — imports existing reel folders into the new SQLite database.
Scans the legacy output directories and creates job records for each.
"""
import asyncio
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone

# Adjust path so we can import the backend
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.config import REELS_DIR, DATA_DIR
from backend.database import init_db, get_db

# Also scan the old output location
LEGACY_DIR = Path(__file__).resolve().parent


async def migrate():
    await init_db()
    
    # Collect all reel directories from both old and new locations
    reel_dirs = []
    
    # Old location: project root has folders like DXI-E02EiNy/
    for d in LEGACY_DIR.iterdir():
        if d.is_dir() and d.name not in ('backend', 'frontend', 'data', 'venv', '__pycache__', 'node_modules'):
            report = d / 'native_report.md'
            if report.exists() or (d / 'report.md').exists():
                reel_dirs.append(d)
    
    # New location: data/reels/
    if REELS_DIR.exists():
        for d in REELS_DIR.iterdir():
            if d.is_dir():
                reel_dirs.append(d)
    
    if not reel_dirs:
        print("No existing reel folders found to migrate.")
        return
    
    db = await get_db()
    imported = 0
    
    for reel_dir in reel_dirs:
        reel_id = reel_dir.name
        
        # Skip if already in DB
        cursor = await db.execute("SELECT id FROM jobs WHERE reel_id = ?", (reel_id,))
        if await cursor.fetchone():
            print(f"  [skip] {reel_id} — already in database")
            continue
        
        # Read report
        report_path = reel_dir / 'native_report.md'
        if not report_path.exists():
            report_path = reel_dir / 'report.md'
        
        analysis_md = ""
        transcript = ""
        url = f"https://www.instagram.com/reel/{reel_id}/"
        
        if report_path.exists():
            content = report_path.read_text()
            # Extract URL from report
            for line in content.split('\n'):
                if line.startswith('**URL:**'):
                    url = line.replace('**URL:**', '').strip()
                    break
            
            # Extract analysis section
            if '## Analysis' in content:
                analysis_md = content.split('## Analysis\n\n', 1)[-1]
                if '## Full Transcript' in analysis_md:
                    parts = analysis_md.split('## Full Transcript')
                    analysis_md = parts[0].rstrip().rstrip('---').strip()
                    transcript = parts[1].strip()
        
        # Find video/audio paths
        video_files = list(reel_dir.glob('reel.*'))
        video_path = str(video_files[0]) if video_files else None
        audio_path = str(reel_dir / 'audio.wav') if (reel_dir / 'audio.wav').exists() else None
        
        # Copy to new location if in old location
        new_dir = REELS_DIR / reel_id
        if reel_dir.parent != REELS_DIR and not new_dir.exists():
            import shutil
            shutil.copytree(reel_dir, new_dir)
            if video_path:
                video_path = str(new_dir / Path(video_path).name)
            if audio_path:
                audio_path = str(new_dir / 'audio.wav')
            print(f"  [copy] {reel_id} → data/reels/{reel_id}/")
        
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        await db.execute(
            """INSERT INTO jobs (id, reel_id, url, title, status, progress_pct, current_step,
               video_path, audio_path, transcript, analysis_md, tags, created_at, completed_at)
               VALUES (?, ?, ?, ?, 'done', 100, 'Imported', ?, ?, ?, ?, '[]', ?, ?)""",
            (job_id, reel_id, url, f"Reel {reel_id}", video_path, audio_path, transcript, analysis_md, now, now),
        )
        imported += 1
        print(f"  [✓] Imported {reel_id}")
    
    await db.commit()
    await db.close()
    print(f"\n[OK] Migrated {imported} reel(s) into database.")


if __name__ == "__main__":
    print("[Migration] Migrating existing reel folders into database...\n")
    asyncio.run(migrate())
