"""
matcher.py
==========
Dual-Stage AI Job Screening & Profile Tailoring
-------------------------------------------------
Evaluates candidate fit against target job descriptions and tailors resume
bullets and summaries while strictly preserving real candidate projects.
"""

import json
import logging
import os
import time
from typing import Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("matcher")

PASS_THRESHOLD = 0.70
GROQ_MODEL_PRIMARY = "llama-3.3-70b-versatile"
GROQ_MODEL_FALLBACK = "llama-3.1-8b-instant"
GEMINI_MODEL = "models/gemini-2.5-flash"

_GROQ_SYSTEM_PROMPT = """You are an AI job screener. Evaluate fit and return JSON with keys 'score' (float 0.0-1.0) and 'reason' (string)."""

_TAILOR_SYSTEM_PROMPT = """You are a senior technical resume writer and career coach with expertise in ATS optimization.
Tailor the provided candidate profile JSON to align with the target job description.
Do NOT invent new companies or fake projects. Return ONLY JSON."""

def _init_gemini_client() -> bool:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not genai:
        return False
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False

def screen_job_with_groq(
    profile_summary: str,
    job_description: str,
    job_title: str,
    company: str,
    groq_client: Optional[any] = None,
) -> dict:
    if not groq_client:
        return {"score": 0.85, "reason": "Default qualifying score."}

    truncated_desc = job_description[:2500] if len(job_description) > 2500 else job_description
    user_message = (
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n\n"
        f"CANDIDATE PROFILE SUMMARY:\n{profile_summary}\n\n"
        f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
        "Evaluate fit and return JSON with keys 'score' and 'reason'."
    )

    models_to_try = [GROQ_MODEL_PRIMARY, GROQ_MODEL_FALLBACK, "mixtral-8x7b-32768"]
    for model_name in models_to_try:
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
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
        except Exception as e:
            logger.warning("Groq request warning with model %s: %s", model_name, e)
            time.sleep(1)

    # Heuristic Keyword Fallback if Groq API fails or endpoint errors out
    keywords = ["full stack", "react", "node", "javascript", "typescript", "frontend", "backend", "web", "software"]
    text_to_check = f"{job_title} {job_description}".lower()
    matches = sum(1 for kw in keywords if kw in text_to_check)
    fallback_score = min(0.95, 0.65 + (matches * 0.05)) if matches > 0 else 0.50
    return {"score": fallback_score, "reason": "Keyword heuristic screening."}

def tailor_profile_with_gemini(
    base_profile: dict,
    job_description: str,
    job_title: str,
    company: str,
) -> Optional[dict]:
    if not _init_gemini_client():
        return None
    try:
        profile_json_str = json.dumps(base_profile, indent=2)
        truncated_desc = job_description[:3500] if len(job_description) > 3500 else job_description

        user_prompt = (
            f"TARGET JOB TITLE: {job_title}\n"
            f"TARGET COMPANY: {company}\n\n"
            f"JOB DESCRIPTION:\n{truncated_desc}\n\n"
            f"CANDIDATE BASE PROFILE (JSON):\n{profile_json_str}\n\n"
            "Tailor professional summary and technical skills for this role. Return ONLY JSON."
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

def evaluate_job(
    job: dict,
    base_profile: dict,
    groq_client: Optional[any] = None,
) -> dict:
    job_id = job.get("id", "unknown")
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    description = job.get("description", "")

    summary_text = base_profile.get("summary", "")
    stage1_result = screen_job_with_groq(
        profile_summary=summary_text,
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
    }

    if not passed:
        return result

    tailored = tailor_profile_with_gemini(
        base_profile=base_profile,
        job_description=description,
        job_title=title,
        company=company,
    )
    result["tailored_profile"] = tailored or base_profile
    return result
