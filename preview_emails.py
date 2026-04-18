"""
One-off preview sender.

Sends all 9 Business Unlocked emails to paolo.segura@gmail.com (or override via
PREVIEW_EMAIL env var) so the sequence can be reviewed in a real inbox before
going live to paid customers.

Each subject is prefixed with [PREVIEW X/9] so they're easy to spot.

Usage:
    BREVO_API_KEY=xxx python preview_emails.py
    BREVO_API_KEY=xxx PREVIEW_EMAIL=someone@example.com python preview_emails.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from send_nurture import (  # noqa: E402
    EMAIL_SCHEDULE,
    SENDER_EMAIL,
    SENDER_NAME,
    brevo_send_email,
    build_brevo_send_payload,
    load_template,
    render_template,
)


def main():
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("ERROR: BREVO_API_KEY env var is required.")
        sys.exit(1)

    to_email = os.environ.get("PREVIEW_EMAIL", "paolo.segura@gmail.com")
    total = len(EMAIL_SCHEDULE)

    print(f"Sending {total} preview emails to {to_email}")
    print(f"From: {SENDER_NAME} <{SENDER_EMAIL}>")
    print("-" * 60)

    for i, entry in enumerate(EMAIL_SCHEDULE, start=1):
        subject = f"[PREVIEW {i}/{total}] {entry['subject']}"
        try:
            html = load_template(entry["template"])
            rendered = render_template(html, to_email)
            payload = build_brevo_send_payload(
                to_email=to_email,
                subject=subject,
                html_body=rendered,
                sender_name=SENDER_NAME,
                sender_email=SENDER_EMAIL,
            )
            message_id = brevo_send_email(payload, api_key)
            print(f"[{i}/{total}] SENT '{entry['template']}' (messageId={message_id})")
        except Exception as e:
            print(f"[{i}/{total}] FAILED '{entry['template']}': {e}")

        if i < total:
            time.sleep(1)

    print("-" * 60)
    print("Done. Check your inbox (and spam folder).")


if __name__ == "__main__":
    main()
