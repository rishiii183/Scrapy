"""
WhatsApp Click-to-Chat Fallback Client (Milestone 4 - Agent 4).

Features:
- Fallback delivery channel for phone-only or email-bounced contractor leads
- Pre-populated wa.me click-to-chat link builder (https://wa.me/1{phone}?text={encoded_msg})
- Full URL percent-encoding for special symbols (?, &, =), newlines (%0A), and emojis
- Strips phone extensions ('ext 102') and standardizes to E.164 10-digit US format with '1' prefix
- Browser safety URL length verification (<2048 chars)
- Dry-run simulator recording click events and payload in DispatchResult
"""

import re
import urllib.parse
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.dispatcher.email_client import DispatchResult

logger = logging.getLogger(__name__)

MAX_WAME_URL_LENGTH = 2048


def is_phone_only_lead(work_email: Optional[str]) -> bool:
    """
    Check if a contractor lead is phone-only (lacks a valid email address).
    Returns True for entries like 'Call: (903) 807-0683' or empty/@-less strings.
    """
    if not work_email:
        return True
    val = work_email.strip()
    return val.startswith("Call:") or "@" not in val


def extract_clean_10digit_phone(phone_str: Optional[str]) -> str:
    """
    Extract 10-digit US phone number, stripping extensions, non-digits, and leading country code.
    Example: '(903) 807-0683 ext 102' -> '9038070683'
    """
    if not phone_str:
        return ""
    # Strip extension tokens (e.g. ext 102, x44, extension 5)
    phone_clean = re.split(
        r"(?:(?:\bext|\bextension|\bx)\.?\s*\d+)|(?:\b(?:ext|extension)\b)",
        phone_str,
        flags=re.IGNORECASE,
    )[0]
    digits = re.sub(r"\D", "", phone_clean)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    elif len(digits) > 11 and digits.startswith("1"):
        digits = digits[1:11]
    elif len(digits) > 10:
        digits = digits[:10]
    return digits if len(digits) == 10 else digits


def build_whatsapp_link(phone: str, message: str) -> str:
    """
    Generate pre-populated wa.me click-to-chat URL with proper URL encoding.
    Prepends US country code '1'.
    """
    clean_digits = extract_clean_10digit_phone(phone)
    if len(clean_digits) == 10:
        phone_param = "1" + clean_digits
    else:
        phone_param = clean_digits

    # URL encode all reserved characters, spaces (%20), newlines (%0A), emojis
    encoded_text = urllib.parse.quote(message, safe="")
    url = f"https://wa.me/{phone_param}?text={encoded_text}"

    if len(url) > MAX_WAME_URL_LENGTH:
        logger.warning(
            "Constructed wa.me URL exceeds browser safe length (%d > %d)",
            len(url),
            MAX_WAME_URL_LENGTH,
        )
    return url


class WhatsAppClient:
    """
    WhatsApp Click-to-Chat delivery client supporting both dry-run simulation and browser link dispatch.
    """

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.audit_log: List[DispatchResult] = []

    def send(
        self,
        phone: str,
        message: str,
        wame_url: Optional[str] = None,
    ) -> DispatchResult:
        """
        Dispatch or simulate WhatsApp click-to-chat link generation.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        clean_phone = extract_clean_10digit_phone(phone)
        link = wame_url or build_whatsapp_link(phone, message)

        if not clean_phone and not wame_url:
            err = f"Cannot generate WhatsApp dispatch: invalid phone number '{phone}'"
            logger.error(err)
            res = DispatchResult(
                success=False,
                channel="WhatsApp wa.me",
                recipient=phone,
                subject=None,
                body=message,
                timestamp=now_str,
                mode="Dry-Run WhatsApp" if self.dry_run else "Live WhatsApp",
                error=err,
            )
            self.audit_log.append(res)
            return res

        logger.info(
            "WhatsApp link generated: %s for %s at %s",
            link[:60] + "...",
            clean_phone or phone,
            now_str,
        )

        res = DispatchResult(
            success=True,
            channel="WhatsApp wa.me",
            recipient=link,
            subject=None,
            body=message,
            timestamp=now_str,
            mode="Dry-Run WhatsApp" if self.dry_run else "Live WhatsApp",
            metadata={
                "phone": clean_phone or phone,
                "wame_url": link,
                "url_length": len(link),
                "status": "Simulated Click" if self.dry_run else "Dispatched Link",
            },
        )
        self.audit_log.append(res)
        return res
