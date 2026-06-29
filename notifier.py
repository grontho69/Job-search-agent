"""
notifier.py
===========
SMTP Resume Email Delivery System
------------------------------------
Constructs and sends a multipart email with the compiled DOCX resume
as a binary attachment using Python's standard-library smtplib and email
packages — no external dependencies required.

Security model:
  All credentials (sender address, SMTP password, recipient address) are
  loaded exclusively from environment variables. They must never be
  hard-coded in source files or committed to version control.

SMTP Configuration:
  - Server:     smtp.gmail.com
  - Port:       587 (STARTTLS — preferred over port 465 SSL for better
                compatibility and firewall traversal)
  - Auth:       Gmail "App Password" (required when 2FA is enabled on the
                sending account — standard account passwords won't work)

Required Environment Variables:
  SMTP_SENDER_EMAIL    — The Gmail address sending the email.
  SMTP_APP_PASSWORD    — The 16-character Gmail App Password.
  SMTP_RECIPIENT_EMAIL — The destination email address.

Gmail App Password Setup:
  1. Enable 2-Step Verification: myaccount.google.com/security
  2. Generate App Password: myaccount.google.com/apppasswords
  3. Select "Mail" + "Other (custom name)" → copy the 16-char password.

Dependencies: Standard library only (smtplib, email, os, logging)
"""

import logging
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("notifier")

# ---------------------------------------------------------------------------
# SMTP Constants
# ---------------------------------------------------------------------------
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587  # STARTTLS port


# ---------------------------------------------------------------------------
# Credential Resolution
# ---------------------------------------------------------------------------

def _load_smtp_credentials() -> tuple[str, str, str]:
    """
    Load SMTP credentials from environment variables.

    Reads the three required environment variables and returns them as a tuple.
    Raises a descriptive EnvironmentError if any variable is missing so
    the failure is immediately diagnosable in GitHub Actions logs.

    Returns:
        (sender_email, app_password, recipient_email) as a 3-tuple of strings.

    Raises:
        EnvironmentError: If any required environment variable is absent.
    """
    required_vars = {
        "SMTP_SENDER_EMAIL": "Gmail address of the sending account",
        "SMTP_APP_PASSWORD": "16-character Gmail App Password",
        "SMTP_RECIPIENT_EMAIL": "Destination email address for resumes",
    }

    missing = []
    values = {}
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if not value:
            missing.append(f"  {var} — {description}")
        else:
            values[var] = value

    if missing:
        raise EnvironmentError(
            "Missing required SMTP environment variables:\n"
            + "\n".join(missing)
            + "\n\nSet these in your shell or GitHub Actions Secrets."
        )

    return (
        values["SMTP_SENDER_EMAIL"],
        values["SMTP_APP_PASSWORD"],
        values["SMTP_RECIPIENT_EMAIL"],
    )


# ---------------------------------------------------------------------------
# Email Construction
# ---------------------------------------------------------------------------

def _build_email_body(
    job_title: str,
    company: str,
    job_url: str,
    score: float,
    reason: str,
) -> str:
    """
    Construct the plain-text email body summarizing the job match.

    This gives the recipient context about which job the attached resume
    was tailored for, including the AI relevance score and rationale.

    Args:
        job_title:  Job title of the matched position.
        company:    Hiring company name.
        job_url:    Direct link to the LinkedIn job posting.
        score:      Groq relevance score (0.0 – 1.0).
        reason:     One-sentence AI rationale for the score.

    Returns:
        Formatted plain-text email body string.
    """
    score_pct = f"{score * 100:.0f}%"
    body = f"""Hi,

Your AI Resume Agent has found a highly relevant job match and compiled a tailored resume for you.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOB DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Position:  {job_title}
  Company:   {company}
  Link:      {job_url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI SCREENING RESULT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Relevance Score: {score_pct}
  Rationale:       {reason}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTION REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Review the attached tailored resume carefully.
  2. Verify all details are accurate before submitting.
  3. Customize the cover letter if required by the job posting.
  4. Apply directly via the link above.

Note: This resume was generated by an AI agent. Always review AI-generated
content for accuracy before submitting to employers.

—
AI Resume Agent | Automated Job Search System
"""
    return body


def _build_html_body(
    job_title: str,
    company: str,
    job_url: str,
    score: float,
    reason: str,
) -> str:
    """
    Build an HTML version of the email body for clients that render HTML.

    Args:
        Same as _build_email_body().

    Returns:
        HTML string for the email's html/text part.
    """
    score_pct = f"{score * 100:.0f}%"
    score_color = "#2e7d32" if score >= 0.85 else "#f57c00" if score >= 0.75 else "#c62828"

    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
    .header {{ background: #1A1A2E; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
    .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #e0e0e0; }}
    .score-badge {{ display: inline-block; background: {score_color}; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; }}
    .job-box {{ background: white; border-left: 4px solid #1A1A2E; padding: 15px; margin: 15px 0; }}
    .cta-button {{ display: inline-block; background: #0F3C78; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; margin-top: 15px; }}
    .footer {{ color: #999; font-size: 12px; margin-top: 20px; padding-top: 10px; border-top: 1px solid #e0e0e0; }}
  </style>
</head>
<body>
  <div class="header">
    <h2 style="margin:0">🤖 AI Resume Agent — Job Match Found</h2>
  </div>
  <div class="content">
    <div class="job-box">
      <h3 style="margin:0 0 8px 0">{job_title}</h3>
      <p style="margin:0; color:#666">{company}</p>
      <a href="{job_url}" class="cta-button">View Job Posting →</a>
    </div>

    <h4>AI Screening Result</h4>
    <p>Relevance Score: <span class="score-badge">{score_pct}</span></p>
    <p><em>{reason}</em></p>

    <hr style="border:none; border-top:1px solid #e0e0e0; margin: 20px 0">

    <h4>Action Required</h4>
    <ol>
      <li>Review the attached tailored resume carefully.</li>
      <li>Verify all details are accurate before submitting.</li>
      <li>Customize the cover letter if required.</li>
      <li>Apply directly via the link above.</li>
    </ol>

    <p style="color:#c62828; font-size:13px">
      ⚠️ This resume was AI-generated. Always review before submitting to employers.
    </p>
  </div>
  <div class="footer">
    <p>AI Resume Agent | Automated Job Search System</p>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Core Email Sender
# ---------------------------------------------------------------------------

def send_resume_email(
    docx_path: str,
    job_title: str,
    company: str,
    job_url: str,
    score: float,
    reason: str,
    candidate_name: Optional[str] = None,
) -> bool:
    """
    Compose and send an email with the tailored resume as a DOCX attachment.

    Reads SMTP credentials from environment variables, constructs a
    MIMEMultipart message with both plain-text and HTML body parts
    (for maximum email client compatibility), attaches the DOCX file
    as a base64-encoded binary payload, and delivers it via STARTTLS.

    Args:
        docx_path:       Absolute path to the compiled DOCX resume file.
        job_title:       Job title for the email subject and body.
        company:         Company name for the email subject and body.
        job_url:         LinkedIn job posting URL.
        score:           Groq relevance score (0.0 – 1.0).
        reason:          AI screening rationale.
        candidate_name:  Optional candidate name for the attachment filename.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    # -----------------------------------------------------------------------
    # Load credentials from environment
    # -----------------------------------------------------------------------
    try:
        sender_email, app_password, recipient_email = _load_smtp_credentials()
    except EnvironmentError as exc:
        logger.error("SMTP credential error: %s", exc)
        return False

    # -----------------------------------------------------------------------
    # Build attachment filename
    # -----------------------------------------------------------------------
    safe_title = job_title.replace("/", "-").replace(" ", "_")[:40]
    safe_company = company.replace("/", "-").replace(" ", "_")[:20]
    name_part = (candidate_name or "Resume").replace(" ", "_")
    attachment_filename = f"{name_part}_{safe_title}_{safe_company}.docx"

    # -----------------------------------------------------------------------
    # Construct the multipart email message
    # -----------------------------------------------------------------------
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[AI Resume] {job_title} at {company} — {score * 100:.0f}% Match"
    msg["From"] = f"AI Resume Agent <{sender_email}>"
    msg["To"] = recipient_email

    # Attach plain-text part first (fallback for text-only email clients).
    text_body = _build_email_body(job_title, company, job_url, score, reason)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))

    # Attach HTML part second (preferred by modern email clients).
    html_body = _build_html_body(job_title, company, job_url, score, reason)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # -----------------------------------------------------------------------
    # Attach the DOCX resume as a binary MIME payload
    # -----------------------------------------------------------------------
    docx_file = Path(docx_path)
    if not docx_file.exists():
        logger.error("DOCX file not found at path: %s", docx_path)
        return False

    try:
        with open(docx_file, "rb") as fh:
            docx_bytes = fh.read()
    except IOError as exc:
        logger.error("Failed to read DOCX file '%s': %s", docx_path, exc)
        return False

    # Create the MIME attachment — application/vnd.openxmlformats is the
    # correct MIME type for .docx files and is recognized by all email clients.
    attachment = MIMEBase(
        "application",
        "vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    attachment.set_payload(docx_bytes)

    # Base64-encode the binary payload so it survives SMTP transport.
    encoders.encode_base64(attachment)

    # Set Content-Disposition header so clients know this is a downloadable file.
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=attachment_filename,
    )

    # MIMEMultipart("alternative") is for body alternatives; for attachments
    # we need to embed in a mixed message. Repackage correctly:
    outer = MIMEMultipart("mixed")
    outer["Subject"] = msg["Subject"]
    outer["From"] = msg["From"]
    outer["To"] = msg["To"]
    outer.attach(msg)         # Attach the alternative text+html block
    outer.attach(attachment)  # Attach the DOCX file

    # -----------------------------------------------------------------------
    # Establish STARTTLS connection and send
    # -----------------------------------------------------------------------
    try:
        logger.info(
            "Connecting to SMTP server %s:%d as %s",
            SMTP_HOST, SMTP_PORT, sender_email,
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()       # Upgrade to encrypted TLS connection
            smtp.ehlo()           # Re-identify after STARTTLS upgrade
            smtp.login(sender_email, app_password)

            smtp.sendmail(
                from_addr=sender_email,
                to_addrs=[recipient_email],
                msg=outer.as_string(),
            )

        logger.info(
            "Email sent successfully to %s | Subject: '%s'",
            recipient_email, outer["Subject"],
        )
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed. "
            "Ensure SMTP_APP_PASSWORD is a valid Gmail App Password "
            "(not your regular Gmail password). "
            "Generate one at: myaccount.google.com/apppasswords"
        )
        return False
    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending email: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error sending email: %s", exc, exc_info=True)
        return False
