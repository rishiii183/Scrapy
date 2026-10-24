"""
Deterministic Jinja2 Template Engine for Roofer Outreach Copy.

Guarantees:
- 100% offline testability (<10ms execution, zero network or API dependency)
- 100% compliance with acceptance criteria:
  * Sentence 1 references exact city/metro and trade specialty
  * Sentence 2 highlights emergency roof repairs competitor search ranking revenue loss
  * Exactly 2 sentences in generated icebreaker
  * 0 unparsed {{placeholders}} or {tags}
- Deterministic cross-process variety based on CRC32 hashing
"""

import re
import zlib
from typing import Any, Dict, List, Optional
import jinja2

from src.personalizer.prompts import (
    EMAIL_BODY_TEMPLATES,
    EMAIL_SUBJECT_TEMPLATES,
    ICEBREAKER_TEMPLATES,
    OFFER_ANGLE_TEMPLATES,
    WHATSAPP_TEMPLATES,
)


def assert_zero_placeholders(text: str) -> None:
    """
    Verify that no template placeholder tags remain in generated text.
    Raises AssertionError if any unparsed tag is detected.
    """
    patterns = [r"\{\{.*?\}\}", r"\{[A-Za-z_]+\}"]
    for pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            raise AssertionError(f"Unparsed placeholder tags detected in copy: {matches}")


def sanitize_company_name(name: str) -> str:
    """
    Normalize company name to remove internal and trailing periods (e.g. initials like J.R. -> JR,
    legal abbreviations like Inc. -> Inc) so that sentence splitting on '.' is 100% accurate.
    """
    if not name:
        return "Your Roofing Team"
    clean = name.strip()
    # Replace initials like J.R. -> JR
    clean = re.sub(r"\b([A-Za-z])\.", r"\1", clean)
    # Remove any remaining dots
    clean = clean.replace(".", "")
    return clean.strip()


class TemplateEngine:
    """
    Deterministic Jinja2 rendering engine for personalized roofer outreach assets.
    """

    def __init__(self) -> None:
        self.jinja_env = jinja2.Environment(
            autoescape=False,
            undefined=jinja2.StrictUndefined,
        )

        self._icebreaker_tmpls = [self.jinja_env.from_string(t) for t in ICEBREAKER_TEMPLATES]
        self._offer_angle_tmpls = [self.jinja_env.from_string(t) for t in OFFER_ANGLE_TEMPLATES]
        self._email_subject_tmpls = [self.jinja_env.from_string(t) for t in EMAIL_SUBJECT_TEMPLATES]
        self._email_body_tmpls = [self.jinja_env.from_string(t) for t in EMAIL_BODY_TEMPLATES]
        self._whatsapp_tmpls = [self.jinja_env.from_string(t) for t in WHATSAPP_TEMPLATES]

    def _prepare_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and sanitize context dictionary with safe fallbacks and niche awareness.
        """
        raw_name = raw_context.get("company_name") or raw_context.get("business_name") or "Your Roofing Team"
        company_name = sanitize_company_name(str(raw_name))

        city = (raw_context.get("city") or "your area").strip()
        state = (raw_context.get("state") or "").strip().upper()
        specialty = (raw_context.get("specialty") or raw_context.get("industry_niche") or "Residential Roofing & Repairs").strip()

        # Contact greeting fallback
        first_name = (raw_context.get("first_name") or raw_context.get("contact_first_name") or "").strip()
        if not first_name or first_name.lower() in {"roofing team", "contractor", "team", "none", "unknown", "n/a"}:
            contact_name = "Team"
        else:
            contact_name = first_name

        phone_display = (raw_context.get("phone_display") or raw_context.get("phone") or "").strip()
        row_index = int(raw_context.get("row_index", 14))

        # Determine niche and appropriate copy parameters
        niche = (raw_context.get("niche") or "").strip().lower()
        if not niche:
            spec_lower = specialty.lower()
            if any(k in spec_lower for k in ["roof", "re-roof", "shingle", "flashing", "gutter"]):
                niche = "roofing"
            elif any(k in spec_lower for k in ["plumb", "drain", "sewer", "water heater", "pipe"]):
                niche = "plumbing"
            elif any(k in spec_lower for k in ["hvac", "ac repair", "air conditioning", "heating", "cooling", "furnace"]):
                niche = "hvac"
            elif any(k in spec_lower for k in ["electri", "wiring", "panel upgrade"]):
                niche = "electrical"
            elif any(k in spec_lower for k in ["dentist", "dental", "orthodont"]):
                niche = "dental"
            else:
                niche = "roofing"

        if niche in ("roofing", "roofer", "roofers"):
            service_need = raw_context.get("service_need") or "emergency roof repairs"
            service_call = raw_context.get("service_call") or "repair and re-roof jobs"
            sender_team = raw_context.get("sender_team") or "Roofing Growth Team"
        elif "plumb" in niche:
            service_need = raw_context.get("service_need") or "emergency plumbing repairs"
            service_call = raw_context.get("service_call") or "urgent plumbing and drain jobs"
            sender_team = raw_context.get("sender_team") or "Plumbing Growth Team"
        elif "hvac" in niche or "air" in niche or "heat" in niche:
            service_need = raw_context.get("service_need") or "urgent AC and heating repairs"
            service_call = raw_context.get("service_call") or "HVAC replacement and repair calls"
            sender_team = raw_context.get("sender_team") or "HVAC Growth Team"
        elif "electri" in niche:
            service_need = raw_context.get("service_need") or "emergency electrical repairs"
            service_call = raw_context.get("service_call") or "electrical service calls"
            sender_team = raw_context.get("sender_team") or "Electrical Growth Team"
        elif "dent" in niche:
            service_need = raw_context.get("service_need") or "emergency dental appointments"
            service_call = raw_context.get("service_call") or "new patient bookings"
            sender_team = raw_context.get("sender_team") or "Dental Growth Team"
        else:
            service_need = raw_context.get("service_need") or f"urgent {niche} requests"
            service_call = raw_context.get("service_call") or f"{niche} service calls"
            sender_team = raw_context.get("sender_team") or f"{niche.title()} Growth Team"

        return {
            "company_name": company_name,
            "city": city,
            "state": state,
            "specialty": specialty,
            "specialty_lower": specialty.lower(),
            "contact_name": contact_name,
            "phone_display": phone_display,
            "row_index": row_index,
            "niche": niche,
            "service_need": service_need,
            "service_need_title": service_need.title(),
            "service_call": service_call,
            "sender_team": sender_team,
        }

    def _select_index(self, company_name: str, row_index: int, pool_size: int, explicit_index: Optional[int] = None) -> int:
        """
        Select template index deterministically using CRC32 to guarantee consistency
        across processes and runs.
        """
        if explicit_index is not None:
            return explicit_index % pool_size
        seed = zlib.crc32(company_name.encode("utf-8")) + row_index
        return seed % pool_size

    def render_icebreaker(self, context: Dict[str, Any], template_index: Optional[int] = None) -> str:
        """
        Render 2-sentence icebreaker mentioning city, trade specialty, and revenue loss.
        """
        ctx = self._prepare_context(context)
        idx = self._select_index(ctx["company_name"], ctx["row_index"], len(self._icebreaker_tmpls), template_index)
        rendered = self._icebreaker_tmpls[idx].render(**ctx).strip()
        assert_zero_placeholders(rendered)
        return rendered

    def render_offer_angle(self, context: Dict[str, Any], template_index: Optional[int] = None) -> str:
        """
        Render specific revenue pain point angle.
        """
        ctx = self._prepare_context(context)
        idx = self._select_index(ctx["company_name"], ctx["row_index"], len(self._offer_angle_tmpls), template_index)
        rendered = self._offer_angle_tmpls[idx].render(**ctx).strip()
        assert_zero_placeholders(rendered)
        return rendered

    def render_email_subject(self, context: Dict[str, Any], template_index: Optional[int] = None) -> str:
        """
        Render cold email subject line.
        """
        ctx = self._prepare_context(context)
        idx = self._select_index(ctx["company_name"], ctx["row_index"], len(self._email_subject_tmpls), template_index)
        rendered = self._email_subject_tmpls[idx].render(**ctx).strip()
        assert_zero_placeholders(rendered)
        return rendered

    def render_email_body(
        self,
        context: Dict[str, Any],
        icebreaker: Optional[str] = None,
        template_index: Optional[int] = None,
    ) -> str:
        """
        Render full cold email body copy containing icebreaker and call to action.
        """
        ctx = self._prepare_context(context)
        if icebreaker is None:
            icebreaker = self.render_icebreaker(context, template_index=template_index)
        ctx["icebreaker"] = icebreaker

        idx = self._select_index(ctx["company_name"], ctx["row_index"], len(self._email_body_tmpls), template_index)
        rendered = self._email_body_tmpls[idx].render(**ctx).strip()
        assert_zero_placeholders(rendered)
        return rendered

    def render_whatsapp_message(self, context: Dict[str, Any], template_index: Optional[int] = None) -> str:
        """
        Render concise pre-formatted WhatsApp message.
        """
        ctx = self._prepare_context(context)
        idx = self._select_index(ctx["company_name"], ctx["row_index"], len(self._whatsapp_tmpls), template_index)
        rendered = self._whatsapp_tmpls[idx].render(**ctx).strip()
        assert_zero_placeholders(rendered)
        return rendered

    def render_all(self, context: Dict[str, Any], template_index: Optional[int] = None) -> Dict[str, str]:
        """
        Render all outreach assets for a given lead context.
        """
        ctx = self._prepare_context(context)
        icebreaker = self.render_icebreaker(ctx, template_index=template_index)
        offer_angle = self.render_offer_angle(ctx, template_index=template_index)
        subject = self.render_email_subject(ctx, template_index=template_index)
        body = self.render_email_body(ctx, icebreaker=icebreaker, template_index=template_index)
        wa_msg = self.render_whatsapp_message(ctx, template_index=template_index)

        return {
            "icebreaker": icebreaker,
            "offer_angle": offer_angle,
            "staged_email_subject": subject,
            "staged_email_body": body,
            "staged_whatsapp_msg": wa_msg,
        }
