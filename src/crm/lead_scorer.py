"""
Lead Scoring and Priority Tagging Engine for Roofer Outreach CRM.

Defines rules for:
- Priority Tier assignment (🔥 High, ⚡ Medium, ❄️ Low)
- Deal Value calculation ($3,000 to $4,500) based on review volume and trade specialty
"""

from typing import Tuple, Union
from src.models import RawLead, QualifiedLead

HIGH_PRIORITY_EMOJI = "🔥 High"
MEDIUM_PRIORITY_EMOJI = "⚡ Medium"
LOW_PRIORITY_EMOJI = "❄️ Low"

DEFAULT_DEAL_VALUE_HIGH_RESIDENTIAL = 4000
DEFAULT_DEAL_VALUE_HIGH_TICKET = 4500
DEFAULT_DEAL_VALUE_MEDIUM = 3500
DEFAULT_DEAL_VALUE_LOW = 3000


def is_high_ticket_specialty(specialty: str) -> bool:
    """Check if specialty is commercial or storm restoration (higher deal value)."""
    if not specialty:
        return False
    s_lower = specialty.lower()
    return any(k in s_lower for k in ["storm", "hail", "restoration", "commercial", "industrial", "tpo", "solar"])


def score_lead(
    review_count: int,
    specialty: str = "Residential Roofing & Repairs",
    has_social: bool = False,
) -> Tuple[str, int]:
    """
    Score lead priority and estimated deal value adhering to Feature 9 rules:
    - review_count >= 10: 🔥 High ($4,000, or $4,500 for storm/commercial)
    - review_count >= 5 and specialty is storm/commercial: 🔥 High ($4,500)
    - 3 <= review_count < 10 or has_social: ⚡ Medium ($3,500)
    - review_count < 3: ❄️ Low ($3,000)
    """
    count = max(0, int(review_count or 0))
    high_ticket = is_high_ticket_specialty(specialty)

    if count >= 10:
        deal = DEFAULT_DEAL_VALUE_HIGH_TICKET if high_ticket else DEFAULT_DEAL_VALUE_HIGH_RESIDENTIAL
        return HIGH_PRIORITY_EMOJI, deal
    elif count >= 5 and high_ticket:
        return HIGH_PRIORITY_EMOJI, DEFAULT_DEAL_VALUE_HIGH_TICKET
    elif count >= 3 or has_social:
        return MEDIUM_PRIORITY_EMOJI, DEFAULT_DEAL_VALUE_MEDIUM
    else:
        return LOW_PRIORITY_EMOJI, DEFAULT_DEAL_VALUE_LOW


def score_lead_record(lead: Union[RawLead, QualifiedLead]) -> Tuple[str, int]:
    """Score priority and deal value directly from a RawLead or QualifiedLead instance."""
    has_social = False
    if lead.website_status and "social" in lead.website_status.lower():
        has_social = True
    elif lead.website_url:
        has_social = True

    return score_lead(
        review_count=lead.review_count,
        specialty=lead.specialty,
        has_social=has_social,
    )
