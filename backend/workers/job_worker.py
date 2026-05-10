"""
Async job worker — consumes jobs from the queue and runs the analysis pipeline.

Design: Single worker since MLX models serialize on the GPU anyway.
Jobs are processed sequentially, which is correct for Apple Silicon.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from backend.database import update_job
from backend.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Global job queue
job_queue: asyncio.Queue = asyncio.Queue()

# WebSocket connections for broadcasting progress
ws_connections: set = set()


async def broadcast_progress(job_id: str, status: str, progress_pct: int, current_step: str, error_message: str | None = None):
    """Broadcast job progress to all connected WebSocket clients."""
    import json
    message = json.dumps({
        "type": f"job:{status}" if status in ("done", "failed") else "job:progress",
        "job_id": job_id,
        "status": status,
        "progress_pct": progress_pct,
        "current_step": current_step,
        "error_message": error_message,
    })
    disconnected = set()
    for ws in ws_connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    if disconnected:
        ws_connections.difference_update(disconnected)


async def process_job(job_id: str, url: str, reel_id: str):
    """Process a single job through the full pipeline."""
    now = datetime.now(timezone.utc).isoformat()

    # Mark as started
    await update_job(job_id, status="downloading", started_at=now, progress_pct=0)

    async def on_progress(status: str, pct: int, step: str):
        """Progress callback — updates DB and broadcasts to WebSocket."""
        fields = {"status": status, "progress_pct": pct, "current_step": step}
        if status == "done":
            fields["completed_at"] = datetime.now(timezone.utc).isoformat()
        await update_job(job_id, **fields)
        await broadcast_progress(job_id, status, pct, step)

    result = await run_pipeline(url, reel_id, on_progress=on_progress)

    # Save final results to DB
    if result.error:
        await update_job(
            job_id,
            status="failed",
            error_message=result.error,
            processing_ms=result.processing_ms,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        await broadcast_progress(job_id, "failed", 0, f"Error: {result.error}", result.error)
    else:
        await update_job(
            job_id,
            status="done",
            title=result.title,
            video_path=str(result.video_path) if result.video_path else None,
            audio_path=str(result.audio_path) if result.audio_path else None,
            transcript=result.transcript,
            analysis_md=result.analysis_md,
            category=result.category,
            subcategory=result.subcategory,
            processing_ms=result.processing_ms,
            view_count=result.view_count,
            like_count=result.like_count,
            share_count=result.share_count,
            comment_count=result.comment_count,
            progress_pct=100,
            current_step="Done!",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        await broadcast_progress(job_id, "done", 100, "Done!")


async def worker_loop():
    """Main worker loop — processes jobs from the queue sequentially."""
    logger.info("Job worker started — waiting for jobs...")
    while True:
        try:
            job_id, url, reel_id = await job_queue.get()
            logger.info(f"Processing job {job_id} (reel: {reel_id})")
            await process_job(job_id, url, reel_id)
            logger.info(f"Job {job_id} completed")
            job_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            break
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            # Still call task_done if get() succeeded but process_job failed
            if 'job_id' in locals():
                job_queue.task_done()
