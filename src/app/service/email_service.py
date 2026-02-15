"""
Email Service

Sends HITL notification emails via SMTP (smtplib — stdlib, no dependencies).
Uses Gmail App Passwords configured in .env.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


def send_hitl_notification(
    run_id: str,
    book: str,
    chapter: int,
    verses: list[int],
    risk_level: str,
    alerts: list[str],
    review_url: Optional[str] = None,
) -> bool:
    """
    Send an email notifying the reviewer of a high-risk analysis.

    Returns True if the email was sent successfully, False otherwise.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    reviewer_email = os.getenv("HITL_REVIEWER_EMAIL")

    if not all([smtp_user, smtp_password, reviewer_email]):
        logger.warning(
            "SMTP credentials not configured — skipping email notification",
            extra={"event": "email_skip", "run_id": run_id},
        )
        return False

    # Build the email
    verses_str = ", ".join(str(v) for v in verses)
    alerts_html = "".join(f"<li>{alert}</li>" for alert in alerts)

    if not review_url:
        review_url = f"http://localhost:8000/hitl/{run_id}"

    subject = (
        f"⚠️ HITL Review Required — {book} {chapter}:{verses_str} [{risk_level.upper()}]"
    )

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #FEF3CD; border-left: 4px solid #FFC107; padding: 16px; margin-bottom: 16px;">
            <h2 style="margin: 0 0 8px 0; color: #856404;">⚠️ Revisão Humana Necessária</h2>
            <p style="margin: 0; color: #856404;">O validador teológico identificou riscos na análise.</p>
        </div>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
            <tr><td style="padding: 8px; font-weight: bold;">Referência:</td><td style="padding: 8px;">{book} {chapter}:{verses_str}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Nível de Risco:</td><td style="padding: 8px; color: #DC3545; font-weight: bold;">{risk_level.upper()}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Run ID:</td><td style="padding: 8px; font-family: monospace;">{run_id}</td></tr>
        </table>

        <h3>Alertas Identificados:</h3>
        <ul style="background: #F8D7DA; padding: 16px 16px 16px 32px; border-radius: 4px;">
            {alerts_html}
        </ul>

        <div style="text-align: center; margin: 24px 0;">
            <a href="{review_url}"
               style="background: #0D6EFD; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                Revisar Análise
            </a>
        </div>

        <hr style="border: none; border-top: 1px solid #dee2e6;">
        <p style="color: #6c757d; font-size: 12px;">
            Este email foi gerado automaticamente pelo Agente Teológico.
            Para aprovar ou editar a análise, acesse o link acima.
        </p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = reviewer_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, reviewer_email, msg.as_string())

        logger.info(
            f"HITL notification email sent for {book} {chapter}:{verses_str}",
            extra={"event": "email_sent", "run_id": run_id, "risk_level": risk_level},
        )
        return True

    except Exception as e:
        logger.error(
            f"Email send failed: {e}",
            extra={"event": "email_error", "run_id": run_id},
        )
        return False
