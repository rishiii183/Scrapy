"""
Cold Email Delivery Client & Dry-Run Simulator (Milestone 4 - Agent 4).

Features:
- Live SMTP delivery with SSL/TLS support and exponential backoff
- High-fidelity Dry-Run Simulator mode recording audit traces
- Email format normalization (RFC 5322 validation, quotes/whitespace stripping)
- CRLF to Unix LF newline normalization
- Safe fallback to Simulator when SMTP credentials are absent
- Structured DispatchResult interface contract
"""

import os
import re
import time
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Standard RFC 5322 compliant email regex pattern
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)


class DispatchResult(BaseModel):
    """
    Structured outcome of an outreach dispatch attempt.
    """
    success: bool = Field(..., description="Whether dispatch succeeded or was simulated cleanly")
    channel: str = Field(default="Cold Email", description="Outreach channel used")
    recipient: str = Field(..., description="Target email address or phone/wa.me link")
    subject: Optional[str] = Field(default=None, description="Email subject or message header")
    body: str = Field(..., description="Message body delivered or simulated")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of dispatch")
    mode: str = Field(..., description="'Dry-Run Simulator' or 'Live SMTP' or 'WhatsApp wa.me'")
    error: Optional[str] = Field(default=None, description="Error message if dispatch failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context/headers")


def clean_email(raw_email: str) -> str:
    """
    Strip surrounding quotes, whitespace, and clean raw email string.
    """
    if not raw_email:
        return ""
    cleaned = raw_email.strip().strip('"').strip("'")
    return cleaned.strip()


def is_valid_email(email_str: str) -> bool:
    """
    Validate email address per RFC 5322 format.
    Ensures '@' is present and followed by domain with dot.
    """
    cleaned = clean_email(email_str)
    if not cleaned:
        return False
    if "@" not in cleaned:
        return False
    parts = cleaned.split("@")
    if len(parts) != 2:
        return False
    domain = parts[1]
    if "." not in domain or domain.endswith(".") or domain.startswith("."):
        return False
    return bool(EMAIL_REGEX.match(cleaned))


def normalize_newlines(text: str) -> str:
    """
    Normalize CRLF (\\r\\n) and CR (\\r) newlines to standard Unix LF (\\n).
    """
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def create_mime_message(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> MIMEText:
    """
    Construct a UTF-8 MIMEText email structure with To, From, and Subject headers.
    """
    clean_body = normalize_newlines(body)
    msg = MIMEText(clean_body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = clean_email(sender)
    msg["To"] = clean_email(recipient)
    return msg


class EmailClient:
    """
    Cold Email Dispatcher supporting both Live SMTP sending and Dry-Run Simulation.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        sender_email: Optional[str] = None,
        dry_run: bool = True,
        timeout: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.sender_email = sender_email or os.getenv("SENDER_EMAIL", "outreach@roofinggrowth.com")
        self.timeout = timeout
        self.max_retries = max_retries

        # Safety: default to dry_run if credentials missing
        has_smtp = bool(self.smtp_host and self.smtp_user)
        if not dry_run and not has_smtp:
            logger.warning(
                "Live SMTP requested but SMTP_HOST / SMTP_USER not configured. Falling back to Dry-Run Simulator."
            )
            self.dry_run = True
        else:
            self.dry_run = dry_run

        self.audit_log: List[DispatchResult] = []

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        sender: Optional[str] = None,
    ) -> DispatchResult:
        """
        Dispatch an email or simulate its delivery based on active mode.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        clean_to = clean_email(recipient)
        from_addr = clean_email(sender or self.sender_email)
        norm_body = normalize_newlines(body)

        # 1. Format validation
        if not is_valid_email(clean_to):
            err_msg = f"Invalid email recipient format: '{clean_to}'"
            logger.error(err_msg)
            res = DispatchResult(
                success=False,
                channel="Cold Email",
                recipient=clean_to,
                subject=subject,
                body=norm_body,
                timestamp=now_str,
                mode="Dry-Run Simulator" if self.dry_run else "Live SMTP",
                error=err_msg,
            )
            self.audit_log.append(res)
            return res

        # 2. Simulator mode (Default / Offline / Safe)
        if self.dry_run:
            logger.info("Email simulated to %s at %s | Subject: %s", clean_to, now_str, subject)
            res = DispatchResult(
                success=True,
                channel="Cold Email",
                recipient=clean_to,
                subject=subject,
                body=norm_body,
                timestamp=now_str,
                mode="Dry-Run Simulator",
                metadata={"from": from_addr, "status": "Simulated"},
            )
            self.audit_log.append(res)
            return res

        # 3. Live SMTP sending with retry backoff
        mime_msg = create_mime_message(
            sender=from_addr,
            recipient=clean_to,
            subject=subject,
            body=norm_body,
        )

        last_error = ""
        for attempt in range(self.max_retries):
            try:
                if self.smtp_port == 465:
                    server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
                else:
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
                    server.starttls()

                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                server.send_message(mime_msg)
                server.quit()

                logger.info("Email successfully sent via SMTP to %s at %s", clean_to, now_str)
                res = DispatchResult(
                    success=True,
                    channel="Cold Email",
                    recipient=clean_to,
                    subject=subject,
                    body=norm_body,
                    timestamp=now_str,
                    mode="Live SMTP",
                    metadata={"from": from_addr, "attempts": attempt + 1},
                )
                self.audit_log.append(res)
                return res

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "SMTP dispatch attempt %d/%d to %s failed: %s",
                    attempt + 1,
                    self.max_retries,
                    clean_to,
                    last_error,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        fail_res = DispatchResult(
            success=False,
            channel="Cold Email",
            recipient=clean_to,
            subject=subject,
            body=norm_body,
            timestamp=now_str,
            mode="Live SMTP",
            error=f"SMTP dispatch failed after {self.max_retries} attempts: {last_error}",
            metadata={"from": from_addr, "attempts": self.max_retries},
        )
        self.audit_log.append(fail_res)
        return fail_res
