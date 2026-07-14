"""
api/index.py
============
AI Job Search Agent — Public Web Dashboard & Onboarding Wizard
---------------------------------------------------------------
Anyone can clone this repo, deploy to Vercel, set env vars,
then fill out the onboarding wizard to configure their own profile.

Routes:
  GET  /           → Dashboard (if profile set) or Onboarding wizard
  GET  /setup      → Onboarding wizard (always)
  POST /api/save-profile  → Save profile to session / return env var JSON
  GET  /api/load-profile  → Return current profile from env var
  POST /api/run    → Trigger job search pipeline
  GET  /api/status → System status JSON
"""

import os
import sys
import json
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string, session

sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "ai-job-agent-secret-2025")

# --- Load .env for local development ---
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _get_profile() -> dict | None:
    """Load user profile from USER_PROFILE_JSON env var."""
    raw = os.environ.get("USER_PROFILE_JSON", "")
    if not raw:
        # fallback: try base_profile.json
        bp = Path(__file__).parent.parent / "base_profile.json"
        if bp.exists():
            try:
                with open(bp, encoding="utf-8") as f:
                    data = json.load(f)
                # Only return if it looks like a real profile (not the template)
                if data.get("name") and data["name"] != "Your Full Name":
                    return data
            except Exception:
                pass
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _has_api_keys() -> dict:
    return {
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        "google_sheet": bool(os.environ.get("GOOGLE_SHEET_ID") or os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL")),
    }


# ============================================================
# TEMPLATES
# ============================================================

SETUP_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Setup — AI Job Search Agent</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#060b18;--surface:rgba(15,23,42,0.9);--surface2:rgba(30,41,59,0.6);
  --border:rgba(255,255,255,0.08);--accent:#38bdf8;--accent2:#818cf8;
  --green:#4ade80;--green-bg:rgba(74,222,128,0.08);--green-border:rgba(74,222,128,0.25);
  --yellow:#fbbf24;--red:#f87171;--text:#f1f5f9;--text-sub:#94a3b8;--text-dim:#475569;
  --r:14px;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;
  background-image:radial-gradient(ellipse 80% 50% at 50% -10%,rgba(56,189,248,0.1) 0%,transparent 60%),
  radial-gradient(ellipse 50% 40% at 85% 85%,rgba(129,140,248,0.07) 0%,transparent 50%);}

/* ── Layout ── */
.page{max-width:780px;margin:0 auto;padding:48px 20px 80px;}

/* ── Hero ── */
.hero{text-align:center;margin-bottom:44px;}
.hero-tag{display:inline-block;padding:4px 14px;border-radius:20px;
  background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.25);
  color:var(--accent);font-size:.78rem;font-weight:600;letter-spacing:1.5px;
  text-transform:uppercase;margin-bottom:18px;}
.hero h1{font-size:clamp(1.8rem,4vw,2.6rem);font-weight:700;line-height:1.2;
  background:linear-gradient(135deg,#f1f5f9 0%,#94a3b8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px;}
.hero h1 span{background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hero p{color:var(--text-sub);font-size:1rem;line-height:1.6;max-width:520px;margin:0 auto;}

/* ── Progress bar ── */
.progress-bar{display:flex;align-items:center;justify-content:center;gap:0;margin-bottom:40px;}
.step-dot{width:32px;height:32px;border-radius:50%;border:2px solid var(--border);
  background:var(--surface);display:flex;align-items:center;justify-content:center;
  font-size:.78rem;font-weight:700;color:var(--text-dim);transition:all .3s;cursor:default;position:relative;z-index:1;}
.step-dot.active{border-color:var(--accent);color:var(--accent);background:rgba(56,189,248,0.1);}
.step-dot.done{border-color:var(--green);background:var(--green-bg);color:var(--green);}
.step-line{flex:1;height:2px;background:var(--border);max-width:60px;transition:background .3s;}
.step-line.done{background:var(--green);}

/* ── Card ── */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:32px;margin-bottom:20px;}
.card-title{font-size:1.1rem;font-weight:700;margin-bottom:6px;display:flex;align-items:center;gap:10px;}
.card-sub{font-size:.88rem;color:var(--text-sub);margin-bottom:24px;}

/* ── Form elements ── */
.field{margin-bottom:18px;}
.field label{display:block;font-size:.82rem;font-weight:600;color:var(--text-sub);
  text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px;}
.field input,.field textarea,.field select{
  width:100%;background:rgba(15,23,42,0.8);border:1px solid var(--border);
  border-radius:10px;padding:11px 14px;color:var(--text);font-family:'Outfit',sans-serif;
  font-size:.92rem;outline:none;transition:border-color .2s;}
.field input:focus,.field textarea:focus,.field select:focus{border-color:rgba(56,189,248,0.5);}
.field textarea{resize:vertical;min-height:90px;}
.field small{font-size:.78rem;color:var(--text-dim);margin-top:5px;display:block;}
.row-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
@media(max-width:560px){.row-2{grid-template-columns:1fr;}}

/* ── Skills grid ── */
.skills-cat{margin-bottom:20px;}
.skills-cat-label{font-size:.82rem;font-weight:600;color:var(--accent);margin-bottom:8px;
  text-transform:uppercase;letter-spacing:.8px;}

/* ── Project block ── */
.project-block{background:rgba(15,23,42,0.6);border:1px solid var(--border);
  border-radius:10px;padding:20px;margin-bottom:16px;}
.project-number{font-size:.78rem;font-weight:700;color:var(--accent2);
  text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;}

/* ── Keyword tags ── */
.tag-input-wrap{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  background:rgba(15,23,42,0.8);border:1px solid var(--border);border-radius:10px;
  padding:8px 12px;min-height:46px;}
.tag{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;
  background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.25);
  border-radius:20px;font-size:.82rem;color:var(--accent);}
.tag button{background:none;border:none;color:var(--accent);cursor:pointer;
  padding:0;line-height:1;font-size:.9rem;}
.tag-input{background:transparent;border:none;outline:none;color:var(--text);
  font-family:'Outfit',sans-serif;font-size:.88rem;min-width:140px;flex:1;}

/* ── Status checks ── */
.check-list{display:flex;flex-direction:column;gap:10px;}
.check-item{display:flex;align-items:center;gap:12px;padding:12px 16px;
  border-radius:10px;border:1px solid var(--border);background:rgba(15,23,42,0.5);}
.check-item.ok{border-color:var(--green-border);background:var(--green-bg);}
.check-item.fail{border-color:rgba(248,113,113,.25);background:rgba(248,113,113,.06);}
.check-icon{font-size:1.1rem;flex-shrink:0;}
.check-text h4{font-size:.9rem;font-weight:600;}
.check-text p{font-size:.8rem;color:var(--text-sub);}

/* ── Buttons ── */
.btn-row{display:flex;gap:12px;justify-content:space-between;margin-top:28px;}
.btn-primary{background:linear-gradient(135deg,#0284c7 0%,#4f46e5 100%);color:#fff;
  border:none;padding:13px 32px;font-size:.95rem;font-weight:600;border-radius:11px;
  cursor:pointer;transition:all .25s;box-shadow:0 6px 20px rgba(2,132,199,.3);
  font-family:'Outfit',sans-serif;display:inline-flex;align-items:center;gap:8px;}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 10px 28px rgba(2,132,199,.45);}
.btn-secondary{background:rgba(255,255,255,.05);border:1px solid var(--border);
  color:var(--text);padding:13px 24px;font-size:.95rem;font-weight:500;border-radius:11px;
  cursor:pointer;transition:all .2s;font-family:'Outfit',sans-serif;}
.btn-secondary:hover{background:rgba(255,255,255,.1);}

/* ── JSON output box ── */
.json-box{background:#04080f;border:1px solid rgba(56,189,248,.15);border-radius:12px;
  padding:20px;font-family:'Courier New',monospace;font-size:.78rem;color:#38bdf8;
  max-height:300px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;}

/* ── Alert ── */
.alert{padding:12px 16px;border-radius:10px;font-size:.88rem;margin-bottom:16px;}
.alert-info{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);color:#7dd3fc;}
.alert-warn{background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.2);color:#fde68a;}

/* ── Step panels ── */
.step-panel{display:none;animation:fadeIn .35s ease;}
.step-panel.active{display:block;}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── Copy button ── */
.copy-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;
  border-radius:8px;background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.2);
  color:var(--accent);font-size:.82rem;font-weight:600;cursor:pointer;
  font-family:'Outfit',sans-serif;transition:all .2s;margin-top:12px;}
.copy-btn:hover{background:rgba(56,189,248,.18);}
</style>
</head>
<body>
<div class="page">

  <!-- Hero -->
  <div class="hero">
    <div class="hero-tag">🚀 First-Time Setup</div>
    <h1>Set Up Your<br><span>AI Job Agent</span></h1>
    <p>Takes 3 minutes. Enter your profile details and job preferences — the agent handles everything else automatically.</p>
  </div>

  <!-- Progress -->
  <div class="progress-bar">
    <div class="step-dot active" id="dot-1">1</div>
    <div class="step-line" id="line-1"></div>
    <div class="step-dot" id="dot-2">2</div>
    <div class="step-line" id="line-2"></div>
    <div class="step-dot" id="dot-3">3</div>
    <div class="step-line" id="line-3"></div>
    <div class="step-dot" id="dot-4">4</div>
    <div class="step-line" id="line-4"></div>
    <div class="step-dot" id="dot-5">5</div>
  </div>

  <!-- ─── STEP 1: API Keys Check ─── -->
  <div class="step-panel active" id="step-1">
    <div class="card">
      <div class="card-title">🔑 API Keys Check</div>
      <div class="card-sub">These keys must be set as environment variables in Vercel before continuing.</div>
      <div class="check-list">
        <div class="check-item {{ 'ok' if keys.groq else 'fail' }}">
          <span class="check-icon">{{ '✅' if keys.groq else '❌' }}</span>
          <div class="check-text">
            <h4>GROQ_API_KEY {{ '— Set ✓' if keys.groq else '— Missing' }}</h4>
            <p>{{ 'Detected.' if keys.groq else 'Get free key at console.groq.com → API Keys' }}</p>
          </div>
        </div>
        <div class="check-item {{ 'ok' if keys.gemini else 'fail' }}">
          <span class="check-icon">{{ '✅' if keys.gemini else '❌' }}</span>
          <div class="check-text">
            <h4>GEMINI_API_KEY {{ '— Set ✓' if keys.gemini else '— Missing' }}</h4>
            <p>{{ 'Detected.' if keys.gemini else 'Get free key at aistudio.google.com/app/apikey' }}</p>
          </div>
        </div>
        <div class="check-item {{ 'ok' if keys.google_sheet else 'fail' }}">
          <span class="check-icon">{{ '✅' if keys.google_sheet else '❌' }}</span>
          <div class="check-text">
            <h4>GOOGLE_SHEETS_WEBHOOK_URL {{ '— Set ✓' if keys.google_sheet else '— Missing' }}</h4>
            <p>{{ 'Detected.' if keys.google_sheet else 'Optional but recommended — see README for Google Sheets webhook setup' }}</p>
          </div>
        </div>
      </div>
      {% if not keys.groq or not keys.gemini %}
      <div class="alert alert-warn" style="margin-top:16px;">
        ⚠️ <strong>Required keys are missing.</strong> You cannot continue until <code>GROQ_API_KEY</code> and <code>GEMINI_API_KEY</code> are set.<br><br>
        Add them in <strong>Vercel → Your Project → Settings → Environment Variables</strong>, then redeploy and come back.
      </div>
      {% endif %}
    </div>
    <div class="btn-row">
      <div></div>
      {% if keys.groq and keys.gemini %}
      <button class="btn-primary" onclick="goStep(2)">Continue → Personal Info</button>
      {% else %}
      <button class="btn-primary" disabled style="opacity:.4;cursor:not-allowed;" title="Set GROQ_API_KEY and GEMINI_API_KEY first">🔒 Set API Keys First</button>
      {% endif %}
    </div>
  </div>

  <!-- ─── STEP 2: Personal Info ─── -->
  <div class="step-panel" id="step-2">
    <div class="card">
      <div class="card-title">👤 Personal Information</div>
      <div class="card-sub">This appears at the top of every resume. Use real, professional details.</div>

      <div class="field">
        <label>Full Name *</label>
        <input type="text" id="name" placeholder="e.g. Jane Smith" />
      </div>
      <div class="field">
        <label>Professional Title *</label>
        <input type="text" id="prof_title" placeholder="e.g. Full Stack Web Developer (MERN Stack)" />
        <small>This is the headline on your CV — make it specific and keyword-rich.</small>
      </div>
      <div class="row-2">
        <div class="field">
          <label>Email *</label>
          <input type="email" id="email" placeholder="you@gmail.com" />
        </div>
        <div class="field">
          <label>Phone</label>
          <input type="text" id="phone" placeholder="+1 555 000 0000" />
        </div>
      </div>
      <div class="row-2">
        <div class="field">
          <label>LinkedIn URL</label>
          <input type="url" id="linkedin" placeholder="https://linkedin.com/in/yourprofile" />
        </div>
        <div class="field">
          <label>GitHub URL</label>
          <input type="url" id="github" placeholder="https://github.com/yourusername" />
        </div>
      </div>
      <div class="row-2">
        <div class="field">
          <label>Portfolio URL</label>
          <input type="url" id="portfolio" placeholder="https://yourportfolio.com" />
        </div>
        <div class="field">
          <label>Location</label>
          <input type="text" id="location" placeholder="e.g. New York, NY, USA" />
        </div>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn-secondary" onclick="goStep(1)">← Back</button>
      <button class="btn-primary" onclick="goStep(3)">Continue → Professional Summary</button>
    </div>
  </div>

  <!-- ─── STEP 3: Summary + Skills ─── -->
  <div class="step-panel" id="step-3">
    <div class="card">
      <div class="card-title">💼 Professional Summary</div>
      <div class="card-sub">Write a 3–5 sentence keyword-rich summary. This is used by AI to screen your relevance to each job.</div>
      <div class="field">
        <label>Summary *</label>
        <textarea id="summary" rows="5" placeholder="Full Stack JavaScript Developer with X years experience building... Skilled in React, Node.js, MongoDB... Proven track record of..."></textarea>
        <small>💡 Tip: Include your top 8–10 technical keywords. The AI scoring uses this text to evaluate job fit.</small>
      </div>
    </div>

    <div class="card">
      <div class="card-title">🛠 Technical Skills</div>
      <div class="card-sub">Group your skills by category. Each category becomes a line on your CV. Only list skills you genuinely have.</div>

      <div class="skills-cat">
        <div class="skills-cat-label">Frontend Development</div>
        <div class="field">
          <input type="text" id="skills_frontend" placeholder="e.g. React.js, Next.js, TypeScript, HTML5, CSS3, Tailwind CSS" />
          <small>Comma-separated list</small>
        </div>
      </div>
      <div class="skills-cat">
        <div class="skills-cat-label">Backend & Databases</div>
        <div class="field">
          <input type="text" id="skills_backend" placeholder="e.g. Node.js, Express.js, MongoDB, PostgreSQL, REST APIs" />
        </div>
      </div>
      <div class="skills-cat">
        <div class="skills-cat-label">Tools & Workflow</div>
        <div class="field">
          <input type="text" id="skills_tools" placeholder="e.g. Git, GitHub, Docker, Postman, Figma, VS Code" />
        </div>
      </div>
      <div class="skills-cat">
        <div class="skills-cat-label">Other Skills (optional)</div>
        <div class="field">
          <input type="text" id="skills_other" placeholder="e.g. AWS, CI/CD, Agile, Unit Testing, GraphQL" />
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">🎓 Education</div>
      <div class="field">
        <label>Degree</label>
        <input type="text" id="edu_degree" placeholder="e.g. Bachelor of Science in Computer Science" />
      </div>
      <div class="row-2">
        <div class="field">
          <label>Institution</label>
          <input type="text" id="edu_institution" placeholder="e.g. MIT" />
        </div>
        <div class="field">
          <label>Graduation Year</label>
          <input type="text" id="edu_year" placeholder="e.g. 2023 or 2022–2024" />
        </div>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn-secondary" onclick="goStep(2)">← Back</button>
      <button class="btn-primary" onclick="goStep(4)">Continue → Projects</button>
    </div>
  </div>

  <!-- ─── STEP 4: Projects ─── -->
  <div class="step-panel" id="step-4">
    <div class="card">
      <div class="card-title">🚀 Your Projects</div>
      <div class="card-sub">Add up to 4 real projects. These are the proof points on your CV. Be specific about what you built and what tech you used.</div>

      <div id="projects-container">
        <!-- Project 1 -->
        <div class="project-block">
          <div class="project-number">Project 1</div>
          <div class="field"><label>Project Name *</label>
            <input type="text" id="p1_name" placeholder="e.g. E-Commerce Platform" /></div>
          <div class="row-2">
            <div class="field"><label>Live URL</label>
              <input type="url" id="p1_url" placeholder="https://yourproject.com" /></div>
            <div class="field"><label>Technologies Used</label>
              <input type="text" id="p1_tech" placeholder="React.js, Node.js, MongoDB" /></div>
          </div>
          <div class="field"><label>What you built (bullet 1) *</label>
            <input type="text" id="p1_b1" placeholder="Built a full-stack e-commerce platform with..." /></div>
          <div class="field"><label>Key feature or achievement (bullet 2)</label>
            <input type="text" id="p1_b2" placeholder="Implemented secure payment integration..." /></div>
          <div class="field"><label>Technical detail or impact (bullet 3)</label>
            <input type="text" id="p1_b3" placeholder="Optimized database queries reducing load time by..." /></div>
        </div>

        <!-- Project 2 -->
        <div class="project-block">
          <div class="project-number">Project 2</div>
          <div class="field"><label>Project Name</label>
            <input type="text" id="p2_name" placeholder="e.g. Task Management SaaS" /></div>
          <div class="row-2">
            <div class="field"><label>Live URL</label>
              <input type="url" id="p2_url" placeholder="https://yourproject.com" /></div>
            <div class="field"><label>Technologies Used</label>
              <input type="text" id="p2_tech" placeholder="Next.js, TypeScript, PostgreSQL" /></div>
          </div>
          <div class="field"><label>What you built (bullet 1)</label>
            <input type="text" id="p2_b1" placeholder="Developed a..." /></div>
          <div class="field"><label>Key feature or achievement (bullet 2)</label>
            <input type="text" id="p2_b2" placeholder="" /></div>
        </div>

        <!-- Project 3 -->
        <div class="project-block">
          <div class="project-number">Project 3 (optional)</div>
          <div class="field"><label>Project Name</label>
            <input type="text" id="p3_name" placeholder="" /></div>
          <div class="row-2">
            <div class="field"><label>Live URL</label>
              <input type="url" id="p3_url" placeholder="" /></div>
            <div class="field"><label>Technologies</label>
              <input type="text" id="p3_tech" placeholder="" /></div>
          </div>
          <div class="field"><label>Bullet 1</label>
            <input type="text" id="p3_b1" placeholder="" /></div>
        </div>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn-secondary" onclick="goStep(3)">← Back</button>
      <button class="btn-primary" onclick="goStep(5)">Continue → Job Search Settings</button>
    </div>
  </div>

  <!-- ─── STEP 5: Job Keywords & Final Config ─── -->
  <div class="step-panel" id="step-5">
    <div class="card">
      <div class="card-title">🔍 Job Search Settings</div>
      <div class="card-sub">Configure what kinds of jobs the agent searches for, how many per day, and where.</div>

      <div class="field">
        <label>Job Keywords *</label>
        <div class="tag-input-wrap" id="kw-wrap" onclick="document.getElementById('kw-input').focus()">
          <input class="tag-input" id="kw-input" placeholder="Type a keyword, press Enter or comma..." />
        </div>
        <small>💡 Examples: "Full Stack Developer", "React Developer", "MERN Stack Developer", "Frontend Engineer"</small>
      </div>

      <div class="row-2">
        <div class="field">
          <label>Search Location</label>
          <input type="text" id="search_location" value="Remote" placeholder="Remote, or New York, NY" />
          <small>Use "Remote" for fully remote jobs.</small>
        </div>
        <div class="field">
          <label>Daily Job Target</label>
          <select id="daily_limit">
            <option value="5">5 jobs/day</option>
            <option value="10" selected>10 jobs/day (recommended)</option>
            <option value="15">15 jobs/day</option>
            <option value="20">20 jobs/day</option>
          </select>
        </div>
      </div>

      <div class="field">
        <label>AI Match Threshold</label>
        <select id="threshold">
          <option value="0.70">70% — More jobs, less strict</option>
          <option value="0.80" selected>80% — Balanced (recommended)</option>
          <option value="0.85">85% — High quality only</option>
          <option value="0.90">90% — Very strict</option>
        </select>
        <small>Jobs scoring below this % will be skipped — no CV compiled.</small>
      </div>
    </div>

    <div class="card">
      <div class="card-title">✅ Save Your Profile</div>
      <div class="card-sub">Click "Generate Profile" to build your profile JSON. Then add it as a Vercel environment variable.</div>

      <div class="alert alert-info">
        📋 Your profile will be shown as a JSON string. Copy it and add it as <strong>USER_PROFILE_JSON</strong> in your Vercel project settings → Environment Variables. Then redeploy.
      </div>

      <button class="btn-primary" onclick="generateProfile()" id="gen-btn" style="width:100%;justify-content:center;">
        ⚡ Generate My Profile JSON
      </button>

      <div id="output-area" style="display:none;margin-top:20px;">
        <div style="font-size:.88rem;font-weight:600;margin-bottom:8px;color:var(--text-sub);">
          USER_PROFILE_JSON — Add this to Vercel Environment Variables:
        </div>
        <div class="json-box" id="json-output"></div>
        <button class="copy-btn" onclick="copyJSON()">📋 Copy to Clipboard</button>

        <div class="alert alert-warn" style="margin-top:16px;">
          <strong>Next steps:</strong><br>
          1. Copy the JSON above<br>
          2. Go to Vercel → Your Project → Settings → Environment Variables<br>
          3. Add variable: <code>USER_PROFILE_JSON</code> = paste the JSON<br>
          4. Also add: <code>SEARCH_KEYWORDS</code> = your comma-separated keywords<br>
          5. Add: <code>SEARCH_LOCATION</code> = your location preference<br>
          6. Redeploy your project — then visit the dashboard ✅
        </div>

        <a href="/" class="btn-primary" style="text-decoration:none;display:inline-flex;margin-top:12px;">
          🏠 Go to Dashboard
        </a>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn-secondary" onclick="goStep(4)">← Back</button>
      <div></div>
    </div>
  </div>

</div><!-- /page -->

<script>
let currentStep = 1;
const keywords = [];

// ── Step navigation ──
function goStep(n) {
  document.getElementById('step-' + currentStep).classList.remove('active');
  document.getElementById('dot-' + currentStep).classList.remove('active');
  if (n > currentStep) document.getElementById('dot-' + currentStep).classList.add('done');
  if (currentStep > 1 && n < currentStep) {
    document.getElementById('dot-' + currentStep).classList.remove('done');
  }
  if (currentStep < 5) {
    const line = document.getElementById('line-' + currentStep);
    if (line) line.classList.toggle('done', n > currentStep);
  }
  currentStep = n;
  document.getElementById('step-' + n).classList.add('active');
  document.getElementById('dot-' + n).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}

// ── Keyword tag input ──
const kwInput = document.getElementById('kw-input');
kwInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    addKeyword(kwInput.value.replace(',','').trim());
    kwInput.value = '';
  } else if (e.key === 'Backspace' && kwInput.value === '' && keywords.length > 0) {
    removeKeyword(keywords.length - 1);
  }
});

function addKeyword(kw) {
  if (!kw || keywords.includes(kw)) return;
  keywords.push(kw);
  const tag = document.createElement('span');
  tag.className = 'tag';
  tag.innerHTML = kw + '<button onclick="removeKeyword(' + (keywords.length-1) + ')">×</button>';
  tag.id = 'tag-' + (keywords.length-1);
  document.getElementById('kw-wrap').insertBefore(tag, kwInput);
}

function removeKeyword(idx) {
  keywords.splice(idx, 1);
  // re-render all tags
  document.querySelectorAll('.tag').forEach(t => t.remove());
  const saved = [...keywords];
  keywords.length = 0;
  saved.forEach(k => addKeyword(k));
}

// Prefill some common keywords
['Full Stack Developer', 'React Developer', 'Node.js Developer'].forEach(k => addKeyword(k));

// ── Collect skills ──
function getSkills() {
  const s = {};
  const fe = document.getElementById('skills_frontend').value.trim();
  const be = document.getElementById('skills_backend').value.trim();
  const tl = document.getElementById('skills_tools').value.trim();
  const ot = document.getElementById('skills_other').value.trim();
  if (fe) s['Frontend Development'] = fe.split(',').map(x=>x.trim()).filter(Boolean);
  if (be) s['Backend & Databases'] = be.split(',').map(x=>x.trim()).filter(Boolean);
  if (tl) s['Tools & Workflow'] = tl.split(',').map(x=>x.trim()).filter(Boolean);
  if (ot) s['Other Skills'] = ot.split(',').map(x=>x.trim()).filter(Boolean);
  return s;
}

// ── Collect projects ──
function getProjects() {
  const projs = [];
  for (let i = 1; i <= 3; i++) {
    const name = (document.getElementById('p'+i+'_name')||{}).value||'';
    if (!name.trim()) continue;
    const bullets = [
      (document.getElementById('p'+i+'_b1')||{}).value||'',
      (document.getElementById('p'+i+'_b2')||{}).value||'',
      (document.getElementById('p'+i+'_b3')||{}).value||'',
    ].map(b=>b.trim()).filter(Boolean);
    projs.push({
      name: name.trim(),
      live_link: (document.getElementById('p'+i+'_url')||{}).value||'',
      technologies: (document.getElementById('p'+i+'_tech')||{}).value||'',
      bullets,
    });
  }
  return projs;
}

// ── Generate Profile JSON ──
function generateProfile() {
  const name = document.getElementById('name').value.trim();
  const email = document.getElementById('email').value.trim();
  if (!name || !email) { alert('Please fill in your name and email first (Step 2).'); return; }
  if (keywords.length === 0) { alert('Please add at least one job keyword.'); return; }

  const kw = [...keywords];
  const loc = document.getElementById('search_location').value.trim() || 'Remote';
  const limit = parseInt(document.getElementById('daily_limit').value);
  const threshold = parseFloat(document.getElementById('threshold').value);

  const profile = {
    name: name,
    professional_title: document.getElementById('prof_title').value.trim() || name,
    contact: {
      email: email,
      phone: document.getElementById('phone').value.trim(),
      portfolio: document.getElementById('portfolio').value.trim(),
      linkedin: document.getElementById('linkedin').value.trim(),
      github: document.getElementById('github').value.trim(),
      location: document.getElementById('location').value.trim(),
    },
    summary: document.getElementById('summary').value.trim(),
    technical_skills: getSkills(),
    professional_experience: [],
    projects: getProjects(),
    education: (() => {
      const deg = document.getElementById('edu_degree').value.trim();
      const inst = document.getElementById('edu_institution').value.trim();
      const yr = document.getElementById('edu_year').value.trim();
      if (!deg && !inst) return [];
      const parts = deg.split(' in ');
      return [{ degree: parts[0]||deg, field: parts[1]||'', institution: inst, graduation_year: yr }];
    })(),
    certifications: [],
    // Agent config stored inside profile for convenience
    _agent_config: {
      search_keywords: kw,
      search_location: loc,
      daily_job_limit: limit,
      pass_threshold: threshold,
    }
  };

  const jsonStr = JSON.stringify(profile, null, 2);
  document.getElementById('json-output').textContent = jsonStr;
  document.getElementById('output-area').style.display = 'block';

  // Save to localStorage as fallback cache
  localStorage.setItem('user_profile', jsonStr);
  localStorage.setItem('search_keywords', kw.join(','));
  localStorage.setItem('search_location', loc);

  window.scrollTo({top: document.body.scrollHeight, behavior:'smooth'});
}

function copyJSON() {
  const text = document.getElementById('json-output').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.copy-btn');
    btn.textContent = '✅ Copied!';
    setTimeout(() => btn.innerHTML = '📋 Copy to Clipboard', 2000);
  });
}
</script>
</body>
</html>"""


DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ profile.name }} — AI Job Agent Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#060b18;--surface:rgba(15,23,42,0.85);--surface2:rgba(30,41,59,0.6);
  --border:rgba(255,255,255,0.08);--accent:#38bdf8;--accent2:#818cf8;
  --green:#4ade80;--green-bg:rgba(74,222,128,0.08);--green-border:rgba(74,222,128,0.25);
  --yellow:#fbbf24;--red:#f87171;--text:#f1f5f9;--text-sub:#94a3b8;--text-dim:#475569;
  --r:16px;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;
  background-image:radial-gradient(ellipse 80% 50% at 50% -10%,rgba(56,189,248,0.12) 0%,transparent 60%),
  radial-gradient(ellipse 60% 40% at 80% 80%,rgba(129,140,248,0.08) 0%,transparent 50%);}

.topbar{display:flex;align-items:center;justify-content:space-between;padding:16px 40px;
  border-bottom:1px solid var(--border);backdrop-filter:blur(12px);position:sticky;top:0;z-index:10;
  background:rgba(6,11,24,0.7);}
.brand{display:flex;align-items:center;gap:12px;}
.logo{width:36px;height:36px;background:linear-gradient(135deg,#0284c7,#6366f1);
  border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;}
.brand-name{font-size:1rem;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.topbar-right{display:flex;align-items:center;gap:12px;}
.badge-live{display:flex;align-items:center;gap:7px;padding:5px 14px;border-radius:20px;
  background:var(--green-bg);border:1px solid var(--green-border);color:var(--green);
  font-size:.8rem;font-weight:600;}
.dot{width:7px;height:7px;background:var(--green);border-radius:50%;
  box-shadow:0 0 8px var(--green);animation:blink 2s ease-in-out infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.setup-link{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:20px;
  background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--text-sub);
  font-size:.8rem;text-decoration:none;transition:all .2s;}
.setup-link:hover{background:rgba(255,255,255,.1);color:var(--text);}

.page{max-width:960px;margin:0 auto;padding:44px 20px 80px;}

/* ── Hero ── */
.hero{display:flex;align-items:center;gap:24px;margin-bottom:44px;padding:28px 32px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  position:relative;overflow:hidden;}
.hero::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));}
.avatar{width:64px;height:64px;border-radius:16px;background:linear-gradient(135deg,#0284c7,#6366f1);
  display:flex;align-items:center;justify-content:center;font-size:1.8rem;flex-shrink:0;}
.hero-info h1{font-size:1.5rem;font-weight:700;margin-bottom:4px;}
.hero-info p{color:var(--text-sub);font-size:.9rem;}
.hero-badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:12px;
  font-size:.75rem;font-weight:600;}
.badge-blue{background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.2);color:var(--accent);}
.badge-purple{background:rgba(129,140,248,.1);border:1px solid rgba(129,140,248,.2);color:var(--accent2);}
.badge-green{background:var(--green-bg);border:1px solid var(--green-border);color:var(--green);}

/* ── Stats ── */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:32px;}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:20px 18px;position:relative;overflow:hidden;transition:border-color .2s;}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));opacity:.5;}
.stat:hover{border-color:rgba(56,189,248,.3);}
.stat-label{font-size:.75rem;font-weight:600;color:var(--text-sub);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:8px;}
.stat-value{font-size:1.5rem;font-weight:700;}
.stat-sub{font-size:.78rem;color:var(--text-dim);margin-top:4px;}

/* ── Sections ── */
.sec-title{font-size:.75rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;
  color:var(--text-dim);margin-bottom:12px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:24px;}

/* ── Two column ── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:28px;}
@media(max-width:640px){.two-col{grid-template-columns:1fr;}}

/* ── List ── */
.tag-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;}
.kw-tag{padding:5px 12px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);
  border-radius:16px;font-size:.82rem;color:var(--accent);}

/* ── Action ── */
.action-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:28px;text-align:center;margin-bottom:28px;}
.action-card h3{font-size:1.1rem;font-weight:700;margin-bottom:6px;}
.action-card p{color:var(--text-sub);font-size:.88rem;margin-bottom:22px;}
.btn-primary{background:linear-gradient(135deg,#0284c7 0%,#4f46e5 100%);color:#fff;
  border:none;padding:13px 32px;font-size:.95rem;font-weight:600;border-radius:11px;
  cursor:pointer;transition:all .25s;box-shadow:0 6px 20px rgba(2,132,199,.3);
  font-family:'Outfit',sans-serif;display:inline-flex;align-items:center;gap:8px;}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 10px 28px rgba(2,132,199,.45);}
.btn-primary:disabled{opacity:.55;cursor:not-allowed;transform:none;box-shadow:none;}
.btn-ghost{display:inline-flex;align-items:center;gap:8px;padding:11px 22px;border-radius:11px;
  background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--text);
  font-size:.88rem;font-weight:500;text-decoration:none;transition:all .2s;
  font-family:'Outfit',sans-serif;cursor:pointer;margin-left:10px;}
.btn-ghost:hover{background:rgba(255,255,255,.1);}

/* ── Console ── */
.console{margin-top:18px;background:#04080f;border:1px solid rgba(56,189,248,.15);
  border-radius:12px;padding:16px 18px;font-family:'Courier New',monospace;font-size:.82rem;
  color:#38bdf8;max-height:200px;overflow-y:auto;text-align:left;display:none;line-height:1.7;}

/* ── Sheet link ── */
.sheet-bar{display:flex;align-items:center;justify-content:space-between;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 22px;}
.sheet-bar-info{display:flex;align-items:center;gap:14px;}
.sheet-icon{width:40px;height:40px;background:var(--green-bg);border:1px solid var(--green-border);
  border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;}
.sheet-bar-text h4{font-size:.92rem;font-weight:600;margin-bottom:2px;}
.sheet-bar-text p{font-size:.8rem;color:var(--text-sub);}
.btn-green{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:10px;
  background:var(--green-bg);border:1px solid var(--green-border);color:var(--green);
  font-size:.85rem;font-weight:600;text-decoration:none;transition:all .2s;}
.btn-green:hover{background:rgba(74,222,128,.15);}

/* ── Schedule card ── */
.sched-card{display:flex;align-items:center;gap:18px;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--r);padding:20px 24px;margin-bottom:28px;}
.sched-icon{width:46px;height:46px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);
  border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.4rem;flex-shrink:0;}
.sched-info h4{font-size:.95rem;font-weight:600;margin-bottom:3px;}
.sched-info p{font-size:.84rem;color:var(--text-sub);}
.badge-gh{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:12px;
  background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.25);color:var(--yellow);
  font-size:.75rem;font-weight:600;margin-top:6px;}

.spinner{width:14px;height:14px;border:2px solid rgba(255,255,255,.2);border-top-color:#fff;
  border-radius:50%;animation:spin .7s linear infinite;display:inline-block;}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">
    <div class="logo">🤖</div>
    <span class="brand-name">AI Job Search Agent</span>
  </div>
  <div class="topbar-right">
    <div class="badge-live"><div class="dot"></div>Live</div>
    <a class="setup-link" href="/setup">⚙ Edit Profile</a>
  </div>
</div>

<div class="page">

  <!-- Candidate Hero -->
  <div class="hero">
    <div class="avatar">👤</div>
    <div class="hero-info">
      <h1>{{ profile.name }}</h1>
      <p>{{ profile.professional_title or 'Developer' }}</p>
      <div class="hero-badges">
        <span class="badge badge-blue">📧 {{ profile.contact.email }}</span>
        {% if profile.contact.location %}
        <span class="badge badge-purple">📍 {{ profile.contact.location }}</span>
        {% endif %}
        <span class="badge badge-green">✅ Profile Active</span>
      </div>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat">
      <div class="stat-label">Daily Job Target</div>
      <div class="stat-value">{{ agent_config.daily_job_limit }}</div>
      <div class="stat-sub">Unique new jobs per run</div>
    </div>
    <div class="stat">
      <div class="stat-label">Keywords</div>
      <div class="stat-value">{{ keywords|length }}</div>
      <div class="stat-sub">Job search terms</div>
    </div>
    <div class="stat">
      <div class="stat-label">AI Threshold</div>
      <div class="stat-value">{{ (agent_config.pass_threshold * 100)|int }}%</div>
      <div class="stat-sub">Min match to compile CV</div>
    </div>
    <div class="stat">
      <div class="stat-label">Job Filter</div>
      <div class="stat-value" style="font-size:1rem;margin-top:4px;">24h Only</div>
      <div class="stat-sub">Last 24 hours posts</div>
    </div>
  </div>

  <!-- Schedule -->
  <div class="sched-card">
    <div class="sched-icon">⏰</div>
    <div class="sched-info">
      <h4>Runs automatically — Mon to Fri, 9:00 AM UTC</h4>
      <p>Scrapes LinkedIn → AI screens → tailors CV → logs to Google Sheets. No manual action needed.</p>
      <span class="badge-gh">⚙ GitHub Actions Scheduler</span>
    </div>
  </div>

  <!-- Keywords & Pipeline -->
  <div class="two-col">
    <div>
      <div class="sec-title">🔍 Job Keywords</div>
      <div class="card">
        <div class="tag-list">
          {% for kw in keywords %}
          <span class="kw-tag">{{ kw }}</span>
          {% endfor %}
        </div>
        <p style="font-size:.82rem;color:var(--text-dim);margin-top:14px;">
          Location: <strong style="color:var(--text-sub);">{{ agent_config.search_location }}</strong>
        </p>
      </div>
    </div>
    <div>
      <div class="sec-title">🧠 Pipeline</div>
      <div class="card" style="font-size:.88rem;color:var(--text-sub);line-height:2;">
        <div>① Scrape LinkedIn (24h posts)</div>
        <div>② Skip already-applied jobs</div>
        <div>③ Groq AI relevance score</div>
        <div>④ Gemini CV tailoring per job</div>
        <div>⑤ Compile DOCX resume</div>
        <div>⑥ Log to Google Sheets</div>
      </div>
    </div>
  </div>

  <!-- Manual Trigger -->
  <div class="sec-title">🚀 Manual Trigger</div>
  <div class="action-card">
    <h3>Run Job Search Now</h3>
    <p>Starts the full pipeline immediately. Skips any already-applied jobs. Results appear in Google Sheets.</p>
    <button class="btn-primary" id="runBtn" onclick="triggerAgent()">
      🚀 Launch Job Search & Sync
    </button>
    {% if sheet_url %}
    <a class="btn-ghost" href="{{ sheet_url }}" target="_blank">📊 Google Sheet</a>
    {% endif %}
    <div class="console" id="console"></div>
  </div>

  <!-- Google Sheet -->
  {% if sheet_url %}
  <div class="sec-title">📊 Live Output</div>
  <div class="sheet-bar" style="margin-bottom:20px;">
    <div class="sheet-bar-info">
      <div class="sheet-icon">📋</div>
      <div class="sheet-bar-text">
        <h4>Job Tracker — Google Sheet</h4>
        <p>All processed jobs, AI scores, rationale & CV links</p>
      </div>
    </div>
    <a class="btn-green" href="{{ sheet_url }}" target="_blank">Open Sheet ↗</a>
  </div>
  {% endif %}

</div>

<script>
async function triggerAgent() {
  const btn = document.getElementById('runBtn');
  const box = document.getElementById('console');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Running pipeline...';
  box.style.display = 'block';
  box.innerHTML = '> Starting job search pipeline...\n> Searching {{ keywords|length }} keywords on LinkedIn (24h posts only)...\n';
  try {
    const res = await fetch('/api/run?limit={{ agent_config.daily_job_limit }}', {method:'POST'});
    const data = await res.json();
    if (data.status === 'success') {
      box.innerHTML += '> ✅ ' + data.message + '\n';
      if (data.summary) {
        const s = data.summary;
        box.innerHTML += '> Total scraped:       ' + (s.total_scraped||0) + '\n';
        box.innerHTML += '> Skipped (applied):   ' + (s.skipped_duplicate||0) + '\n';
        box.innerHTML += '> New unique jobs:     ' + (s.new_jobs||0) + '\n';
        box.innerHTML += '> Passed AI screen:    ' + (s.passed_screening||0) + '\n';
        box.innerHTML += '> CVs compiled:        ' + (s.resumes_compiled||0) + '\n';
        box.innerHTML += '> Sheet rows added:    ' + (s.gsheets_rows_added||0) + '\n';
      }
    } else {
      box.innerHTML += '> ⚡ ' + (data.message||'Done.') + '\n';
    }
  } catch(e) {
    box.innerHTML += '> Pipeline dispatched. Full results via GitHub Actions (60s Vercel limit).\n';
    box.innerHTML += '> Check your Google Sheet for incoming rows.\n';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🚀 Launch Job Search & Sync';
    box.scrollTop = box.scrollHeight;
  }
}
</script>
</body>
</html>"""


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    profile = _get_profile()
    if not profile:
        # No profile set — show setup wizard
        return setup()

    keys = _has_api_keys()
    agent_cfg = profile.get("_agent_config", {})
    keywords = agent_cfg.get("search_keywords") or [
        kw.strip() for kw in os.environ.get(
            "SEARCH_KEYWORDS",
            "Full Stack Developer,React Developer,Node.js Developer"
        ).split(",") if kw.strip()
    ]
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    sheet_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        if sheet_id else ""
    )
    agent_config = {
        "daily_job_limit": agent_cfg.get("daily_job_limit", 10),
        "pass_threshold": agent_cfg.get("pass_threshold", 0.80),
        "search_location": agent_cfg.get("search_location", os.environ.get("SEARCH_LOCATION", "Remote")),
    }
    return render_template_string(
        DASHBOARD_TEMPLATE,
        profile=profile,
        keywords=keywords,
        agent_config=agent_config,
        sheet_url=sheet_url,
        keys=keys,
    )


@app.route("/setup")
def setup():
    keys = _has_api_keys()
    return render_template_string(SETUP_TEMPLATE, keys=keys)


@app.route("/api/status")
def api_status():
    profile = _get_profile()
    keys = _has_api_keys()
    return jsonify({
        "status": "online",
        "profile_configured": profile is not None,
        "candidate": profile.get("name") if profile else None,
        "api_keys": keys,
        "scheduler": "GitHub Actions — Mon-Fri 9:00 AM UTC",
    })


@app.route("/api/load-profile")
def api_load_profile():
    profile = _get_profile()
    if not profile:
        return jsonify({"error": "No profile configured. Visit /setup to set up your profile."}), 404
    return jsonify(profile)


@app.route("/api/save-profile", methods=["POST"])
def api_save_profile():
    """Accept profile JSON and return it — user must manually add to Vercel env vars."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body received"}), 400
    required = ["name", "contact", "summary"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Missing required field: {field}"}), 400
    return jsonify({
        "status": "ok",
        "message": "Profile validated. Add USER_PROFILE_JSON to your Vercel environment variables.",
        "env_var_name": "USER_PROFILE_JSON",
        "env_var_value": json.dumps(data),
    })


@app.route("/api/run", methods=["POST", "GET"])
def api_run():
    """Trigger the job search pipeline."""
    try:
        import core_orchestrator

        profile = _get_profile()
        limit = int(request.args.get("limit", 10))
        threshold = float(request.args.get("threshold", 0.80))

        # Apply user's config
        core_orchestrator.DAILY_JOB_LIMIT = limit
        core_orchestrator.FETCH_PER_KEYWORD = 8
        core_orchestrator.PASS_THRESHOLD = threshold

        # Apply user's keywords/location from profile config if available
        if profile:
            agent_cfg = profile.get("_agent_config", {})
            kws = agent_cfg.get("search_keywords")
            if kws:
                core_orchestrator.SEARCH_KEYWORDS = kws
            loc = agent_cfg.get("search_location")
            if loc:
                core_orchestrator.SEARCH_LOCATIONS = [loc]

        summary = core_orchestrator.run_pipeline()
        added = summary.get("gsheets_rows_added", 0)
        return jsonify({
            "status": "success",
            "message": f"Pipeline complete. {added} new row(s) added to Google Sheet.",
            "summary": summary,
        })
    except Exception as exc:
        return jsonify({
            "status": "partial",
            "message": "Pipeline triggered. Check Google Sheet for results (GitHub Actions handles full runs).",
        }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
