"""
scraper.py
==========
LinkedIn Guest API Job Scraper
-------------------------------
Extracts job listings from LinkedIn's public guest endpoint without authentication.
Uses LinkedIn's dynamic search API surface (the same surface indexed by Google),
which has a significantly lower anti-detection threshold than browser automation.

Strategy:
  - Paginate via the `start` offset parameter in batches of 25.
  - Rotate User-Agent headers to simulate different browser clients.
  - Apply randomized delays between requests to avoid triggering rate limits.
  - Parse HTML responses with BeautifulSoup + lxml for robust extraction.

Dependencies:
    pip install requests beautifulsoup4 lxml
"""

import time
import random
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# LinkedIn's public guest job-search API endpoint.
# This surface is indexed by Google and has relaxed anti-scraping compared
# to the main authenticated site, making it suitable for lightweight polling.
GUEST_API_BASE = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)

# LinkedIn's public job detail page — used to fetch full descriptions.
JOB_DETAIL_BASE = "https://www.linkedin.com/jobs/view/{job_id}/"

# Batch size enforced by LinkedIn's guest API.
BATCH_SIZE = 25

# Seconds to wait between page requests (randomized within this range).
DELAY_MIN = 2.0
DELAY_MAX = 5.0

# ---------------------------------------------------------------------------
# User-Agent Pool
# ---------------------------------------------------------------------------
# Rotating among multiple common browser User-Agent strings prevents a single
# fingerprint from being flagged by LinkedIn's rate-limiting heuristics.

USER_AGENTS = [
    # Chrome 124 on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # Chrome 123 on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Firefox 125 on Linux
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    # Safari 17 on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
    # Edge 124 on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    ),
]


def _get_headers() -> dict:
    """
    Build a randomized HTTP header block.

    Selects a random User-Agent and populates Accept/Accept-Language headers
    to mimic a genuine browser request and avoid bot-detection heuristics.

    Returns:
        dict: A headers dictionary ready to pass to requests.get().
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        # Signals to LinkedIn that the request comes from their own domain
        # (guest job listing pages legitimately set this referer).
        "Referer": "https://www.linkedin.com/jobs/search/",
    }


def _random_delay() -> None:
    """
    Sleep for a randomized duration within [DELAY_MIN, DELAY_MAX] seconds.

    This prevents predictable request cadences that trigger rate-limit
    detection systems and simulates human-like browsing behaviour.
    """
    delay = random.uniform(DELAY_MIN, DELAY_MAX)
    logger.debug("Sleeping for %.2f seconds before next request.", delay)
    time.sleep(delay)


def _extract_job_id(url: str) -> Optional[str]:
    """
    Parse the numeric LinkedIn job ID from a full job URL.

    LinkedIn job URLs follow patterns such as:
      https://www.linkedin.com/jobs/view/1234567890/
      https://www.linkedin.com/jobs/view/software-engineer-at-google-1234567890

    The job ID is always the last numeric segment of the path.

    Args:
        url: Raw href extracted from the job listing anchor tag.

    Returns:
        The job ID string if found, otherwise None.
    """
    if not url:
        return None
    # Split the URL path by "/" and find the last purely-numeric segment.
    parts = url.rstrip("/").split("/")
    for part in reversed(parts):
        # Job IDs are numeric strings, sometimes embedded at the end of slugs.
        # Handle slugified IDs like "software-engineer-at-google-1234567890".
        numeric_suffix = part.split("-")[-1]
        if numeric_suffix.isdigit():
            return numeric_suffix
    return None


def scrape_job_listings(
    keywords: str,
    location: str,
    max_results: int = 100,
) -> list[dict]:
    """
    Scrape job listings from LinkedIn's guest search API.

    Paginates through results in batches of 25 using the `start` offset
    parameter, collecting structured metadata for each listing found.

    Args:
        keywords:    Search query string (e.g., "Python Developer").
        location:    Geographic filter (e.g., "Remote" or "New York, NY").
        max_results: Maximum number of job listings to collect before stopping.
                     Defaults to 100. Actual results may be slightly fewer if
                     LinkedIn returns an incomplete final page.

    Returns:
        A list of job dictionaries, each containing:
          - id         (str):  Unique LinkedIn job ID.
          - title      (str):  Job title.
          - company    (str):  Hiring company name.
          - location   (str):  Job location string.
          - url        (str):  Full URL to the LinkedIn job detail page.
          - description(str):  Raw job description text (fetched separately).
    """
    collected_jobs: list[dict] = []
    offset = 0

    logger.info(
        'Starting job scrape | keywords="%s" location="%s" max_results=%d',
        keywords,
        location,
        max_results,
    )

    while len(collected_jobs) < max_results:
        # ----------------------------------------------------------------
        # Build the paginated request URL
        # ----------------------------------------------------------------
        params = {
            "keywords": keywords,
            "location": location,
            "start": offset,
            "f_WT": "2",  # Strict LinkedIn Remote workplace filter
            "f_TPR": "r604800",  # Past week filter to surface fresh postings
        }

        try:
            logger.info(
                "Fetching page | offset=%d | collected_so_far=%d",
                offset,
                len(collected_jobs),
            )
            response = requests.get(
                GUEST_API_BASE,
                params=params,
                headers=_get_headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            # LinkedIn returns 429 when rate-limited; back off and break.
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("Rate limited (HTTP 429). Stopping pagination.")
            else:
                logger.error("HTTP error fetching listings: %s", exc)
            break
        except requests.exceptions.RequestException as exc:
            logger.error("Network error fetching listings: %s", exc)
            break

        # ----------------------------------------------------------------
        # Parse the HTML response
        # ----------------------------------------------------------------
        soup = BeautifulSoup(response.text, "lxml")
        job_cards = soup.find_all("li")

        if not job_cards:
            logger.info("No more job cards returned. Pagination complete.")
            break

        page_count = 0
        for card in job_cards:
            # -- Extract job title ----------------------------------------
            title_tag = card.find("h3", class_="base-search-card__title")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            # -- Extract company name -------------------------------------
            # The company subtitle may be a direct <h4> or a nested <a>.
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            if company_tag:
                company_link = company_tag.find("a")
                company = (
                    company_link.get_text(strip=True)
                    if company_link
                    else company_tag.get_text(strip=True)
                )
            else:
                company = "Unknown Company"

            # -- Extract job URL & ID -------------------------------------
            link_tag = card.find("a", class_="base-card__full-link")
            raw_url = link_tag["href"] if link_tag and link_tag.get("href") else ""
            # Strip query parameters to get the canonical job URL.
            canonical_url = raw_url.split("?")[0] if raw_url else ""
            job_id = _extract_job_id(canonical_url)

            if not job_id:
                logger.debug("Could not extract job ID from URL '%s'. Skipping.", raw_url)
                continue

            # -- Extract location -----------------------------------------
            location_tag = card.find(class_="job-search-card__location")
            job_location = (
                location_tag.get_text(strip=True) if location_tag else "Unknown Location"
            )

            job_record = {
                "id": job_id,
                "title": title,
                "company": company,
                "location": job_location,
                "url": canonical_url,
                # Description is populated lazily by scrape_job_description()
                # to avoid hammering detail pages for every listing.
                "description": "",
            }
            collected_jobs.append(job_record)
            page_count += 1

            # Stop early if we've hit our target.
            if len(collected_jobs) >= max_results:
                break

        logger.info("Parsed %d jobs from this page.", page_count)

        # LinkedIn returns an empty page when results are exhausted.
        if page_count < BATCH_SIZE:
            logger.info("Received fewer than %d results — end of listings.", BATCH_SIZE)
            break

        offset += BATCH_SIZE
        _random_delay()

    logger.info("Scrape complete. Total jobs collected: %d", len(collected_jobs))
    return collected_jobs


def scrape_job_description(job_url: str) -> str:
    """
    Fetch and extract the full job description text from a LinkedIn job page.

    LinkedIn renders two possible markup containers for job descriptions:
      1. `.description__text`          — older layout
      2. `.show-more-less-html__markup` — newer layout with expanded text

    Both are tried in order; the first non-empty result is returned.

    Args:
        job_url: The canonical LinkedIn job detail URL (e.g.
                 "https://www.linkedin.com/jobs/view/1234567890/").

    Returns:
        The raw description text, or an empty string if extraction fails.
    """
    _random_delay()

    try:
        response = requests.get(
            job_url,
            headers=_get_headers(),
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        logger.warning("HTTP error fetching job description from '%s': %s", job_url, exc)
        return ""
    except requests.exceptions.RequestException as exc:
        logger.error("Network error fetching job description from '%s': %s", job_url, exc)
        return ""

    soup = BeautifulSoup(response.text, "lxml")

    # Try the newer expanded markup container first.
    desc_tag = soup.find(class_="show-more-less-html__markup")
    if desc_tag:
        return desc_tag.get_text(separator="\n", strip=True)

    # Fall back to the older description container.
    desc_tag = soup.find(class_="description__text")
    if desc_tag:
        return desc_tag.get_text(separator="\n", strip=True)

    logger.warning("No description markup found for URL: %s", job_url)
    return ""
