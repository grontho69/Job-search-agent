"""
supabase_client.py
==================
Supabase client for deduplicating scraped jobs and logging daily applications.
Ensures zero repeat jobs across daily runs.
"""

import os
import logging
from typing import Set, Optional
from datetime import datetime, timezone

logger = logging.getLogger("supabase_client")

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

TABLE_NAME = "processed_jobs"

def get_supabase_client() -> Optional[any]:
    """Returns an initialized Supabase Client if env vars are present."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key or not create_client:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        logger.warning("Could not connect to Supabase: %s", e)
        return None

def get_all_processed_job_ids() -> Set[str]:
    """Fetches all previously processed job IDs from Supabase."""
    client = get_supabase_client()
    if not client:
        return set()
    try:
        response = client.table(TABLE_NAME).select("job_id").execute()
        if response and response.data:
            return {str(item["job_id"]).strip() for item in response.data if item.get("job_id")}
    except Exception as e:
        logger.warning("Failed to fetch processed job IDs from Supabase: %s", e)
    return set()

def insert_processed_job(
    job_id: str,
    title: str,
    company: str,
    location: str,
    url: str,
    score: float,
    country: str = "Worldwide",
    salary: str = "Not Specified",
    rationale: str = "",
    pdf_url: str = "",
    status: str = "Ready To Apply"
) -> bool:
    """Inserts a freshly screened job into Supabase."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        record = {
            "job_id": str(job_id),
            "title": str(title),
            "company": str(company),
            "location": str(location),
            "url": str(url),
            "country": str(country),
            "salary": str(salary),
            "score": float(score),
            "rationale": str(rationale),
            "pdf_url": str(pdf_url),
            "status": str(status),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        client.table(TABLE_NAME).upsert(record).execute()
        return True
    except Exception as e:
        logger.error("Error inserting job %s to Supabase: %s", job_id, e)
        return False
