"""
FastAPI entry point — the main server application.

Starts the API server with CORS, WebSocket support, and the background job worker.
"""
import asyncio
import logging
import httpx

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import FRONTEND_URL, NVIDIA_API_KEY, USE_NVIDIA_API
from backend.database import init_db
from backend.routes.jobs import router as jobs_router
from backend.routes.media import router as media_router
from backend.workers.job_worker import worker_loop, ws_connections

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def check_nvidia_api():
    """Verify NVIDIA API key and connectivity at startup."""
    if not USE_NVIDIA_API:
        logger.info("[API] NVIDIA API Key not found. Using local models only.")
        return

    logger.info("[API] Validating NVIDIA Cloud connection...")
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "mistralai/mistral-small-4-119b-2603",
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 1
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            logger.info("[API] NVIDIA Cloud Connection: OK ✅")
        else:
            logger.warning(f"[API] NVIDIA Cloud returned {response.status_code}. Using local fallback. ⚠️")
    except Exception as e:
        logger.warning(f"[API] NVIDIA Cloud Unreachable: {e}. Using local fallback. ⚠️")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — init DB and start worker on startup."""
    logger.info("[Main] Reel Analyser Backend starting up...")

    # Initialize database
    await init_db()
    logger.info("[OK] Database initialized")

    # Check API connectivity
    await check_nvidia_api()

    # Start background worker
    worker_task = asyncio.create_task(worker_loop())
    logger.info("[OK] Job worker started")

    yield

    # Shutdown
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Backend shut down.")


app = FastAPI(
    title="Reel Analyser API",
    description="Instagram Reel analysis powered by MLX (Apple Silicon native)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(jobs_router)
app.include_router(media_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time job progress updates."""
    await websocket.accept()
    ws_connections.add(websocket)
    logger.info(f"WebSocket client connected ({len(ws_connections)} total)")
    try:
        while True:
            # Keep connection alive; we push messages from the worker
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(ws_connections)} total)")


@app.get("/")
async def root():
    return {
        "app": "Reel Analyser",
        "version": "1.0.0",
        "docs": "/docs",
    }
