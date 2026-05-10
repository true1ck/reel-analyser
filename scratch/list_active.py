import asyncio
import sys
import os

# Add parent dir to path
sys.path.append(os.getcwd())

from backend.database import list_jobs, update_job

async def main():
    print("Checking for active jobs in DB...")
    jobs, total = await list_jobs(limit=100)
    active = [j for j in jobs if j['status'] in ('queued', 'downloading', 'transcribing', 'analyzing')]
    
    if not active:
        print("No active jobs found in DB.")
        return

    for j in active:
        print(f"Found active job: ID={j['id']} Reel={j['reel_id']} Status={j['status']}")
        # Mark as cancelled if requested
        if "--stop" in sys.argv:
            print(f"Stopping job {j['id']}...")
            await update_job(j['id'], status='cancelled', current_step='Manually stopped')
            print(f"Job {j['id']} marked as cancelled.")

if __name__ == "__main__":
    asyncio.run(main())
