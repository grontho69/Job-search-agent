# 🤖 AI Resume Agent — Zero-Cost LinkedIn Job Search & ATS Resume Generator

> **Automatically search LinkedIn → screen jobs with AI → compile tailored ATS resumes → email them to yourself — completely free, every weekday.**

[![GitHub Actions](https://img.shields.io/badge/Powered%20By-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Groq](https://img.shields.io/badge/Stage%201-Groq%20AI-F55036?logo=groq&logoColor=white)](https://console.groq.com/)
[![Gemini](https://img.shields.io/badge/Stage%202-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)

---

## 📋 Table of Contents

- [Architecture Overview](#-architecture-overview)
- [File Structure](#-file-structure)
- [How It Works](#-how-it-works)
- [Setup Instructions](#-setup-instructions)
- [Configuration Reference](#-configuration-reference)
- [API Key Acquisition](#-api-key-acquisition)
- [Gmail App Password Setup](#-gmail-app-password-setup)
- [ATS Resume Design Decisions](#-ats-resume-design-decisions)
- [Troubleshooting](#-troubleshooting)

---

## 🏗 Architecture Overview

```
GitHub Actions (cron: weekdays 9 AM UTC)
        │
        ▼
core_orchestrator.py
        │
        ├──► scraper.py          ── LinkedIn Guest API → Job listings (no auth needed)
        │         │
        │         └──► scrape_job_description() ── Full job description text
        │
        ├──► matcher.py
        │         ├── Stage 1: Groq (qwen-qwq-32b) ── Fast relevance score (0.0–1.0)
        │         │              └── score < 0.75 → SKIP (saves Gemini quota)
        │         └── Stage 2: Gemini 2.5 Flash ── Tailor profile JSON to job
        │
        ├──► compiler.py         ── python-docx + OpenXML → ATS-safe .docx
        │
        ├──► notifier.py         ── smtplib → Gmail SMTP → Email with DOCX attachment
        │
        └──► processed_jobs.json ── Git-committed state (prevents re-processing)
```

---

## 📁 File Structure

```
ai-job-search/
├── scraper.py                              # LinkedIn guest API job extraction
├── matcher.py                              # Dual-stage AI screening & profile tailoring
├── compiler.py                             # ATS-optimized DOCX resume compiler
├── notifier.py                             # SMTP email delivery with DOCX attachment
├── core_orchestrator.py                    # Stateful pipeline controller
├── base_profile.json                       # ← YOUR PROFILE — edit this!
├── processed_jobs.json                     # Auto-managed state (do not edit)
├── requirements.txt                        # Pinned Python dependencies
├── output/                                 # Compiled DOCX resumes (auto-created)
└── .github/
    └── workflows/
        ├── resume_agent_scheduler.yml      # Main cron job (weekdays 9 AM UTC)
        └── keep_awake_huggingface.yml      # HuggingFace Space keep-alive (2x/day)
```

---

## ⚙️ How It Works

### Stage 1 — Groq Pre-Screening (Fast & Free)
Every scraped job is scored 0.0–1.0 for relevance against your profile summary using **Groq's** high-throughput free API. Jobs scoring below **0.75** are skipped, conserving Gemini quota. Only the best matches proceed.

### Stage 2 — Gemini Tailoring (Precise & Factual)
For high-scoring jobs, **Gemini 2.5 Flash** rewrites your profile JSON to:
- Lead the summary with your most relevant skills for that specific role
- Transform passive duty descriptions into achievement-oriented bullets
- Align exact keywords from the job description where your experience supports it
- **Never fabricate skills, companies, or metrics not in your original profile**

### ATS-Safe Compilation
`compiler.py` uses `python-docx` with raw OpenXML injection to produce a document that:
- Uses a **strict single-column layout** (no tables, columns, or text boxes)
- Applies **0.75-inch margins** and Calibri/Arial fonts
- Injects **`w:pBdr/w:bottom` XML borders** for section dividers (not images)
- Reads sequentially by ATS parsers — your content won't be scrambled

### Stateful Deduplication
`processed_jobs.json` is **committed back to your repository** after each run. On the next scheduled run, this file is loaded and already-processed job IDs are skipped, preventing duplicate resumes and email spam across GitHub Actions' ephemeral runners.

---

## 🚀 Setup Instructions

### 1. Fork or Clone This Repository
```bash
git clone https://github.com/yourusername/ai-job-search.git
cd ai-job-search
```

### 2. Edit Your Profile
Open `base_profile.json` and replace all placeholder values with your real information:
- `name`, `contact` — your name and contact details
- `summary` — a dense, keyword-rich professional summary (critical for Stage 1 scoring)
- `technical_skills` — grouped by category; only list skills you actually have
- `professional_experience` — real companies, dates, and quantified achievements
- `education`, `certifications`, `projects` — factual information only

> ⚠️ **Important:** The AI is instructed to never add skills or experiences not present in your profile. The quality of your `base_profile.json` directly determines the quality of output resumes.

### 3. Configure GitHub Repository Secrets

Navigate to: **Repository → Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value | Where to Get It |
|---|---|---|
| `GROQ_API_KEY` | Your Groq API key | [console.groq.com](https://console.groq.com/) |
| `GEMINI_API_KEY` | Your Gemini API key | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `SMTP_SENDER_EMAIL` | Your Gmail address | Your Gmail account |
| `SMTP_APP_PASSWORD` | 16-char App Password | See [Gmail App Password Setup](#-gmail-app-password-setup) |
| `SMTP_RECIPIENT_EMAIL` | Where to receive resumes | Any email address |
| `HUGGINGFACE_SPACE_URL` | Your HF Space URL | Optional — your HF Space |

**Optional search configuration secrets:**

| Secret Name | Default | Example |
|---|---|---|
| `SEARCH_KEYWORDS` | `Python Developer,Data Engineer,...` | `"Software Engineer,ML Engineer"` |
| `SEARCH_LOCATION` | `Remote` | `"San Francisco, CA"` |
| `SEARCH_MAX_JOBS` | `50` | `"100"` |

### 4. Enable GitHub Actions
Ensure Actions are enabled: **Repository → Settings → Actions → General → Allow all actions**

### 5. Run Manually to Test
Go to **Actions → 🤖 AI Resume Agent — Daily Job Search → Run workflow** to trigger an immediate test run before waiting for the scheduled cron.

---

## 🔑 API Key Acquisition

### Groq API Key (Free)
1. Visit [console.groq.com](https://console.groq.com/) and sign up
2. Navigate to **API Keys** → **Create API Key**
3. Copy the key (shown only once) — add as `GROQ_API_KEY` secret

**Free tier limits:** 30 requests/minute, 14,400 requests/day — more than sufficient.

### Google Gemini API Key (Free)
1. Visit [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API Key** → select a GCP project (or create one)
3. Copy the key — add as `GEMINI_API_KEY` secret

**Free tier limits:** 15 requests/minute, 1,500 requests/day (Gemini 2.5 Flash).  
The Groq pre-screening filter ensures you'll only use Gemini for 10–20% of scraped jobs.

---

## 📧 Gmail App Password Setup

Standard Gmail passwords are **blocked by Google** for third-party SMTP apps. You must use a 16-character App Password:

1. Ensure **2-Step Verification** is enabled on your Gmail account:  
   [myaccount.google.com/security](https://myaccount.google.com/security)

2. Generate an App Password:  
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Select app: **Mail**
   - Select device: **Other (Custom name)** → type `AI Resume Agent`
   - Click **Generate**

3. Copy the 16-character password (spaces are optional, copy as-is)

4. Add as the `SMTP_APP_PASSWORD` GitHub secret

---

## 🎯 ATS Resume Design Decisions

### Why Single-Column Layout?
ATS (Applicant Tracking Systems) read documents linearly — top to bottom, left to right. Multi-column layouts, text boxes, and table-based formatting cause parsers to read columns out of order, mixing content from different sections. Single-column ensures your experience reads correctly.

### Why OpenXML Borders Instead of Images?
Section dividers created as images are often ignored or incorrectly parsed by ATS. The `w:pBdr` XML approach creates semantic paragraph borders that ATS engines treat as structural separators, not images.

### Why Calibri/Arial?
These fonts are built into the default font tables of all major ATS systems. Unusual fonts either substitute to Times New Roman (changing spacing) or cause character rendering errors.

### Why 0.75-Inch Margins?
Standard margins maximize content density while remaining within professional norms. Narrower margins can cause ATS margin parsers to clip content; wider margins waste space.

---

## ⚙️ Configuration Reference

### Adjusting the Cron Schedule
Edit `.github/workflows/resume_agent_scheduler.yml`:
```yaml
schedule:
  - cron: "0 9 * * 1-5"   # 9:00 AM UTC, Mon-Fri
```
Common alternatives:
- `"0 14 * * 1-5"` — 9:00 AM EST (UTC-5)
- `"0 1 * * 1-5"` — 9:00 AM SGT (UTC+8)
- `"0 9 * * *"` — Daily including weekends

### Adjusting the Relevance Threshold
Edit the `PASS_THRESHOLD` constant in both `matcher.py` and `core_orchestrator.py`:
```python
PASS_THRESHOLD = 0.75   # Increase to 0.85 for stricter filtering
```

### Changing the Groq Model
Edit `matcher.py`:
```python
GROQ_MODEL_PRIMARY = "llama-3.3-70b-versatile"   # More powerful
GROQ_MODEL_PRIMARY = "llama-3.1-8b-instant"       # Faster, lower quota usage
```

---

## 🔧 Troubleshooting

### "No jobs found" on every run
- LinkedIn's guest API may be temporarily rate-limited — wait 24 hours
- Check the runner IP isn't blocked — try different keywords
- Inspect the `orchestrator.log` artifact in Actions for detailed output

### "Stage 2 tailoring returned None"
- Gemini 2.5 Flash may be hitting the 15 RPM free-tier limit
- Reduce `SEARCH_MAX_JOBS` to decrease the number of concurrent API calls
- The orchestrator falls back to the base profile for compilation — resumes still send

### SMTP Authentication Error
- Confirm `SMTP_APP_PASSWORD` is the 16-char App Password, NOT your Gmail password
- Re-generate the App Password if it was accidentally exposed
- Verify 2-Step Verification is still active on your Gmail account

### "processed_jobs.json not committed"
- Ensure the workflow has `permissions: contents: write`
- Check the "Commit Updated State" step logs in Actions for Git errors
- Verify the repository's branch protection rules allow bot commits

### Running Locally
```bash
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="your_groq_key"
export GEMINI_API_KEY="your_gemini_key"
export SMTP_SENDER_EMAIL="you@gmail.com"
export SMTP_APP_PASSWORD="your_app_password"
export SMTP_RECIPIENT_EMAIL="recipient@email.com"

# Optional overrides
export SEARCH_KEYWORDS="Python Developer,Backend Engineer"
export SEARCH_LOCATION="Remote"
export SEARCH_MAX_JOBS="10"   # Lower for local testing

python core_orchestrator.py
```

---

## 📜 License

MIT — Free for personal and commercial use.

---

> **Ethical Note:** This tool queries LinkedIn's publicly-indexed guest API endpoints — the same surfaces crawled by search engines. All scraping includes randomized delays to avoid rate limit abuse. Use responsibly and in accordance with LinkedIn's Terms of Service.
