"""
SQLite database layer using aiosqlite for async operations.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone

import aiosqlite

from backend.config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    reel_id         TEXT NOT NULL,
    url             TEXT NOT NULL,
    platform        TEXT NOT NULL DEFAULT 'instagram',
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'queued',
    progress_pct    INTEGER DEFAULT 0,
    current_step    TEXT,
    error_message   TEXT,
    video_path      TEXT,
    audio_path      TEXT,
    transcript      TEXT,
    analysis_md     TEXT,
    category        TEXT DEFAULT 'Uncategorized',
    subcategory     TEXT,
    tags            TEXT DEFAULT '[]',
    notes           TEXT,
    created_at      TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    processing_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_reel_id ON jobs(reel_id);
CREATE INDEX IF NOT EXISTS idx_jobs_category_sub ON jobs(category, subcategory);
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(str(DB_PATH), timeout=20.0)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize the database schema."""
    db = await get_db()
    try:
        # First: check for missing columns on existing tables
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        table_exists = await cursor.fetchone()

        if table_exists:
            # Migrate existing table — add missing columns BEFORE schema runs indexes
            cursor = await db.execute("PRAGMA table_info(jobs)")
            columns = [row[1] for row in await cursor.fetchall()]
            if "platform" not in columns:
                await db.execute("ALTER TABLE jobs ADD COLUMN platform TEXT NOT NULL DEFAULT 'instagram'")
            if "category" not in columns:
                await db.execute("ALTER TABLE jobs ADD COLUMN category TEXT DEFAULT 'Uncategorized'")
            if "subcategory" not in columns:
                await db.execute("ALTER TABLE jobs ADD COLUMN subcategory TEXT")
            await db.commit()

        # Then: run full schema (CREATE TABLE IF NOT EXISTS + indexes)
        await db.executescript(SCHEMA)

        # Category index (safe now that column exists)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_category_sub ON jobs(category, subcategory)")
        await db.commit()
    finally:
        await db.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert a Row to a dict, parsing JSON fields."""
    d = dict(row)
    # Parse tags from JSON string
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    else:
        d["tags"] = []
    return d


async def create_job(reel_id: str, url: str, platform: str = "instagram", category: str = "Uncategorized") -> dict:
    """Create a new job record and return it."""
    job_id = str(uuid.uuid4())
    now = _now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO jobs (id, reel_id, url, platform, status, progress_pct, tags, category, created_at)
               VALUES (?, ?, ?, ?, 'queued', 0, '[]', ?, ?)""",
            (job_id, reel_id, url, platform, category, now),
        )
        await db.commit()
        return {
            "id": job_id,
            "reel_id": reel_id,
            "url": url,
            "platform": platform,
            "status": "queued",
            "progress_pct": 0,
            "current_step": None,
            "error_message": None,
            "title": None,
            "transcript": None,
            "analysis_md": None,
            "category": category,
            "subcategory": None,
            "tags": [],
            "notes": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "processing_ms": None,
        }
    finally:
        await db.close()


async def get_job(job_id: str) -> dict | None:
    """Get a single job by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        await db.close()


async def get_job_by_reel_id(reel_id: str) -> dict | None:
    """Get a single job by reel_id."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE reel_id = ?", (reel_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        await db.close()


async def list_jobs(
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """List jobs with optional filters. Returns (jobs, total_count)."""
    db = await get_db()
    try:
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if category:
            conditions.append("category = ?")
            params.append(category)

        if search:
            conditions.append(
                "(title LIKE ? OR transcript LIKE ? OR analysis_md LIKE ? OR reel_id LIKE ? OR platform LIKE ? OR category LIKE ?)"
            )
            search_term = f"%{search}%"
            params.extend([search_term] * 6)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Get total count
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM jobs{where_clause}", params
        )
        total = (await count_cursor.fetchone())[0]

        # Get paginated results
        cursor = await db.execute(
            f"SELECT * FROM jobs{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows], total
    finally:
        await db.close()


async def update_job(job_id: str, **fields) -> dict | None:
    """Update specific fields of a job. Returns updated job or None."""
    db = await get_db()
    try:
        # Serialize tags to JSON if present
        if "tags" in fields and isinstance(fields["tags"], list):
            fields["tags"] = json.dumps(fields["tags"])

        set_clauses = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        await db.execute(
            f"UPDATE jobs SET {set_clauses} WHERE id = ?", values
        )
        await db.commit()
    finally:
        await db.close()
        
    return await get_job(job_id)


async def delete_job(job_id: str) -> bool:
    """Delete a job by ID. Returns True if deleted."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_stats() -> dict:
    """Get dashboard statistics."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as completed_jobs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_jobs,
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued_jobs,
                SUM(CASE WHEN status IN ('downloading', 'transcribing', 'analyzing') THEN 1 ELSE 0 END) as processing_jobs,
                AVG(CASE WHEN processing_ms IS NOT NULL THEN processing_ms END) as avg_processing_ms,
                COALESCE(SUM(processing_ms), 0) as total_processing_ms
            FROM jobs
        """)
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def list_collections() -> list[dict]:
    """Get all categories with their job counts."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT
                COALESCE(category, 'Uncategorized') as category,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as completed,
                MAX(completed_at) as last_updated
            FROM jobs
            WHERE status = 'done'
            GROUP BY COALESCE(category, 'Uncategorized')
            ORDER BY total DESC
        """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()
