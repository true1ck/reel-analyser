"""
Job API routes — create, list, get, update, delete, retry analysis jobs.
"""
from __future__ import annotations
import shutil
from pathlib import Path
import asyncio

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from backend.database import create_job, get_job, list_jobs, update_job, delete_job, get_stats, list_collections, get_top_reels, get_creators, get_trending_hashtags
from backend.models import (
    JobCreate,
    ChannelJobCreate,
    JobResponse,
    JobListResponse,
    BatchCreateResponse,
    JobUpdate,
    StatsResponse,
    CollectionsResponse,
    CollectionItem,
    ChatRequest,
    ChatResponse,
    TopReelItem,
    CreatorItem,
    HashtagItem,
)
from backend.utils.url_parser import parse_batch_input
from backend.workers.job_worker import job_queue

router = APIRouter(prefix="/api")


@router.post("/jobs", response_model=BatchCreateResponse)
async def create_jobs(body: JobCreate):
    """Submit one or more Instagram Reel URLs for analysis."""
    raw_text = "\n".join(body.urls)
    parsed = parse_batch_input(raw_text)

    created_jobs = []
    invalid_urls = []

    for entry in parsed:
        if entry["reel_id"] is None:
            invalid_urls.append(entry["original"])
            continue

        job = await create_job(entry["reel_id"], entry["url"], platform=entry["platform"])
        created_jobs.append(JobResponse(**job))

        # Enqueue for processing
        print(f"DEBUG: Enqueueing job {job['id']} for reel {entry['reel_id']}")
        await job_queue.put((job["id"], entry["url"], entry["reel_id"]))
        print(f"DEBUG: Enqueued job {job['id']}, queue size: {job_queue.qsize()}")

    return BatchCreateResponse(jobs=created_jobs, invalid_urls=invalid_urls)


@router.post("/jobs/channel", response_model=BatchCreateResponse)
async def create_channel_jobs(body: ChannelJobCreate):
    """Fetch top videos from a channel and submit them for analysis."""
    from backend.services.downloader import fetch_channel_videos
    from backend.database import get_job_by_reel_id
    
    # 1. Fetch URLs
    try:
        urls = fetch_channel_videos(body.channel_url, limit=body.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch channel: {str(e)}")

    if not urls:
        raise HTTPException(status_code=400, detail="No videos found or unsupported channel URL")

    # 2. Parse URLs
    raw_text = "\n".join(urls)
    parsed = parse_batch_input(raw_text)

    created_jobs = []
    invalid_urls = []

    for entry in parsed:
        if entry["reel_id"] is None:
            invalid_urls.append(entry["original"])
            continue

        # 3. Check if already analyzed/in database
        existing = await get_job_by_reel_id(entry["reel_id"])
        if existing is not None:
            # Skip since we don't want to re-analyze
            continue

        # 4. Create Job
        category_to_use = body.category if body.category else "Uncategorized"
        job = await create_job(entry["reel_id"], entry["url"], platform=entry["platform"], category=category_to_use)
            
        created_jobs.append(JobResponse(**job))

        # Enqueue for processing
        print(f"DEBUG: Enqueueing channel job {job['id']} for reel {entry['reel_id']}")
        await job_queue.put((job["id"], entry["url"], entry["reel_id"]))
        print(f"DEBUG: Enqueued channel job {job['id']}, queue size: {job_queue.qsize()}")

    return BatchCreateResponse(jobs=created_jobs, invalid_urls=invalid_urls)


@router.get("/jobs", response_model=JobListResponse)
async def get_jobs(
    status: str | None = Query(None, description="Filter by status"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search in title, transcript, analysis"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all jobs with optional filters and pagination."""
    jobs, total = await list_jobs(status=status, category=category, limit=limit, offset=offset, search=search)
    return JobListResponse(
        jobs=[JobResponse(**j) for j in jobs],
        total=total,
    )


async def _refresh_job_stats_task(job_id: str, url: str):
    """Background task to fetch latest stats for a video."""
    from backend.services.downloader import refresh_metadata
    from backend.database import update_job
    
    stats = await asyncio.to_thread(refresh_metadata, url)
    if stats:
        await update_job(job_id, **stats)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_by_id(job_id: str, background_tasks: BackgroundTasks):
    """Get a single job by its ID and refresh its stats in the background."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Trigger a background refresh if the job is complete
    if job["status"] == "done":
        background_tasks.add_task(_refresh_job_stats_task, job_id, job["url"])
        
    return JobResponse(**job)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def update_job_metadata(job_id: str, body: JobUpdate):
    """Update tags or notes for a job."""
    existing = await get_job(job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Job not found")

    updates = {}
    if body.tags is not None:
        updates["tags"] = body.tags
    if body.notes is not None:
        updates["notes"] = body.notes

    if updates:
        job = await update_job(job_id, **updates)
    else:
        job = existing

    return JobResponse(**job)


@router.delete("/jobs/{job_id}")
async def delete_job_by_id(job_id: str):
    """Delete a job and its associated files."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete files if they exist
    if job.get("video_path"):
        reel_dir = Path(job["video_path"]).parent
        if reel_dir.exists():
            shutil.rmtree(reel_dir, ignore_errors=True)

    await delete_job(job_id)
    return {"status": "deleted", "job_id": job_id}


@router.post("/jobs/{job_id}/refresh-metadata", response_model=JobResponse)
async def refresh_metadata(job_id: str):
    """Re-fetch metadata (views, likes, comments, creator info) without re-downloading video."""
    from backend.services.downloader import fetch_metadata
    
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    try:
        # Fetch fresh metadata
        new_meta = fetch_metadata(job["url"])
        
        # Update database with new fields
        update_data = {
            "view_count": new_meta.get("view_count", 0),
            "play_count": new_meta.get("play_count", 0),
            "like_count": new_meta.get("like_count", 0),
            "comment_count": new_meta.get("comment_count", 0),
            "share_count": new_meta.get("share_count", 0),
            "owner_username": new_meta.get("owner_username"),
            "owner_name": new_meta.get("owner_name"),
            "owner_id": new_meta.get("owner_id"),
            "duration_sec": new_meta.get("duration_sec"),
            "published_at": new_meta.get("published_at"),
            "hashtags_json": new_meta.get("hashtags_json"),
            "comments_json": new_meta.get("comments_json"),
        }
        
        # Merge dictionary using update_job
        updated_job = await update_job(job_id, **update_data)
        if not updated_job:
            raise HTTPException(status_code=500, detail="Failed to update job metadata in database")
            
        return JobResponse(**updated_job)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh metadata: {str(e)}")


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str):
    """Retry a failed job."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("failed",):
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    # Reset job state
    updated = await update_job(
        job_id,
        status="queued",
        progress_pct=0,
        current_step=None,
        error_message=None,
        started_at=None,
        completed_at=None,
        processing_ms=None,
    )

    # Re-enqueue
    await job_queue.put((job_id, job["url"], job["reel_id"]))

    return JobResponse(**updated)


@router.post("/jobs/{job_id}/stop")
async def stop_job_by_id(job_id: str):
    """Stop/cancel a running job."""
    from backend.workers.job_worker import stop_job, active_tasks
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Stop requested for job_id: {job_id}")
    logger.info(f"Currently active tasks: {list(active_tasks.keys())}")
    
    success = await stop_job(job_id)
    if not success:
        logger.warning(f"Failed to stop job {job_id} — not in active_tasks")
        raise HTTPException(status_code=400, detail=f"Job {job_id} is not currently running. Active: {list(active_tasks.keys())}")
        
    return {"status": "stopping", "job_id": job_id}


@router.get("/stats", response_model=StatsResponse)
async def get_dashboard_stats():
    """Get aggregate statistics for the dashboard."""
    stats = await get_stats()
    return StatsResponse(**stats)


@router.get("/collections", response_model=CollectionsResponse)
async def get_collections():
    """Get all collections (categories) with their counts."""
    collections = await list_collections()
    return CollectionsResponse(
        collections=[CollectionItem(**c) for c in collections]
    )


@router.post("/jobs/{job_id}/chat", response_model=ChatResponse)
async def chat_with_job(job_id: str, body: ChatRequest):
    """Interact with a specific video's analysis via chat or re-analysis."""
    from backend.services.analyzer import _run_text_pass, _run_vision_pass
    
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
        
    user_msg = body.message.strip()
    
    # ── Logic Branch 1: Vision Re-analysis ──
    if user_msg.lower().startswith(r"\reanalyse") or user_msg.lower().startswith(r"\reanalyze"):
        # Extract the prompt
        cmd_prefix = user_msg.split()[0]
        custom_prompt = user_msg[len(cmd_prefix):].strip()
        
        if not custom_prompt:
            custom_prompt = "Describe the video in detail."
            
        video_path = job.get("video_path")
        if not video_path or not Path(video_path).exists():
            raise HTTPException(status_code=400, detail="Video file not available for re-analysis.")
            
        wrapper_prompt = f"Analyze this video and strictly answer the user's question. QUESTION: {custom_prompt}"
        
        try:
            # We must run this in a thread because it's synchronous
            import asyncio
            reply = await asyncio.to_thread(_run_vision_pass, Path(video_path), wrapper_prompt)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")
            
        return ChatResponse(reply=reply)


# ── Analytics Endpoints ────────────────────────────────────────────────────────────

    # ── Logic Branch 2: Standard Text RAG ──
    transcript = job.get("transcript", "No transcript available.")
    analysis_md = job.get("analysis_md", "No analysis available.")
    
    prompt = f"""You are a helpful AI assistant answering questions about a specific video.
Use the provided transcript and analysis notes to answer the user's question accurately.
If the answer is not in the provided text, just say you don't know based on the current notes.

TRANSCRIPT:
{transcript}

ANALYSIS NOTES:
{analysis_md}

USER QUESTION: {user_msg}
"""
    
    try:
        import asyncio
        reply = await asyncio.to_thread(_run_text_pass, prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")
        
    return ChatResponse(reply=reply)


# ── Analytics Endpoints ────────────────────────────────────────────────────────────



@router.get("/analytics/top", response_model=list[TopReelItem])
async def get_top_reels_endpoint(
    sort_by: str = Query("likes", description="likes | plays | shares | comments | hook_rate | engagement"),
    limit: int = Query(10, ge=1, le=50)
):
    """Get top reels sorted by a virality metric. Powers the Hub leaderboard."""
    rows = await get_top_reels(sort_by=sort_by, limit=limit)
    items = []
    for r in rows:
        v = r.get("view_count") or 0
        p = r.get("play_count") or 0
        l = r.get("like_count") or 0
        c = r.get("comment_count") or 0
        s = r.get("share_count") or 0
        hook_rate = round(p / v, 2) if v > 0 else None
        engagement_rate = round((l + c + s) / v, 4) if v > 0 else None
        items.append(TopReelItem(
            id=r["id"], reel_id=r["reel_id"], url=r["url"],
            title=r.get("title"), owner_username=r.get("owner_username"),
            owner_name=r.get("owner_name"), category=r.get("category", "Uncategorized"),
            subcategory=r.get("subcategory"), view_count=v, play_count=p,
            like_count=l, share_count=s, comment_count=c,
            duration_sec=r.get("duration_sec"), published_at=r.get("published_at"),
            hook_rate=hook_rate, engagement_rate=engagement_rate,
        ))
    return items


@router.get("/analytics/creators", response_model=list[CreatorItem])
async def get_creators_endpoint(limit: int = Query(20, ge=1, le=100)):
    """Get top creators by reel count and engagement."""
    rows = await get_creators(limit=limit)
    return [CreatorItem(**r) for r in rows]


@router.get("/analytics/trending-hashtags", response_model=list[HashtagItem])
async def get_trending_hashtags_endpoint(limit: int = Query(20, ge=1, le=100)):
    """Get trending hashtags across all analyzed reels."""
    tags = await get_trending_hashtags(limit=limit)
    return [HashtagItem(**t) for t in tags]

