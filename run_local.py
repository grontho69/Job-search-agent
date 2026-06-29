"""
run_local.py
============
Local test runner — loads credentials from .env file and runs the pipeline.
Use this to test the agent on your machine before deploying to GitHub Actions.

Usage:
    python run_local.py

Requirements:
    pip install -r requirements.txt
    (Ensure .env file exists with your credentials)
"""

import os
import sys

# Force UTF-8 output on Windows consoles that default to cp1252
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path


def load_env_file(env_path: str = ".env") -> None:
    """
    Parse and load a .env file into os.environ.

    This is a minimal .env loader — no external library (like python-dotenv)
    required. Handles comments (#), blank lines, and quoted values.

    Args:
        env_path: Path to the .env file (default: ".env" in current directory).
    """
    env_file = Path(env_path)
    if not env_file.exists():
        print(f"[WARN] .env file not found at: {env_file.absolute()}")
        print("   Create it by copying .env.example or running the setup again.")
        sys.exit(1)

    loaded = []
    with open(env_file, "r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Split on first "=" only
            if "=" not in line:
                print(f"[WARN] Skipping malformed line {line_num}: {line!r}")
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Strip surrounding quotes if present (both " and ')
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]

            # Only set if not already in environment (env vars take priority over .env)
            if key not in os.environ:
                os.environ[key] = value
                loaded.append(key)

    print(f"[OK] Loaded {len(loaded)} environment variables from {env_path}")
    # Show which keys were loaded (values are hidden for security)
    for key in loaded:
        display_val = os.environ[key]
        # Mask values — show first 4 chars then asterisks
        if len(display_val) > 8:
            masked = display_val[:4] + "*" * (len(display_val) - 4)
        else:
            masked = "****"
        print(f"   {key} = {masked}")


def validate_environment() -> bool:
    """
    Check that all required environment variables are set.

    Returns:
        True if all required vars are present, False otherwise.
    """
    required = [
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "SMTP_SENDER_EMAIL",
        "SMTP_APP_PASSWORD",
        "SMTP_RECIPIENT_EMAIL",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print("\n[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"   {var}")
        return False

    print(f"[OK] All required environment variables are set.")
    return True


if __name__ == "__main__":
    print("=" * 55)
    print("  AI Resume Agent -- Local Test Runner")
    print("=" * 55)

    # Step 1: Load .env into environment
    load_env_file(".env")

    # Step 2: Validate all required vars are present
    if not validate_environment():
        sys.exit(1)

    print("\nStarting pipeline...\n")

    # Step 3: Import and run the orchestrator
    # (import is deferred until after env vars are loaded)
    try:
        from core_orchestrator import run_pipeline
        summary = run_pipeline()

        print("\n" + "=" * 55)
        print("  Run Complete")
        print("=" * 55)
        print(f"  Resumes compiled : {summary.get('resumes_compiled', 0)}")
        print(f"  Emails sent      : {summary.get('emails_sent', 0)}")
        print(f"  Errors           : {len(summary.get('errors', []))}")

    except ImportError as exc:
        print(f"\n[ERROR] Import error: {exc}")
        print("   Run: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
