"""
supabase_client.py
==================
Supabase client for deduplicating scraped jobs and logging daily applications.
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

def _clean_supabase_url(raw_url: str) -> str:
    """Ensures Supabase URL has https and no trailing path like /rest/v1"""
    if not raw_url:
        return ""
    url = raw_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    url = url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-8]
    return url

def get_supabase_client() -> Optional[any]:
    raw_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not raw_url or not key or not create_client:
        return None
    url = _clean_supabase_url(raw_url)
    try:
        return create_client(url, key)
    except Exception as e:
        logger.warning("Could not connect to Supabase: %s", e)
        return None

def get_all_processed_job_ids() -> Set[str]:
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
