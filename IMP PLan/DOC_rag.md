# Reel Knowledge Base — Full Implementation Plan

> **Goal** : A centralised, AI-powered knowledge base over 1000+ reel analysis reports (markdown files), with per-video chat, a central search hub, and smart retrieval that can answer "which web scraping repo did I see 3 months ago?" accurately every time.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Folder & File Structure](#2-folder--file-structure)
3. [Phase 1 — Ingestion Pipeline](#3-phase-1--ingestion-pipeline)
4. [Phase 2 — Storage Layer](#4-phase-2--storage-layer)
5. [Phase 3 — RAG Core (Backend)](#5-phase-3--rag-core-backend)
6. [Phase 4 — API Layer](#6-phase-4--api-layer)
7. [Phase 5 — Frontend](#7-phase-5--frontend)
8. [Phase 6 — Integration into Your Existing App](#8-phase-6--integration-into-your-existing-app)
9. [Smartness Upgrades (Do These in Order)](#9-smartness-upgrades-do-these-in-order)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [Week-by-Week Build Plan](#11-week-by-week-build-plan)
12. [Tech Stack Summary](#12-tech-stack-summary)
13. [Common Pitfalls to Avoid](#13-common-pitfalls-to-avoid)

---

## 1. System Overview

### What the system does (as built)

**Current stack:** FastAPI + SQLite (`aiosqlite`) + Qwen2.5-VL-7B (MLX on Apple Silicon) + Whisper (MLX) + React (Vite). Everything runs locally — no Docker, no external API calls for inference.

The user asks a question in natural language — "which open source web scraping repo did I see a few months back?" — and the system:

1. Retrieves `analysis_md` + `transcript` from the SQLite database for matching jobs
2. Builds a context prompt from those fields and sends to `_run_text_pass()` (Qwen2.5-VL text-only mode)
3. Returns a grounded answer citing which section the info came from
4. If the answer is visual-only (not in the stored text), the user types `\reanalyse <question>` to trigger `_run_vision_pass()` — which re-watches the actual saved `video.mp4`

### Three surfaces (live vs planned)

| Surface | Status | Description |
| ----------------------- | ------ | ------------ |
| **Per-reel Chat** | ✅ Live | `POST /api/jobs/{job_id}/chat`. Uses `analysis_md` + `transcript` from DB as RAG context. |
| **`\reanalyse` command** | ✅ Live | Bypasses stored notes. Calls `_run_vision_pass()` on local `video.mp4`. |
| **Skills autocomplete** | ✅ Live | Type `\` in chat → dropdown of `\reanalyse`, `\summarize`, `\extract_tools`. Tab/Enter to complete. |
| **Category browsing** | ✅ Live | Collections page filters by `category` column in SQLite. |
| **Central hub search** | 🔜 Planned | Search ALL reports at once. Needs vector DB (Qdrant/FAISS) to scale beyond ~100 jobs. |
| **`\summarize` / `\extract_tools`** | 🔜 Planned | Defined in UI dropdown but backend route branches not yet wired. |

---

## 2. Folder & File Structure

This is the **actual** project structure as it exists today:

```
Reel analyser/
│
├── backend/
│   ├── main.py                      ← FastAPI entrypoint
│   ├── config.py                    ← model names, paths, settings
│   ├── database.py                  ← SQLite schema + async CRUD (aiosqlite)
│   ├── models.py                    ← Pydantic schemas (JobResponse, ChatRequest, etc.)
│   ├── routes/
│   │   └── jobs.py                  ← All API endpoints incl. /api/jobs/{id}/chat
│   ├── services/
│   │   ├── analyzer.py              ← Qwen2.5-VL: _run_vision_pass(), _run_text_pass()
│   │   ├── downloader.py            ← yt-dlp wrapper, refresh_metadata()
│   │   ├── pipeline.py              ← Full async pipeline orchestrator
│   │   ├── router.py                ← VideoRouter.classify() — LLM content classification
│   │   ├── strategy_factory.py      ← Strategy pattern: Tech/Education/Business/Default
│   │   ├── transcriber.py           ← MLX Whisper transcription
│   │   ├── pdf_exporter.py          ← PDF generation from analysis_md
│   │   └── prompts/
│   │       ├── router_prompt.py     ← ROUTER_PROMPT template
│   │       └── strategies.py        ← All extraction + synthesis prompt templates
│   └── workers/
│       └── job_worker.py            ← Async queue worker + WebSocket broadcaster
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── ReportPage.jsx       ← 3-column layout: sidebar | report | chat
│       │   ├── CollectionsPage.jsx  ← Category browser
│       │   └── DashboardPage.jsx    ← Main dashboard
│       ├── utils/
│       │   └── api.js               ← fetchJob(), sendChatMessage(), etc.
│       └── index.css                ← Full design system
│
├── data/
│   ├── reel_analyser.db             ← SQLite database (all jobs, transcripts, reports)
│   └── reels/
│       └── {reel_id}/
│           ├── video.mp4            ← Downloaded video (used by \reanalyse)
│           └── audio.wav            ← Extracted audio for Whisper
│
├── venv/                            ← Python 3.9 virtual environment (MLX requires this)
├── requirements.txt
└── start.sh                         ← Starts both backend (port 8000) + frontend (port 5173)
```

> **Note on Python version:** Always use `./venv/bin/python` or `source venv/bin/activate`. The system Python 3.14 (Homebrew) does NOT have `mlx_whisper`, `mlx_vlm`, or any ML dependencies.

---

## 3. Phase 1 — Ingestion Pipeline

This is the most important phase. **How you chunk your reports determines the quality of every search result.** Do this right and everything else becomes easy.

### 3.1 Naming and organising your MD files

Before ingestion, make sure every MD file has a consistent naming convention and lives in a category folder:

```
technology/ai-tools/reel_001_magic-ai-tool.md
technology/developer-tools/reel_042_firecrawl-scraping.md
marketing/social-media/reel_103_hooks-strategy.md
```

The folder path becomes the category automatically during parsing. No manual tagging needed.

### 3.2 How to parse each MD report

Your reports already have a clean structure with emoji-prefixed sections. The parser should detect and extract these sections individually:

| Section in `analysis_md` (actual)           | What to extract                                    | Chunk type       |
| ------------------------------------------- | -------------------------------------------------- | ---------------- |
| `### 📂 CATEGORY: X > Y`                   | category, subcategory (parsed by `extract_category()`) | metadata     |
| `### 📊 Quick Overview`                    | content type, difficulty, target audience, summary (parsed by `parseQuickOverview()` in React) | overview_chunk |
| `### 🗣️ English Transcript (Full)`        | full translated English transcript text            | transcript_chunk |
| `### 🛠️ Tools & Resources Mentioned`     | tool names, URLs, platforms shown on screen        | tools_chunk      |
| `### 🪜 Exact Step-by-Step Tutorial`       | numbered steps (Tech/Education strategies only)    | tutorial_chunk   |
| `### 💻 Code Snippets & Commands`          | fenced code blocks with language tags (Tech only)  | code_chunk       |
| `### 🔄 Alternative Tools & Rankings`     | top 3 free + paid tools — populated from ddgs web search | alternatives_chunk |
| `### 🔗 Related Resources & Metadata Links` | URLs from pinned comments, description, visuals   | links_chunk      |
| `### 💡 Key Notes & Takeaways`             | bullet points                                      | insights_chunk   |
| `### 🎯 Action Items`                      | bullet points                                      | actions_chunk    |
| `### 📈 Key Metrics & Tools Used`          | numbers, metrics (Business strategy only)          | metrics_chunk    |

 **Why this matters** : When someone asks "which web scraping tool?", the retriever targets `tools_chunk` sections. When someone asks "what are the steps to build X?", it targets `tutorial_chunk`. Section-aware chunking makes the system dramatically smarter than naive character-based chunking.

### 3.3 Metadata to attach to every chunk

Every single chunk, regardless of section type, must carry this metadata. This is what enables filtering before retrieval:

```json
{
  "reel_id": "reel_042",
  "file_path": "technology/developer-tools/reel_042_firecrawl-scraping.md",
  "category": "Technology",
  "subcategory": "Developer Tools",
  "section_type": "tools_chunk",
  "difficulty": "Beginner",
  "content_type": "Tutorial / How-To",
  "tools_mentioned": ["Firecrawl", "Playwright", "BeautifulSoup"],
  "language": "en",
  "chunk_index": 2,
  "total_chunks": 6
}
```

The `tools_mentioned` field is especially powerful — populate it by scanning the Tools section of each report and extracting proper nouns. This enables queries like "show me all reports mentioning Playwright" to work as a pure metadata filter with zero LLM calls.

### 3.4 Chunk size guidelines

Do not use a single global chunk size. Use section-appropriate sizes:

| Section type        | Recommended chunk size      | Overlap    |
| ------------------- | --------------------------- | ---------- |
| Overview / Summary  | 300–500 tokens             | 50 tokens  |
| Transcript          | 400–600 tokens             | 100 tokens |
| Tools section       | Keep intact (usually short) | None       |
| Tutorial steps      | 300–500 tokens             | 50 tokens  |
| Takeaways / Actions | Keep intact                 | None       |

If a transcript is very long (over 1000 tokens), split it into multiple transcript chunks, each overlapping by 100 tokens so context isn't lost at boundaries.

### 3.5 Running ingestion

The ingestion script should be idempotent — safe to run multiple times. When you add new reports, running it again should only add new chunks, not re-embed everything.

Ingestion steps in order:

1. Scan `data/raw/` recursively for all `.md` files
2. For each file, check if `reel_id` already exists in Qdrant — skip if yes
3. Parse the file into sections
4. Create chunks with metadata from each section
5. Embed all chunks using nomic-embed-text (batched, 32 at a time for speed)
6. Upsert into Qdrant with full payload
7. Index the full report text into Meilisearch with the same reel_id
8. Append to `index_manifest.json`

At 1000 reports with ~6 chunks each, this is ~6000 vectors. Ingestion should take about 15–20 minutes on a laptop the first time. Re-runs for new reports take seconds.

---

## 4. Phase 2 — Storage Layer

### 4.1 Qdrant (vector database)

Run locally via Docker:

```
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

Create one collection called `reel_reports` with:

* Vector size: 768 (for nomic-embed-text) or 1536 (for OpenAI ada-002)
* Distance: Cosine
* Payload indexes on: `category`, `subcategory`, `section_type`, `difficulty`, `tools_mentioned`

The payload indexes are critical — they make metadata filtering fast even at 10,000+ vectors.

### 4.2 Meilisearch (full-text search)

Run locally via Docker:

```
docker run -p 7700:7700 -v meili_data:/meili_data getmeili/meilisearch
```

Create one index called `reports` with:

* Primary key: `reel_id`
* Searchable attributes: `title`, `summary`, `transcript`, `tools_mentioned`, `takeaways`
* Filterable attributes: `category`, `subcategory`, `difficulty`, `content_type`
* Sortable attributes: none needed initially

Meilisearch handles typos automatically. A user typing "playright" still finds Playwright. Qdrant handles semantic meaning. Together they cover every retrieval case.

### 4.3 Why both?

| Query type                             | Best handled by        |
| -------------------------------------- | ---------------------- |
| "web scraping tool" (vague, semantic)  | Qdrant                 |
| "Firecrawl" (exact tool name)          | Meilisearch            |
| "scraping tool for beginners" (both)   | Both, results merged   |
| "show me all AI tools" (filter)        | Qdrant metadata filter |
| "Playwright vs Puppeteer" (comparison) | Both                   |

---

## 5. Phase 3 — RAG Core (Backend)

This is the intelligence layer. Four components chained together.

### 5.1 Query Rewriter

Before retrieval, an LLM rewrites the user's question into a better retrieval query.

 **Input** : "which web scraping repo did i see a few months ago that was open source"

 **Output** :

```json
{
  "rewritten_query": "open source web scraping repository tool",
  "intent": "tool_discovery",
  "filters": {
    "section_type": "tools_chunk",
    "tools_category": "web scraping"
  },
  "keywords": ["web scraping", "scraper", "crawler", "open source"]
}
```

Use a small, fast model for this (local mistral or claude-haiku). This step takes <1 second and dramatically improves what the retriever finds.

### 5.2 Hybrid Retriever

Takes the rewritten query and runs two searches in parallel:

 **Semantic search (Qdrant)** :

* Embed the rewritten query
* Apply metadata filters extracted by the rewriter
* Retrieve top-20 chunks by cosine similarity

 **Keyword search (Meilisearch)** :

* Search using extracted keywords
* Apply same category/difficulty filters
* Retrieve top-20 results

 **Merge with Reciprocal Rank Fusion (RRF)** :

* Both result lists are merged using RRF scoring
* A chunk appearing in both lists gets a big boost
* Output: top-30 merged, deduplicated chunks

RRF is a simple formula: `score = 1/(k + rank)` where k=60. No extra model needed, just math.

### 5.3 Reranker

Takes the top-30 merged chunks and re-scores them using a cross-encoder model.

Use `BAAI/bge-reranker-v2-m3` (free, runs locally via sentence-transformers).

The cross-encoder looks at the (query, chunk) pair together — unlike embeddings which score them separately. This is much more accurate and typically bumps precision from ~60% to ~85%+.

After reranking, keep only the top 5–8 chunks for the generator.

### 5.4 Generator

Takes the user's original question + the top 5–8 reranked chunks and generates a final answer.

The prompt structure:

```
You are a knowledge assistant for a reel analysis library of {total_count} videos.
The user is asking: "{original_question}"

Here are the most relevant sections from the reports:

[CHUNK 1 - from reel_042, Tools section, Technology > Developer Tools]
{chunk_text}

[CHUNK 2 - from reel_089, Overview section, Technology > AI Tools]
{chunk_text}

...

Answer the question using only the information in these chunks.
Always cite which report (reel_id) the information came from.
If a specific tool is mentioned, include its name exactly as it appears.
If no chunk is relevant, say "I couldn't find this in your analysed reels."
```

Use **Claude claude-haiku-4-5** for speed and cost (~$0.001 per query) or run **mistral/llama3** locally via Ollama for zero cost.

Always stream the response token by token — do not wait for the full answer before sending to the frontend.

---

## 6. Phase 4 — API Layer

The FastAPI backend (`backend/routes/jobs.py`) exposes these **live** endpoints. All run on `http://localhost:8000`.

| Method | Path | Status | Description |
| ------ | ---- | ------ | ----------- |
| `POST` | `/api/jobs` | ✅ Live | Submit one or more URLs for analysis |
| `GET` | `/api/jobs` | ✅ Live | List all jobs (filter by `status`, `category`, `search`) |
| `GET` | `/api/jobs/{id}` | ✅ Live | Get job — triggers background `refresh_metadata()` for latest stats |
| `PATCH` | `/api/jobs/{id}` | ✅ Live | Update tags/notes |
| `DELETE` | `/api/jobs/{id}` | ✅ Live | Delete job + local video/audio files |
| `POST` | `/api/jobs/{id}/retry` | ✅ Live | Retry a failed job |
| `POST` | `/api/jobs/{id}/chat` | ✅ Live | **Per-video RAG Chat** — Standard RAG or `\reanalyse` vision command |
| `GET` | `/api/jobs/{id}/video` | ✅ Live | Stream local video file to browser |
| `GET` | `/api/jobs/{id}/pdf` | ✅ Live | Download `analysis_md` as PDF |
| `GET` | `/api/stats` | ✅ Live | Dashboard aggregate stats |
| `GET` | `/api/collections` | ✅ Live | Category list with job counts |
| `POST` | `/api/jobs/channel` | ✅ Live | Fetch all videos from a channel/profile URL |
| `WS` | `/ws` | ✅ Live | WebSocket for real-time progress events |
| `POST` | `/api/chat/global` | 🔜 **Planned** | **Global Chat** — search ALL reports + web, return source cards with links |

### Chat endpoint — how it actually works

**Request:**
```json
{ "message": "What command did he type in the terminal?" }
```
or with vision re-analysis:
```json
{ "message": "\\reanalyse what shirt is the host wearing?" }
```

**Branch 1 — Standard RAG (text query):**
- Fetches `transcript` + `analysis_md` from SQLite for that `job_id`
- Builds a prompt: `"Using this transcript and analysis, answer: {message}"`
- Calls `_run_text_pass(prompt)` (Qwen2.5-VL in text-only mode, no video needed)
- Returns `ChatResponse(reply=...)`

**Branch 2 — `\reanalyse` vision command:**
- Detects `\reanalyse` or `\reanalyze` prefix
- Loads `video_path` from DB, raises 400 if file doesn't exist
- Builds a wrapper prompt: `"Analyze this video and answer: {custom_prompt}"`
- Calls `_run_vision_pass(video_path, prompt)` — re-watches the actual video
- Returns `ChatResponse(reply=...)`

**Planned future branches:**
- `\summarize` — will generate a short TL;DR using `_run_text_pass`
- `\extract_tools` — will extract the tools list from `analysis_md` section

---

## 6A. Global Chat — Source Cards, Report Links & Web Search

> **This section documents the planned Global Chat feature** — the central hub where you can ask questions across ALL your analysed videos and get back structured results with clickable links, summaries, and live web search context.

### Problem with the current output

Today, `POST /api/jobs/{id}/chat` returns a plain markdown string. There is no link back to the report page, no summary of which videos matched, and no external web search context in the answer.

The user sees:
```
"The tool mentioned was Firecrawl. It is a web scraping API that..."
```

What they actually want:
- A direct answer to the question
- A list of the **top matching report cards** with clickable links (`http://localhost:5173/report/{job_id}`)
- Each card showing: title, category, difficulty, 1-sentence summary of why it matched
- Web search results mixed in to enrich the answer with context that isn't in any of your reports

---

### Step 1: New `POST /api/chat/global` endpoint

Create a new route in `backend/routes/` (e.g. `global_chat.py`):

```python
@router.post("/api/chat/global", response_model=GlobalChatResponse)
async def global_chat(body: GlobalChatRequest, background_tasks: BackgroundTasks):
    """
    Search ALL analysed reports + web, answer the question, return source cards.
    """
    ...
```

**New Pydantic models to add in `backend/models.py`:**

```python
class GlobalChatRequest(BaseModel):
    message: str = Field(..., description="User question")
    category: str | None = None    # Optional: restrict to one category
    limit: int = Field(5, description="Max number of source cards to return")

class SourceCard(BaseModel):
    job_id: str
    title: str | None
    category: str
    subcategory: str | None
    report_url: str              # e.g. "http://localhost:5173/report/{job_id}"
    original_url: str            # e.g. Instagram/YouTube link
    match_summary: str           # 1-sentence: why this report matched the query
    view_count: int
    like_count: int

class WebResult(BaseModel):
    title: str
    url: str
    snippet: str

class GlobalChatResponse(BaseModel):
    answer: str                        # The synthesised answer
    sources: list[SourceCard]          # Top matching report cards
    web_results: list[WebResult]       # Live web search results
    total_reports_searched: int        # How many DB records were searched
```

---

### Step 2: How the endpoint works internally

```
User question: "which AI tool helps with cold email outreach?"
         ↓
[1] SQLite Full-Text Search
    → SELECT * FROM jobs WHERE analysis_md LIKE '%cold email%'
       OR transcript LIKE '%cold email%'
       OR analysis_md LIKE '%outreach%'
    → Returns top-N matching job rows
         ↓
[2] Score & Rank results
    → Simple keyword overlap score (no vector DB needed for <500 jobs)
    → Boost jobs where the Tools section matches
    → Keep top 5
         ↓
[3] ddgs Web Search  (reuse existing pipeline.py logic)
    → Search: "AI tool cold email outreach 2025"
    → Get top 3-5 web results (title, URL, snippet)
         ↓
[4] Build context for LLM
    For each top-5 job: include its analysis_md summary section + Tools section
    Include web search results
         ↓
[5] _run_text_pass(synthesis_prompt)
    → Prompt tells the LLM:
       - Answer the question
       - Cite which report it found each piece of info in
       - Also use the web results for context not in any report
       - For each report cited, generate a 1-sentence "why this matched" summary
         ↓
[6] Return GlobalChatResponse
    - answer: string
    - sources: [{job_id, title, category, report_url, match_summary, ...}]
    - web_results: [{title, url, snippet}]
    - total_reports_searched: N
```

---

### Step 3: The synthesis prompt

```python
GLOBAL_CHAT_PROMPT = """
You are an AI assistant with access to a personal library of {total} analysed videos.
The user has asked: "{question}"

Here are the most relevant reports from the library:

{report_contexts}

Here are real-time web search results for additional context:

{web_context}

─── INSTRUCTIONS ───
1. Answer the user's question directly and clearly.
2. Use information from both the library reports AND the web search results.
3. When citing a library report, use the format: [Report: {title}]
4. When citing a web source, use the format: [Web: {url}]
5. After your answer, output a JSON block like this (so the frontend can parse it):

```json
{
  "match_summaries": {
    "{job_id_1}": "One sentence about why this report is relevant to the query.",
    "{job_id_2}": "..."
  }
}
```

Do NOT make up tools or links. Only cite what is in the provided context.
"""
```

---

### Step 4: SQLite FTS search (no Qdrant needed yet)

For under ~500 jobs, SQLite full-text search is fast enough. Add this to `backend/database.py`:

```python
async def search_jobs_fts(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """
    Full-text search across analysis_md + transcript.
    Returns jobs ranked by keyword match count.
    """
    db = await get_db()
    try:
        # Simple LIKE-based search across key fields
        terms = query.lower().split()
        conditions = []
        params = []
        for term in terms[:5]:  # cap at 5 terms
            conditions.append(
                "(LOWER(analysis_md) LIKE ? OR LOWER(transcript) LIKE ? OR LOWER(title) LIKE ?)"
            )
            t = f"%{term}%"
            params.extend([t, t, t])
        
        where = " AND ".join(conditions) if conditions else "1=1"
        if category:
            where += " AND category = ?"
            params.append(category)
        
        params.extend([limit])
        cursor = await db.execute(
            f"SELECT * FROM jobs WHERE status='done' AND ({where}) "
            f"ORDER BY completed_at DESC LIMIT ?",
            params
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()
```

> **Upgrade path:** When job count exceeds ~500, swap this for Qdrant vector search — same interface, much better recall on semantic queries.

---

### Step 5: Report URL format

The frontend report page URL is:
```
http://localhost:5173/report/{job_id}
```

In the `SourceCard`, set:
```python
FRONTEND_BASE_URL = "http://localhost:5173"  # add to backend/config.py

source_card = SourceCard(
    job_id=job["id"],
    title=job["title"],
    category=job["category"],
    subcategory=job.get("subcategory"),
    report_url=f"{FRONTEND_BASE_URL}/report/{job['id']}",
    original_url=job["url"],
    match_summary=match_summaries.get(job["id"], ""),
    view_count=job.get("view_count", 0),
    like_count=job.get("like_count", 0),
)
```

---

### Step 6: Frontend — Global Chat UI

Add a new **Hub/Search page** (`frontend/src/pages/HubPage.jsx`) or embed a global chat widget in `DashboardPage.jsx`.

**Result rendering logic:**

```jsx
// After receiving GlobalChatResponse:
function GlobalChatResult({ data }) {
  return (
    <div className="global-chat-result">
      {/* 1. Main answer */}
      <div className="answer glass">
        <ReactMarkdown>{data.answer}</ReactMarkdown>
      </div>

      {/* 2. Source cards — top matching reports */}
      <h3>📚 From Your Library ({data.total_reports_searched} searched)</h3>
      <div className="source-cards">
        {data.sources.map(src => (
          <a href={src.report_url} className="source-card glass" key={src.job_id}>
            <div className="source-card__title">{src.title}</div>
            <div className="source-card__meta">
              <span className="category-badge">{src.category}</span>
              {src.subcategory && <span className="subcategory">{src.subcategory}</span>}
              <span>👁️ {formatNumber(src.view_count)}</span>
              <span>❤️ {formatNumber(src.like_count)}</span>
            </div>
            <div className="source-card__summary">{src.match_summary}</div>
            <div className="source-card__cta">📄 View Full Report →</div>
          </a>
        ))}
      </div>

      {/* 3. Web results */}
      {data.web_results.length > 0 && (
        <>
          <h3>🌍 From the Web</h3>
          <div className="web-results">
            {data.web_results.map((r, i) => (
              <a href={r.url} target="_blank" rel="noopener" className="web-result glass" key={i}>
                <div className="web-result__title">{r.title}</div>
                <div className="web-result__snippet">{r.snippet}</div>
                <div className="web-result__url">{r.url}</div>
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

---

### What this looks like to the user

**Question typed:** `"which AI tool did I see for cold email outreach?"`

**Response:**
```
🤖 Answer:
Based on your library, the tool mentioned for cold email outreach was Lemlist,
shown in the video by @marketinghacks. It was used alongside Apollo.io for
lead generation. [Report: Lemlist Cold Email Setup] [Report: Apollo + Lemlist Combo]

The web also suggests tools like Instantly.ai and Smartlead as top alternatives in 2025.
[Web: instantly.ai]

📚 From Your Library (47 reports searched)
┌─────────────────────────────────────────────────────────────┐
| 💼 Lemlist Cold Email Setup                                   |
| Marketing > Email Automation  | 👁️ 45.2K | ❤️ 1.2K                  |
| "Directly demonstrates Lemlist setup for cold outreach"        |
| [View Full Report →]  http://localhost:5173/report/76c0b4b5... |
└─────────────────────────────────────────────────────────────┘

🌍 From the Web
- Instantly.ai — Top cold email tool for 2025 with AI warm-up
- Smartlead — Multi-mailbox cold email platform
```

---

### Build order (do this in this order)

1. Add `search_jobs_fts()` to `database.py`
2. Add `GlobalChatRequest`, `SourceCard`, `WebResult`, `GlobalChatResponse` to `models.py`
3. Add `FRONTEND_BASE_URL` to `config.py`
4. Create `backend/routes/global_chat.py` with `POST /api/chat/global`
5. Register the new router in `backend/main.py`
6. Build `HubPage.jsx` (or add a global chat widget to the Dashboard)
7. Add CSS for `.source-card`, `.web-result` to `index.css`

---

## 7. Phase 5 — Frontend

The frontend is **React + Vite** (not Next.js). All pages are in `frontend/src/pages/`. The design system uses glassmorphism + dark mode defined in `index.css`.

### 7.1 Chat Panel (currently live in `ReportPage.jsx`)

The chat is the **right column** of the 3-column grid layout (`300px sidebar | 1fr report | 340px chat`).

Currently implemented:
- Text input at the bottom of the sticky right panel
- `\` triggers a **skills autocomplete dropdown** (Arrow keys, Tab/Enter, Escape)
- Sends `POST /api/jobs/{job_id}/chat` and displays the AI reply
- Messages displayed in a scrollable conversation thread
- Handles both Branch 1 (text RAG) and Branch 2 (`\reanalyse`)

**Planned improvements:**
- Streaming token-by-token display (currently returns full response)
- Source citations shown as cards
- Conversation memory across session

### 7.2 Report Page (`/report/:id` — `ReportPage.jsx`)

Layout: **3-column CSS grid** (`300px | 1fr | 340px`)

- **Left column:** Video player, Quick Overview card (`parseQuickOverview()` parses `analysis_md`), Info metadata, Engagement stats (views, likes, shares, comments — auto-refreshed on page load)
- **Centre column:** Full `analysis_md` rendered as Markdown with `react-markdown` + syntax highlighting
- **Right column:** Sticky chat panel (always visible while scrolling through long reports)

### 7.3 Collections Page (`/collections` — `CollectionsPage.jsx`)

- Category grid showing all `category` values from SQLite with job counts
- Clicking a category filters the job list
- Each card has a colour + icon via `getCategoryMeta()` helper

### 7.4 Dashboard Page (`/` — `DashboardPage.jsx`)

- URL/channel submission form
- Stats summary (total, completed, failed, processing)
- Job list with status indicators and real-time WebSocket progress

### 7.3 Per-reel page (`/knowledge/reel/[id]`)

Layout (two-column on desktop, stacked on mobile):

* Left column (60%): Full markdown report rendered with syntax highlighting
  * Collapsible sections (Transcript can be long)
  * Tools mentioned as clickable chips (clicking searches for that tool)
  * Metadata bar at top: category, difficulty, content type
* Right column (40%): `ChatWindow` scoped to this reel
  * Uses `scope: "reel:reel_042"`
  * Pre-filled suggested questions: "What are the key steps?", "What tools are needed?", "Give me a summary"
  * Below chat: "Related reels" section (5 cards)

### 7.4 Category page (`/knowledge/category/[slug]`)

Layout:

* Category header with total count
* `ChatWindow` scoped to this category (uses `scope: "category:technology/developer-tools"`)
* Grid of reel cards below
* Subcategory filter tabs

---

## 8. Phase 6 — Integration into Your Existing App

Everything is already in one repo. The backend and frontend are co-located and started together via `start.sh`.

### 8.1 How it already connects

- **Backend** runs on `http://localhost:8000` (FastAPI)
- **Frontend** runs on `http://localhost:5173` (Vite dev server)
- All API calls in `frontend/src/utils/api.js` hit `http://localhost:8000/api/...`
- Real-time progress uses a WebSocket connection to `ws://localhost:8000/ws`

### 8.2 Auto-ingestion (already live)

When a new video is submitted, it flows through the pipeline automatically:
1. `POST /api/jobs` creates a DB record and enqueues the job
2. `job_worker.py` picks it up and runs `run_pipeline()`
3. On completion, `analysis_md`, `transcript`, and social stats are saved to SQLite
4. The chat endpoint immediately has access to the new report — no separate indexing step needed

### 8.3 Adding vector search for the Central Hub (future)

When the job count grows beyond ~100, you'll want to add vector search so you can search ALL reports at once:

1. After `run_pipeline()` completes, call a new `ingest_to_qdrant(job)` function
2. Parse `analysis_md` into section chunks (see Phase 1)
3. Embed each chunk with `nomic-embed-text` via Ollama (local, free)
4. Upsert into a Qdrant collection called `reel_reports`
5. Add a new `GET /api/search` endpoint that queries Qdrant + SQLite full-text

### 8.4 Surfacing results in the Dashboard

Once central search is live, embed it in the Dashboard:

- **"Ask your library"** search bar at the top of the dashboard
- **"Trending tools this week"** widget — count tool mentions across recent jobs
- **Related reels** sidebar on each ReportPage (vector similarity search)

---

## 9. Smartness Upgrades (Do These in Order)

Do not try to add all of these at once. Build the basic system first, then add these one at a time in order of impact.

### Upgrade 1 — Metadata extraction at ingest (highest impact)

Already described in Phase 1. The single biggest quality improvement. Without good metadata, filtering doesn't work and the system returns irrelevant results.

### Upgrade 2 — Query rewriting (high impact)

Before retrieval, use an LLM to rewrite the user's casual question into a better search query. This alone improves retrieval precision by 20–30%.

### Upgrade 3 — Reranking (high impact)

Add the cross-encoder reranker after hybrid retrieval. Turns good results into great results. Especially important when the user asks nuanced questions.

### Upgrade 4 — Conversation memory (medium impact)

Store the last 5 turns of each conversation and include them in the retrieval context. This allows follow-up questions like "and what about the pricing?" to work correctly without re-asking the full question.

Use a simple in-memory store keyed by `session_id` during development. Migrate to Redis for production.

### Upgrade 5 — Tool graph (medium impact, harder to build)

After ingestion, build a graph of which tools appear together in reports. When a user asks about Playwright, you can also surface reports mentioning Puppeteer, Selenium, and Firecrawl because they appear together frequently. Implement with a simple co-occurrence matrix in SQLite.

### Upgrade 6 — User feedback loop (medium impact)

Add thumbs up/down to every chat response. Store feedback with the query, retrieved chunks, and answer. Use this data to fine-tune retrieval — chunks that consistently produce thumbs up get a small relevance boost.

### Upgrade 7 — Auto-tagging improvement (lower priority)

Run a small LLM pass over every report at ingest time to extract additional structured data: sentiment, key entities, problem being solved, outcome. Store as metadata. This enriches filtering options.

---

## 10. Infrastructure & Deployment

### Local development setup

All three backing services run via Docker Compose. One `docker-compose.yml` in `knowledge-base/`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]

  meilisearch:
    image: getmeili/meilisearch
    ports: ["7700:7700"]
    volumes: ["meili_data:/meili_data"]
    environment:
      MEILI_MASTER_KEY: "your-local-key"

  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: ["ollama_data:/root/.ollama"]
```

Run `docker-compose up -d` once. Everything persists across restarts via Docker volumes.

### Production deployment

For a solo developer or small team, the cheapest reliable setup is:

| Service                | Where to run                                                        | Cost                       |
| ---------------------- | ------------------------------------------------------------------- | -------------------------- |
| Qdrant                 | Qdrant Cloud free tier (1GB) or self-host on a $6/mo VPS | $0–6/mo |                            |
| Meilisearch            | Self-host on same VPS                                               | Included                   |
| FastAPI backend        | Same VPS (2GB RAM is enough for 1000 reports)                       | Included                   |
| Ollama (local LLM)     | Run on your own machine, not on VPS                                 | $0                         |
| Claude API (generator) | Anthropic API pay-as-you-go                                         | ~$1–5/mo at typical usage |
| Next.js frontend       | Vercel free tier                                                    | $0                         |

For 1000 reports with typical usage (50–100 queries/day), total cost is under $15/month.

### Environment variables

```env
# Vector DB
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=reel_reports

# Full-text search
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_KEY=your-key

# Embedding model
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_URL=http://localhost:11434  # Ollama endpoint

# Generator LLM
GENERATOR_PROVIDER=anthropic          # or "ollama"
ANTHROPIC_API_KEY=sk-ant-...
GENERATOR_MODEL=claude-haiku-4-5-20251001

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# App
DATA_DIR=./data/raw
PROCESSED_DIR=./data/processed
```

---

## 11. Week-by-Week Build Plan

### Week 1 — Ingestion (most important week)

* Day 1–2: Write `parse_reports.py` — load one MD file, extract all sections, print them. Verify it handles edge cases (missing sections, Hindi transcripts, etc.)
* Day 3: Write `chunk_reports.py` — take parsed sections, create chunks with full metadata. Print out 5 sample chunks and verify they look right.
* Day 4: Set up Docker Compose, get Qdrant and Meilisearch running locally.
* Day 5: Write `embed_and_index.py` — embed 10 sample chunks and insert into Qdrant. Do a test query and verify results make sense.
* Weekend: Run full ingestion on all 1000 reports. Fix any parsing errors.

 **Exit criteria** : You can run a Qdrant query for "web scraping" and get relevant chunks back.

### Week 2 — RAG Backend

* Day 1–2: FastAPI skeleton. GET `/api/health` works. Basic chat endpoint accepts a message and returns a hardcoded response.
* Day 3: Implement hybrid retrieval (Qdrant + Meilisearch, RRF merge). Test with 10 queries, check quality.
* Day 4: Add query rewriter. Compare results with and without it. Tune the prompt.
* Day 5: Add reranker. Compare top-5 results before and after. Should be noticeably better.
* Weekend: Add generator (Claude API or Ollama). Full end-to-end test via curl.

 **Exit criteria** : `curl -X POST /api/chat -d '{"message":"web scraping tool"}'` returns a good answer with correct source citations.

### Week 3 — Central Hub Frontend

* Day 1–2: Build `ChatWindow.tsx` component. Hardcode a mock API response. Get the streaming UI working.
* Day 3: Wire `ChatWindow` to the real `/api/chat` endpoint. Test live.
* Day 4: Build `ReportCard.tsx` — the result card shown below each answer.
* Day 5: Build the central hub page (`/knowledge`) with search bar, filters, and chat.

 **Exit criteria** : You can ask a question in the browser and get a streamed answer with source cards.

### Week 4 — Per-reel and Category Pages

* Day 1–2: Build `/api/report/:id` endpoint. Returns full MD + metadata + related reels.
* Day 3: Build per-reel page. Render the MD with a sidebar chat (scoped to that reel).
* Day 4: Build category page with scoped chat.
* Day 5: Connect navigation. Every source card in the hub links to its reel page.

 **Exit criteria** : Full user journey works end-to-end: search → result card → reel page → chat about that specific video.

### Week 5 — Integration and Polish

* Day 1–2: Auto-ingestion hook. When your reel analyser saves a new report, it triggers the KB backend to ingest it immediately.
* Day 3: Add the KB to your app's main navigation.
* Day 4: Conversation memory (last 5 turns stored per session).
* Day 5: Mobile responsiveness, loading states, error handling.

 **Exit criteria** : The KB feels like a natural part of your app, not a separate tool.

---

## 12. Tech Stack Summary

### Current (Live)

| Component | Tool | Version | Status |
| --------- | ---- | ------- | ------ |
| Vision LLM | Qwen2.5-VL-7B-Instruct | 4-bit (MLX) | ✅ Live |
| Transcription | Whisper Large v3 Turbo | MLX | ✅ Live |
| Framework (ML) | mlx-vlm + mlx-whisper | Latest | ✅ Live |
| Video download | yt-dlp | Latest | ✅ Live |
| Web search | ddgs | 9.8+ | ✅ Live |
| Backend framework | FastAPI + aiosqlite | 0.110+ / Python 3.9 | ✅ Live |
| Database | SQLite | via aiosqlite | ✅ Live |
| Frontend | React + Vite | 18 / 5+ | ✅ Live |
| Streaming (progress) | WebSocket | FastAPI native | ✅ Live |
| PDF export | WeasyPrint / reportlab | Latest | ✅ Live |
| Content routing | Custom VideoRouter (LLM-based) | In-repo | ✅ Live |
| Prompt strategies | Strategy pattern (4 classes) | In-repo | ✅ Live |

### Planned (for Central Hub / Scale)

| Component | Tool | Version | Notes |
| --------- | ---- | ------- | ----- |
| Vector database | Qdrant | Latest | Local Docker or Qdrant Cloud free tier |
| Full-text search | SQLite FTS5 or Meilisearch | Latest | FTS5 is zero-infra (already in SQLite) |
| Embedding model | nomic-embed-text | via Ollama | Free, local, 768-dim |
| Reranker | BAAI/bge-reranker-v2-m3 | sentence-transformers | Free, local, high precision boost |
| RAG framework | LlamaIndex | 0.10+ | Optional — can do retrieval manually |
| Streaming (chat) | Server-Sent Events | FastAPI StreamingResponse | Currently returns full response |

---

## 13. Common Pitfalls to Avoid

### Do not chunk by character count alone

Splitting at 1000 characters regardless of where you are in the document destroys semantic coherence. A chunk that starts mid-sentence in the Tools section and ends mid-sentence in the Transcript is useless. Always split at section boundaries first, then further split long sections with overlap.

### Do not skip metadata indexing

The most common mistake: embed the text but forget to store rich metadata in the payload. Without `category`, `section_type`, and `tools_mentioned` as filterable fields in Qdrant, every query has to search all 6000 chunks instead of the 300 relevant ones.

### Do not use the same model for embedding and reranking

Embeddings compress meaning into a fixed vector — fast but lossy. The reranker reads the full (query, chunk) pair — slow but accurate. They do different jobs. You need both.

### Do not make the generator do the retrieval work

The LLM should receive 5–8 already-relevant chunks and synthesise an answer. If you send it 50 chunks and ask it to find the answer, it will hallucinate, miss things, and be slow and expensive.

### Do not ignore the transcript language

Your reports contain Hindi transcripts alongside English summaries. Index both but keep them in separate chunk fields. When the user searches in English, search against the English summary and tools sections primarily. The Hindi transcript is useful context for the LLM but should be lower-weight in retrieval.

### Do not rebuild the index from scratch every time

Your ingestion script must check if a `reel_id` already exists before re-embedding. Re-running ingestion on 1000 reports every time you add one new report is a 20-minute wait for no reason.

### Do not use `localhost` URLs in Docker containers

When FastAPI (running in Docker) tries to connect to Qdrant (also running in Docker), `localhost` refers to the FastAPI container itself, not Qdrant. Use the Docker service name instead: `http://qdrant:6333`. This is a very common Docker networking mistake.

---

*Built for a reel analysis knowledge base with 1000+ reports across 10+ categories. Designed to answer "which tool did I see months ago?" reliably every time.*
