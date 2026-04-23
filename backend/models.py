"""
Pydantic models for API request/response schemas.
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Request body for creating new analysis jobs."""
    urls: list[str] = Field(..., min_length=1, description="List of Instagram Reel URLs or IDs")


class JobProgress(BaseModel):
    """WebSocket progress event payload."""
    job_id: str
    status: str
    progress_pct: int = 0
    current_step: str = ""
    error_message: str | None = None


class JobResponse(BaseModel):
    """Single job in API responses."""
    id: str
    reel_id: str
    url: str
    platform: str = "instagram"
    title: str | None = None
    status: str
    progress_pct: int = 0
    current_step: str | None = None
    error_message: str | None = None
    transcript: str | None = None
    analysis_md: str | None = None
    tags: list[str] = []
    notes: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    processing_ms: int | None = None


class JobListResponse(BaseModel):
    """Response for listing jobs."""
    jobs: list[JobResponse]
    total: int


class BatchCreateResponse(BaseModel):
    """Response for batch job creation."""
    jobs: list[JobResponse]
    invalid_urls: list[str] = []


class JobUpdate(BaseModel):
    """Request body for updating job metadata."""
    tags: list[str] | None = None
    notes: str | None = None


class StatsResponse(BaseModel):
    """Dashboard statistics."""
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    queued_jobs: int = 0
    processing_jobs: int = 0
    avg_processing_ms: int | None = None
    total_processing_ms: int = 0
