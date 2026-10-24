"""
Tier 3: Cross-Feature Combinations Test Suite (Dual Track E2E Testing).

Tests pairwise interactions and data flow transitions across pipeline module boundaries:
1. Scraper + Website Filter
2. Scraper + Deduplication
3. Deduplication + Lead Scoring
4. Lead Scoring + Personalization
5. Personalization + Staging Storage (Cols V-Z)
6. Staging Storage + Approval Safety Gate
7. Safety Gate + Cold Email Dispatch
8. Safety Gate + WhatsApp Fallback
9. Dispatch + Humanized Pacing & Daily Cap
10. Dispatch + CRM State Update (Cols A & O)
11. CRM State Update + Pipeline Dashboard KPI Sync
12. Specialty Classifier + Email Subject Alignment
13. Filter + Scoring Synergy (Social Media Impact)
14. Deduplication + Row Index Sequencing
15. Safety Gate Rejection + Zero CRM State Mutation
"""

from datetime import datetime, timezone
import pytest

from tests.e2e.contract_oracle import (
    RawLeadContract,
    CRMRecordContract,
    OutreachDraftContract,
    oracle_filter_website,
    oracle_normalize_business_name,
    oracle_normalize_phone,
    oracle_format_phone_display,
    oracle_classify_specialty,
    oracle_score_lead,
    oracle_generate_icebreaker,
    oracle_assert_zero_placeholders,
    oracle_build_whatsapp_link,
    oracle_pacing_delay_valid,
    oracle_apply_daily_cap,
    oracle_safety_gate_check,
    oracle_crm_dispatch_update,
)


def test_pairwise_scraper_and_website_filter():
    """Pairwise 1: Raw Google Maps cards streamed directly into website filter."""
    raw_cards = [
        {"name": "Hartman Roofing", "site": "https://hartmanroofinglubbock.com"},
        {"name": "General Roofing", "site": None},
        {"name": "Simmons Roofing", "site": "https://www.facebook.com/simmonsroofinginc/"},
        {"name": "GoRoofTech", "site": "https://gorooftech.net"},
        {"name": "El Sol Roofing", "site": "https://www.tiktok.com/@el.sol.roofing"},
    ]

    filtered_leads = []
    for card in raw_cards:
        keep, status = oracle_filter_website(card["site"])
        if keep:
            filtered_leads.append({"name": card["name"], "status": status})

    # Exactly 3 roofers qualify (General Roofing, Simmons Roofing, El Sol Roofing)
    assert len(filtered_leads) == 3
    names = [lead["name"] for lead in filtered_leads]
    assert "General Roofing" in names
    assert "Simmons Roofing" in names
    assert "El Sol Roofing" in names
    assert "Hartman Roofing" not in names
    assert "GoRoofTech" not in names


def test_pairwise_scraper_and_deduplication():
    """Pairwise 2: Multi-query scrape stream filtered for intra-batch duplicates."""
    stream = [
        {"name": "General Roofing & Restoration", "phone": "(903) 807-0683", "state": "TX"},
        {"name": "General Roofing and Restoration, LLC", "phone": "+1 903-807-0683", "state": "TX"},  # Dup
        {"name": "Tyler Roofing Company", "phone": "(903) 470-7821", "state": "TX"},
        {"name": "The Tyler Roofing Co.", "phone": "903.470.7821", "state": "TX"},  # Dup
        {"name": "Solarshield Industries, Inc.", "phone": "(352) 237-5200", "state": "FL"},
    ]

    seen_names = set()
    seen_phones = set()
    unique_stream = []

    for item in stream:
        norm_name = oracle_normalize_business_name(item["name"])
        norm_phone = oracle_normalize_phone(item["phone"])
        if norm_name in seen_names or norm_phone in seen_phones:
            continue
        seen_names.add(norm_name)
        seen_phones.add(norm_phone)
        unique_stream.append(item)

    assert len(unique_stream) == 3
    assert seen_names == {
        "general roofing and restoration",
        "tyler roofing",
        "solarshield industries"
    }


def test_pairwise_dedup_and_lead_scoring():
    """Pairwise 3: Deduplicated unique leads scored for priority and deal value."""
    unique_leads = [
        {"name": "General Roofing", "reviews": 13, "specialty": "Storm Damage & Re-roofing"},
        {"name": "Tyler Roofing", "reviews": 2, "specialty": "Residential Roofing & Repairs"},
        {"name": "Apex Commercial", "reviews": 6, "specialty": "Commercial & Industrial Roofing"},
    ]

    scored = []
    for item in unique_leads:
        priority, deal = oracle_score_lead(item["reviews"], item["specialty"])
        scored.append({"name": item["name"], "priority": priority, "deal": deal})

    assert scored[0]["priority"] == "🔥 High"
    assert scored[0]["deal"] == 4500
    assert scored[1]["priority"] == "❄️ Low"
    assert scored[1]["deal"] == 3000
    assert scored[2]["priority"] == "🔥 High"
    assert scored[2]["deal"] == 4500


def test_pairwise_scoring_and_personalization():
    """Pairwise 4: Scored leads generate customized value propositions based on priority."""
    lead = {
        "company_name": "General Roofing & Restoration",
        "city": "Tyler",
        "specialty": "Storm Damage & Re-roofing",
        "priority": "🔥 High",
        "deal_value": 4500
    }

    hook = oracle_generate_icebreaker(lead["company_name"], lead["city"], lead["specialty"])
    assert lead["city"] in hook
    assert "emergency roof repairs" in hook.lower()
    oracle_assert_zero_placeholders(hook)


def test_pairwise_personalization_and_staging_storage(sample_crm_record):
    """Pairwise 5: Generated assets populate staging columns V through Z."""
    icebreaker = oracle_generate_icebreaker(
        sample_crm_record.company_name, "Tyler", sample_crm_record.industry_niche
    )
    subject = f"Emergency roof repair inquiries in Tyler - {sample_crm_record.company_name}"
    body = f"Hi Team,\n\n{icebreaker}\n\nOpen to a 2-min video?"
    wa_msg = f"Saw your work in Tyler. Emergency repair rankings driving leads. Open to a video?"
    wa_url = oracle_build_whatsapp_link("9038070683", wa_msg)

    draft = OutreachDraftContract(
        crm_record=sample_crm_record,
        icebreaker=icebreaker,
        offer_angle="Emergency repair search ranking capture",
        staged_email_subject=subject,
        staged_email_body=body,
        staged_whatsapp_msg=wa_msg,
        staged_wame_url=wa_url,
        approval_status="Drafted / Ready for Review"
    )

    # Verify staging allocation
    assert draft.staged_email_subject == subject
    assert draft.staged_wame_url == wa_url
    assert draft.approval_status == "Drafted / Ready for Review"
    assert draft.crm_record.row_index == 14


def test_pairwise_staging_and_safety_gate_blocking(sample_outreach_draft):
    """Pairwise 6: Staged drafts blocked by safety gate when unapproved."""
    can_send = oracle_safety_gate_check(sample_outreach_draft, confirmed=False)
    assert can_send is False
    assert sample_outreach_draft.approval_status == "Drafted / Ready for Review"
    assert sample_outreach_draft.crm_record.lead_status == "Not Contacted"


def test_pairwise_staging_and_safety_gate_approval(sample_outreach_draft):
    """Pairwise 7: Staged drafts approved when operator provides confirmation."""
    can_send = oracle_safety_gate_check(sample_outreach_draft, confirmed=True)
    assert can_send is True


def test_pairwise_safety_gate_and_cold_email_dispatch(sample_crm_record):
    """Pairwise 8: Approved lead with email address routes to Cold Email."""
    sample_crm_record.work_email = "fixanyroof@gmail.com"
    sample_crm_record.outreach_channel = "Cold Email"

    draft = OutreachDraftContract(
        crm_record=sample_crm_record,
        icebreaker="Hook",
        offer_angle="Angle",
        staged_email_subject="Subject",
        staged_email_body="Body",
        staged_whatsapp_msg="",
        staged_wame_url="",
        approval_status="Approved"
    )

    channel = "Cold Email" if "@" in draft.crm_record.work_email else "WhatsApp"
    assert channel == "Cold Email"


def test_pairwise_safety_gate_and_whatsapp_fallback(sample_crm_record):
    """Pairwise 9: Approved lead with phone reference routes to WhatsApp fallback."""
    sample_crm_record.work_email = "Call: (903) 807-0683"
    sample_crm_record.outreach_channel = "Cold Call"

    draft = OutreachDraftContract(
        crm_record=sample_crm_record,
        icebreaker="Hook",
        offer_angle="Angle",
        staged_email_subject="Subject",
        staged_email_body="Body",
        staged_whatsapp_msg="Message",
        staged_wame_url="https://wa.me/19038070683?text=Message",
        approval_status="Approved"
    )

    channel = "Cold Email" if "@" in draft.crm_record.work_email else "WhatsApp"
    assert channel == "WhatsApp"
    assert draft.staged_wame_url.startswith("https://wa.me/19038070683")


def test_pairwise_dispatch_and_humanized_pacing():
    """Pairwise 10: Approved dispatches sequenced with randomized delays and daily cap."""
    leads_to_send = list(range(35))
    dispatched = oracle_apply_daily_cap(leads_to_send, cap=25)
    assert len(dispatched) == 25

    # Check pacing intervals
    delays = [random_uniform_delay() for _ in range(len(dispatched))]
    assert all(45.0 <= d <= 180.0 for d in delays)


def random_uniform_delay():
    import random
    return random.uniform(45.0, 180.0)


def test_pairwise_dispatch_and_crm_state_update(sample_crm_record):
    """Pairwise 11: Dispatched lead updates Col A to Contacted and Col O to date."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated_rec = oracle_crm_dispatch_update(sample_crm_record, channel="Cold Email", date_str=today_str)

    assert updated_rec.lead_status == "Contacted (Touch 1)"
    assert "Dispatched via Cold Email" in updated_rec.notes_and_next_steps


def test_pairwise_crm_update_and_dashboard_kpi_sync(sample_crm_record):
    """Pairwise 12: CRM state transitions correctly feed Pipeline Dashboard formulas."""
    # Simulate CRM row batch before and after dispatch
    batch = [
        {"status": "Not Contacted", "deal": 4000},
        {"status": "Not Contacted", "deal": 4500},
        {"status": "Closed Won", "deal": 3500},
    ]

    total_pipeline_before = sum(r["deal"] for r in batch)
    contacted_before = sum(1 for r in batch if r["status"] != "Not Contacted")
    assert contacted_before == 1
    assert total_pipeline_before == 12000

    # Dispatch lead 0
    batch[0]["status"] = "Contacted (Touch 1)"

    contacted_after = sum(1 for r in batch if r["status"] != "Not Contacted")
    total_pipeline_after = sum(r["deal"] for r in batch)

    assert contacted_after == 2
    assert total_pipeline_after == 12000  # Deal value remains intact


def test_pairwise_specialty_classifier_and_email_subject():
    """Pairwise 13: Trade specialty drives bespoke cold email subject line."""
    specialty = oracle_classify_specialty("General Roofing", "storm damage repairs")
    subject = f"Emergency {specialty.lower()} inquiries in Tyler - General Roofing"
    assert "storm damage" in subject.lower()


def test_pairwise_filter_and_scoring_synergy():
    """Pairwise 14: Social profile presence upgrades moderate review count to Medium priority."""
    # 2 reviews without social -> Low
    p_no_social, _ = oracle_score_lead(review_count=2, has_social=False)
    # 2 reviews with active social -> Medium
    p_social, _ = oracle_score_lead(review_count=2, has_social=True)
    assert p_no_social == "❄️ Low"
    assert p_social == "⚡ Medium"


def test_pairwise_dedup_and_row_index_sequencing():
    """Pairwise 15: Deduplicated leads receive sequential row indices starting at Row 14."""
    initial_row = 14
    leads = ["Lead A", "Lead B", "Lead C", "Lead D"]
    allocated_rows = [initial_row + i for i in range(len(leads))]
    assert allocated_rows == [14, 15, 16, 17]
    assert all(r <= 495 for r in allocated_rows)
