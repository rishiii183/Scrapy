"""
Pytest configuration and shared fixtures for Roofer Outreach Pipeline E2E tests.
"""

import json
from pathlib import Path
import pytest

from tests.e2e.contract_oracle import (
    RawLeadContract,
    CRMRecordContract,
    OutreachDraftContract,
    oracle_generate_icebreaker,
    oracle_build_whatsapp_link,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def verified_leads_json():
    """Load the 25 verified roofer leads discovered across TX, FL, OH, GA, AZ."""
    path = FIXTURES_DIR / "sample_leads.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_texas_raw_lead():
    """Texas storm repair contractor without website (>10 reviews -> High Priority)."""
    return RawLeadContract(
        business_name="General Roofing & Restoration",
        cleaned_phone="9038070683",
        phone_display="(903) 807-0683",
        city="Tyler",
        state="TX",
        zip_code="75701",
        review_count=13,
        star_rating=5.0,
        specialty="Storm Damage & Re-roofing",
        website_status="None (No Website)",
        website_url=None,
        place_url="https://maps.google.com/?cid=1001",
    )


@pytest.fixture
def sample_florida_raw_lead():
    """Florida residential contractor without website (>10 reviews -> High Priority)."""
    return RawLeadContract(
        business_name="Solarshield Industries, Inc.",
        cleaned_phone="3522375200",
        phone_display="(352) 237-5200",
        city="Ocala",
        state="FL",
        zip_code="34471",
        review_count=21,
        star_rating=4.2,
        specialty="Residential Roofing & Repairs",
        website_status="None (No Website)",
        website_url=None,
        place_url="https://maps.google.com/?cid=1002",
    )


@pytest.fixture
def sample_ohio_raw_lead():
    """Ohio storm repair contractor (>10 reviews -> High Priority)."""
    return RawLeadContract(
        business_name="Dyer Restoration Solutions Inc",
        cleaned_phone="2343606842",
        phone_display="(234) 360-6842",
        city="Canton",
        state="OH",
        zip_code="44702",
        review_count=35,
        star_rating=4.8,
        specialty="Storm Damage & Re-roofing",
        website_status="None (No Website)",
        website_url=None,
        place_url="https://maps.google.com/?cid=1003",
    )


@pytest.fixture
def sample_georgia_raw_lead():
    """Georgia high-review roofer without website."""
    return RawLeadContract(
        business_name="Roofing Macon, GA",
        cleaned_phone="4785550199",
        phone_display="(478) 555-0199",
        city="Macon",
        state="GA",
        zip_code="31201",
        review_count=72,
        star_rating=4.8,
        specialty="Residential Roofing & Repairs",
        website_status="None (No Website)",
        website_url=None,
        place_url="https://maps.google.com/?cid=1004",
    )


@pytest.fixture
def sample_arizona_raw_lead():
    """Arizona high-volume roofer without website (97 reviews)."""
    return RawLeadContract(
        business_name="High Elevation Roofing",
        cleaned_phone="9285223531",
        phone_display="(928) 522-3531",
        city="Flagstaff",
        state="AZ",
        zip_code="86001",
        review_count=97,
        star_rating=4.8,
        specialty="Residential Roofing & Repairs",
        website_status="None (No Website)",
        website_url=None,
        place_url="https://maps.google.com/?cid=1005",
    )


@pytest.fixture
def sample_crm_record(sample_texas_raw_lead):
    """Valid CRM record at Row 14 adhering to 21-column schema."""
    return CRMRecordContract(
        row_index=14,
        lead_status="Not Contacted",
        priority="🔥 High",
        company_name=sample_texas_raw_lead.business_name,
        website=sample_texas_raw_lead.website_status,
        industry_niche=sample_texas_raw_lead.specialty,
        company_size="1-10",
        contact_first_name="Roofing Team",
        contact_last_name="Contractor",
        job_title="Owner / Contractor",
        work_email=f"Call: {sample_texas_raw_lead.phone_display}",
        email_verification="Unverified",
        linkedin_profile=sample_texas_raw_lead.place_url,
        location="Tyler, TX (CST)",
        outreach_channel="Cold Call",
        est_deal_value=4500,
        notes_and_next_steps=f"Phone: {sample_texas_raw_lead.phone_display}. Candidate for high-converting landing page.",
    )


@pytest.fixture
def sample_outreach_draft(sample_crm_record):
    """Valid staged outreach package adhering to columns V-Z."""
    icebreaker = oracle_generate_icebreaker(
        sample_crm_record.company_name,
        "Tyler",
        sample_crm_record.industry_niche
    )
    offer_angle = "Emergency roof repair Google Maps search volume capture"
    wa_msg = f"Hi, saw your {sample_crm_record.industry_niche} work in Tyler. Competitors ranking on Google Maps for emergency repairs are capturing jobs without a website. Open to a 2-min video?"
    wa_url = oracle_build_whatsapp_link("9038070683", wa_msg)

    return OutreachDraftContract(
        crm_record=sample_crm_record,
        icebreaker=icebreaker,
        offer_angle=offer_angle,
        staged_email_subject="Emergency roof repair inquiries in Tyler - General Roofing & Restoration",
        staged_email_body=f"Hi Team,\n\n{icebreaker}\n\nWould you be open to a quick 2-min video showing how to capture this traffic?",
        staged_whatsapp_msg=wa_msg,
        staged_wame_url=wa_url,
        approval_status="Drafted / Ready for Review",
    )
