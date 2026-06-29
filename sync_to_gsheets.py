"""
sync_to_gsheets.py
==================
Google Sheets Synchronizer for AI Resume Agent
----------------------------------------------
Target Sheet ID: 1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI

This script reads all entries from your local `job_tracker.xlsx` and uploads
them to your Google Sheet.

Supports 2 authentication modes:
  Mode 1 (Recommended / Service Account):
    1. Place your `service_account.json` file in the project folder.
    2. Share your Google Sheet (1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI)
       with the client_email found inside service_account.json (Editor access).
    3. Run: python sync_to_gsheets.py

  Mode 2 (Google Apps Script Webhook):
    1. Set GOOGLE_SHEETS_WEBHOOK_URL in your .env file.
    2. Run: python sync_to_gsheets.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI")
EXCEL_FILE = Path("job_tracker.xlsx")

def sync_excel_to_google_sheets():
    print("=" * 60)
    print("  AI Resume Agent — Google Sheets Synchronizer")
    print("=" * 60)
    print(f"Target Sheet ID: {GOOGLE_SHEET_ID}")
    print(f"Local Source   : {EXCEL_FILE.absolute()}")
    print("-" * 60)

    if not EXCEL_FILE.exists():
        print(f"❌ Error: Local tracker '{EXCEL_FILE}' not found. Run the agent first!")
        return

    try:
        import openpyxl
    except ImportError:
        print("❌ openpyxl is required. Run: pip install openpyxl")
        return

    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        print("❌ Tracker is empty.")
        return

    headers = [str(cell) if cell is not None else "" for cell in rows[0]]
    data_rows = []
    for r in rows[1:]:
        if r[0] and not str(r[0]).startswith("---"):
            data_rows.append([str(cell) if cell is not None else "" for cell in r])

    print(f"Found {len(data_rows)} job records to sync.")

    # Try Service Account sync via gspread
    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    if Path(sa_path).exists():
        try:
            import gspread
            print(f"Authenticating via Service Account: {sa_path}...")
            gc = gspread.service_account(filename=sa_path)
            sh = gc.open_by_key(GOOGLE_SHEET_ID)
            worksheet = sh.sheet1

            # Clear existing content and update with fresh headers and data
            worksheet.clear()
            worksheet.update("A1", [headers] + data_rows)
            print(f"✅ SUCCESS: Synced {len(data_rows)} rows to Google Sheet via Service Account!")
            return
        except Exception as e:
            print(f"⚠️ Service Account sync error: {e}")

    # Try Webhook sync
    webhook_url = os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL")
    if webhook_url:
        try:
            import requests
            print("Syncing via Google Apps Script Webhook...")
            payload = {
                "action": "full_sync",
                "sheet_id": GOOGLE_SHEET_ID,
                "headers": headers,
                "rows": data_rows
            }
            resp = requests.post(webhook_url, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"✅ SUCCESS: Synced {len(data_rows)} rows to Google Sheet via Webhook!")
                return
            else:
                print(f"⚠️ Webhook returned status code: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Webhook sync error: {e}")

    print("\n" + "=" * 60)
    print("🔒 Google Sheets Authentication Needed")
    print("=" * 60)
    print("To allow automatic sync to your Google Sheet, choose ONE option:")
    print()
    print("Option A (Service Account — Recommended):")
    print("  1. Download your Service Account JSON key from Google Cloud Console.")
    print("  2. Save it in this folder as 'service_account.json'.")
    print("  3. Open your Google Sheet (https://docs.google.com/spreadsheets/d/1PQMwFgu_C_3AZOEec4I61dG2jpjvLYUYsBLNGlF4taI)")
    print("     and share it with the service account email address (with Editor permissions).")
    print()
    print("Option B (Apps Script Webhook):")
    print("  1. In your Google Sheet, click Extensions → Apps Script.")
    print("  2. Paste a simple receiver script, click Deploy → New Deployment (Web app, Anyone).")
    print("  3. Add GOOGLE_SHEETS_WEBHOOK_URL=your_url to your .env file.")

if __name__ == "__main__":
    sync_excel_to_google_sheets()
