import os
import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

# Ensure qdrant data directory exists
os.makedirs("data/qdrant", exist_ok=True)

# Initialize Qdrant in local, no-docker mode
client = QdrantClient(path="data/qdrant")

COLLECTION_NAME = "reel_reports"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384

# Create collection if it doesn't exist
if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    print(f"[Vector DB] Created Qdrant collection: {COLLECTION_NAME}")

# Initialize FastEmbed locally
print("[Vector DB] Loading embedding model...")
embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
print("[Vector DB] Model loaded.")

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """Simple word-based chunker."""
    if not text:
        return []
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def extract_chunks_from_job(job: dict) -> List[Dict[str, Any]]:
    chunks_meta = []
    
    # 1. Chunk analysis
    analysis = job.get("analysis_md") or ""
    for c in chunk_text(analysis, 300, 50):
        chunks_meta.append({
            "id": str(uuid.uuid4()),
            "text": f"[Report Analysis] {c}",
            "job_id": job["id"],
            "title": job.get("title", ""),
            "category": job.get("category", "Uncategorized"),
            "chunk_type": "analysis"
        })
        
    # 2. Chunk transcript
    transcript = job.get("transcript") or ""
    for c in chunk_text(transcript, 400, 50):
        chunks_meta.append({
            "id": str(uuid.uuid4()),
            "text": f"[Video Transcript] {c}",
            "job_id": job["id"],
            "title": job.get("title", ""),
            "category": job.get("category", "Uncategorized"),
            "chunk_type": "transcript"
        })
        
    return chunks_meta

def ingest_job(job: dict):
    """Chunks a job and upserts its vectors into Qdrant."""
    chunks = extract_chunks_from_job(job)
    if not chunks:
        return
        
    texts = [c["text"] for c in chunks]
    # FastEmbed returns a generator
    embeddings = list(embedding_model.embed(texts))
    
    points = []
    for i, chunk in enumerate(chunks):
        points.append(PointStruct(
            id=chunk["id"],
            vector=embeddings[i].tolist(),
            payload=chunk
        ))
        
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )

def search_qdrant(query: str, limit: int = 5) -> List[dict]:
    """
    Searches Qdrant via semantic similarity.
    Returns a list of deduplicated matches with job_id and best_chunk.
    """
    # Embed the search query
    query_vector = next(embedding_model.embed([query]))
    
    # Search Qdrant (use query_points for qdrant-client >= 1.7)
    try:
        result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=20
        )
        hits = result.points
    except AttributeError:
        # Fallback for older API
        hits = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector.tolist(),
            limit=20
        )
    
    seen_jobs = set()
    best_matches = []
    
    for hit in hits:
        job_id = hit.payload["job_id"]
        if job_id not in seen_jobs:
            seen_jobs.add(job_id)
            best_matches.append({
                "job_id": job_id,
                "score": hit.score,
                "best_chunk": hit.payload["text"],
                "category": hit.payload["category"],
                "title": hit.payload["title"]
            })
            if len(best_matches) >= limit:
                break
                
    return best_matches

def get_total_chunks() -> int:
    try:
        return client.get_collection(COLLECTION_NAME).points_count
    except Exception:
        return 0
