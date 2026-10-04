"""
unified_aggregator.py
=====================
Aggregates remote jobs across multiple free sources (Remotive, Jobicy, LinkedIn Guest API)
and filters out non-eligible regions (US-only/Visa restrictions) to guarantee a diverse pool.
"""

import logging
from typing import List, Dict, Set
from scrapers.remotive_scraper import scrape_remotive_jobs
from scrapers.jobicy_scraper import scrape_jobicy_jobs
from scraper import scrape_job_listings

logger = logging.getLogger("unified_aggregator")

def aggregate_target_jobs(
    keywords: List[str],
    excluded_countries: List[str],
    known_job_ids: Set[str],
    target_count: int = 20
) -> List[Dict]:
    """
    Collects fresh remote job listings from all configured sources until target_count is reached.
    """
    collected: List[Dict] = []
    seen_ids: Set[str] = set(known_job_ids)

    # 1. Fetch from Remotive API (High Quality Remote Jobs)
    remotive_jobs = scrape_remotive_jobs(excluded_countries=excluded_countries)
    for job in remotive_jobs:
        if job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            collected.append(job)

    # 2. Fetch from Jobicy API
    jobicy_jobs = scrape_jobicy_jobs(excluded_countries=excluded_countries)
    for job in jobicy_jobs:
        if job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            collected.append(job)

    # 3. If still need more, query LinkedIn Guest API for specific keywords
    if len(collected) < target_count * 2:
        logger.info("Aggregator querying LinkedIn Guest API for additional listings...")
        for kw in keywords[:3]:  # Top 3 relevant keywords
            if len(collected) >= target_count * 2.5:
                break
            try:
                li_jobs = scrape_job_listings(keywords=kw, location="Remote", max_results=8)
                for lj in li_jobs:
                    jid = f"linkedin_{lj.get('id')}"
                    if jid not in seen_ids:
                        seen_ids.add(jid)
                        lj["source"] = "LinkedIn"
                        lj["id"] = jid
                        lj["country"] = lj.get("location") or "Worldwide Remote"
                        lj["salary"] = "Not Specified"
                        collected.append(lj)
            except Exception as e:
                logger.warning("LinkedIn fallback scrape notice: %s", e)

    logger.info("Aggregator assembled %d unique candidate jobs.", len(collected))
    return collected
