import json
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from ddgs import DDGS
import asyncio

from backend.models import GlobalChatRequest, GlobalChatResponse, SourceCard, WebResult
from backend.database import get_db, get_jobs_by_ids, _row_to_dict
from backend.services.analyzer import _run_text_pass
from backend.services.vector_db import ingest_job, search_qdrant, get_total_chunks
from backend.config import FRONTEND_URL

router = APIRouter()
logger = logging.getLogger(__name__)

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
3. When citing a library report, use the format: [Report: {{title}}]
4. When citing a web source, use the format: [Web: {{url}}]
5. After your answer, output a JSON block like this (so the frontend can parse it):

```json
{{
  "match_summaries": {{
    "job_id_1": "One sentence about why this report is relevant to the query.",
    "job_id_2": "..."
  }}
}}
```

Do NOT make up tools or links. Only cite what is in the provided context.
"""

@router.post("/api/chat/global", response_model=GlobalChatResponse)
async def global_chat(request: GlobalChatRequest):
    # 1. Semantic Search via Qdrant
    qdrant_matches = search_qdrant(query=request.message, limit=request.limit)
    job_ids = [m["job_id"] for m in qdrant_matches]
    
    # 2. Fetch full metadata from SQLite
    db_jobs = await get_jobs_by_ids(job_ids) if job_ids else []
    
    # Re-order to match Qdrant rank
    db_jobs_dict = {j["id"]: j for j in db_jobs}
    matched_jobs = [db_jobs_dict[jid] for jid in job_ids if jid in db_jobs_dict]
    
    # Count total chunks searched across the vector DB
    total_searched = get_total_chunks()
    
    # 3. Extract context from matched reports
    report_contexts = ""
    for job in matched_jobs:
        report_contexts += f"\n--- [Job ID: {job['id']}] Title: {job.get('title', 'Unknown')} ---\n"
        # Include the first 1500 chars to keep context size manageable
        analysis_preview = (job.get('analysis_md') or '')[:1500] 
        report_contexts += f"{analysis_preview}\n"

    if not matched_jobs:
        report_contexts = "No relevant reports found in the library."

    # 3. Web Search
    web_results = []
    web_context = ""
    try:
        def perform_search():
            results = []
            with DDGS() as ddgs:
                search_results = list(ddgs.text(request.message, max_results=3))
                for r in search_results:
                    results.append(WebResult(title=r.get("title", ""), url=r.get("href", ""), snippet=r.get("body", "")))
            return results
            
        web_results = await asyncio.to_thread(perform_search)
        for w in web_results:
            web_context += f"- {w.title} ({w.url}): {w.snippet}\n"
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        web_context = "No web search results available."

    if not web_results:
        web_context = "No web search results available."

    # 4. Generate LLM response
    prompt = GLOBAL_CHAT_PROMPT.format(
        total=total_searched,
        question=request.message,
        report_contexts=report_contexts,
        web_context=web_context
    )
    
    # Run the text-only pass
    raw_response = await asyncio.to_thread(_run_text_pass, prompt)

    # 5. Parse JSON block out of response
    answer_text = raw_response
    match_summaries = {}
    
    # Simple extraction of the JSON block if present
    if "```json" in raw_response:
        parts = raw_response.split("```json")
        answer_text = parts[0].strip()
        try:
            json_str = parts[1].split("```")[0].strip()
            parsed_json = json.loads(json_str)
            match_summaries = parsed_json.get("match_summaries", {})
        except Exception as e:
            logger.error(f"Failed to parse match summaries JSON: {e}")
    
    # 6. Build Source Cards
    sources = []
    for job in matched_jobs:
        summary = match_summaries.get(job["id"], f"Matched based on keywords from the query: {request.message[:20]}...")
        card = SourceCard(
            job_id=job["id"],
            title=job.get("title") or "Unknown Video",
            category=job.get("category") or "Uncategorized",
            subcategory=job.get("subcategory"),
            report_url=f"{FRONTEND_URL}/report/{job['id']}",
            original_url=job.get("url") or "",
            match_summary=summary,
            view_count=job.get("view_count") or 0,
            like_count=job.get("like_count") or 0
        )
        sources.append(card)

    return GlobalChatResponse(
        answer=answer_text,
        sources=sources,
        web_results=web_results,
        total_reports_searched=total_searched
    )

@router.post("/api/admin/backfill-qdrant")
async def backfill_qdrant_route():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE status='done'")
        rows = await cursor.fetchall()
        jobs = [_row_to_dict(r) for r in rows]
        
        logger.info(f"Found {len(jobs)} completed jobs to backfill into Qdrant.")
        for job in jobs:
            ingest_job(job)
            
        return {"status": "success", "message": f"Ingested {len(jobs)} jobs into Qdrant."}
    finally:
        await db.close()
