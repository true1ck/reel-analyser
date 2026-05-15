"""
Pydantic models for API request/response schemas.
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Request body for creating new analysis jobs."""
    urls: list[str] = Field(..., min_length=1, description="List of Instagram Reel URLs or IDs")


class ChannelJobCreate(BaseModel):
    """Request body for submitting a channel to fetch top videos."""
    channel_url: str = Field(..., description="URL of the channel or profile")
    limit: int = Field(5, ge=1, le=50, description="Number of recent/top videos to fetch")
    category: str = Field("Uncategorized", description="Category or folder to save to")

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
    category: str = "Uncategorized"
    subcategory: str | None = None
    tags: list[str] = []
    notes: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    processing_ms: int | None = None
    view_count: int = 0
    like_count: int = 0
    share_count: int = 0
    comment_count: int = 0
    # Enriched fields
    play_count: int = 0
    owner_username: str | None = None
    owner_name: str | None = None
    owner_id: str | None = None
    duration_sec: float | None = None
    published_at: str | None = None
    hashtags_json: str = '[]'
    comments_json: str = '[]'


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
    avg_processing_ms: float | None = None
    total_processing_ms: int = 0


class CollectionItem(BaseModel):
    """A single category/collection with aggregate info."""
    category: str
    total: int = 0
    completed: int = 0
    last_updated: str | None = None


class CollectionsResponse(BaseModel):
    """Response for listing collections."""
    collections: list[CollectionItem]


class ChatRequest(BaseModel):
    """Request body for video chat."""
    message: str = Field(..., description="User chat message")


class ChatResponse(BaseModel):
    """Response for video chat."""
    reply: str = Field(..., description="AI response")

class GlobalChatRequest(BaseModel):
    message: str = Field(..., description="User question")
    category: str | None = None
    limit: int = Field(5, description="Max number of source cards to return")

class SourceCard(BaseModel):
    job_id: str
    title: str | None
    category: str
    subcategory: str | None
    report_url: str
    original_url: str
    match_summary: str
    view_count: int
    like_count: int

class WebResult(BaseModel):
    title: str
    url: str
    snippet: str

class GlobalChatResponse(BaseModel):
    answer: str
    sources: list[SourceCard]
    web_results: list[WebResult]
    total_reports_searched: int


# ── Analytics Models ──────────────────────────────────────────────────────────

class TopReelItem(BaseModel):
    """A reel in a leaderboard list."""
    id: str
    reel_id: str
    url: str
    title: str | None = None
    owner_username: str | None = None
    owner_name: str | None = None
    category: str = "Uncategorized"
    subcategory: str | None = None
    view_count: int = 0
    play_count: int = 0
    like_count: int = 0
    share_count: int = 0
    comment_count: int = 0
    duration_sec: float | None = None
    published_at: str | None = None
    hook_rate: float | None = None       # computed: play_count / view_count
    engagement_rate: float | None = None # computed: (likes+comments+shares) / view_count


class CreatorItem(BaseModel):
    """Aggregate stats per creator."""
    owner_username: str
    owner_name: str | None = None
    reel_count: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_plays: int = 0
    latest_post: str | None = None


class HashtagItem(BaseModel):
    """Trending hashtag entry."""
    tag: str
    count: int
    total_views: int = 0
