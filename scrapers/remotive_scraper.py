"""
remotive_scraper.py
===================
Fetches software and web development jobs from Remotive API (100% remote).
"""

import logging
import requests
from typing import List, Dict

logger = logging.getLogger("remotive_scraper")

REMOTIVE_URL = "https://remotive.com/api/remote-jobs?category=software-dev&limit=40"

def scrape_remotive_jobs(excluded_countries: List[str] = None) -> List[Dict]:
    """Scrapes remote jobs from Remotive API."""
    jobs = []
    excluded = [c.lower() for c in (excluded_countries or ["united states", "usa", "us only"])]
    try:
        resp = requests.get(REMOTIVE_URL, timeout=15)
        if resp.status_code != 200:
            logger.warning("Remotive API returned %d", resp.status_code)
            return jobs
        
        data = resp.json()
        for item in data.get("jobs", []):
            candidate_location = (item.get("candidate_required_location") or "Worldwide").strip()
            
            # Filter out US Only or excluded locations
            is_excluded = any(ex in candidate_location.lower() for ex in excluded)
            if is_excluded and "worldwide" not in candidate_location.lower():
                continue
            
            salary = item.get("salary") or "Not Specified"
            
            jobs.append({
                "source": "Remotive",
                "id": f"remotive_{item.get('id')}",
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "location": candidate_location,
                "country": candidate_location,
                "salary": salary,
                "url": item.get("url", ""),
                "description": item.get("description", "")
            })
    except Exception as e:
        logger.warning("Error fetching Remotive jobs: %s", e)

    logger.info("Remotive scraper yielded %d eligible remote jobs.", len(jobs))
    return jobs
