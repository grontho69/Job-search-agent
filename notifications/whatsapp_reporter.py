"""
whatsapp_reporter.py
====================
Delivers daily verified job briefings and tailored CV links via Meta WhatsApp Cloud API.
"""

import os
import logging
import requests
from typing import Dict, List

logger = logging.getLogger("whatsapp_reporter")

def send_whatsapp_job_report(job_summary_list: List[Dict]) -> bool:
    """
    Sends structured WhatsApp messages containing company, title, country, salary,
    match score, application link, and CV download link for each job.
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    recipient = os.environ.get("RECIPIENT_PHONE_NUMBER")

    if not token or not phone_number_id or not recipient:
        logger.warning("WhatsApp credentials missing in environment variables. Skipping WhatsApp dispatch.")
        return False

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Send Header Message
    header_text = (
        f"🚀 *Daily AI Job Search Briefing*\n"
        f"📅 Date: {len(job_summary_list)} Verified Remote Opportunities Ready For You!"
    )
    try:
        requests.post(url, headers=headers, json={
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": header_text}
        }, timeout=10)
    except Exception as e:
        logger.error("Failed to send WhatsApp header: %s", e)

    # 2. Send Each Job Item
    success_count = 0
    for idx, job in enumerate(job_summary_list, start=1):
        msg_body = (
            f"*{idx}. {job.get('title')}*\n"
            f"🏢 *Company:* {job.get('company')}\n"
            f"🌍 *Country/Location:* {job.get('country', 'Worldwide')}\n"
            f"💰 *Salary:* {job.get('salary', 'Not Specified')}\n"
            f"🎯 *Match Score:* {int(job.get('score', 0) * 100)}%\n"
            f"🔗 *Apply Here:* {job.get('url')}\n"
            f"📄 *Tailored CV:* {job.get('pdf_filename', 'Compiled in output folder')}"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": msg_body}
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            if r.status_code in (200, 201):
                success_count += 1
            else:
                logger.warning("WhatsApp dispatch failed for job %d: %s", idx, r.text)
        except Exception as ex:
            logger.error("WhatsApp dispatch error: %s", ex)

    logger.info("Dispatched %d/%d WhatsApp job updates.", success_count, len(job_summary_list))
    return success_count > 0
