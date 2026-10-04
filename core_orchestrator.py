"""
core_orchestrator.py
====================
Next-Gen Autonomous Remote Job Search & Tailored ATS Resume Agent
- Queries multi-channel free remote job APIs (Remotive, Jobicy, LinkedIn Guest)
- Filters strictly for non-US / eligible international remote candidates
- Deduplicates via Supabase cloud database to guarantee zero repeated jobs
- Prioritizes Mahathir's core projects (EduTec, Zenji, AI Job Agent, Restaurant)
- Compiles custom Overleaf/Jake's Resume LaTeX sources into 90+ ATS-score vector PDFs
- Dispatches formatted daily job briefings directly to WhatsApp
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scrapers.unified_aggregator import aggregate_target_jobs
from matcher import evaluate_job
from cv_generator.latex_templates import generate_latex_source
from cv_generator.latex_compiler import compile_latex_to_pdf
from database.supabase_client import get_all_processed_job_ids, insert_processed_job
from notifications.whatsapp_reporter import send_whatsapp_job_report
from groq import Groq

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("orchestrator")

BASE_PROFILE_PATH = Path("base_profile.json")
OUTPUT_BASE_DIR = Path("output")

def _load_profile() -> dict:
    """Loads master user profile from USER_PROFILE_JSON env or base_profile.json."""
    raw_env = os.environ.get("USER_PROFILE_JSON", "").strip()
    if raw_env:
        try:
            p = json.loads(raw_env)
            if p.get("name"):
                return p
        except Exception:
            pass

    if BASE_PROFILE_PATH.exists():
        with open(BASE_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.critical("No master profile configured. Please populate base_profile.json.")
    sys.exit(1)

def run_pipeline() -> dict:
    """Main automated workflow execution."""
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("AI Job Search & Tailored ATS Resume Agent - Starting Workflow")
    logger.info("Time: %s", start_time.strftime("%Y-%m-%d %H:%M UTC"))
    logger.info("=" * 60)

    profile = _load_profile()
    cfg = profile.get("_agent_config", {})
    daily_limit = int(cfg.get("daily_job_limit", 20))
    pass_threshold = float(cfg.get("pass_threshold", 0.75))
    keywords = cfg.get("search_keywords", ["Full Stack Web Developer", "MERN Stack Developer"])
    excluded_countries = cfg.get("excluded_countries", ["United States", "US", "USA"])

    # 1. Fetch previously seen job IDs from Supabase
    seen_job_ids = get_all_processed_job_ids()
    logger.info("Database loaded: %d previously processed job IDs.", len(seen_job_ids))

    # 2. Gather fresh candidates from multi-channel remote sources
    candidates = aggregate_target_jobs(
        keywords=keywords,
        excluded_countries=excluded_countries,
        known_job_ids=seen_job_ids,
        target_count=daily_limit
    )

    today_str = start_time.strftime("%Y-%m-%d")
    output_dir = OUTPUT_BASE_DIR / today_str
    output_dir.mkdir(parents=True, exist_ok=True)

    groq_api_key = os.environ.get("GROQ_API_KEY")
    groq_client = Groq(api_key=groq_api_key) if groq_api_key else None

    qualified_jobs = []

    # 3. Process and screen jobs
    for idx, job in enumerate(candidates, start=1):
        if len(qualified_jobs) >= daily_limit:
            break

        jid = job.get("id")
        title = job.get("title")
        company = job.get("company")
        logger.info("[%d/%d candidates] Evaluating: %s @ %s", idx, len(candidates), title, company)

        eval_result = evaluate_job(job=job, base_profile=profile, groq_client=groq_client)
        score = eval_result.get("score", 0.0)
        passed = score >= pass_threshold or not groq_client  # Fallback to keep flowing

        if not passed:
            logger.info("  Skipping: Fit score %.0f%% below %.0f%% threshold.", score * 100, pass_threshold * 100)
            continue

        tailored_profile = eval_result.get("tailored_profile") or profile

        # Generate LaTeX & PDF Custom CV
        safe_company = "".join(c if c.isalnum() else "_" for c in company)[:15]
        safe_title = "".join(c if c.isalnum() else "_" for c in title)[:20]
        tex_filename = f"Resume_{safe_company}_{safe_title}.tex"
        pdf_filename = f"Resume_{safe_company}_{safe_title}.pdf"
        tex_path = output_dir / tex_filename
        pdf_path = output_dir / pdf_filename

        tex_code = generate_latex_source(profile=tailored_profile, target_job=job)
        compile_latex_to_pdf(tex_code=tex_code, output_pdf_path=str(pdf_path), output_tex_path=str(tex_path))

        job_info = {
            "id": jid,
            "title": title,
            "company": company,
            "country": job.get("country", "Worldwide"),
            "salary": job.get("salary", "Not Specified"),
            "score": score,
            "url": job.get("url"),
            "pdf_filename": pdf_filename,
            "pdf_path": str(pdf_path)
        }

        # Record in Supabase
        insert_processed_job(
            job_id=jid,
            title=title,
            company=company,
            location=job.get("location", ""),
            url=job.get("url", ""),
            score=score,
            country=job.get("country", "Worldwide"),
            salary=job.get("salary", "Not Specified"),
            rationale=eval_result.get("reason", ""),
            pdf_url=str(pdf_path)
        )

        qualified_jobs.append(job_info)
        logger.info("  ✅ Qualified Job [%d/%d]: %s (%s)", len(qualified_jobs), daily_limit, title, company)

    # 4. Dispatch Briefing to WhatsApp
    if qualified_jobs:
        send_whatsapp_job_report(qualified_jobs)
        logger.info("Dispatched WhatsApp briefing for %d jobs.", len(qualified_jobs))
    else:
        logger.warning("No new qualified jobs met the threshold today.")

    logger.info("Pipeline Complete. %d opportunities processed and logged.", len(qualified_jobs))
    return {"qualified_count": len(qualified_jobs)}

if __name__ == "__main__":
    run_pipeline()
