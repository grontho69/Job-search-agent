"""
matcher.py
==========
Dual-Stage AI Job Screening & Profile Tailoring
-------------------------------------------------
Implements a two-stage AI pipeline designed to stay within free-tier API quotas:

  Stage 1 — Groq Pre-Screening:
    Uses a fast, high-throughput Groq model (qwen-qwq-32b or llama-3.1-8b) to
    score each job's relevance to the candidate's profile (0.0 – 1.0). Only
    jobs scoring >= PASS_THRESHOLD proceed to Stage 2, conserving Gemini quota.

  Stage 2 — Gemini Tailoring:
    Uses Google's Gemini 2.5 Flash model to intelligently tailor the candidate's
    base JSON profile to match a specific job description, synthesizing passive
    duties into achievement-oriented bullets and aligning keywords — all while
    strictly preserving factual accuracy (no fabrication).

Quota Management:
    Groq free tier: generous RPM/TPM limits — safe for every job listing.
    Gemini free tier: 15 RPM — only called for high-relevance jobs (score >= 0.75).

Dependencies:
    pip install groq google-genai  (or google-generativeai)
"""

import json
import logging
import os
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Groq SDK — https://github.com/groq/groq-python
# ---------------------------------------------------------------------------
try:
    from groq import Groq
except ImportError as exc:
    raise ImportError(
        "Groq SDK not found. Install with: pip install groq"
    ) from exc

# ---------------------------------------------------------------------------
# Google Generative AI SDK — https://github.com/google-gemini/generative-ai-python
# ---------------------------------------------------------------------------
try:
    import google.generativeai as genai
except ImportError as exc:
    raise ImportError(
        "Google Generative AI SDK not found. Install with: pip install google-generativeai"
    ) from exc

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("matcher")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum relevance score from Stage 1 to trigger Stage 2 Gemini tailoring.
# Setting this at 0.75 means only well-matched jobs consume Gemini API quota.
PASS_THRESHOLD = 0.75

# Groq model selection — llama-3.3-70b-versatile is the most capable free model;
# fall back to llama-3.1-8b-instant if quota is exhausted (faster, lower quota usage).
GROQ_MODEL_PRIMARY = "llama-3.3-70b-versatile"
GROQ_MODEL_FALLBACK = "llama-3.1-8b-instant"

# Gemini model — 2.5 Flash is optimized for speed/cost balance.
GEMINI_MODEL = "models/gemini-2.5-flash"

# Retry parameters for transient API errors.
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10


# ---------------------------------------------------------------------------
# Client Initialization
# ---------------------------------------------------------------------------

def _init_groq_client() -> Groq:
    """
    Initialize and return a Groq API client.

    Reads the GROQ_API_KEY environment variable. Raises EnvironmentError
    if the key is absent, providing a clear actionable error message.

    Returns:
        An authenticated Groq client instance.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Obtain a free key at https://console.groq.com/"
        )
    return Groq(api_key=api_key)


def _init_gemini_client() -> None:
    """
    Configure the Google Generative AI SDK with the API key.

    Reads the GEMINI_API_KEY environment variable. Raises EnvironmentError
    if the key is absent.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Obtain a free key at https://aistudio.google.com/app/apikey"
        )
    genai.configure(api_key=api_key)


# ---------------------------------------------------------------------------
# Stage 1: Groq Pre-Screening
# ---------------------------------------------------------------------------

# System prompt for Stage 1: instructs the model to output ONLY valid JSON
# with no markdown fences, comments, or prose — enabling direct json.loads().
_GROQ_SYSTEM_PROMPT = """You are an expert technical recruiter assistant performing rapid job-candidate fit analysis.

Your task: Given a candidate profile summary and a job description, output ONLY a valid JSON object with this exact structure:
{"score": <float between 0.0 and 1.0>, "reason": "<one sentence rationale>"}

Scoring rubric:
  1.0 = Perfect match (all required skills, experience level, and domain align)
  0.75-0.99 = Strong match (most requirements met, minor gaps)
  0.50-0.74 = Moderate match (some alignment, notable gaps)
  0.0-0.49 = Poor match (significant misalignment)

CRITICAL RULES:
- Output ONLY the raw JSON object. No markdown, no code fences, no explanation.
- The "score" field MUST be a float, not a string.
- Keep "reason" under 30 words.
"""


def screen_job_with_groq(
    profile_summary: str,
    job_description: str,
    job_title: str,
    company: str,
    groq_client: Optional[Groq] = None,
) -> dict:
    """
    Stage 1: Fast relevance scoring using Groq's free-tier inference.

    Constructs a concise prompt from the candidate's profile summary and
    the job description, then asks a Groq-hosted model to score the fit
    and provide a one-sentence rationale.

    Args:
        profile_summary:  A compact text summary of the candidate's background.
                          Extract this from base_profile.json["summary"].
        job_description:  Raw job description text (max ~3,000 tokens; truncate
                          longer descriptions before passing).
        job_title:        The job title for context in the prompt.
        company:          The hiring company name.
        groq_client:      Optional pre-initialized Groq client. If None, one
                          is created from the GROQ_API_KEY environment variable.

    Returns:
        A dict with keys:
          - "score"  (float): Relevance score 0.0–1.0.
          - "reason" (str):   One-sentence rationale.
          - "error"  (str):   Present only if the call failed; score will be 0.0.
    """
    client = groq_client or _init_groq_client()

    # Truncate description to ~2,500 chars to stay well within token limits
    # while preserving the most discriminating early content.
    truncated_desc = job_description[:2500] if len(job_description) > 2500 else job_description

    user_message = (
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n\n"
        f"CANDIDATE PROFILE SUMMARY:\n{profile_summary}\n\n"
        f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
        "Evaluate the candidate's fit for this role and return the JSON score object."
    )

    # Retry loop for transient network/API errors.
    last_error: Optional[str] = None
    model_to_use = GROQ_MODEL_PRIMARY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(
                "Stage 1 | Attempt %d | Model: %s | Job: %s @ %s",
                attempt, model_to_use, job_title, company,
            )
            response = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": _GROQ_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                # Request JSON mode so the model is explicitly instructed
                # to return valid JSON (reduces parse failures significantly).
                response_format={"type": "json_object"},
                temperature=0.1,   # Low temperature for deterministic scoring
                max_tokens=150,    # Score + reason is very short
            )

            raw_content = response.choices[0].message.content.strip()
            logger.debug("Groq raw response: %s", raw_content)

            # Parse the JSON response.
            parsed = json.loads(raw_content)

            # Validate schema — coerce types defensively.
            score = float(parsed.get("score", 0.0))
            reason = str(parsed.get("reason", "No reason provided."))

            # Clamp score to valid range.
            score = max(0.0, min(1.0, score))

            logger.info(
                "Stage 1 result | Job: '%s' @ '%s' | Score: %.2f | Reason: %s",
                job_title, company, score, reason,
            )
            return {"score": score, "reason": reason}

        except json.JSONDecodeError as exc:
            last_error = f"JSON parse error: {exc} — Raw: {raw_content!r}"
            logger.warning("Attempt %d failed (JSON parse): %s", attempt, last_error)

        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            logger.warning("Attempt %d failed: %s", attempt, last_error)

            # On first failure, try falling back to the secondary model.
            if attempt == 1 and model_to_use == GROQ_MODEL_PRIMARY:
                logger.info("Falling back to model: %s", GROQ_MODEL_FALLBACK)
                model_to_use = GROQ_MODEL_FALLBACK

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    logger.error("Stage 1 failed after %d attempts. Last error: %s", MAX_RETRIES, last_error)
    return {"score": 0.0, "reason": "Screening failed.", "error": last_error}


# ---------------------------------------------------------------------------
# Stage 2: Gemini Profile Tailoring
# ---------------------------------------------------------------------------

# System prompt for Stage 2 tailoring.
# This prompt enforces the critical constraint: Gemini may ONLY synthesize
# and restructure existing facts — it must NEVER fabricate skills, roles, or
# achievements not present in the original profile.
_GEMINI_SYSTEM_PROMPT = """You are a senior technical resume writer and career coach with expertise in ATS optimization.

Your task: Tailor the provided candidate profile JSON to better align with the target job description.

MANDATORY RULES (violation of any rule is grounds for rejection):
1. FACTUAL PRESERVATION: Do NOT add any skill, technology, certification, company, role, or achievement that is not already present in the input profile JSON. Every bullet must be grounded in the original data.
2. ACTIVE VOICE: Transform passive, duty-focused descriptions ("Responsible for managing...") into achievement-oriented bullets ("Managed X resulting in Y improvement").
3. KEYWORD ALIGNMENT: Where the candidate's existing experience supports it, substitute or include exact terminology from the job description (e.g., if they used "Kubernetes" and the job says "container orchestration", use both).
4. QUANTIFICATION: Where numeric results, percentages, or time savings are implied but not stated, it is acceptable to ask for clarification but NOT to invent numbers. Preserve all existing metrics exactly.
5. SUMMARY TAILORING: Rewrite the professional summary to lead with the most relevant skills for this specific role. Keep it to 3–4 sentences.
6. OUTPUT FORMAT: Return ONLY a valid JSON object matching the exact schema of the input profile. No markdown, no prose, no explanation.
7. SKILLS ORDERING: Reorder skill categories so the most relevant ones appear first, but do not add new skills.

Return the tailored profile as a single JSON object with the identical top-level keys as the input."""


def tailor_profile_with_gemini(
    base_profile: dict,
    job_description: str,
    job_title: str,
    company: str,
) -> Optional[dict]:
    """
    Stage 2: Deep profile tailoring using Google Gemini 2.5 Flash.

    Only called when a job passes the Stage 1 threshold (score >= 0.75).
    Asks Gemini to rewrite the profile JSON to highlight relevant experience
    and align keywords with the job description — without fabricating content.

    Args:
        base_profile:    The candidate's complete profile as a Python dict
                         (loaded from base_profile.json).
        job_description: The full job description text.
        job_title:       Job title for context.
        company:         Hiring company name for context.

    Returns:
        A tailored profile dict if successful, or None if all retries fail.
    """
    _init_gemini_client()

    # Serialize profile to JSON string for the prompt.
    profile_json_str = json.dumps(base_profile, indent=2)

    # Truncate description to ~4,000 chars — Gemini 2.5 Flash has generous
    # context but we keep prompts lean to stay within free-tier TPM limits.
    truncated_desc = job_description[:4000] if len(job_description) > 4000 else job_description

    user_prompt = (
        f"TARGET JOB TITLE: {job_title}\n"
        f"TARGET COMPANY: {company}\n\n"
        f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
        f"CANDIDATE BASE PROFILE (JSON):\n{profile_json_str}\n\n"
        "Tailor the profile JSON for this role following all rules above. "
        "Return ONLY the JSON object."
    )

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=_GEMINI_SYSTEM_PROMPT,
        # Note: use genai.GenerationConfig directly (not genai.types.GenerationConfig)
        # as of google-generativeai >= 0.8.x
        generation_config=genai.GenerationConfig(
            temperature=0.3,        # Slightly creative but mostly deterministic
            response_mime_type="application/json",  # Enforce JSON output
        ),
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Stage 2 | Attempt %d | Tailoring profile for '%s' @ '%s'",
                attempt, job_title, company,
            )
            response = model.generate_content(user_prompt)
            raw_text = response.text.strip()

            # Strip any accidental markdown fences that slip through.
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            tailored_profile = json.loads(raw_text)

            logger.info(
                "Stage 2 success | Tailored profile generated for '%s' @ '%s'",
                job_title, company,
            )
            return tailored_profile

        except json.JSONDecodeError as exc:
            logger.warning(
                "Attempt %d: Gemini returned invalid JSON: %s", attempt, exc
            )
        except Exception as exc:  # noqa: BLE001
            exc_str = str(exc)
            logger.warning("Attempt %d: Gemini API error: %s", attempt, exc_str[:300])

            if "429" in exc_str:
                import re as _re
                # Check if this is a DAILY quota (not per-minute).
                # Daily quota cannot be resolved by waiting — fail fast.
                if "PerDay" in exc_str or "per_day" in exc_str.lower():
                    logger.warning(
                        "Gemini DAILY quota exhausted (limit: 20/day). "
                        "Skipping Stage 2 for all remaining jobs today. "
                        "Quota resets at midnight UTC."
                    )
                    return None  # Fast-fail — no point retrying

                # Per-minute quota: parse suggested wait and honour it.
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY_SECONDS * attempt
                    m = _re.search(r"seconds:\s*(\d+)", exc_str)
                    if m:
                        wait = int(m.group(1)) + 5
                    logger.info("Rate limit (per-minute). Retrying in %d seconds...", wait)
                    time.sleep(wait)

            elif attempt < MAX_RETRIES:
                wait = RETRY_DELAY_SECONDS * attempt
                logger.info("Retrying Stage 2 in %d seconds...", wait)
                time.sleep(wait)
            continue

    logger.error(
        "Stage 2 failed after %d attempts for job '%s' @ '%s'.",
        MAX_RETRIES, job_title, company,
    )
    return None


# ---------------------------------------------------------------------------
# Public Orchestration Entry Point
# ---------------------------------------------------------------------------

def evaluate_job(
    job: dict,
    base_profile: dict,
    groq_client: Optional[Groq] = None,
) -> dict:
    """
    Run the full two-stage evaluation pipeline for a single job listing.

    This is the primary entry point called by core_orchestrator.py.

    Pipeline:
      1. Extract a compact profile summary for Stage 1.
      2. Run Stage 1 Groq screening to get a relevance score.
      3. If score >= PASS_THRESHOLD, run Stage 2 Gemini tailoring.
      4. Return a structured result dict.

    Args:
        job:          A job dict from scraper.scrape_job_listings(), which must
                      include "id", "title", "company", "description" keys.
        base_profile: The candidate's full profile loaded from base_profile.json.
        groq_client:  Optional pre-initialized Groq client (passed for reuse
                      across multiple calls to avoid repeated key lookups).

    Returns:
        A dict with keys:
          - "job_id"          (str):  LinkedIn job ID.
          - "title"           (str):  Job title.
          - "company"         (str):  Company name.
          - "score"           (float): Stage 1 relevance score.
          - "reason"          (str):  Stage 1 rationale.
          - "passed"          (bool): Whether the job passed Stage 1 threshold.
          - "tailored_profile"(dict|None): Stage 2 result, or None if not triggered.
          - "error"           (str|None): Error message if pipeline failed.
    """
    job_id = job.get("id", "unknown")
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    description = job.get("description", "")

    # Build a compact profile summary for Stage 1 (saves tokens vs. full JSON).
    summary_text = base_profile.get("summary", "")
    # Include top technical skills in the summary for richer context.
    skills_preview = []
    for category_data in base_profile.get("technical_skills", {}).values():
        if isinstance(category_data, list):
            skills_preview.extend(category_data[:3])  # Take up to 3 per category
    skills_str = ", ".join(skills_preview[:15])  # Cap at 15 total skills

    profile_summary = (
        f"{summary_text}\n\n"
        f"Key technical skills: {skills_str}"
    )

    # -----------------------------------------------------------------------
    # Stage 1: Groq Pre-Screening
    # -----------------------------------------------------------------------
    logger.info("Evaluating job %s: '%s' @ '%s'", job_id, title, company)

    stage1_result = screen_job_with_groq(
        profile_summary=profile_summary,
        job_description=description,
        job_title=title,
        company=company,
        groq_client=groq_client,
    )

    score = stage1_result.get("score", 0.0)
    reason = stage1_result.get("reason", "")
    passed = score >= PASS_THRESHOLD

    result = {
        "job_id": job_id,
        "title": title,
        "company": company,
        "url": job.get("url", ""),
        "score": score,
        "reason": reason,
        "passed": passed,
        "tailored_profile": None,
        "error": stage1_result.get("error"),
    }

    if not passed:
        logger.info(
            "Job %s did not pass Stage 1 threshold (%.2f < %.2f). Skipping Stage 2.",
            job_id, score, PASS_THRESHOLD,
        )
        return result

    # -----------------------------------------------------------------------
    # Stage 2: Gemini Profile Tailoring (only for high-relevance jobs)
    # -----------------------------------------------------------------------
    tailored = tailor_profile_with_gemini(
        base_profile=base_profile,
        job_description=description,
        job_title=title,
        company=company,
    )

    result["tailored_profile"] = tailored
    if tailored is None:
        result["error"] = (result.get("error") or "") + " | Stage 2 tailoring failed."

    return result
