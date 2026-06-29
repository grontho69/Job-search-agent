"""
core_orchestrator.py  (v2 — Excel edition)
===========================================
Stateful AI Job Search Pipeline — Excel Output
-----------------------------------------------
Redesigned workflow:
  1. Search LinkedIn for 6 job categories (15 total unique jobs per day)
  2. Skip already-logged jobs (read from job_tracker.xlsx, not processed_jobs.json)
  3. Fetch full job descriptions
  4. Stage 1: Groq relevance screening (skip jobs < 80% match)
  5. Stage 2: Gemini profile tailoring per job (one specific CV per job)
  6. Compile DOCX resume into output/YYYY-MM-DD/ date folder
  7. Log everything to job_tracker.xlsx (no email)
  8. Save processed IDs back to processed_jobs.json for GitHub Actions state

Job categories searched (15 total, spread across 6 keywords):
  - Full Stack Web Developer
  - Junior Web Developer
  - MERN Stack Web Developer
  - Frontend Web Developer
  - React Developer
  - JavaScript Web Developer

Output structure:
  output/
    2026-06-29/
      resume_FullStack_Shopify_120500.docx
      resume_React_Developer_GitHub_120612.docx
      ...
  job_tracker.xlsx   <-- Master Excel log (open this to see all results)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scraper import scrape_job_listings, scrape_job_description
from matcher import evaluate_job
from compiler import compile_resume
from reporter import append_job_row, write_run_summary, get_all_logged_job_ids
from groq import Groq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("orchestrator.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_PROFILE_PATH  = Path("base_profile.json")
PROCESSED_JOBS_PATH = Path("processed_jobs.json")
OUTPUT_BASE_DIR    = Path("output")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Target: fetch this many unique new jobs total per run.
DAILY_JOB_LIMIT = 15

# Minimum Groq score to proceed to CV compilation (80% as requested).
PASS_THRESHOLD = 0.80

# Jobs to request per keyword from LinkedIn (we over-fetch then cap at DAILY_JOB_LIMIT).
FETCH_PER_KEYWORD = 5

# The 6 job categories to search — exactly as requested.
SEARCH_KEYWORDS = [
    kw.strip()
    for kw in os.environ.get(
        "SEARCH_KEYWORDS",
        "Full Stack Web Developer,"
        "Junior Web Developer,"
        "MERN Stack Web Developer,"
        "Frontend Web Developer,"
        "React Developer,"
        "JavaScript Web Developer",
    ).split(",")
    if kw.strip()
]

SEARCH_LOCATION = os.environ.get("SEARCH_LOCATION", "Remote")

# Seconds between processing each job (avoids API hammering).
JOB_PROCESSING_DELAY = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_todays_output_dir() -> Path:
    """Return and create today's dated output folder: output/YYYY-MM-DD/"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = OUTPUT_BASE_DIR / today
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _load_base_profile() -> dict:
    if not BASE_PROFILE_PATH.exists():
        logger.critical("base_profile.json not found. Exiting.")
        sys.exit(1)
    with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)
    logger.info("Profile loaded for: %s", profile.get("name", "Unknown"))
    return profile


def _load_processed_ids() -> set:
    """Load state from both Excel tracker and processed_jobs.json."""
    # Primary source: Excel tracker (most up-to-date)
    ids_from_excel = get_all_logged_job_ids()

    # Secondary source: JSON state file (for GitHub Actions continuity)
    ids_from_json = set()
    if PROCESSED_JOBS_PATH.exists():
        try:
            with open(PROCESSED_JOBS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            ids_from_json = set(data.get("processed_job_ids", []))
        except Exception:
            pass

    combined = ids_from_excel | ids_from_json
    logger.info(
        "Known processed jobs: %d (Excel: %d, JSON: %d)",
        len(combined), len(ids_from_excel), len(ids_from_json),
    )
    return combined


def _save_processed_ids(ids: set, summary: dict) -> None:
    """Persist state to processed_jobs.json for GitHub Actions."""
    state = {
        "processed_job_ids": sorted(list(ids)),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_processed": len(ids),
        "last_run_summary": summary,
    }
    with open(PROCESSED_JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    logger.info("State saved: %d total processed jobs.", len(ids))


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    """
    Full daily job search and CV compilation pipeline.

    Steps:
      1. Load profile + processed state
      2. Scrape LinkedIn for 6 job categories
      3. Deduplicate and cap at DAILY_JOB_LIMIT (15)
      4. For each new job: describe → screen → tailor → compile → log
      5. Write Excel summary row
      6. Persist state

    Returns:
        Run statistics dict.
    """
    run_start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("AI Resume Agent v2 (Excel Edition) - Pipeline Start")
    logger.info("Run: %s | Target: %d jobs | Threshold: %.0f%%",
                run_start.strftime("%Y-%m-%d %H:%M UTC"),
                DAILY_JOB_LIMIT,
                PASS_THRESHOLD * 100)
    logger.info("=" * 60)

    # -----------------------------------------------------------------------
    # Init
    # -----------------------------------------------------------------------
    from reporter import ensure_sheet_headers
    ensure_sheet_headers()

    output_dir   = _get_todays_output_dir()
    base_profile = _load_base_profile()
    processed_ids = _load_processed_ids()

    try:
        groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
        logger.info("Groq client ready.")
    except KeyError:
        logger.critical("GROQ_API_KEY not set. Exiting.")
        sys.exit(1)

    stats = {
        "total_scraped": 0,
        "skipped_duplicate": 0,
        "new_jobs": 0,
        "below_threshold": 0,
        "passed_screening": 0,
        "resumes_compiled": 0,
        "gemini_tailored": 0,
        "gsheets_rows_added": 0,
        "errors": [],
    }

    newly_processed: set = set()

    # -----------------------------------------------------------------------
    # Phase 1: Scrape all keywords, collect unique new jobs
    # -----------------------------------------------------------------------
    logger.info("Phase 1: Scraping LinkedIn for %d keywords...", len(SEARCH_KEYWORDS))
    seen_ids: set = set()
    candidate_jobs: list = []

    for keyword in SEARCH_KEYWORDS:
        if len(candidate_jobs) >= DAILY_JOB_LIMIT * 2:
            # We have more than enough candidates; stop scraping early
            break

        logger.info("  Searching: '%s' | Location: '%s'", keyword, SEARCH_LOCATION)
        try:
            raw = scrape_job_listings(
                keywords=keyword,
                location=SEARCH_LOCATION,
                max_results=FETCH_PER_KEYWORD,
            )
        except Exception as exc:
            msg = f"Scrape failed for '{keyword}': {exc}"
            logger.error(msg)
            stats["errors"].append(msg)
            continue

        stats["total_scraped"] += len(raw)

        for job in raw:
            jid = job.get("id")
            if not jid:
                continue
            if jid in processed_ids:
                stats["skipped_duplicate"] += 1
                continue
            if jid in seen_ids:
                # Deduplicate within this run (same job found by 2 keywords)
                continue
            seen_ids.add(jid)
            candidate_jobs.append(job)

        logger.info("  Candidates so far: %d unique new jobs", len(candidate_jobs))

    # Cap at daily limit
    jobs_to_process = candidate_jobs[:DAILY_JOB_LIMIT]
    stats["new_jobs"] = len(jobs_to_process)

    logger.info("=" * 60)
    logger.info("Phase 1 complete: %d new unique jobs to process (capped at %d)",
                len(jobs_to_process), DAILY_JOB_LIMIT)

    if not jobs_to_process:
        logger.info("No new jobs found. All done for today.")
        write_run_summary(
            stats["total_scraped"], 0, 0, 0, stats["errors"]
        )
        _save_processed_ids(processed_ids | newly_processed, stats)
        return stats

    # -----------------------------------------------------------------------
    # Phase 2: Process each job
    # -----------------------------------------------------------------------
    logger.info("Phase 2: Screening, tailoring, and compiling CVs...")

    for idx, job in enumerate(jobs_to_process, start=1):
        job_id  = job.get("id", "unknown")
        title   = job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")
        url     = job.get("url", "")
        location = job.get("location", "")

        logger.info("-" * 50)
        logger.info("[%d/%d] %s @ %s (ID: %s)",
                    idx, len(jobs_to_process), title, company, job_id)

        # -------------------------------------------------------------------
        # Step A: Fetch full job description
        # -------------------------------------------------------------------
        if not job.get("description") and url:
            try:
                job["description"] = scrape_job_description(url)
                if job["description"]:
                    logger.info("  Description fetched (%d chars).", len(job["description"]))
                else:
                    logger.warning("  No description found — will screen on title only.")
            except Exception as exc:
                logger.warning("  Description fetch failed: %s", exc)
                job["description"] = ""

        # -------------------------------------------------------------------
        # Step B: AI Evaluation (Stage 1 Groq + Stage 2 Gemini)
        # -------------------------------------------------------------------
        try:
            result = evaluate_job(
                job=job,
                base_profile=base_profile,
                groq_client=groq_client,
            )
        except Exception as exc:
            msg = f"evaluate_job failed for {job_id}: {exc}"
            logger.error(msg)
            stats["errors"].append(msg)
            newly_processed.add(job_id)
            continue

        score  = result.get("score", 0.0)
        reason = result.get("reason", "")
        passed = score >= PASS_THRESHOLD

        logger.info("  Groq Score: %.0f%% | %s", score * 100, reason)

        if not passed:
            stats["below_threshold"] += 1
            logger.info("  Below %.0f%% threshold — skipping CV.", PASS_THRESHOLD * 100)
            newly_processed.add(job_id)
            # Still log to Google Sheets so you have full visibility
            append_job_row(
                job_id=job_id, title=title, company=company,
                location=location, url=url, score=score,
                rationale=reason, cv_filename="N/A (Below threshold)",
                cv_abs_path="", gemini_tailored=False, status="Skipped",
            )
            stats["gsheets_rows_added"] += 1
            continue

        stats["passed_screening"] += 1
        gemini_ok = result.get("tailored_profile") is not None
        # Make a shallow copy of the profile so we don't mutate base_profile globally
        profile_to_compile = dict(result.get("tailored_profile") or base_profile)
        # Set the exact target job title as the CV headline for this specific job
        profile_to_compile["professional_title"] = title

        if gemini_ok:
            stats["gemini_tailored"] += 1
            logger.info("  Gemini tailored CV ready for '%s'.", title)
        else:
            logger.warning("  Gemini failed/quota — compiling specific CV using base profile for '%s'.", title)

        # -------------------------------------------------------------------
        # Step C: Compile the DOCX — one specific CV for this specific job
        # -------------------------------------------------------------------
        # Filename: resume_{Title}_{Company}_{Time}.docx
        safe_title   = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:30].strip().replace(" ", "_")
        safe_company = "".join(c if c.isalnum() or c in " _-" else "" for c in company)[:18].strip().replace(" ", "_")
        timestamp    = datetime.now(timezone.utc).strftime("%H%M%S")
        docx_name    = f"resume_{safe_title}_{safe_company}_{timestamp}.docx"
        docx_path    = str(output_dir / docx_name)

        try:
            compile_resume(profile=profile_to_compile, output_path=docx_path)
            stats["resumes_compiled"] += 1
            logger.info("  CV compiled: %s", docx_name)
        except Exception as exc:
            msg = f"CV compile failed for {job_id}: {exc}"
            logger.error(msg, exc_info=True)
            stats["errors"].append(msg)
            newly_processed.add(job_id)
            continue

        # -------------------------------------------------------------------
        # Step D: Log directly to Google Sheets
        # -------------------------------------------------------------------
        append_job_row(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            url=url,
            score=score,
            rationale=reason,
            cv_filename=docx_name,
            cv_abs_path=docx_path,
            gemini_tailored=gemini_ok,
            status="Applied" if score >= 0.90 else "Review",
        )
        stats["gsheets_rows_added"] += 1

        newly_processed.add(job_id)

        # Automatically cleanup local temporary CV files so they are NOT saved in the local system
        try:
            if os.path.exists(docx_path):
                os.remove(docx_path)
            pdf_path = docx_path.replace(".docx", ".pdf")
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            logger.info("  Cleaned up local temporary CV files for %s", job_id)
        except Exception:
            pass

        if idx < len(jobs_to_process):
            time.sleep(JOB_PROCESSING_DELAY)

    # -----------------------------------------------------------------------
    # Phase 3: Save state and write summary
    # -----------------------------------------------------------------------
    write_run_summary(
        total_scraped=stats["total_scraped"],
        new_jobs=stats["new_jobs"],
        passed_screening=stats["passed_screening"],
        resumes_compiled=stats["resumes_compiled"],
        errors=stats["errors"],
    )
    _save_processed_ids(processed_ids | newly_processed, stats)

    # -----------------------------------------------------------------------
    # Final summary log
    # -----------------------------------------------------------------------
    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    logger.info("=" * 60)
    logger.info("Pipeline Complete | %.1fs", elapsed)
    logger.info("  Scraped:          %d", stats["total_scraped"])
    logger.info("  Skipped (dupe):   %d", stats["skipped_duplicate"])
    logger.info("  New jobs:         %d", stats["new_jobs"])
    logger.info("  Passed %.0f%% screen: %d", PASS_THRESHOLD * 100, stats["passed_screening"])
    logger.info("  Below threshold:  %d", stats["below_threshold"])
    logger.info("  CVs compiled:     %d", stats["resumes_compiled"])
    logger.info("  Gemini tailored:  %d", stats["gemini_tailored"])
    logger.info("  Google Sheets rows added: %d", stats["gsheets_rows_added"])
    if stats["errors"]:
        logger.warning("  Errors:                   %d", len(stats["errors"]))
    logger.info("  Output folder:            %s", output_dir.absolute())
    logger.info("  Google Sheet ID:          1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI")
    logger.info("=" * 60)

    return stats


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        summary = run_pipeline()
        logger.info("🛑 [AUTOMATIC STOP] 15 jobs completed. Agent shutting down cleanly.")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        logger.critical("Unhandled error: %s", exc, exc_info=True)
        sys.exit(1)
