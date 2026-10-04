"""
jobicy_scraper.py
=================
Fetches remote tech jobs from Jobicy Remote API.
"""

import logging
import requests
from typing import List, Dict

logger = logging.getLogger("jobicy_scraper")

JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs?count=30&tag=dev"

def scrape_jobicy_jobs(excluded_countries: List[str] = None) -> List[Dict]:
    jobs = []
    excluded = [c.lower() for c in (excluded_countries or ["united states", "usa", "us only"])]
    try:
        resp = requests.get(JOBICY_URL, timeout=15)
        if resp.status_code != 200:
            logger.warning("Jobicy API returned %d", resp.status_code)
            return jobs
        
        data = resp.json()
        for item in data.get("jobs", []):
            geo = (item.get("jobGeo") or "Worldwide").strip()
            if any(ex in geo.lower() for ex in excluded) and "worldwide" not in geo.lower():
                continue
            
            salary_min = item.get("annualSalaryMin")
            salary_max = item.get("annualSalaryMax")
            currency = item.get("salaryCurrency") or "USD"
            if salary_min and salary_max:
                salary = f"{salary_min}-{salary_max} {currency}"
            elif salary_min:
                salary = f"{salary_min}+ {currency}"
            else:
                salary = "Not Specified"
                
            jobs.append({
                "source": "Jobicy",
                "id": f"jobicy_{item.get('id')}",
                "title": item.get("jobTitle", ""),
                "company": item.get("companyName", ""),
                "location": geo,
                "country": geo,
                "salary": salary,
                "url": item.get("url", ""),
                "description": item.get("jobDescription", "")
            })
    except Exception as e:
        logger.warning("Error fetching Jobicy jobs: %s", e)

    logger.info("Jobicy scraper yielded %d eligible remote jobs.", len(jobs))
    return jobs
