"""
Data Models and Interface Contracts for Roofer Outreach Pipeline.

Defines Pydantic schemas across pipeline stages:
- M1 -> M2: RawLead & QualifiedLead
- M2 -> M3: CRMRecord
- M3 -> M4: OutreachDraft
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

VALID_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

US_STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


class RawLead(BaseModel):
    """
    Extracted contractor record from Google Maps search results.
    Direct interface contract output of Milestone 1 (Google Maps Extraction Engine).
    """
    business_name: str = Field(..., description="Legal or operating business name")
    cleaned_phone: str = Field(default="", description="10-digit normalized phone number (digits only)")
    phone_display: str = Field(..., description="Formatted phone number for display e.g. (903) 807-0683")
    city: str = Field(..., description="Municipal city name")
    state: str = Field(..., description="Two-letter US state code e.g. TX")
    zip_code: str = Field(..., description="5-digit US postal ZIP code")
    review_count: int = Field(default=0, ge=0, description="Total verified Google review count")
    star_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Star rating from 0.0 to 5.0")
    specialty: str = Field(..., description="Categorized trade specialty (e.g. Storm Damage & Re-roofing)")
    website_status: str = Field(
        ...,
        description="Website qualification status: 'None (No Website)' or 'None (No Website - Social Only)'"
    )
    website_url: Optional[str] = Field(default=None, description="URL of social or directory profile if available")
    place_url: str = Field(default="", description="Direct Google Maps place profile URL")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("State code cannot be empty. Must be a valid 2-letter US state code.")
        v_clean = v.strip().upper()
        if not v_clean:
            raise ValueError("State code cannot be empty. Must be a valid 2-letter US state code.")
        v_lower = v.strip().lower()
        if v_lower in US_STATE_NAME_TO_CODE:
            return US_STATE_NAME_TO_CODE[v_lower]
        if v_lower in {"dc", "district of columbia", "washington dc"}:
            return "DC"
        if v_clean in VALID_US_STATES:
            return v_clean
        raise ValueError(
            f"Invalid US state: '{v}'. Must be a valid 2-letter US state code (e.g. TX, FL, OH, GA, AZ) or DC."
        )

    @field_validator("cleaned_phone")
    @classmethod
    def validate_cleaned_phone(cls, v: str) -> str:
        if v is None:
            return ""
        v_clean = str(v).strip()
        if not v_clean:
            return ""
        if len(v_clean) != 10 or not v_clean.isdigit():
            raise ValueError(
                f"Invalid phone number: '{v}'. cleaned_phone must be empty or exactly 10 digits."
            )
        return v_clean

    @property
    def dedup_key(self) -> str:
        """Normalized deduplication key: 10-digit phone or normalized name + state."""
        from src.scraper.normalizer import get_dedup_key
        return get_dedup_key(self.cleaned_phone, self.business_name, self.state)

    @property
    def is_high_priority(self) -> bool:
        """Lead qualifies for high priority if review count > 10 without a website."""
        return self.review_count > 10


class QualifiedLead(RawLead):
    """
    Qualified contractor lead ready for CRM ingestion.
    Includes pipeline priority scoring and provenance search query.
    """
    priority: str = Field(default="Standard", description="Priority tier: 🔥 High, ⚡ Medium, or ❄️ Low")
    search_query: Optional[str] = Field(default=None, description="Google Maps query that discovered this lead")

    @classmethod
    def from_raw(cls, raw: RawLead, priority: Optional[str] = None, search_query: Optional[str] = None) -> "QualifiedLead":
        """Instantiate QualifiedLead from a RawLead with calculated priority."""
        if priority is None:
            priority = "🔥 High" if raw.is_high_priority else "⚡ Medium"
        return cls(
            **raw.model_dump(),
            priority=priority,
            search_query=search_query
        )


class CRMRecord(BaseModel):
    """
    Contractor lead row schema matching Google Sheet 'Leads Tracker' columns A through U.
    Interface contract between Milestone 2 (CRM Ingest) and Milestone 3 (Personalization).
    """
    row_index: int = Field(..., ge=14, description="1-indexed row number in Google Sheet (starting at row 14)")
    lead_status: str = Field(default="Not Contacted", description="Current pipeline stage")
    priority: str = Field(default="⚡ Medium", description="Lead priority tier: 🔥 High, ⚡ Medium, ❄️ Low")
    company_name: str = Field(..., description="Company name")
    website: str = Field(default="None (No Website)", description="Website column display")
    industry_niche: str = Field(..., description="Trade specialty classification")
    company_size: str = Field(default="1-10", description="Estimated company size")
    contact_first_name: str = Field(default="Roofing Team", description="Contact person first name")
    contact_last_name: str = Field(default="Contractor", description="Contact person last name")
    job_title: str = Field(default="Owner / Contractor", description="Contact job title")
    work_email: str = Field(..., description="Outreach destination (email address or phone reference)")
    email_verification: str = Field(default="Unverified", description="Verification state of email")
    linkedin_profile: str = Field(default="", description="Google Maps URL or social directory profile")
    location: str = Field(..., description="City, State and timezone string, e.g. 'Tyler, TX (CST)'")
    outreach_channel: str = Field(default="Cold Email", description="Primary outreach channel: Cold Email or Cold Call")
    est_deal_value: int = Field(default=4000, description="Estimated deal value in USD")
    notes_and_next_steps: str = Field(default="", description="Audit notes and contact metadata")


class OutreachDraft(BaseModel):
    """
    Generated personalized outreach package staged in Google Sheet columns V through Z.
    Interface contract between Milestone 3 (Personalizer) and Milestone 4 (Dispatcher).
    """
    crm_record: CRMRecord = Field(..., description="Underlying CRM row reference")
    icebreaker: str = Field(..., description="2-sentence personalized opening referencing location & specialty")
    offer_angle: str = Field(..., description="Revenue pain-point angle referencing emergency repair competitor search rank")
    staged_email_subject: str = Field(..., description="Subject line for cold outreach email")
    staged_email_body: str = Field(..., description="Full body copy for cold outreach email")
    staged_whatsapp_msg: str = Field(..., description="Pre-formatted mobile text message for WhatsApp")
    staged_wame_url: str = Field(..., description="Pre-populated wa.me click-to-chat URL")
    approval_status: str = Field(default="Drafted / Ready for Review", description="Safety gate review status")
