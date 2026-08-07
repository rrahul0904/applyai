from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class EmailDelivery:
    provider: str
    delivered: bool


def email_provider() -> str:
    return os.getenv("EMAIL_PROVIDER", "disabled").strip().lower()


def send_email(*, to_address: str, subject: str, text_body: str) -> EmailDelivery:
    """Send one transactional email through the configured provider.

    `disabled` is the safe default. `smtp` works with Mailpit locally and with a reviewed SMTP
    relay in a deployed environment. SMTP failures are not swallowed so local certification and
    operators can detect a broken delivery integration.
    """
    provider = email_provider()
    if provider == "disabled":
        return EmailDelivery(provider=provider, delivered=False)
    if provider != "smtp":
        raise RuntimeError(f"Unsupported EMAIL_PROVIDER: {provider}")

    host = os.getenv("SMTP_HOST", "127.0.0.1")
    port = int(os.getenv("SMTP_PORT", "1025"))
    sender = os.getenv("EMAIL_FROM", "ApplyAI <no-reply@applyai.local>")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_STARTTLS", "false").strip().lower() in {"1", "true", "yes", "on"}

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(text_body)

    with smtplib.SMTP(host=host, port=port, timeout=10) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)
    return EmailDelivery(provider=provider, delivered=True)
