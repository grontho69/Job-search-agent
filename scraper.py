"""
scraper.py — LinkedIn Guest API Job Scraper

Scrapes job listings from LinkedIn's public guest endpoint without authentication.
Paginates via the `start` offset, rotates User-Agents, applies random delays,
and filters results to the last 24 hours only.
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

# ── Constants ─────────────────────────────────────────────────────────────────

GUEST_API_BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
BATCH_SIZE = 25
DELAY_MIN  = 2.0
DELAY_MAX  = 5.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


# ── Private helpers ───────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.linkedin.com/jobs/search/",
    }


def _delay() -> None:
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def _extract_job_id(url: str) -> Optional[str]:
    """Parse the numeric job ID from a LinkedIn job URL."""
    if not url:
        return None
    for part in reversed(url.rstrip("/").split("/")):
        suffix = part.split("-")[-1]
        if suffix.isdigit():
            return suffix
    return None


def _is_within_24h(card) -> bool:
    """
    Return True if the job card was posted within the last 24 hours.

    Checks the ISO-8601 datetime attribute on the <time> tag first,
    then falls back to parsing the human-readable text. Returns True
    (accept) when no timestamp is found to avoid discarding valid jobs.
    """
    cutoff = timedelta(hours=24)
    now    = datetime.now(timezone.utc)

    time_tag = card.find("time")
    if not time_tag:
        return True

    # Step 1: exact datetime attribute
    dt_attr = time_tag.get("datetime", "")
    if dt_attr:
        try:
            posted_at = datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
            if now - posted_at > cutoff:
                logger.debug("Skipping old job (age %s).", now - posted_at)
                return False
            return True
        except ValueError:
            pass

    # Step 2: human-readable text fallback
    text = time_tag.get_text(strip=True).lower()
    if any(kw in text for kw in ("just now", "moment", "second", "minute")):
        return True
    hour_match = re.search(r"(\d+)\s*hour", text)
    if hour_match:
        return int(hour_match.group(1)) <= 23
    if any(kw in text for kw in ("day", "week", "month", "year")):
        logger.debug("Skipping old job: '%s'.", text)
        return False

    return True  # unknown age — accept


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_job_listings(keywords: str, location: str, max_results: int = 100) -> list[dict]:
    """
    Scrape LinkedIn job listings (24-hour posts only).

    Returns a list of job dicts with keys:
        id, title, company, location, url, description (empty — filled later)
    """
    collected: list[dict] = []
    offset = 0

    logger.info('Scraping: "%s" in "%s" (max %d)', keywords, location, max_results)

    while len(collected) < max_results:
        params = {
            "keywords": keywords,
            "location": location,
            "start":    offset,
            "f_WT":     "2",       # Remote filter
            "f_TPR":    "r86400",  # Past 24 hours only
        }

        try:
            resp = requests.get(GUEST_API_BASE, params=params, headers=_headers(), timeout=15)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("Rate limited (429). Stopping.")
            else:
                logger.error("HTTP error: %s", exc)
            break
        except requests.exceptions.RequestException as exc:
            logger.error("Network error: %s", exc)
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.find_all("li")
        if not cards:
            break

        page_count = 0
        for card in cards:
            title_tag   = card.find("h3", class_="base-search-card__title")
            title       = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            company_tag = card.find("h4", class_="base-search-card__subtitle")
            if company_tag:
                a = company_tag.find("a")
                company = a.get_text(strip=True) if a else company_tag.get_text(strip=True)
            else:
                company = "Unknown Company"

            link_tag      = card.find("a", class_="base-card__full-link")
            raw_url       = link_tag["href"] if link_tag and link_tag.get("href") else ""
            canonical_url = raw_url.split("?")[0] if raw_url else ""
            job_id        = _extract_job_id(canonical_url)

            if not job_id:
                continue

            if not _is_within_24h(card):
                logger.info("  Skipped (>24 h): %s @ %s", title, company)
                continue

            location_tag = card.find(class_="job-search-card__location")
            job_location = location_tag.get_text(strip=True) if location_tag else "Unknown Location"

            collected.append({
                "id":          job_id,
                "title":       title,
                "company":     company,
                "location":    job_location,
                "url":         canonical_url,
                "description": "",
            })
            page_count += 1

            if len(collected) >= max_results:
                break

        logger.info("  Page: %d cards parsed, %d total collected.", page_count, len(collected))

        if page_count < BATCH_SIZE:
            break

        offset += BATCH_SIZE
        _delay()

    logger.info("Scrape complete — %d jobs.", len(collected))
    return collected


def scrape_job_description(job_url: str) -> str:
    """Fetch and extract the full job description text from a LinkedIn job page."""
    _delay()
    try:
        resp = requests.get(job_url, headers=_headers(), timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch description from '%s': %s", job_url, exc)
        return ""

    soup = BeautifulSoup(resp.text, "lxml")

    tag = soup.find(class_="show-more-less-html__markup")
    if tag:
        return tag.get_text(separator="\n", strip=True)

    tag = soup.find(class_="description__text")
    if tag:
        return tag.get_text(separator="\n", strip=True)

    logger.warning("No description markup found: %s", job_url)
    return ""
