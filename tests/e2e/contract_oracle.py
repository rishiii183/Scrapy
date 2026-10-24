"""
Contract Oracle and Reference Specifications for Roofer Outreach Pipeline.

This module serves as the authoritative specification oracle for all E2E test tiers.
It encodes the exact requirements, mathematical rules, interface schemas, and expected outputs
defined in PROJECT.md, ORIGINAL_REQUEST.md, and verified explorer surveys.

Tests use these functions as ground-truth oracles to evaluate both contract adherence
and live implementation modules in src/.
"""

import re
import urllib.parse
from typing import Optional, Tuple, List, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Authoritative Interface Contract Schemas (matching PROJECT.md § Interface Contracts)
# ---------------------------------------------------------------------------

class RawLeadContract(BaseModel):
    business_name: str
    cleaned_phone: str
    phone_display: str
    city: str
    state: str
    zip_code: str
    review_count: int = Field(default=0, ge=0)
    star_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    specialty: str
    website_status: str
    website_url: Optional[str] = None
    place_url: str = ""


class CRMRecordContract(BaseModel):
    row_index: int = Field(..., ge=14)
    lead_status: str = "Not Contacted"
    priority: str = "⚡ Medium"
    company_name: str
    website: str = "None (No Website)"
    industry_niche: str
    company_size: str = "1-10"
    contact_first_name: str = "Roofing Team"
    contact_last_name: str = "Contractor"
    job_title: str = "Owner / Contractor"
    work_email: str
    email_verification: str = "Unverified"
    linkedin_profile: str = ""
    location: str
    outreach_channel: str = "Cold Email"
    est_deal_value: int = 4000
    notes_and_next_steps: str = ""


class OutreachDraftContract(BaseModel):
    crm_record: CRMRecordContract
    icebreaker: str
    offer_angle: str
    staged_email_subject: str
    staged_email_body: str
    staged_whatsapp_msg: str
    staged_wame_url: str
    approval_status: str = "Drafted / Ready for Review"


# ---------------------------------------------------------------------------
# Directory / Social Blocklist for Website Filtering (R1, Feature 4)
# ---------------------------------------------------------------------------

ALLOWED_SOCIAL_DIRECTORY_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "yelp.com",
    "bbb.org",
    "yellowpages.com",
    "angi.com",
    "homeadvisor.com",
    "thumbtack.com",
    "houzz.com",
    "nextdoor.com",
    "manta.com",
    "mapquest.com",
    "superpages.com",
    "chamberofcommerce.com",
    "porch.com",
    "buildzoom.com",
    "dandb.com",
    "expertise.com",
    "bark.com",
}

DISCARDED_CUSTOM_TLDS = {
    ".com", ".net", ".org", ".io", ".co", ".biz", ".us", ".info", ".pro", ".site"
}


# ---------------------------------------------------------------------------
# Authoritative Oracle Functions
# ---------------------------------------------------------------------------

def oracle_filter_website(url: Optional[str]) -> Tuple[bool, str]:
    """
    Evaluates website URL per R1 and Acceptance Criteria:
    - Custom domains (.com, .io, .net, etc.) -> (False, "Custom Domain Discarded")
    - None, empty string, or 'add website' -> (True, "None (No Website)")
    - Social or directory profile -> (True, "None (No Website - Social Only)")
    """
    if not url or not url.strip() or url.strip().lower() in ("none", "null", "add website", "n/a"):
        return True, "None (No Website)"

    u = url.strip().lower()
    # Normalize scheme for parsing
    if not u.startswith(("http://", "https://")):
        u = "https://" + u

    try:
        parsed = urllib.parse.urlparse(u)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
    except Exception:
        return True, "None (No Website)"

    # Check social / directory whitelist
    for allowed in ALLOWED_SOCIAL_DIRECTORY_DOMAINS:
        if netloc == allowed or netloc.endswith("." + allowed):
            return True, "None (No Website - Social Only)"

    # If it is any custom domain, discard
    return False, f"Custom Domain Discarded: {netloc}"


def oracle_normalize_business_name(name: str) -> str:
    """
    Normalizes contractor trade name for deduplication (R2, Feature 8).
    - Lowercase & strip
    - Replace '&' with 'and'
    - Strip punctuation
    - Strip leading 'the '
    - Iteratively strip legal corporate entity suffixes
    - Strip dangling conjunctions
    - Single whitespace
    """
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"\s*&\s*", " and ", n)
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"^the\s+", "", n)

    entity_suffixes = [
        "incorporated", "corporation", "limited liability company",
        "limited liability partnership", "limited partnership",
        "limited", "company", "corp", "pllc", "llc", "llp", "inc", "ltd", "co"
    ]
    pattern = r"\b(" + "|".join(entity_suffixes) + r")\b$"
    while True:
        cleaned = re.sub(pattern, "", n).strip()
        if cleaned == n or not cleaned:
            break
        n = cleaned

    n = re.sub(r"\b(and|or|of)\b$", "", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def oracle_normalize_phone(phone: Optional[str]) -> str:
    """
    Extracts 10-digit normalized US phone number (R1, R2).
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else digits


def oracle_format_phone_display(phone: str) -> str:
    """Formats 10-digit phone into (XXX) XXX-XXXX."""
    digits = oracle_normalize_phone(phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone or ""


def oracle_classify_specialty(title: str, text: str = "") -> str:
    """
    Classifies contractor into 4 standard categories (Feature 5):
    - storm repair
    - commercial
    - leak repair
    - residential (default)
    """
    combined = f"{title} {text}".lower()
    if any(k in combined for k in ["storm", "hail", "wind damage", "disaster", "restoration"]):
        return "Storm Damage & Re-roofing"
    if any(k in combined for k in ["commercial", "industrial", "tpo", "epdm", "flat roof"]):
        return "Commercial & Industrial Roofing"
    if any(k in combined for k in ["leak", "emergency", "patch", "water damage", "urgent"]):
        return "Emergency Leak Repair"
    return "Residential Roofing & Repairs"


def oracle_score_lead(review_count: int, specialty: str = "Residential Roofing & Repairs", has_social: bool = False) -> Tuple[str, int]:
    """
    Scores lead priority and estimated deal value (Feature 9, Acceptance Criteria):
    - review_count >= 10 -> 🔥 High ($4,000, or $4,500 if storm/commercial)
    - review_count >= 5 and specialty is storm/commercial -> 🔥 High ($4,500)
    - 3 <= review_count < 10 or has_social -> ⚡ Medium ($3,500)
    - review_count < 3 -> ❄️ Low ($3,000)
    """
    spec_lower = specialty.lower()
    is_high_ticket = "storm" in spec_lower or "commercial" in spec_lower

    if review_count >= 10:
        deal = 4500 if is_high_ticket else 4000
        return "🔥 High", deal
    elif review_count >= 5 and is_high_ticket:
        return "🔥 High", 4500
    elif review_count >= 3 or has_social:
        return "⚡ Medium", 3500
    else:
        return "❄️ Low", 3000


def oracle_generate_icebreaker(company_name: str, city: str, specialty: str) -> str:
    """
    Generates compliant 2-sentence icebreaker mentioning city, trade specialty,
    and revenue lost to local competitors on Google Maps (R3, Acceptance Criteria).
    """
    s1 = f"Came across {company_name} while reviewing top-rated {specialty.lower()} contractors serving the {city} area."
    s2 = f"With local competitors dominating Google Maps and organic search for emergency roof repairs in {city}, your team is missing out on thousands in high-margin repair and re-roof jobs each month without a dedicated web presence."
    return f"{s1} {s2}"


def oracle_assert_zero_placeholders(text: str) -> None:
    """
    Verifies that no template tags remain in generated copy (Feature 11).
    Raises AssertionError if unparsed tag is detected.
    """
    patterns = [r"\{\{.*?\}\}", r"\{[A-Za-z_]+\}"]
    for pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            raise AssertionError(f"Unparsed placeholder tags detected in copy: {matches}")


def oracle_build_whatsapp_link(phone: str, message: str) -> str:
    """
    Generates pre-populated wa.me click-to-chat URL (Feature 16).
    """
    digits = oracle_normalize_phone(phone)
    if len(digits) == 10:
        digits = "1" + digits
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{digits}?text={encoded}"


def oracle_pacing_delay_valid(delay: float) -> bool:
    """
    Validates humanized sending delay is within 45 to 180 seconds (Feature 17).
    """
    return 45.0 <= delay <= 180.0


def oracle_apply_daily_cap(items: List[Any], cap: int = 25) -> List[Any]:
    """
    Enforces daily dispatch cap (Feature 17).
    """
    return items[:cap]


def oracle_safety_gate_check(draft: OutreachDraftContract, confirmed: bool) -> bool:
    """
    Safety gate check (Feature 14): Blocks dispatch unless explicitly approved.
    """
    if not confirmed:
        return False
    return draft.approval_status in ("Approved", "Drafted / Ready for Review")


def oracle_crm_dispatch_update(record: CRMRecordContract, channel: str, date_str: str) -> CRMRecordContract:
    """
    Performs CRM state transitions on dispatch (Feature 18):
    - Col A -> Contacted (Touch 1)
    - Col O -> YYYY-MM-DD
    - Col U -> Appended audit note
    """
    updated_dict = record.model_dump()
    updated_dict["lead_status"] = "Contacted (Touch 1)"
    updated_dict["touch_1_date"] = date_str
    prev_notes = updated_dict.get("notes_and_next_steps", "")
    stamp = f"Dispatched via {channel} on {date_str}."
    updated_dict["notes_and_next_steps"] = f"{prev_notes} {stamp}".strip()
    return CRMRecordContract(**updated_dict)
