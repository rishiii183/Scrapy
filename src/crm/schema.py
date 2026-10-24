"""
21-Column CRM Schema Mapping and Data Validation for Google Sheets Leads Tracker.

Adheres strictly to Leads Tracker Columns A through U:
- Col A: Lead Status
- Col B: Priority (mandatory emoji prefix: 🔥 High, ⚡ Medium, ❄️ Low)
- Col C: Company Name
- Col D: Website
- Col E: Industry / Niche
- Col F: Company Size (prefixed string '1-10 to prevent spreadsheet date bugs)
- Col G: Contact First Name
- Col H: Contact Last Name
- Col I: Job Title
- Col J: Work Email
- Col K: Email Verification
- Col L: LinkedIn Profile
- Col M: Location
- Col N: Outreach Channel
- Col O: Touch 1 Date
- Col P: Last Follow-Up Date
- Col Q: Next Action Due
- Col R: Personalized Icebreaker
- Col S: Offer Angle / Pain Point
- Col T: Est. Deal Value ($) (unformatted numeric integer for =SUM formulas)
- Col U: Notes & Next Steps
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from src.models import RawLead, QualifiedLead, CRMRecord

CRM_COLUMNS: List[str] = [
    "Lead Status",
    "Priority",
    "Company Name",
    "Website",
    "Industry / Niche",
    "Company Size",
    "Contact First Name",
    "Contact Last Name",
    "Job Title",
    "Work Email",
    "Email Verification",
    "LinkedIn Profile",
    "Location",
    "Outreach Channel",
    "Touch 1 Date",
    "Last Follow-Up Date",
    "Next Action Due",
    "Personalized Icebreaker",
    "Offer Angle / Pain Point",
    "Est. Deal Value ($)",
    "Notes & Next Steps",
]

ALLOWED_LEAD_STATUSES: List[str] = [
    "Not Contacted",
    "Contacted (Touch 1)",
    "Follow-up 1",
    "Follow-up 2",
    "Follow-up 3",
    "Call Booked",
    "Proposal Sent",
    "Closed Won",
    "Closed Lost",
    "Unresponsive",
]

ALLOWED_PRIORITIES: List[str] = [
    "🔥 High",
    "⚡ Medium",
    "❄️ Low",
]

ALLOWED_EMAIL_VERIFICATIONS: List[str] = [
    "Verified",
    "Catch-all",
    "Unverified",
    "Bounced",
]

ALLOWED_OUTREACH_CHANNELS: List[str] = [
    "Cold Email",
    "LinkedIn DM",
    "Cold Call",
    "Twitter/X DM",
]

STATE_TIMEZONES: Dict[str, str] = {
    "TX": "CST",
    "FL": "EST",
    "OH": "EST",
    "GA": "EST",
    "AZ": "MST",
}


def get_state_timezone(state_code: str) -> str:
    """Return standard timezone abbreviation for US state code."""
    clean = (state_code or "").strip().upper()
    return STATE_TIMEZONES.get(clean, "EST")


def format_location_display(city: str, state: str) -> str:
    """Format Location string adhering to '<City>, <State> (<Timezone>)'."""
    clean_city = (city or "").strip()
    clean_state = (state or "").strip().upper()
    tz = get_state_timezone(clean_state)
    return f"{clean_city}, {clean_state} ({tz})"


def validate_crm_row(row: List[Any]) -> bool:
    """
    Perform strict validation on a 21-element CRM row array.
    Raises ValueError with descriptive context if any cell violates schema rules.
    """
    if not isinstance(row, (list, tuple)):
        raise ValueError(f"CRM row must be a list or tuple, got {type(row)}.")

    if len(row) < 21:
        raise ValueError(f"CRM row must contain at least 21 elements (Cols A through U), got {len(row)}.")

    lead_status = row[0]
    if lead_status not in ALLOWED_LEAD_STATUSES:
        raise ValueError(
            f"Invalid Lead Status '{lead_status}'. Must be one of: {ALLOWED_LEAD_STATUSES}"
        )

    priority = row[1]
    if priority not in ALLOWED_PRIORITIES:
        raise ValueError(
            f"Invalid Priority '{priority}'. Must be one of {ALLOWED_PRIORITIES} with mandatory emoji prefix."
        )

    company_size = str(row[5])
    if not company_size or not isinstance(row[5], str):
        raise ValueError("Company Size must be a string (e.g. '1-10') to prevent date conversion.")

    email_verification = row[10]
    if email_verification not in ALLOWED_EMAIL_VERIFICATIONS:
        raise ValueError(
            f"Invalid Email Verification '{email_verification}'. Must be one of: {ALLOWED_EMAIL_VERIFICATIONS}"
        )

    outreach_channel = row[13]
    if outreach_channel not in ALLOWED_OUTREACH_CHANNELS:
        raise ValueError(
            f"Invalid Outreach Channel '{outreach_channel}'. Must be one of: {ALLOWED_OUTREACH_CHANNELS}"
        )

    deal_value = row[19]
    if isinstance(deal_value, bool) or not isinstance(deal_value, int) or deal_value <= 0:
        raise ValueError(
            f"Invalid Est. Deal Value '{deal_value}'. Must be a pure positive numeric integer (e.g. 4000), not formatted currency."
        )

    return True


def lead_to_crm_row(
    lead: Union[RawLead, QualifiedLead],
    row_index: int = 14,
    icebreaker: str = "",
    offer_angle: str = "",
    override_priority: Optional[str] = None,
    override_deal_value: Optional[int] = None,
) -> List[Any]:
    """
    Convert a RawLead or QualifiedLead into a 21-element list matching Columns A through U.
    Ensures strict adherence to dropdown validation, emoji prefixes, and integer deal values.
    """
    from src.crm.lead_scorer import score_lead_record

    # Lead Status (Col A)
    status = "Not Contacted"

    # Priority & Deal Value (Col B & Col T)
    if override_priority and override_deal_value:
        priority = override_priority
        deal_value = override_deal_value
    else:
        scored_priority, scored_deal = score_lead_record(lead)
        priority = override_priority or (
            lead.priority if isinstance(lead, QualifiedLead) and lead.priority in ALLOWED_PRIORITIES else scored_priority
        )
        deal_value = override_deal_value or scored_deal

    # Ensure emoji prefix
    if priority not in ALLOWED_PRIORITIES:
        if "high" in str(priority).lower():
            priority = "🔥 High"
        elif "low" in str(priority).lower():
            priority = "❄️ Low"
        else:
            priority = "⚡ Medium"

    # Company Name (Col C)
    company_name = lead.business_name.strip()

    # Website (Col D)
    website = lead.website_status or "None (No Website)"

    # Industry / Niche (Col E)
    industry_niche = lead.specialty or "Residential Roofing & Repairs"

    # Company Size (Col F) - prefixed with ' to prevent sheet auto date parsing
    company_size = "'1-10"

    # Contact Info (Cols G, H, I)
    first_name = "Roofing Team"
    last_name = "Contractor"
    job_title = "Owner / Contractor"

    # Work Email & Outreach Channel (Cols J, K, N)
    phone_disp = lead.phone_display or f"({lead.cleaned_phone[:3]}) {lead.cleaned_phone[3:6]}-{lead.cleaned_phone[6:]}"
    work_email = f"Call: {phone_disp}"
    email_verification = "Unverified"
    outreach_channel = "Cold Call"

    # LinkedIn / Place Profile (Col L)
    linkedin_profile = lead.place_url or lead.website_url or ""

    # Location (Col M)
    location = format_location_display(lead.city, lead.state)

    # Outreach Dates (Cols O, P, Q)
    touch_1_date = ""
    last_follow_up_date = ""
    next_action_due = ""

    # Personalization Staging (Cols R, S)
    pers_icebreaker = icebreaker or ""
    pers_offer_angle = offer_angle or ""

    # Notes & Next Steps (Col U)
    notes = f"Phone: {phone_disp}. Candidate for high-converting landing page."

    row = [
        status,                # Col A: Lead Status
        priority,              # Col B: Priority
        company_name,          # Col C: Company Name
        website,               # Col D: Website
        industry_niche,        # Col E: Industry / Niche
        company_size,          # Col F: Company Size
        first_name,            # Col G: Contact First Name
        last_name,             # Col H: Contact Last Name
        job_title,             # Col I: Job Title
        work_email,            # Col J: Work Email
        email_verification,    # Col K: Email Verification
        linkedin_profile,      # Col L: LinkedIn Profile
        location,              # Col M: Location
        outreach_channel,      # Col N: Outreach Channel
        touch_1_date,          # Col O: Touch 1 Date
        last_follow_up_date,   # Col P: Last Follow-Up Date
        next_action_due,       # Col Q: Next Action Due
        pers_icebreaker,       # Col R: Personalized Icebreaker
        pers_offer_angle,      # Col S: Offer Angle / Pain Point
        int(deal_value),       # Col T: Est. Deal Value ($)
        notes,                 # Col U: Notes & Next Steps
    ]

    validate_crm_row(row)
    return row


def crm_row_to_record(row: List[Any], row_index: int = 14) -> CRMRecord:
    """
    Convert a 21-element CRM row array into a validated CRMRecord Pydantic model.
    """
    validate_crm_row(row)
    return CRMRecord(
        row_index=row_index,
        lead_status=str(row[0]),
        priority=str(row[1]),
        company_name=str(row[2]),
        website=str(row[3]),
        industry_niche=str(row[4]),
        company_size=str(row[5]).lstrip("'"),
        contact_first_name=str(row[6]),
        contact_last_name=str(row[7]),
        job_title=str(row[8]),
        work_email=str(row[9]),
        email_verification=str(row[10]),
        linkedin_profile=str(row[11]),
        location=str(row[12]),
        outreach_channel=str(row[13]),
        est_deal_value=int(row[19]),
        notes_and_next_steps=str(row[20]),
    )
