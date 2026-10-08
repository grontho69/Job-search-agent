"""
scraper.py — LinkedIn Guest API Job Scraper
"""

import logging
import random
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

GUEST_API_BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
BATCH_SIZE = 25
DELAY_MIN  = 1.0
DELAY_MAX  = 3.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

def _delay() -> None:
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

def _extract_job_id(url: str) -> Optional[str]:
    if not url:
        return None
    for part in reversed(url.rstrip("/").split("/")):
        suffix = part.split("-")[-1]
        if suffix.isdigit():
            return suffix
    return None

def _is_within_24h(card) -> bool:
    cutoff = timedelta(hours=48)
    now = datetime.now(timezone.utc)

    time_tag = card.find("time")
    if not time_tag:
        return True

    dt_attr = time_tag.get("datetime", "")
    if dt_attr:
        try:
            # Handle ISO timestamp timezone-aware
            dt_str = dt_attr.replace("Z", "+00:00")
            posted_at = datetime.fromisoformat(dt_str)
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
            if now - posted_at > cutoff:
                return False
            return True
        except Exception:
            pass

    text = time_tag.get_text(strip=True).lower()
    if any(kw in text for kw in ("just now", "moment", "second", "minute", "hour")):
        return True
    return True

def scrape_job_listings(keywords: str, location: str, max_results: int = 100) -> list:
    collected = []
    offset = 0

    while len(collected) < max_results:
        params = {
            "keywords": keywords,
            "location": location,
            "start": offset,
            "f_WT": "2",
            "f_TPR": "r86400",
        }

        try:
            resp = requests.get(GUEST_API_BASE, params=params, headers=_headers(), timeout=12)
            if resp.status_code != 200:
                break
        except Exception as exc:
            logger.warning("LinkedIn network error: %s", exc)
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.find_all("li")
        if not cards:
            break

        page_count = 0
        for card in cards:
            title_tag = card.find("h3", class_="base-search-card__title")
            title = title_tag.get_text(strip=True) if title_tag else "Software Developer"

            company_tag = card.find("h4", class_="base-search-card__subtitle")
            company = company_tag.get_text(strip=True) if company_tag else "Tech Company"

            link_tag = card.find("a", class_="base-card__full-link")
            raw_url = link_tag["href"] if link_tag and link_tag.get("href") else ""
            canonical_url = raw_url.split("?")[0] if raw_url else ""
            job_id = _extract_job_id(canonical_url)

            if not job_id:
                continue

            try:
                if not _is_within_24h(card):
                    continue
            except Exception:
                pass

            collected.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": "Remote",
                "url": canonical_url,
                "description": title,
            })
            page_count += 1
            if len(collected) >= max_results:
                break

        if page_count < 5:
            break
        offset += BATCH_SIZE
        _delay()

    return collected

def scrape_job_description(job_url: str) -> str:
    return ""
