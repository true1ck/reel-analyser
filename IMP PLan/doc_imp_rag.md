# Reel Analyser — RAG Architecture & Implementation Reference

> **Status:** Live. All features below are fully implemented and running.
> **Updated:** May 2026

---

## 1. System Overview

Reel Analyser is a **two-pass Vision + LLM pipeline** that ingests short-form videos (Instagram, YouTube Shorts, TikTok), extracts structured knowledge from them, and makes that knowledge queryable via a RAG-based Chat interface.

```
URL Input
   │
   ▼
[Downloader + yt-dlp]  → video.mp4 + metadata (title, views, likes, comments, description, pinned comment)
   │
   ▼
[Transcriber — MLX Whisper]  → English transcript (translated if needed)
   │
   ▼
[VideoRouter — classify()]  → category (Technology / Education / Business / etc.)
   │
   ▼
[StrategyFactory]  → selects category-specific prompt strategy
   │
   ├─── Pass 1: [Vision Pass — Qwen2.5-VL-7B]  → raw visual observations (on-screen text, tools, code, URLs)
   │
   └─── Web Search [ddgs]  → alternative tools, related links, real-time context
   │
   ▼
[Pass 2: Text Synthesis — Qwen2.5-VL-7B (text-only mode)]  → structured Markdown report
   │
   ▼
[Database — SQLite / aiosqlite]  → persists report, transcript, metadata, social stats
   │
   ▼
[Frontend RAG Chat]  → user queries answered against stored report + transcript
```

---

## 2. Core Components

### 2.1 Downloader (`backend/services/downloader.py`)

**Tool:** `yt-dlp` wrapped in Python subprocess calls.
**Supports:** Instagram Reels, YouTube Shorts, TikTok, any yt-dlp-compatible URL.

**What it fetches:**

- Video file (MP4) → saved to `data/reels/{reel_id}/video.mp4`
- **Metadata dictionary:**
  - `title`
  - `uploader`
  - `description`
  - `view_count`, `like_count`, `comment_count`, `share_count` (repost_count)
  - `upload_date`
  - `tags`
  - `top_comment` — tries to fetch pinned comment first, falls back to first comment

**Key function:**

```python
def download_video(url: str, video_id: str) -> tuple[Path, dict]:
    ...
```

**Live Refresh:** `refresh_metadata(url)` is called as a FastAPI `BackgroundTask` every time a report page is opened, keeping social stats up to date.

---

### 2.2 Transcriber (`backend/services/transcriber.py`)

**Model:** `mlx-community/whisper-large-v3-turbo` (Apple Silicon MLX)
**Task:** `translate` — always produces English output regardless of source language (Hindi, Urdu, Hinglish, etc.)

```python
def transcribe_audio(audio_path: Path) -> str:
    result = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=WHISPER_MODEL, task="translate")
    return result["text"].strip()
```

**Important:** `mlx_whisper` only exists inside the project's `./venv` (Python 3.9). Always run via `./venv/bin/python` or `source venv/bin/activate`.

---

### 2.3 VideoRouter (`backend/services/router.py`)

**Purpose:** Classifies the video into a category so the correct prompt strategy can be selected.
**Method:** Text-only LLM pass using `ROUTER_PROMPT` against the transcript snippet and metadata.

**Valid Categories (currently):**

| Category                  | Triggers Tech Prompts? |
| ------------------------- | ---------------------- |
| `Technology`            | ✅                     |
| `AI & Machine Learning` | ✅                     |
| `Business Strategy`     | BusinessStrategy       |
| `Marketing`             | BusinessStrategy       |
| `Social Media`          | BusinessStrategy       |
| `Education`             | EducationStrategy      |
| `Uncategorized`         | DefaultStrategy        |

**Classification call:**

```python
category = VideoRouter.classify(transcript_text, metadata)
```

> **Note:** Uses a deferred import of `_run_text_pass` inside the method to avoid circular imports with `analyzer.py`.

---

### 2.4 StrategyFactory (`backend/services/strategy_factory.py`)

**Pattern:** Strategy Pattern via `AnalysisStrategy` ABC.

Each strategy provides two methods:

- `get_extraction_prompt()` → prompt for Pass 1 (vision model watching the video)
- `get_synthesis_prompt(metadata, visual_observations, transcript, web_context)` → prompt for Pass 2 (text-only reasoning)

| Class                    | Matched Category                           |
| ------------------------ | ------------------------------------------ |
| `TechTutorialStrategy` | Technology, AI & Machine Learning          |
| `BusinessStrategy`     | Business Strategy, Marketing, Social Media |
| `EducationStrategy`    | Education                                  |
| `DefaultStrategy`      | Everything else                            |

---

### 2.5 Analyzer (`backend/services/analyzer.py`)

**Model:** `mlx-community/Qwen2.5-VL-7B-Instruct-4bit`
**Framework:** `mlx-vlm` + `qwen_vl_utils`
**Model is loaded ONCE globally** and reused across all jobs to avoid the ~10s reload penalty.

**Two Functions:**

#### `_run_vision_pass(video_path, prompt)` → str

- Sends video frames (at `VIDEO_FPS=2.0`) to Qwen2.5-VL.
- Used for Pass 1: extracting raw visual observations.
- Used for `\reanalyse` chat commands (re-watches video for visual-specific questions).

#### `_run_text_pass(prompt)` → str

- Text-only mode, no video input.
- Used for: classification, web search query generation, synthesis (Pass 2), and standard chat RAG.

---

### 2.6 Pipeline Orchestrator (`backend/services/pipeline.py`)

**Entry point:** `run_pipeline(url, reel_id, on_progress)`
**Design:** Fully async, with progress callbacks that update the DB and broadcast to WebSocket clients.

**Full Pipeline Flow:**

| Step                | Progress   | Description                                                     |
| ------------------- | ---------- | --------------------------------------------------------------- |
| Download + metadata | 5% → 20%  | yt-dlp fetches video + social stats                             |
| Audio extraction    | 20% → 30% | ffmpeg strips audio as WAV                                      |
| Transcribe          | 35% → 50% | Whisper → English text                                         |
| Classify            | 52%        | VideoRouter determines category via LLM                         |
| Pass 1 — Vision    | 55% → 75% | Qwen2.5-VL extracts visual observations                         |
| Web Search          | 76% → 78% | ddgs queries for tools/alternatives (2 queries, 3 results each) |
| Pass 2 — Synthesis | 78% → 95% | LLM synthesizes full Markdown report                            |
| Done                | 100%       | Saves to DB, broadcasts via WebSocket                           |

**Result object (`PipelineResult`):**

```python
result.video_path       # Path to local video file
result.audio_path       # Path to local WAV file
result.title            # Video title from metadata
result.transcript       # English transcript text
result.analysis_md      # Final structured Markdown report
result.category         # e.g. "Technology"
result.subcategory      # e.g. "AI Tools"
result.processing_ms    # Total time in milliseconds
result.view_count       # From yt-dlp metadata
result.like_count
result.share_count
result.comment_count
```

---

### 2.7 Database (`backend/database.py`)

**Engine:** SQLite (async via `aiosqlite`)
**File:** `data/reel_analyser.db`

**Jobs Table Schema:**

```sql
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
    transcript      TEXT,       -- Raw English transcript
    analysis_md     TEXT,       -- Structured Markdown report (RAG source)
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
    comment_count   INTEGER DEFAULT 0
);
```

> **Migration-safe:** `init_db()` checks for missing columns and runs `ALTER TABLE ADD COLUMN` for each, so existing data is never lost when new fields are added.

---

### 2.8 Job Worker (`backend/workers/job_worker.py`)

**Design:** Single async worker consuming from an `asyncio.Queue`.
**Why single?** MLX models on Apple Silicon are GPU-serialized — parallel jobs would not speed anything up.
**WebSocket broadcast:** Progress events are pushed to all connected frontend clients in real time.

---

## 3. Chat with Video (RAG Interface)

### Endpoint: `POST /api/jobs/{job_id}/chat`

**Request body:**

```json
{ "message": "What command did he type in the terminal?" }
```

or for vision re-analysis:

```json
{ "message": "\\reanalyse what color shirt is the host wearing?" }
```

### Branch 1: Standard RAG Chat

- Builds a prompt with the stored `transcript` + `analysis_md` from the DB.
- Calls `_run_text_pass()` (text-only LLM).
- If the answer is not in the stored text, returns "I don't know based on the current notes."

```
User Question
   ↓
Retrieve transcript + analysis_md from DB
   ↓
Prompt = "Using this transcript and analysis, answer: {question}"
   ↓
_run_text_pass(prompt)
   ↓
ChatResponse(reply=...)
```

### Branch 2: `\reanalyse` Vision Command

- Triggered when the user message starts with `\reanalyse` or `\reanalyze`.
- Bypasses stored notes entirely.
- Calls `_run_vision_pass(video_path, user_prompt)` to re-watch the actual video.
- Best for visual-only questions the report doesn't cover (clothing, exact terminal text, tool logos, etc.)

```
\reanalyse which tool is shown on screen?
   ↓
Load video_path from DB
   ↓
_run_vision_pass(video_path, "Analyze this video and answer: which tool is shown?")
   ↓
ChatResponse(reply=...)
```

### Skills Autocomplete (Frontend)

Typing `\` in the chat input triggers a dropdown of available commands:

| Command            | Description                                               |
| ------------------ | --------------------------------------------------------- |
| `\reanalyse`     | Re-watch video with Vision AI for visual-specific queries |
| `\summarize`     | Generate a short summary of the video                     |
| `\extract_tools` | List all tools mentioned in the video                     |

Navigation: `ArrowUp/Down` to select, `Tab` or `Enter` to autocomplete, `Escape` to close.

---

## 4. Prompt Strategies

All prompts live in `backend/services/prompts/strategies.py`.

### Extraction Prompts (Pass 1 — Vision Model)

Each strategy has a tailored extraction focus:

- **Tech:** Code, terminal commands, IDE file names, API endpoints, architecture diagrams.
- **Education:** Step-by-step UI walkthroughs, whiteboard/slide transcription, on-screen captions.
- **Business:** Dashboards, revenue metrics, marketing funnel diagrams, tool identification.
- **Default:** Full general-purpose extraction (on-screen text, URLs, tools, code, actions).

### Synthesis Prompts (Pass 2 — Text-Only LLM)

All synthesis prompts receive 4 inputs: `{metadata}`, `{visual_observations}`, `{transcript}`, `{web_context}`.

**Shared output sections across all strategies:**

- `### 📂 CATEGORY: [broad] > [subcategory]` — parsed by `extract_category()` to set DB fields
- `### 📊 Quick Overview` — parsed by `parseQuickOverview()` in the frontend for the overview card
- `### 🗣️ English Transcript (Full)`
- `### 🛠️ Tools & Resources Mentioned`
- `### 🔄 Alternative Tools & Rankings` — populated from `{web_context}` (ddgs results)
- `### 🔗 Related Resources & Metadata Links` — from pinned comments, description, visuals
- `### 💡 Key Notes & Takeaways`
- `### 🎯 Action Items`

**Tech-specific extra sections:**

- `### 💻 Code Snippets & Commands`
- `### 🪜 Implementation Guide (Step-by-Step)`
- `### 📐 Architecture / Logic Flow`

**Business-specific extra sections:**

- `### 📈 Key Metrics & Tools Used`
- `### 🧩 The Strategy / Funnel Breakdown`

---

## 5. Web Search Integration

**Library:** `ddgs` (v9.8+) — the new official package replacing `duckduckgo_search`.

**Flow:**

1. LLM generates 2 search queries based on `title + transcript + visual_observations`.
2. Parser strips common prefixes (`1.`, `-`, `*`, quotes) from LLM output.
3. `DDGS.text(query, max_results=3)` is called for each query.
4. Results are concatenated into `web_context` string with title, URL, and body snippet.
5. `web_context` is injected into the synthesis prompt as `{web_context}`.

**Why it matters:** The `🔄 Alternative Tools & Rankings` section in every report is powered entirely by real-time web search results, not hallucinated by the model.

---

## 6. Engagement Metrics

Fetched via `yt-dlp` and stored in the DB at analysis time. Auto-refreshed on every page load via a FastAPI `BackgroundTask`.

| Field             | Source          | yt-dlp key        |
| ----------------- | --------------- | ----------------- |
| `view_count`    | yt-dlp metadata | `view_count`    |
| `like_count`    | yt-dlp metadata | `like_count`    |
| `comment_count` | yt-dlp metadata | `comment_count` |
| `share_count`   | yt-dlp metadata | `repost_count`  |

> **Note:** Instagram often rate-limits or hides some stats (like share counts). Values default to `0` if not available.

---

## 7. Frontend Architecture

| File                              | Responsibility                                                       |
| --------------------------------- | -------------------------------------------------------------------- |
| `src/pages/ReportPage.jsx`      | Main report view, chat panel, metadata sidebar                       |
| `src/utils/api.js`              | API helper functions (`fetchJob`, `sendChatMessage`, etc.)       |
| `src/index.css`                 | Full design system (glassmorphism, 3-column layout, skills dropdown) |
| `src/pages/CollectionsPage.jsx` | Category browsing,`getCategoryMeta()` helper                       |

**Layout:** 3-column CSS Grid: `300px 1fr 340px`

- Left: Video player, Quick Overview card, Info metadata, Engagement stats
- Center: Full Markdown report
- Right: Chat with Video panel (sticky, full viewport height)

---

## 8. API Reference

| Method     | Path                     | Description                                        |
| ---------- | ------------------------ | -------------------------------------------------- |
| `POST`   | `/api/jobs`            | Submit URLs for analysis                           |
| `GET`    | `/api/jobs`            | List all jobs (filter by status, category, search) |
| `GET`    | `/api/jobs/{id}`       | Get job (triggers background stats refresh)        |
| `PATCH`  | `/api/jobs/{id}`       | Update tags/notes                                  |
| `DELETE` | `/api/jobs/{id}`       | Delete job + local files                           |
| `POST`   | `/api/jobs/{id}/retry` | Retry a failed job                                 |
| `POST`   | `/api/jobs/{id}/chat`  | Chat with video (RAG + \reanalyse)                 |
| `GET`    | `/api/jobs/{id}/video` | Stream the local video file                        |
| `GET`    | `/api/jobs/{id}/pdf`   | Download the report as PDF                         |
| `GET`    | `/api/stats`           | Dashboard aggregate stats                          |
| `GET`    | `/api/collections`     | Category list with counts                          |
| `POST`   | `/api/jobs/channel`    | Fetch & analyze all videos from a channel          |
| `WS`     | `/ws`                  | Real-time progress updates                         |

---

## 9. Running the App

```bash
# Start everything
./start.sh

# Or manually:
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
cd frontend && npm run dev
```

> **Critical:** Always use `./venv/bin/` or `source venv/bin/activate` before running Python. The system Python 3.14 (Homebrew) does **not** have `mlx_whisper`, `mlx_vlm`, or any ML libraries installed.

---

## 10. Known Limitations & Future Improvements

| Area                                | Current State                                        | Planned Improvement                                                 |
| ----------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------- |
| RAG context window                  | Full transcript + full analysis_md sent as string    | Implement chunked vector search (ChromaDB or FAISS) for long videos |
| Instagram auth                      | Requires manual `cookies.txt` update               | Automated persistent browser session                                |
| Chat history                        | No multi-turn memory within a session                | Add conversation context array                                      |
| `\summarize` / `\extract_tools` | Defined in UI dropdown but route not implemented yet | Add these as distinct backend branches in `/chat`                 |
| Search reliability                  | ddgs can rate-limit                                  | Consider fallback to Tavily or SerpApi                              |
| Share counts                        | Often 0 on Instagram                                 | No reliable API workaround at this time                             |
