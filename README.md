# 🤖 AI Job Search Agent

> **Clone → Deploy → Fill your profile → Get 10 tailored CVs in your Google Sheet every day. Fully automated. Completely free.**

[![GitHub Actions](https://img.shields.io/badge/Scheduler-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Vercel](https://img.shields.io/badge/Dashboard-Vercel-000000?logo=vercel&logoColor=white)](https://vercel.com)
[![Groq](https://img.shields.io/badge/Stage%201-Groq%20AI-F55036?logoColor=white)](https://console.groq.com/)
[![Gemini](https://img.shields.io/badge/Stage%202-Gemini%202.5%20Flash-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## What It Does

Every weekday at 9 AM UTC, the agent automatically:

1. 🔍 **Searches LinkedIn** for jobs posted in the last 24 hours using your keywords
2. 🧠 **Screens with Groq AI** — scores each job 0–100% against your profile
3. ✂️ **Skips low-match jobs** — only processes jobs above your threshold (default 80%)
4. ✨ **Tailors your CV with Gemini** — rewrites your summary & skills to match each job exactly
5. 📄 **Compiles an ATS-safe DOCX resume** — single-column, no tables, Calibri font
6. 📊 **Logs everything to Google Sheets** — job title, company, AI score, rationale, CV link
7. 🔁 **Never repeats jobs** — tracks applied job IDs so you always get fresh listings

---

## Quick Start (5 Minutes)

### Step 1 — Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/ai-job-search.git
cd ai-job-search
```

### Step 2 — Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/YOUR_USERNAME/ai-job-search)

Or manually:
```bash
npm i -g vercel
vercel --prod
```

### Step 3 — Get Your Free API Keys

| Key | Where to Get | Free Limit |
|-----|-------------|-----------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/) → API Keys | 14,400 req/day |
| `GEMINI_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | 1,500 req/day |

### Step 4 — Set Up Google Sheets Output

1. Create a new [Google Sheet](https://sheets.new)
2. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/`**`YOUR_SHEET_ID`**`/edit`
3. Open **Extensions → Apps Script**, paste this webhook code and deploy as web app:

```javascript
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.openById(data.sheet_id).getSheets()[0];
    if (data.row) sheet.appendRow(data.row);
    return ContentService.createTextOutput(JSON.stringify({status:"ok"}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService.createTextOutput(JSON.stringify({status:"error",msg:err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```
4. **Deploy → New deployment → Web app → Execute as: Me → Who has access: Anyone** → Copy the web app URL

### Step 5 — Add Environment Variables to Vercel

In your Vercel project → **Settings → Environment Variables**, add:

| Variable | Value |
|----------|-------|
| `GROQ_API_KEY` | Your Groq key |
| `GEMINI_API_KEY` | Your Gemini key |
| `GOOGLE_SHEET_ID` | Your Sheet ID |
| `GOOGLE_SHEETS_WEBHOOK_URL` | Your Apps Script web app URL |
| `USER_PROFILE_JSON` | *(generated in Step 6)* |

### Step 6 — Fill Your Profile

1. Visit your deployed Vercel URL
2. You'll see the **Setup Wizard** — it walks you through:
   - ✅ API key status check
   - 👤 Personal info (name, email, LinkedIn, GitHub)
   - 💼 Professional summary & technical skills
   - 🚀 Your projects
   - 🔍 Job keywords & search settings
3. Click **"Generate My Profile JSON"**
4. Copy the generated JSON
5. Add it as `USER_PROFILE_JSON` in Vercel Environment Variables
6. Redeploy → visit your URL → you now see your **personalized dashboard** ✅

### Step 7 — Set Up GitHub Actions (for daily automation)

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|--------|-------|
| `GROQ_API_KEY` | Your Groq key |
| `GEMINI_API_KEY` | Your Gemini key |
| `GOOGLE_SHEETS_WEBHOOK_URL` | Your Apps Script web app URL |
| `GOOGLE_SHEET_ID` | Your Sheet ID |
| `USER_PROFILE_JSON` | Same JSON from Step 6 |

The agent runs **automatically Mon–Fri at 9:00 AM UTC**. To test immediately:
**Actions → 🤖 AI Resume Agent — Daily Job Search → Run workflow**

---

## Architecture

```
GitHub Actions (cron: Mon-Fri 9 AM UTC)
        │
        ▼
core_orchestrator.py
        │
        ├── Reads YOUR profile from USER_PROFILE_JSON env var (never from repo)
        │
        ├──► scraper.py
        │       └── LinkedIn Guest API (no auth) — 24h posts only — 6 keywords
        │
        ├──► matcher.py
        │       ├── Stage 1: Groq AI — relevance score 0.0–1.0 (fast, free)
        │       │              └── score < threshold → SKIP
        │       └── Stage 2: Gemini 2.5 Flash — tailor profile JSON to job
        │
        ├──► compiler.py — python-docx + OpenXML → ATS-safe .docx resume
        │
        └──► reporter.py — append row to YOUR Google Sheet via webhook
```

**Dashboard** (Vercel): Status page + manual trigger. Runs in the browser.  
**Scheduler** (GitHub Actions): Full pipeline with no time limits.

> ⚠️ Vercel has a 60-second execution limit. Use GitHub Actions for the full automated pipeline.

---

## Privacy & Data Safety

| Data | Stored Where | In Git Repo? |
|------|-------------|-------------|
| Your name, email, skills | `USER_PROFILE_JSON` Vercel env var | ❌ Never |
| Applied job IDs | `processed_jobs.json` (local only) | ❌ Gitignored |
| Job history | `job_tracker.xlsx` (local only) | ❌ Gitignored |
| API keys | Vercel env vars / GitHub Secrets | ❌ Never |
| Compiled CVs | Temp files, deleted after upload | ❌ Never |

**The Git repository contains zero personal data.** Every user's profile, job history and credentials stay in their own private environment.

---

## Configuration Reference

### Job Search Settings (inside your profile JSON `_agent_config`)

| Field | Default | Description |
|-------|---------|-------------|
| `search_keywords` | — | List of job titles to search |
| `search_location` | `"Remote"` | Location filter |
| `daily_job_limit` | `10` | Max unique jobs per run |
| `pass_threshold` | `0.80` | Min AI score to compile CV (0.0–1.0) |

### Changing the Schedule

Edit `.github/workflows/resume_agent_scheduler.yml`:
```yaml
- cron: "0 9 * * 1-5"    # 9 AM UTC, Mon–Fri (default)
- cron: "0 14 * * 1-5"   # 9 AM EST (UTC−5)
- cron: "0 2 * * 1-5"    # 9 AM ICT (UTC+7)
- cron: "0 3 * * 1-5"    # 9 AM WIB (UTC+7) / Bangladesh (UTC+6) → 0 3
- cron: "0 9 * * *"      # Daily including weekends
```

### AI Models Used

| Stage | Model | Purpose |
|-------|-------|---------|
| Screening | `llama-3.3-70b-versatile` (Groq) | Score job relevance |
| Tailoring | `gemini-2.5-flash` (Google) | Rewrite CV for each job |
| Fallback | `llama-3.1-8b-instant` (Groq) | Tailoring if Gemini quota exceeded |

---

## ATS Resume Design

The compiled `.docx` is optimized for Applicant Tracking Systems:

- **Single-column layout** — ATS reads top-to-bottom; multi-column scrambles content
- **Calibri font** — universally in ATS font tables; no substitution errors  
- **OpenXML borders** (`w:pBdr`) — semantic dividers, not images
- **0.75-inch margins** — max content density within professional standards
- **No tables, text boxes, or images** — anything that confuses ATS parsers is excluded

---

## File Structure

```
ai-job-search/
├── api/
│   └── index.py              # Vercel dashboard + onboarding wizard
├── .github/
│   └── workflows/
│       └── resume_agent_scheduler.yml   # GitHub Actions cron
├── scraper.py                # LinkedIn guest API scraper (24h filter)
├── matcher.py                # Dual-stage AI screening & CV tailoring
├── compiler.py               # ATS-optimized DOCX compiler
├── pdf_compiler.py           # PDF version compiler
├── reporter.py               # Google Sheets + Excel logging
├── core_orchestrator.py      # Main pipeline controller
├── base_profile.json         # Blank template (your data lives in env var)
├── processed_jobs.json       # Applied job IDs (gitignored, local only)
├── requirements.txt          # Python dependencies
├── vercel.json               # Vercel routing config
├── .env.example              # Environment variable template
└── .gitignore                # Protects all personal data from Git
```

---

## Troubleshooting

**"No profile configured" error**  
→ Add `USER_PROFILE_JSON` to your Vercel/GitHub environment variables. Visit `/setup` on your dashboard.

**"No jobs found" on every run**  
→ LinkedIn's guest API gets rate-limited by IP. GitHub Actions uses rotating IPs — works better than local. Try different keywords.

**"Stage 2 tailoring returned None"**  
→ Gemini free tier (15 req/min) hit. The agent automatically falls back to Groq for tailoring — CVs still compile.

**Google Sheet not updating**  
→ Check the webhook URL is correct and the Apps Script is deployed as "Anyone can access". Re-deploy the Apps Script if needed.

**Running locally**
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your real keys and USER_PROFILE_JSON
python core_orchestrator.py
```

---

## License

MIT — Free for personal and commercial use.

---

> **Ethical note:** This tool queries LinkedIn's publicly-indexed guest API — the same endpoints crawled by search engines like Google. All requests include randomized delays to avoid rate-limit abuse. Use responsibly and in accordance with LinkedIn's Terms of Service.
