"""
AI Personalization & Hook Generator Engine (Agent 3).

Orchestrates:
- Context normalization from CRM records or raw leads
- Dual-engine content generation (LLM with deterministic Jinja2 fallback)
- Strict acceptance criteria and invariant validation:
  * Sentence 1 references exact contractor city/metro and trade specialty
  * Sentence 2 highlights revenue lost to local competitors ranking on Google Maps
    and organic search for emergency roof repairs
  * Exactly 2 complete sentences in icebreaker
  * Zero placeholder leakage
- Staging columns mapping (Cols V through Z + Cols R & S)
- WhatsApp wa.me click-to-chat URL construction
- Staged Google Sheets updates via SheetsClient
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

from src.config import SHEET_ID, SHEET_TAB
from src.crm.schema import crm_row_to_record, lead_to_crm_row
from src.crm.sheets_client import SheetsClient
from src.models import CRMRecord, OutreachDraft, QualifiedLead, RawLead
from src.personalizer.llm_engine import (
    GeneratedOutreachContent,
    LLMEngine,
    validate_icebreaker_invariants,
)
from src.personalizer.template_engine import (
    TemplateEngine,
    assert_zero_placeholders,
)


from src.scraper.normalizer import clean_phone_10digit


def clean_phone_digits(raw_phone: Any) -> str:
    """
    Extract 10-digit base phone number, stripping extensions and country codes.
    Returns 10-digit string (or empty string if invalid/missing).
    """
    if not raw_phone:
        return ""
    phone_str = str(raw_phone).strip()
    if phone_str.startswith("+") and not (phone_str.startswith("+1") or phone_str.startswith("+ 1")):
        return ""
    cleaned = clean_phone_10digit(phone_str)
    if cleaned:
        return cleaned
    # Fallback for dummy/unorthodox test numbers (e.g. 555-000-0000)
    s = re.split(r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+", phone_str)[0]
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[:10] if len(digits) >= 10 else digits


def build_whatsapp_link(phone: str, message: str) -> str:
    """
    Construct pre-populated WhatsApp click-to-chat URL adhering to:
    https://wa.me/1{phone}?text={encoded_msg}
    Returns empty string if phone is missing, empty, or has fewer than 10 digits.
    Strips phone extensions and international US country prefix (+1).
    """
    if not phone or not isinstance(phone, str) or not phone.strip():
        return ""

    digits = clean_phone_digits(phone)
    if len(digits) == 10:
        phone_e164 = f"1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        phone_e164 = digits
    else:
        return ""

    encoded_msg = urllib.parse.quote(message)
    return f"https://wa.me/{phone_e164}?text={encoded_msg}"


def extract_lead_context(
    lead: Union[CRMRecord, QualifiedLead, RawLead, Dict[str, Any]]
) -> Tuple[CRMRecord, Dict[str, Any]]:
    """
    Normalize any supported lead format into a validated CRMRecord
    and template context dictionary.
    """
    if isinstance(lead, CRMRecord) or (hasattr(lead, "company_name") and hasattr(lead, "location") and hasattr(lead, "industry_niche")):
        if isinstance(lead, CRMRecord):
            crm_rec = lead
        else:
            crm_rec = CRMRecord(
                row_index=int(getattr(lead, "row_index", 14)),
                lead_status=getattr(lead, "lead_status", "Not Contacted"),
                priority=getattr(lead, "priority", "⚡ Medium"),
                company_name=str(getattr(lead, "company_name")),
                website=str(getattr(lead, "website", "None (No Website)")),
                industry_niche=str(getattr(lead, "industry_niche", "Residential Roofing & Repairs")),
                company_size=str(getattr(lead, "company_size", "1-10")),
                contact_first_name=str(getattr(lead, "contact_first_name", "Roofing Team")),
                contact_last_name=str(getattr(lead, "contact_last_name", "Contractor")),
                job_title=str(getattr(lead, "job_title", "Owner / Contractor")),
                work_email=str(getattr(lead, "work_email", "Call: (555) 000-0000")),
                email_verification=str(getattr(lead, "email_verification", "Unverified")),
                linkedin_profile=str(getattr(lead, "linkedin_profile", "")),
                location=str(getattr(lead, "location")),
                outreach_channel=str(getattr(lead, "outreach_channel", "Cold Call")),
                est_deal_value=int(getattr(lead, "est_deal_value", 4000)),
                notes_and_next_steps=str(getattr(lead, "notes_and_next_steps", "")),
            )

        # Parse city and state from location string e.g. "Tyler, TX (CST)"
        loc_str = crm_rec.location or ""
        m_loc = re.match(r"^([^,]+),\s*([A-Za-z]{2})", loc_str.strip())
        if m_loc:
            city = m_loc.group(1).strip()
            state = m_loc.group(2).strip()
        else:
            city = loc_str.split(",")[0].strip() if "," in loc_str else loc_str.strip()
            state = ""

        # Extract phone digits from work_email or notes
        phone_match = re.search(
            r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?:\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+)?",
            crm_rec.work_email + " " + crm_rec.notes_and_next_steps,
            re.IGNORECASE,
        )
        if phone_match:
            raw_phone = phone_match.group(0)
            cleaned_phone = clean_phone_digits(raw_phone)
            phone_display = raw_phone
        else:
            cleaned_phone = ""
            phone_display = ""

        context = {
            "company_name": crm_rec.company_name,
            "city": city,
            "state": state,
            "specialty": crm_rec.industry_niche,
            "contact_name": crm_rec.contact_first_name,
            "cleaned_phone": cleaned_phone,
            "phone_display": phone_display,
            "row_index": crm_rec.row_index,
        }
        return crm_rec, context

    elif hasattr(lead, "business_name"):
        b_name = getattr(lead, "business_name")
        c_phone = getattr(lead, "cleaned_phone", "")
        p_disp = getattr(lead, "phone_display", "")
        clean_p = clean_phone_digits(c_phone)
        if not clean_p and p_disp:
            clean_p = clean_phone_digits(p_disp)
        phone_display = p_disp or (f"({clean_p[:3]}) {clean_p[3:6]}-{clean_p[6:]}" if len(clean_p) == 10 else "(555) 000-0000")
        city = getattr(lead, "city", "your area")
        state = getattr(lead, "state", "TX")
        if not state or len(state) != 2:
            state = "TX"
        specialty = getattr(lead, "specialty", "Residential Roofing & Repairs")
        row_idx = getattr(lead, "row_index", 14)

        raw = RawLead(
            business_name=b_name,
            cleaned_phone=clean_p,
            phone_display=phone_display,
            city=city,
            state=state,
            zip_code=getattr(lead, "zip_code", "00000") or "00000",
            specialty=specialty,
            website_status=getattr(lead, "website_status", "None (No Website)"),
            website_url=getattr(lead, "website_url", None),
            place_url=getattr(lead, "place_url", ""),
        )
        crm_row = lead_to_crm_row(raw, row_index=row_idx)
        crm_rec = crm_row_to_record(crm_row, row_index=row_idx)
        context = {
            "company_name": b_name,
            "city": city,
            "state": state,
            "specialty": specialty,
            "contact_name": "Team",
            "cleaned_phone": clean_p,
            "phone_display": phone_display,
            "row_index": row_idx,
        }
        return crm_rec, context

    elif isinstance(lead, dict):
        if "lead_status" in lead and "company_name" in lead and "location" in lead:
            try:
                crm_rec = CRMRecord.model_validate(lead)
                return extract_lead_context(crm_rec)
            except Exception:
                pass

        company = lead.get("company_name") or lead.get("business_name") or lead.get("company") or "Your Roofing Team"
        city = lead.get("city") or "your area"
        state = lead.get("state") or "TX"
        if not state or len(state) != 2:
            state = "TX"
        specialty = lead.get("specialty") or lead.get("industry_niche") or lead.get("niche") or "Residential Roofing & Repairs"
        phone = lead.get("cleaned_phone") or lead.get("phone") or lead.get("phone_display") or ""
        clean_p = clean_phone_digits(phone)
        phone_disp = lead.get("phone_display") or (f"({clean_p[:3]}) {clean_p[3:6]}-{clean_p[6:]}" if len(clean_p) == 10 else "(555) 000-0000")
        row_idx = int(lead.get("row_index", 14))

        raw_temp = RawLead(
            business_name=company,
            cleaned_phone=clean_p,
            phone_display=phone_disp,
            city=city,
            state=state,
            zip_code=lead.get("zip_code") or "00000",
            specialty=specialty,
            website_status=lead.get("website_status", "None (No Website)"),
            website_url=lead.get("website_url"),
            place_url=lead.get("place_url", ""),
        )
        crm_row = lead_to_crm_row(raw_temp, row_index=row_idx)
        crm_rec = crm_row_to_record(crm_row, row_index=row_idx)
        contact_name = lead.get("contact_first_name") or lead.get("first_name") or "Team"
        context = {
            "company_name": company,
            "city": city,
            "state": state,
            "specialty": specialty,
            "contact_name": contact_name,
            "cleaned_phone": clean_p,
            "phone_display": phone_disp,
            "row_index": row_idx,
        }
        return crm_rec, context

    raise TypeError(f"Unsupported lead type: {type(lead)}")


class PersonalizerGenerator:
    """
    AI Personalization & Hook Generator service adhering to Milestone 3 requirements.
    """

    def __init__(
        self,
        engine: Optional[Union[LLMEngine, TemplateEngine]] = None,
        template_engine: Optional[TemplateEngine] = None,
    ) -> None:
        self.template_engine = template_engine or TemplateEngine()
        self.engine = engine or LLMEngine(template_engine=self.template_engine)

    def generate(
        self,
        lead: Union[CRMRecord, QualifiedLead, RawLead, Dict[str, Any]],
        template_index: Optional[int] = None,
    ) -> OutreachDraft:
        """
        Generate bespoke outreach draft package for a single contractor lead.
        """
        crm_record, context = extract_lead_context(lead)

        # Generate content via active engine
        if isinstance(self.engine, TemplateEngine):
            content_dict = self.engine.render_all(context, template_index=template_index)
            content = GeneratedOutreachContent.model_validate(content_dict)
        elif isinstance(self.engine, LLMEngine):
            content = self.engine.generate(context, template_index=template_index)
        else:
            # Duck-typed custom engine
            if hasattr(self.engine, "generate"):
                content = self.engine.generate(context)
                if not isinstance(content, GeneratedOutreachContent):
                    content = GeneratedOutreachContent.model_validate(content)
            elif hasattr(self.engine, "render_all"):
                content_dict = self.engine.render_all(context, template_index=template_index)
                content = GeneratedOutreachContent.model_validate(content_dict)
            else:
                fallback_dict = self.template_engine.render_all(context, template_index=template_index)
                content = GeneratedOutreachContent.model_validate(fallback_dict)

        # Enforce zero-placeholder validation across all generated copy
        assert_zero_placeholders(content.icebreaker)
        assert_zero_placeholders(content.offer_angle)
        assert_zero_placeholders(content.staged_email_subject)
        assert_zero_placeholders(content.staged_email_body)
        assert_zero_placeholders(content.staged_whatsapp_msg)

        # Enforce strict invariant validation on icebreaker
        validate_icebreaker_invariants(
            content.icebreaker,
            city=context["city"],
            specialty=context["specialty"],
        )

        # Construct WhatsApp click-to-chat URL
        staged_wame_url = build_whatsapp_link(
            phone=context.get("cleaned_phone", ""),
            message=content.staged_whatsapp_msg,
        )

        # Return validated OutreachDraft interface contract
        return OutreachDraft(
            crm_record=crm_record,
            icebreaker=content.icebreaker,
            offer_angle=content.offer_angle,
            staged_email_subject=content.staged_email_subject,
            staged_email_body=content.staged_email_body,
            staged_whatsapp_msg=content.staged_whatsapp_msg,
            staged_wame_url=staged_wame_url,
            approval_status="Drafted / Ready for Review",
        )

    def generate_batch(
        self,
        leads: List[Union[CRMRecord, QualifiedLead, RawLead, Dict[str, Any]]],
    ) -> List[OutreachDraft]:
        """
        Generate outreach draft packages for a batch of contractor leads.
        """
        return [self.generate(lead) for lead in leads]

    def stage_to_sheet(
        self,
        drafts: Union[OutreachDraft, List[OutreachDraft]],
        sheets_client: SheetsClient,
        sheet_id: str = SHEET_ID,
        tab_name: str = SHEET_TAB,
        update_crm_columns: bool = True,
    ) -> Any:
        """
        Stage generated draft(s) into Google Sheet columns V-Z (and R-S if update_crm_columns=True).
        """
        if isinstance(drafts, list):
            return stage_drafts_to_sheet(
                drafts,
                sheets_client=sheets_client,
                sheet_id=sheet_id,
                tab_name=tab_name,
                update_crm_columns=update_crm_columns,
            )
        return stage_draft_to_sheet(
            drafts,
            sheets_client=sheets_client,
            sheet_id=sheet_id,
            tab_name=tab_name,
            update_crm_columns=update_crm_columns,
        )


def stage_draft_to_sheet(
    draft: OutreachDraft,
    sheets_client: SheetsClient,
    sheet_id: str = SHEET_ID,
    tab_name: str = SHEET_TAB,
    update_crm_columns: bool = True,
) -> Dict[str, Any]:
    """
    Write staging fields for a single draft to Google Sheet Leads Tracker.
    - Columns R & S: Personalized Icebreaker and Offer Angle
    - Columns V through Z: Email Subject, Email Body, WhatsApp Msg, wa.me Link, Approval Status
    """
    row_idx = draft.crm_record.row_index
    results: Dict[str, Any] = {}

    if update_crm_columns:
        range_rs = f"'{tab_name}'!R{row_idx}:S{row_idx}"
        res_rs = sheets_client.update_range(
            sheet_id=sheet_id,
            range_str=range_rs,
            values=[[draft.icebreaker, draft.offer_angle]],
        )
        results["crm_personalization_update"] = res_rs

    range_vz = f"'{tab_name}'!V{row_idx}:Z{row_idx}"
    res_vz = sheets_client.update_range(
        sheet_id=sheet_id,
        range_str=range_vz,
        values=[[
            draft.staged_email_subject,
            draft.staged_email_body,
            draft.staged_whatsapp_msg,
            draft.staged_wame_url,
            draft.approval_status,
        ]],
    )
    results["staging_columns_update"] = res_vz

    return results


def stage_drafts_to_sheet(
    drafts: List[OutreachDraft],
    sheets_client: SheetsClient,
    sheet_id: str = SHEET_ID,
    tab_name: str = SHEET_TAB,
    update_crm_columns: bool = True,
) -> List[Dict[str, Any]]:
    """
    Write staging fields for multiple drafts to Google Sheet.
    """
    return [
        stage_draft_to_sheet(
            draft=d,
            sheets_client=sheets_client,
            sheet_id=sheet_id,
            tab_name=tab_name,
            update_crm_columns=update_crm_columns,
        )
        for d in drafts
    ]
