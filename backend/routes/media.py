"""
Media routes — serve video and audio files for embedded playback in the UI.
"""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.database import get_job

router = APIRouter(prefix="/api")


@router.get("/jobs/{job_id}/video")
async def stream_video(job_id: str):
    """Stream the downloaded video file for embedded playback."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    video_path = job.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/jobs/{job_id}/audio")
async def stream_audio(job_id: str):
    """Stream the extracted audio file."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    audio_path = job.get("audio_path")
    if not audio_path or not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        audio_path,
        media_type="audio/wav",
    )


@router.get("/jobs/{job_id}/pdf")
async def export_pdf(job_id: str):
    """Generate and return a PDF export of the analysis."""
    from backend.services.pdf_exporter import generate_pdf
    
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.get("analysis_md"):
        raise HTTPException(status_code=400, detail="Analysis not yet completed")

    # Save PDF in the same directory as the video
    report_dir = Path(job["video_path"]).parent
    pdf_path = report_dir / f"{job['reel_id']}_report.pdf"
    
    generate_pdf(job["analysis_md"], pdf_path, title=job.get("title") or f"Analysis: {job['reel_id']}")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{job['reel_id']}_report.pdf"
    )
