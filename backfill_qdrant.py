import asyncio
import logging
from backend.database import get_db, _row_to_dict
from backend.services.vector_db import ingest_job

logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Starting Qdrant backfill...")
    db = await get_db()
    try:
        # Fetch all completed jobs
        cursor = await db.execute("SELECT * FROM jobs WHERE status='done'")
        rows = await cursor.fetchall()
        jobs = [_row_to_dict(r) for r in rows]
        
        logging.info(f"Found {len(jobs)} completed jobs to backfill.")
        
        for i, job in enumerate(jobs):
            logging.info(f"Ingesting [{i+1}/{len(jobs)}] {job.get('reel_id')}...")
            ingest_job(job)
            
        logging.info("Backfill complete! All jobs are now in Qdrant.")
        
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
