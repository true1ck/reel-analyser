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
    processing_ms   INTEGER,
    view_count      INTEGER DEFAULT 0,
    like_count      INTEGER DEFAULT 0,
    share_count     INTEGER DEFAULT 0,
    comment_count   INTEGER DEFAULT 0,
    play_count      INTEGER DEFAULT 0,
    owner_username  TEXT,
    owner_name      TEXT,
    owner_id        TEXT,
    duration_sec    REAL,
    published_at    TEXT,
    hashtags_json   TEXT DEFAULT '[]',
    comments_json   TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_reel_id ON jobs(reel_id);
CREATE INDEX IF NOT EXISTS idx_jobs_category_sub ON jobs(category, subcategory);
CREATE INDEX IF NOT EXISTS idx_jobs_owner ON jobs(owner_username);
CREATE INDEX IF NOT EXISTS idx_jobs_likes ON jobs(like_count DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_plays ON jobs(play_count DESC);
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
            new_cols = {
                "platform":       "TEXT NOT NULL DEFAULT 'instagram'",
                "category":       "TEXT DEFAULT 'Uncategorized'",
                "subcategory":    "TEXT",
                "view_count":     "INTEGER DEFAULT 0",
                "like_count":     "INTEGER DEFAULT 0",
                "share_count":    "INTEGER DEFAULT 0",
                "comment_count":  "INTEGER DEFAULT 0",
                "play_count":     "INTEGER DEFAULT 0",
                "owner_username": "TEXT",
                "owner_name":     "TEXT",
                "owner_id":       "TEXT",
                "duration_sec":   "REAL",
                "published_at":   "TEXT",
                "hashtags_json":  "TEXT DEFAULT '[]'",
                "comments_json":  "TEXT DEFAULT '[]'",
            }
            for col, col_type in new_cols.items():
                if col not in columns:
                    await db.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
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
            "completed_at": now,
            "processing_ms": None,
            "view_count": 0,
            "like_count": 0,
            "share_count": 0,
            "comment_count": 0,
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


async def get_jobs_by_ids(job_ids: list[str]) -> list[dict]:
    """Fetch multiple jobs by their IDs."""
    if not job_ids:
        return []
    db = await get_db()
    try:
        placeholders = ",".join("?" for _ in job_ids)
        cursor = await db.execute(f"SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids)
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
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


async def search_jobs_fts(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """
    Full-text search across analysis_md + transcript.
    Returns jobs ranked by keyword match count.
    """
    db = await get_db()
    try:
        # Ignore common stop words to avoid matching irrelevant jobs
        stop_words = {"how", "to", "get", "a", "an", "the", "and", "or", "for", "is", "of", "in", "my", "on", "it", "this", "with"}
        terms = [t for t in query.lower().split() if t not in stop_words and len(t) > 2]
        
        # If they only searched stop words, fallback to the full query
        if not terms:
            terms = [query.lower().strip()]
            
        conditions = []
        params = []
        for term in terms[:6]:  # cap at 6 meaningful terms
            conditions.append(
                "(LOWER(analysis_md) LIKE ? OR LOWER(transcript) LIKE ? OR LOWER(title) LIKE ?)"
            )
            t = f"%{term}%"
            params.extend([t, t, t])
        
        # Use OR so partial matches work (e.g. if one word is a typo)
        where = " OR ".join(conditions) if conditions else "1=1"
        if category:
            where = f"({where}) AND category = ?"
            params.append(category)
        
        cursor = await db.execute(
            f"SELECT * FROM jobs WHERE status='done' AND ({where})",
            tuple(params)
        )
        rows = await cursor.fetchall()
        jobs = [_row_to_dict(r) for r in rows]
        
        # In-memory scoring to rank best matches at the top
        for job in jobs:
            score = 0
            text_corpus = (
                (job.get('analysis_md') or "") + " " + 
                (job.get('transcript') or "") + " " + 
                (job.get('title') or "")
            ).lower()
            
            for term in terms:
                if term in text_corpus:
                    score += 1
            job['_match_score'] = score
            
        # Sort by score descending, then by completion date
        jobs.sort(key=lambda x: (x['_match_score'], x.get('completed_at', '')), reverse=True)
        
        # Remove the temporary score key and return up to the limit
        for job in jobs:
            job.pop('_match_score', None)
            
        return jobs[:limit]
    finally:
        await db.close()


async def get_top_reels(sort_by: str = "likes", limit: int = 10) -> list[dict]:
    """
    Get top reels sorted by a virality metric.
    sort_by: 'likes' | 'plays' | 'shares' | 'comments' | 'hook_rate' | 'engagement'
    """
    db = await get_db()
    try:
        if sort_by == "hook_rate":
            order = "CASE WHEN view_count > 0 THEN CAST(play_count AS REAL)/view_count ELSE 0 END DESC"
        elif sort_by == "engagement":
            order = "CASE WHEN view_count > 0 THEN CAST((like_count + comment_count + share_count) AS REAL)/view_count ELSE 0 END DESC"
        elif sort_by == "plays":
            order = "play_count DESC"
        elif sort_by == "shares":
            order = "share_count DESC"
        elif sort_by == "comments":
            order = "comment_count DESC"
        else:  # likes
            order = "like_count DESC"

        cursor = await db.execute(
            f"SELECT * FROM jobs WHERE status='done' ORDER BY {order} LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()


async def get_creators(limit: int = 20) -> list[dict]:
    """Get top creators by reel count with aggregate engagement stats."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT
                owner_username,
                owner_name,
                COUNT(*) as reel_count,
                SUM(view_count) as total_views,
                SUM(like_count) as total_likes,
                SUM(play_count) as total_plays,
                MAX(published_at) as latest_post
            FROM jobs
            WHERE status='done' AND owner_username IS NOT NULL
            GROUP BY owner_username
            ORDER BY reel_count DESC, total_likes DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_trending_hashtags(limit: int = 20) -> list[dict]:
    """Aggregate hashtag frequency across all analyzed reels."""
    import json
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT hashtags_json, view_count FROM jobs WHERE status='done' AND hashtags_json IS NOT NULL AND hashtags_json != '[]'"
        )
        rows = await cursor.fetchall()
        tag_counts: dict[str, dict] = {}
        for row in rows:
            try:
                tags = json.loads(row[0] or '[]')
                views = row[1] or 0
                for tag in tags:
                    tag = tag.lower().strip('#')
                    if not tag:
                        continue
                    if tag not in tag_counts:
                        tag_counts[tag] = {"tag": tag, "count": 0, "total_views": 0}
                    tag_counts[tag]["count"] += 1
                    tag_counts[tag]["total_views"] += views
            except Exception:
                continue
        sorted_tags = sorted(tag_counts.values(), key=lambda x: x["count"], reverse=True)
        return sorted_tags[:limit]
    finally:
        await db.close()
