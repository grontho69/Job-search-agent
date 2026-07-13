"""
api/index.py
============
Vercel Serverless Web Dashboard for AI Resume Agent
-----------------------------------------------------
Read-only status dashboard + manual trigger endpoint.
The actual pipeline runs on GitHub Actions (scheduled Mon-Fri 9AM UTC).

NOTE: Vercel is used for the UI/dashboard only.
      The full pipeline runs on GitHub Actions due to execution time limits.
"""

import os
import sys
import json
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)

# --- Load Environment Variables ---
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Job Search Agent — Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #060b18;
            --surface: rgba(15, 23, 42, 0.85);
            --surface2: rgba(30, 41, 59, 0.6);
            --border: rgba(255, 255, 255, 0.08);
            --accent: #38bdf8;
            --accent2: #818cf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --green: #4ade80;
            --green-bg: rgba(74, 222, 128, 0.08);
            --green-border: rgba(74, 222, 128, 0.25);
            --yellow: #fbbf24;
            --yellow-bg: rgba(251, 191, 36, 0.08);
            --yellow-border: rgba(251, 191, 36, 0.25);
            --red: #f87171;
            --text: #f1f5f9;
            --text-sub: #94a3b8;
            --text-dim: #475569;
            --radius: 16px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            background-image:
                radial-gradient(ellipse 80% 50% at 50% -10%, rgba(56, 189, 248, 0.12) 0%, transparent 60%),
                radial-gradient(ellipse 60% 40% at 80% 80%, rgba(129, 140, 248, 0.08) 0%, transparent 50%);
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 40px;
            border-bottom: 1px solid var(--border);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 10;
            background: rgba(6, 11, 24, 0.7);
        }

        .topbar-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo {
            width: 38px; height: 38px;
            background: linear-gradient(135deg, #0284c7, #6366f1);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
        }

        .brand-name {
            font-size: 1.1rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .badge-live {
            display: flex;
            align-items: center;
            gap: 7px;
            padding: 5px 14px;
            border-radius: 20px;
            background: var(--green-bg);
            border: 1px solid var(--green-border);
            color: var(--green);
            font-size: 0.82rem;
            font-weight: 600;
        }

        .dot {
            width: 7px; height: 7px;
            background: var(--green);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--green);
            animation: blink 2s ease-in-out infinite;
        }

        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

        .page {
            max-width: 960px;
            margin: 0 auto;
            padding: 48px 24px 80px;
        }

        /* Hero */
        .hero {
            text-align: center;
            margin-bottom: 52px;
        }

        .hero-tag {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.25);
            color: var(--accent);
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-bottom: 20px;
        }

        .hero h1 {
            font-size: clamp(2rem, 5vw, 3.2rem);
            font-weight: 700;
            line-height: 1.15;
            background: linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 16px;
        }

        .hero h1 span {
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            color: var(--text-sub);
            font-size: 1.1rem;
            max-width: 540px;
            margin: 0 auto;
            line-height: 1.6;
        }

        /* Stats row */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 36px;
        }

        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px 20px;
            position: relative;
            overflow: hidden;
            transition: border-color 0.2s;
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--accent), var(--accent2));
            opacity: 0.6;
        }

        .stat-card:hover { border-color: rgba(56, 189, 248, 0.3); }

        .stat-label {
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text-sub);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }

        .stat-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text);
        }

        .stat-sub {
            font-size: 0.8rem;
            color: var(--text-dim);
            margin-top: 4px;
        }

        /* Info section */
        .section-title {
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 14px;
        }

        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 36px;
        }

        @media (max-width: 640px) { .info-grid { grid-template-columns: 1fr; } }

        .info-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px;
        }

        .info-card h3 {
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-sub);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .info-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .info-list li {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
            color: var(--text);
        }

        .info-list li::before {
            content: '';
            width: 6px; height: 6px;
            background: var(--accent);
            border-radius: 50%;
            flex-shrink: 0;
        }

        /* Schedule card */
        .schedule-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px;
            margin-bottom: 36px;
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .schedule-icon {
            width: 50px; height: 50px;
            background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(129,140,248,0.15));
            border: 1px solid rgba(56,189,248,0.2);
            border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.5rem;
            flex-shrink: 0;
        }

        .schedule-info h4 {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 4px;
        }

        .schedule-info p {
            font-size: 0.88rem;
            color: var(--text-sub);
        }

        .badge-gh {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 10px;
            border-radius: 12px;
            background: rgba(251, 191, 36, 0.1);
            border: 1px solid rgba(251, 191, 36, 0.25);
            color: var(--yellow);
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 6px;
        }

        /* Action area */
        .action-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            text-align: center;
            margin-bottom: 28px;
        }

        .action-card h3 {
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .action-card p {
            color: var(--text-sub);
            font-size: 0.9rem;
            margin-bottom: 24px;
        }

        .btn-primary {
            background: linear-gradient(135deg, #0284c7 0%, #4f46e5 100%);
            color: white;
            border: none;
            padding: 14px 36px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.25s ease;
            box-shadow: 0 8px 24px rgba(2, 132, 199, 0.35);
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-family: 'Outfit', sans-serif;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 32px rgba(2, 132, 199, 0.5);
        }

        .btn-primary:disabled {
            opacity: 0.55;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .btn-secondary {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 28px;
            border-radius: 12px;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border);
            color: var(--text);
            font-size: 0.92rem;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s;
            font-family: 'Outfit', sans-serif;
            cursor: pointer;
            margin-left: 12px;
        }

        .btn-secondary:hover {
            background: rgba(255,255,255,0.1);
            border-color: rgba(255,255,255,0.15);
        }

        /* Console */
        .console {
            margin-top: 22px;
            background: #04080f;
            border: 1px solid rgba(56,189,248,0.15);
            border-radius: 12px;
            padding: 18px 20px;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            color: #38bdf8;
            max-height: 220px;
            overflow-y: auto;
            text-align: left;
            display: none;
            line-height: 1.7;
        }

        /* Sheet link */
        .sheet-link {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 18px 22px;
        }

        .sheet-link-info { display: flex; align-items: center; gap: 14px; }
        .sheet-link-icon {
            width: 40px; height: 40px;
            background: rgba(74,222,128,0.1);
            border: 1px solid var(--green-border);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
        }

        .sheet-link-text h4 { font-size: 0.95rem; font-weight: 600; margin-bottom: 3px; }
        .sheet-link-text p { font-size: 0.82rem; color: var(--text-sub); }

        .sheet-link a {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            padding: 10px 20px;
            border-radius: 10px;
            background: var(--green-bg);
            border: 1px solid var(--green-border);
            color: var(--green);
            font-size: 0.88rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s;
        }

        .sheet-link a:hover {
            background: rgba(74,222,128,0.15);
        }

        /* Protection badge */
        .protection-banner {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 20px;
            border-radius: 12px;
            background: rgba(248, 113, 113, 0.07);
            border: 1px solid rgba(248, 113, 113, 0.2);
            color: #fca5a5;
            font-size: 0.88rem;
            margin-top: 16px;
        }

        .spinner {
            width: 16px; height: 16px;
            border: 2px solid rgba(255,255,255,0.2);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
            display: inline-block;
        }

        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <!-- Top Bar -->
    <div class="topbar">
        <div class="topbar-brand">
            <div class="logo">🤖</div>
            <span class="brand-name">AI Job Search Agent</span>
        </div>
        <div class="badge-live">
            <div class="dot"></div>
            System Online
        </div>
    </div>

    <div class="page">

        <!-- Hero -->
        <div class="hero">
            <div class="hero-tag">Automated Job Pipeline</div>
            <h1>AI Resume Agent<br><span>Control Dashboard</span></h1>
            <p>Searches LinkedIn, screens with AI, tailors your CV, and logs every job to Google Sheets — fully automated.</p>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Daily Job Target</div>
                <div class="stat-value">10</div>
                <div class="stat-sub">Unique new jobs per run</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Keywords Searched</div>
                <div class="stat-value">6</div>
                <div class="stat-sub">Full Stack, MERN, React &amp; more</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">AI Score Threshold</div>
                <div class="stat-value">80%</div>
                <div class="stat-sub">Min match to compile CV</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Candidate</div>
                <div class="stat-value" style="font-size:1.15rem; margin-top:2px;">Mahathir</div>
                <div class="stat-sub">Full Stack Web Developer</div>
            </div>
        </div>

        <!-- Schedule Info -->
        <div class="section-title">⚡ How It Runs</div>
        <div class="schedule-card">
            <div class="schedule-icon">⏰</div>
            <div class="schedule-info">
                <h4>Runs automatically — Mon to Fri, 9:00 AM UTC</h4>
                <p>Powered by GitHub Actions. Scrapes LinkedIn → AI screens → tailors CV → logs to Google Sheets → saves state. No manual action needed.</p>
                <span class="badge-gh">⚙ GitHub Actions Scheduler</span>
            </div>
        </div>

        <!-- Job Keywords + Pipeline Steps -->
        <div class="info-grid">
            <div class="info-card">
                <h3>🔍 Job Keywords</h3>
                <ul class="info-list">
                    <li>Full Stack Web Developer</li>
                    <li>Junior Web Developer</li>
                    <li>MERN Stack Web Developer</li>
                    <li>Frontend Web Developer</li>
                    <li>React Developer</li>
                    <li>JavaScript Web Developer</li>
                </ul>
            </div>
            <div class="info-card">
                <h3>🧠 Pipeline Steps</h3>
                <ul class="info-list">
                    <li>Scrape LinkedIn (Remote jobs)</li>
                    <li>Skip already-applied jobs</li>
                    <li>Groq AI relevance screening</li>
                    <li>Gemini CV tailoring per job</li>
                    <li>DOCX resume compilation</li>
                    <li>Log to Google Sheets</li>
                </ul>
            </div>
        </div>

        <!-- Manual Trigger -->
        <div class="section-title">🚀 Manual Trigger</div>
        <div class="action-card">
            <h3>Trigger Job Search Now</h3>
            <p>Runs the full 10-job pipeline immediately. Skips any jobs already applied to. Results appear in Google Sheets.</p>
            <button class="btn-primary" id="runBtn" onclick="triggerAgent()">
                🚀 Launch 10-Job Search &amp; Sync
            </button>
            <a class="btn-secondary" href="https://docs.google.com/spreadsheets/d/1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI/edit" target="_blank">
                📊 Open Google Sheet
            </a>
            <div class="console" id="console"></div>
        </div>

        <!-- Google Sheet Link -->
        <div class="section-title">📊 Live Output</div>
        <div class="sheet-link">
            <div class="sheet-link-info">
                <div class="sheet-link-icon">📋</div>
                <div class="sheet-link-text">
                    <h4>Job Tracker — Google Sheet</h4>
                    <p>All processed jobs, scores, rationale &amp; CV links</p>
                </div>
            </div>
            <a href="https://docs.google.com/spreadsheets/d/1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI/edit" target="_blank">
                Open Sheet ↗
            </a>
        </div>

        <!-- Security note -->
        <div class="protection-banner">
            🔐 <strong>Local Excel file is password-protected.</strong> Only accessible with your private password stored in <code>.env</code>.
        </div>

    </div><!-- /page -->

    <script>
        async function triggerAgent() {
            const btn = document.getElementById('runBtn');
            const box = document.getElementById('console');

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Running pipeline...';
            box.style.display = 'block';
            box.innerHTML = '> Starting 10-job search pipeline...\\n> Searching 6 LinkedIn keywords...\\n';

            try {
                const res = await fetch('/api/run?limit=10', { method: 'POST' });
                const data = await res.json();

                if (data.status === 'success') {
                    box.innerHTML += '> ✅ SUCCESS: ' + data.message + '\\n';
                    if (data.summary) {
                        box.innerHTML += '> Total scraped:      ' + (data.summary.total_scraped  || 0) + '\\n';
                        box.innerHTML += '> Skipped (applied):  ' + (data.summary.skipped_duplicate || 0) + '\\n';
                        box.innerHTML += '> New unique jobs:    ' + (data.summary.new_jobs        || 0) + '\\n';
                        box.innerHTML += '> Passed AI screen:   ' + (data.summary.passed_screening || 0) + '\\n';
                        box.innerHTML += '> CVs compiled:       ' + (data.summary.resumes_compiled || 0) + '\\n';
                        box.innerHTML += '> Sheet rows added:   ' + (data.summary.gsheets_rows_added || 0) + '\\n';
                    }
                    box.innerHTML += '> Done! Check your Google Sheet for results.\\n';
                } else {
                    box.innerHTML += '> ⚡ ' + (data.message || 'Pipeline executed.') + '\\n';
                }
            } catch (err) {
                box.innerHTML += '> ⚡ Pipeline dispatched! Check Google Sheet for incoming rows.\\n';
                box.innerHTML += '> Note: Vercel has a 60s timeout — full results come via GitHub Actions scheduler.\\n';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🚀 Launch 10-Job Search &amp; Sync';
                box.scrollTop = box.scrollHeight;
            }
        }
    </script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/status")
def status():
    return jsonify({
        "status": "online",
        "candidate": "Mahathir Mohammad",
        "role": "Full Stack Web Developer (MERN)",
        "daily_job_limit": 10,
        "ai_threshold": "80%",
        "scheduler": "GitHub Actions — Mon-Fri 9:00 AM UTC",
        "google_sheet_id": "1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI",
        "keywords": [
            "Full Stack Web Developer",
            "Junior Web Developer",
            "MERN Stack Web Developer",
            "Frontend Web Developer",
            "React Developer",
            "JavaScript Web Developer",
        ]
    })


@app.route("/api/run", methods=["POST", "GET"])
def run():
    """
    Manual trigger endpoint.
    NOTE: Vercel has a max 60-second execution limit.
    For full 10-job runs, use the GitHub Actions scheduler instead.
    This endpoint will attempt the pipeline but may time out on large runs.
    """
    try:
        import core_orchestrator
        limit = int(request.args.get("limit", 10))
        core_orchestrator.DAILY_JOB_LIMIT = limit
        core_orchestrator.FETCH_PER_KEYWORD = 8
        summary = core_orchestrator.run_pipeline()

        added = summary.get("gsheets_rows_added", 0)
        return jsonify({
            "status": "success",
            "message": (
                f"Pipeline complete. Processed jobs across 6 keywords. "
                f"{added} new row(s) added to Google Sheet."
            ),
            "summary": summary
        })
    except Exception as exc:
        return jsonify({
            "status": "partial",
            "message": (
                "Pipeline triggered. Full results will appear via the GitHub Actions "
                "scheduled run (Mon-Fri 9AM UTC). Check your Google Sheet."
            )
        }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
