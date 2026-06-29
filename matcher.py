"""
matcher.py
==========
Dual-Stage AI Job Screening & Profile Tailoring
-------------------------------------------------
Implements a two-stage AI pipeline designed to stay within free-tier API quotas:

  Stage 1 — Groq Pre-Screening:
    Uses a fast, high-throughput Groq model (qwen-qwq-32b or llama-3.3-70b) to
    score each job's relevance to the candidate's profile (0.0 – 1.0). Only
    jobs scoring >= PASS_THRESHOLD proceed to Stage 2.

  Stage 2 — Gemini / Groq Tailoring:
    Intelligently tailors the candidate's professional summary, technical skills,
    and bullet alignments specifically to match the target job description while
    strictly preserving real personal details and project facts.

Dependencies:
    pip install groq google-generativeai
"""

import json
import logging
import os
import time
from typing import Optional

try:
    from groq import Groq
except ImportError as exc:
    raise ImportError("Groq SDK not found. Install with: pip install groq") from exc

try:
    import google.generativeai as genai
except ImportError as exc:
    raise ImportError("Google Generative AI SDK not found. Install with: pip install google-generativeai") from exc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("matcher")

PASS_THRESHOLD = 0.80
GROQ_MODEL_PRIMARY = "llama-3.3-70b-versatile"
GROQ_MODEL_FALLBACK = "llama-3.1-8b-instant"
GEMINI_MODEL = "models/gemini-2.5-flash"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

_GROQ_SYSTEM_PROMPT = """You are an AI job screener. Evaluate fit and return JSON with keys 'score' (float 0.0-1.0) and 'reason' (string)."""

_TAILOR_SYSTEM_PROMPT = """You are a senior technical resume writer and career coach with expertise in ATS optimization.

Your task: Tailor the provided candidate profile JSON to align perfectly with the target job description.

MANDATORY RULES:
1. DYNAMIC SUMMARY & SKILLS: Rewrite the professional summary and restructure technical skills to dynamically highlight the exact tech stack, tools, framework priorities, and methodologies requested in the Job Description.
2. STRICT PERSONAL INFO & PROJECTS: Do NOT modify candidate name, contact info, email, phone, portfolio URL, LinkedIn, GitHub, or location. Do NOT add new companies or fake jobs. ONLY use the candidate's real projects (FoodFlow, Blood Donation Application SaaS, Volans Clothing E-Commerce, Community Cleanliness Platform).
3. FACTUAL PRESERVATION: Every technical bullet and achievement must be strictly grounded in the original candidate data. Do NOT fabricate experience.
4. ACTIVE VOICE & KEYWORDS: Align keywords with exact terms in the job description using strong active verbs.
5. OUTPUT FORMAT: Return ONLY a valid JSON object matching the exact schema of the input profile. No markdown formatting outside JSON."""


def _init_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY environment variable is not set.")
    return Groq(api_key=api_key)


def _init_gemini_client() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)


def screen_job_with_groq(
    profile_summary: str,
    job_description: str,
    job_title: str,
    company: str,
    groq_client: Optional[Groq] = None,
) -> dict:
    client = groq_client or _init_groq_client()
    truncated_desc = job_description[:2500] if len(job_description) > 2500 else job_description

    user_message = (
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n\n"
        f"CANDIDATE PROFILE SUMMARY:\n{profile_summary}\n\n"
        f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
        "Evaluate fit and return JSON with keys 'score' and 'reason'."
    )

    model_to_use = GROQ_MODEL_PRIMARY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": _GROQ_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=150,
            )
            raw_content = response.choices[0].message.content.strip()
            parsed = json.loads(raw_content)
            score = float(parsed.get("score", 0.0))
            reason = str(parsed.get("reason", "Evaluated relevance."))
            return {"score": max(0.0, min(1.0, score)), "reason": reason}
        except Exception as exc:
            if attempt == 1:
                model_to_use = GROQ_MODEL_FALLBACK
            time.sleep(1)

    return {"score": 0.0, "reason": "Screening failed."}


def tailor_profile_with_gemini(
    base_profile: dict,
    job_description: str,
    job_title: str,
    company: str,
) -> Optional[dict]:
    try:
        _init_gemini_client()
        profile_json_str = json.dumps(base_profile, indent=2)
        truncated_desc = job_description[:4000] if len(job_description) > 4000 else job_description

        user_prompt = (
            f"TARGET JOB TITLE: {job_title}\n"
            f"TARGET COMPANY: {company}\n\n"
            f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
            f"CANDIDATE BASE PROFILE (JSON):\n{profile_json_str}\n\n"
            "Tailor professional summary and technical skills for this role following rules. Return ONLY JSON."
        )

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=_TAILOR_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        response = model.generate_content(user_prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        return json.loads(raw_text)
    except Exception as exc:
        logger.warning("Gemini tailoring notice: %s", exc)
        return None


def tailor_profile_with_groq(
    base_profile: dict,
    job_description: str,
    job_title: str,
    company: str,
    groq_client: Optional[Groq] = None,
) -> Optional[dict]:
    try:
        client = groq_client or _init_groq_client()
        profile_json_str = json.dumps(base_profile, indent=2)
        truncated_desc = job_description[:3000] if len(job_description) > 3000 else job_description

        user_message = (
            f"TARGET JOB TITLE: {job_title}\n"
            f"TARGET COMPANY: {company}\n\n"
            f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
            f"CANDIDATE BASE PROFILE (JSON):\n{profile_json_str}\n\n"
            "Tailor the summary and technical skills JSON for this job description. Return ONLY JSON."
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL_PRIMARY,
            messages=[
                {"role": "system", "content": _TAILOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1500,
        )
        raw_content = response.choices[0].message.content.strip()
        return json.loads(raw_content)
    except Exception as exc:
        logger.warning("Groq tailoring fallback error: %s", exc)
        return None


def evaluate_job(
    job: dict,
    base_profile: dict,
    groq_client: Optional[Groq] = None,
) -> dict:
    job_id = job.get("id", "unknown")
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    description = job.get("description", "")

    summary_text = base_profile.get("summary", "")
    profile_summary = f"{summary_text}\n\nKey skills: MERN Stack, React, Node, Express, MongoDB"

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
        "error": None,
    }

    if not passed:
        return result

    # Stage 2: Gemini Tailoring with Groq Fallback
    tailored = tailor_profile_with_gemini(
        base_profile=base_profile,
        job_description=description,
        job_title=title,
        company=company,
    )

    if tailored is None:
        logger.info("Using Groq fallback for Stage 2 profile tailoring...")
        tailored = tailor_profile_with_groq(
            base_profile=base_profile,
            job_description=description,
            job_title=title,
            company=company,
            groq_client=groq_client,
        )

    result["tailored_profile"] = tailored or base_profile
    return result
