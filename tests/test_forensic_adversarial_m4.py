"""
Forensic Integrity & Adversarial Stress Suite for Milestone 4 (Outreach Dispatch & CLI).
Independently written and executed by Forensic Auditor (auditor_m4_1).
"""

import io
import math
import random
import urllib.parse
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from email.mime.text import MIMEText
import pytest

from src.dispatcher.email_client import (
    EmailClient,
    DispatchResult,
    clean_email,
    is_valid_email,
    normalize_newlines,
    create_mime_message,
)
from src.dispatcher.whatsapp_client import (
    WhatsAppClient,
    build_whatsapp_link,
    is_phone_only_lead,
    extract_clean_10digit_phone,
)
from src.dispatcher.pacing import (
    PacingController,
    compute_random_delay,
    is_valid_pacing_delay,
    apply_daily_cap,
)
from src.dispatcher.safety_gate import (
    SafetyGate,
    SafetyGateError,
    check_safety_gate,
    require_confirmation,
    filter_approved_drafts,
    prompt_user_approval,
    STATUS_READY_FOR_REVIEW,
    STATUS_APPROVED,
    STATUS_DISPATCHED,
)
from src.dispatcher.orchestrator import (
    OutreachDispatcher,
    DispatchSummary,
    update_crm_dispatch_record,
    update_sheet_dispatch_state,
)
from src.models import CRMRecord, OutreachDraft
from src.cli import main


class TestForensicMIMEAuthenticity:
    """Empirical audit of MIME email message construction."""

    def test_mime_structure_and_headers(self):
        sender = "outreach@roofinggrowth.com"
        recipient = "owner@apexroofing.com"
        subject = "Quick question regarding Apex Roofing in Tyler"
        body = "Hi Team,\n\nWe noticed you don't have a website.\n\nBest,\nAlex"

        msg = create_mime_message(sender, recipient, subject, body)
        assert isinstance(msg, MIMEText)
        assert msg.get_content_type() == "text/plain"
        assert msg.get_content_charset() == "utf-8"
        assert msg["Subject"] == subject
        assert msg["From"] == sender
        assert msg["To"] == recipient
        payload = msg.get_payload(decode=True).decode("utf-8")
        assert payload == body

    def test_mime_with_crlf_normalization(self):
        body_with_crlf = "Line 1\r\nLine 2\rLine 3\nLine 4"
        msg = create_mime_message("from@test.com", "to@test.com", "Subj", body_with_crlf)
        payload = msg.get_payload(decode=True).decode("utf-8")
        assert "\r" not in payload
        assert payload == "Line 1\nLine 2\nLine 3\nLine 4"

    def test_mime_with_unicode_and_emojis(self):
        body_unicode = "🔨 Roofing & Restoration for Tyler, TX — Call René at Café Roof!"
        msg = create_mime_message("from@test.com", "to@test.com", "Subj 🚀", body_unicode)
        payload = msg.get_payload(decode=True).decode("utf-8")
        assert payload == body_unicode


class TestForensicWhatsAppAuthenticity:
    """Empirical audit of WhatsApp URL percent-encoding and phone normalization."""

    def test_whatsapp_link_encoding_roundtrip(self):
        phone_raw = "(903) 807-0683 ext 102"
        msg_raw = "Hi John! Found you on Google Maps. Need a site? Let's chat: https://test.com?q=roof&city=Tyler 🏠"
        url = build_whatsapp_link(phone_raw, msg_raw)

        assert url.startswith("https://wa.me/19038070683?text=")
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == "wa.me"
        assert parsed.path == "/19038070683"
        qs = urllib.parse.parse_qs(parsed.query)
        assert "text" in qs
        assert qs["text"][0] == msg_raw

    def test_phone_number_cleaning_variations(self):
        cases = [
            ("(903) 807-0683", "9038070683"),
            ("+1 (903) 807-0683", "9038070683"),
            ("1-903-807-0683", "9038070683"),
            ("9038070683", "9038070683"),
            ("(903) 807-0683 ext. 45", "9038070683"),
            ("(903) 807-0683 x12", "9038070683"),
            ("Call: (903) 807-0683", "9038070683"),
        ]
        for raw, expected in cases:
            cleaned = extract_clean_10digit_phone(raw)
            assert cleaned == expected, f"Failed for '{raw}': got '{cleaned}', expected '{expected}'"


class TestForensicPacingAuthenticity:
    """Empirical statistical audit of pacing delay and jitter."""

    def test_delay_bounds_and_statistical_properties(self):
        samples = [compute_random_delay(45.0, 180.0) for _ in range(2500)]
        assert all(45.0 <= s <= 180.0 for s in samples)

        mean = sum(samples) / len(samples)
        variance = sum((s - mean) ** 2 for s in samples) / len(samples)
        std_dev = math.sqrt(variance)

        # Theoretical uniform distribution on [45, 180]:
        # Mean = (45 + 180) / 2 = 112.5
        # StdDev = (180 - 45) / sqrt(12) = 135 / 3.4641 = 38.97
        assert 108.0 <= mean <= 117.0, f"Mean delay {mean} deviates significantly from theoretical 112.5s"
        assert 36.0 <= std_dev <= 42.0, f"StdDev {std_dev} deviates significantly from theoretical 38.97s"
        assert len(set(samples)) == 2500, "Samples are not unique continuous floats"

    def test_daily_cap_slicing(self):
        items = list(range(100))
        assert len(apply_daily_cap(items, cap=25)) == 25
        assert len(apply_daily_cap(items, cap=0)) == 0
        assert len(apply_daily_cap(items, cap=-5)) == 0
        assert len(apply_daily_cap(items[:10], cap=25)) == 10


class TestForensicZeroBypassSafetyGate:
    """Adversarial stress-testing of Safety Gate to detect bypasses or backdoors."""

    @pytest.fixture
    def sample_draft(self):
        crm = CRMRecord(
            row_index=20,
            lead_status="Not Contacted",
            priority="High",
            company_name="Adversarial Roof Co",
            website="None (No Website)",
            industry_niche="Storm Damage",
            company_size="1-10",
            contact_first_name="Jane",
            contact_last_name="Doe",
            job_title="Owner",
            work_email="jane@adversarialroof.com",
            email_verification="Verified",
            linkedin_profile="",
            location="Tyler, TX",
            outreach_channel="Cold Email",
            est_deal_value=5000,
            notes_and_next_steps="Audit test lead",
        )
        return OutreachDraft(
            crm_record=crm,
            icebreaker="Hook line 1. Hook line 2.",
            offer_angle="Angle",
            staged_email_subject="Subject",
            staged_email_body="Body",
            staged_whatsapp_msg="WA Msg",
            staged_wame_url="https://wa.me/19038070683?text=WA%20Msg",
            approval_status=STATUS_READY_FOR_REVIEW,
        )

    def test_unconfirmed_blocks_execution(self, sample_draft):
        assert check_safety_gate(sample_draft, confirmed=False) is False
        with pytest.raises(SafetyGateError) as exc_info:
            require_confirmation(sample_draft, confirmed=False)
        assert "Explicit user confirmation required" in str(exc_info.value)

    def test_already_dispatched_lead_blocked_even_with_confirm(self, sample_draft):
        sample_draft.approval_status = STATUS_DISPATCHED
        assert check_safety_gate(sample_draft, confirmed=True) is False
        with pytest.raises(SafetyGateError) as exc_info:
            require_confirmation(sample_draft, confirmed=True)
        assert "Lead has already been dispatched" in str(exc_info.value)

    def test_invalid_status_blocked(self, sample_draft):
        sample_draft.approval_status = "Hacked_Status"
        assert check_safety_gate(sample_draft, confirmed=True) is False
        with pytest.raises(SafetyGateError) as exc_info:
            require_confirmation(sample_draft, confirmed=True)
        assert "Invalid approval status" in str(exc_info.value)

    def test_dispatcher_single_blocks_unconfirmed(self, sample_draft):
        dispatcher = OutreachDispatcher(test_mode=True, default_confirmed=False)
        res = dispatcher.dispatch_single(sample_draft, confirmed=False)
        assert res is None
        assert sample_draft.approval_status == STATUS_READY_FOR_REVIEW
        assert sample_draft.crm_record.lead_status == "Not Contacted"

    def test_dispatcher_batch_blocks_unconfirmed(self, sample_draft):
        dispatcher = OutreachDispatcher(test_mode=True, default_confirmed=False)
        summary = dispatcher.dispatch_batch([sample_draft], confirmed=False)
        assert summary.total_dispatched == 0
        assert summary.skipped_count == 1
        assert len(summary.results) == 0

    def test_cli_dispatch_blocks_when_confirm_omitted(self, monkeypatch):
        # When --confirm is omitted, main(["dispatch"]) must abort with status 1
        rc = main(["dispatch", "--dry-run", "--test-mode"])
        assert rc == 1, "CLI must return exit code 1 when --confirm is missing"

    def test_cli_pipeline_skips_dispatch_when_confirm_omitted(self, monkeypatch):
        # In pipeline mode without --confirm, steps 1-3 run and dispatch is withheld
        rc = main(["pipeline", "--dry-run", "--test-mode", "--limit", "2"])
        assert rc == 0


class TestForensicCRMAndSheetsContract:
    """Audit of CRM state transitions and SheetsClient interaction."""

    def test_crm_state_transitions(self):
        rec = CRMRecord(
            row_index=25,
            lead_status="Not Contacted",
            priority="High",
            company_name="Heritage Roofing",
            website="None (No Website)",
            industry_niche="Residential",
            company_size="1-10",
            contact_first_name="Bob",
            contact_last_name="Smith",
            job_title="Owner",
            work_email="bob@heritage.com",
            email_verification="Verified",
            linkedin_profile="",
            location="Tyler, TX",
            outreach_channel="Cold Email",
            est_deal_value=3000,
            notes_and_next_steps="Follow up soon.",
        )
        updated = update_crm_dispatch_record(rec, channel="Cold Email", date_str="2026-10-24")
        assert updated.lead_status == "Contacted (Touch 1)"
        assert getattr(updated, "touch_1_date", None) == "2026-10-24"
        assert "Dispatched via Cold Email on 2026-10-24." in updated.notes_and_next_steps
        assert updated.priority == "High"
        assert updated.company_name == "Heritage Roofing"

    def test_sheets_client_exact_range_updates(self):
        rec = CRMRecord(
            row_index=42,
            lead_status="Not Contacted",
            priority="High",
            company_name="Lone Star Apex",
            website="None (No Website)",
            industry_niche="Storm Damage",
            company_size="1-10",
            contact_first_name="Al",
            contact_last_name="Apex",
            job_title="Owner",
            work_email="al@apex.com",
            email_verification="Verified",
            linkedin_profile="",
            location="Tyler, TX",
            outreach_channel="Cold Email",
            est_deal_value=4000,
            notes_and_next_steps="Candidate for web.",
        )
        draft = OutreachDraft(
            crm_record=rec,
            icebreaker="H1. H2.",
            offer_angle="Angle",
            staged_email_subject="Subj",
            staged_email_body="Body",
            staged_whatsapp_msg="WA",
            staged_wame_url="https://wa.me/19038070683?text=WA",
            approval_status=STATUS_READY_FOR_REVIEW,
        )

        mock_client = MagicMock()
        update_sheet_dispatch_state(
            draft=draft,
            channel="Cold Email",
            date_str="2026-10-24",
            sheets_client=mock_client,
            sheet_id="TEST_SHEET",
            sheet_tab="Leads Tracker",
        )

        assert mock_client.update_range.call_count == 4
        calls = mock_client.update_range.call_args_list

        # Col A
        assert calls[0][1]["range_str"] == "'Leads Tracker'!A42"
        assert calls[0][1]["values"] == [["Contacted (Touch 1)"]]

        # Col O
        assert calls[1][1]["range_str"] == "'Leads Tracker'!O42"
        assert calls[1][1]["values"] == [["2026-10-24"]]

        # Col U
        assert calls[2][1]["range_str"] == "'Leads Tracker'!U42"

        # Col Z
        assert calls[3][1]["range_str"] == "'Leads Tracker'!Z42"
        assert calls[3][1]["values"] == [["Dispatched"]]
