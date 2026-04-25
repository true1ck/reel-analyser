"""
Job API routes — create, list, get, update, delete, retry analysis jobs.
"""
from __future__ import annotations
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.database import create_job, get_job, list_jobs, update_job, delete_job, get_stats, list_collections
from backend.models import (
    JobCreate,
    JobResponse,
    JobListResponse,
    BatchCreateResponse,
    JobUpdate,
    StatsResponse,
    CollectionsResponse,
    CollectionItem,
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


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_by_id(job_id: str):
    """Get a single job by its ID."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
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
