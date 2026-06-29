"""
diagnose_gemini.py - Check Gemini API key and list available models
"""
import sys
import os
import urllib.request
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get("GEMINI_API_KEY", "")
print(f"Key prefix : {key[:12]}...")
print(f"Key length : {len(key)} chars")
print(f"Looks valid: {'Yes' if key.startswith('AIza') else 'NO - expected prefix AIza...'}")
print()

# Direct REST call to list models
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        models = data.get("models", [])
        flash_models = [m["name"] for m in models if "flash" in m["name"].lower()]
        pro_models   = [m["name"] for m in models if "pro" in m["name"].lower() and "flash" not in m["name"].lower()]

        print(f"Total models returned: {len(models)}")
        print()
        print("Flash models (free tier, best choice):")
        for m in flash_models:
            print(f"  - {m}")
        print()
        print("Pro models:")
        for m in pro_models[:5]:
            print(f"  - {m}")

except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"HTTP {e.code} ERROR: {e.reason}")
    print("Response body:", body[:500])
except Exception as e:
    print(f"ERROR: {e}")
