"""
api/index.py
============
Vercel Serverless Web Dashboard & Control Hub for AI Resume Agent
------------------------------------------------------------------
Serves a modern web UI and API endpoints to trigger daily job searches,
monitor live agent activity, and auto-sync to Google Sheets from anywhere.
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
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.3);
            --text: #f8fafc;
            --text-sub: #94a3b8;
            --success: #4ade80;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; }

        body {
            background-color: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            background-image: radial-gradient(circle at 50% 0%, #1e293b 0%, #0f172a 75%);
        }

        .container {
            width: 100%;
            max-width: 850px;
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), 0 0 40px var(--accent-glow);
        }

        .header {
            text-align: center;
            margin-bottom: 35px;
        }

        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }

        .header p { color: var(--text-sub); font-size: 1.1rem; }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            border-radius: 20px;
            background: rgba(74, 222, 128, 0.1);
            border: 1px solid rgba(74, 222, 128, 0.3);
            color: var(--success);
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 15px;
        }

        .pulse-dot {
            width: 8px; height: 8px; background-color: var(--success);
            border-radius: 50%; box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 35px;
        }

        .card {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
        }

        .card h3 { font-size: 0.9rem; color: var(--text-sub); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .card p { font-size: 1.2rem; font-weight: 600; }
        .card a { color: var(--accent); text-decoration: none; word-break: break-all; font-size: 0.95rem; }
        .card a:hover { text-decoration: underline; }

        .action-area {
            text-align: center;
        }

        .btn {
            background: linear-gradient(135deg, #0284c7 0%, #4f46e5 100%);
            color: white;
            border: none;
            padding: 16px 40px;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 10px 25px rgba(2, 132, 199, 0.4);
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 35px rgba(2, 132, 199, 0.6);
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .console {
            margin-top: 30px;
            background: #090d16;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 14px;
            padding: 20px;
            font-family: monospace;
            font-size: 0.9rem;
            color: #38bdf8;
            max-height: 250px;
            overflow-y: auto;
            text-align: left;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Resume & Job Agent</h1>
            <p>Automated LinkedIn Search & ATS Tailoring System</p>
            <div class="status-badge">
                <div class="pulse-dot"></div> System Active & Vercel Ready
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Candidate Profile</h3>
                <p>Mahathir Mohammad</p>
                <span style="font-size: 0.85rem; color: #94a3b8;">Full Stack Web Developer (MERN)</span>
            </div>
            <div class="card">
                <h3>Target Daily Jobs</h3>
                <p>15 Unique Jobs / Day</p>
                <span style="font-size: 0.85rem; color: #94a3b8;">Full Stack, Junior, MERN, React</span>
            </div>
            <div class="card">
                <h3>Google Sheet Output</h3>
                <a href="https://docs.google.com/spreadsheets/d/1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI/edit" target="_blank">Open Live Tracker ↗</a>
            </div>
        </div>

        <div class="action-area">
            <button class="btn" id="runBtn" onclick="triggerAgent()">
                🚀 Run Agent Search Now (15 Jobs)
            </button>
            <div class="console" id="console"></div>
        </div>
    </div>

    <script>
        async function triggerAgent() {
            const btn = document.getElementById('runBtn');
            const consoleBox = document.getElementById('console');
            
            btn.disabled = true;
            btn.innerHTML = '⚡ Processing Jobs & Syncing Google Sheets...';
            consoleBox.style.display = 'block';
            consoleBox.innerHTML = '> Starting pipeline execution...\\n';

            try {
                const res = await fetch('/api/run', { method: 'POST' });
                const data = await res.json();
                consoleBox.innerHTML += '> Execution Finished! Status: ' + data.status + '\\n';
                consoleBox.innerHTML += '> Summary: ' + JSON.stringify(data.summary, null, 2) + '\\n';
            } catch (err) {
                consoleBox.innerHTML += '> Error: ' + err.message + '\\n';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🚀 Run Agent Search Now (15 Jobs)';
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
        "google_sheet_id": "1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI"
    })

@app.route("/api/cron", methods=["GET"])
@app.route("/api/run", methods=["POST", "GET"])
def run():
    try:
        from core_orchestrator import run_pipeline
        summary = run_pipeline()
        return jsonify({"status": "success", "summary": summary})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
