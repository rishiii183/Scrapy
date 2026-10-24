"""
Unit Test Suite for Milestone 4: Humanized Outreach Dispatch Engine & Unified CLI.

Covers:
- Safety Gate approval logic, interactive prompt handling, idempotency, and exceptions
- Email Client normalization, MIME formatting, RFC 5322 validation, and dry-run simulation
- WhatsApp Client fallback routing, extension stripping, URL percent-encoding, and link creation
- Pacing controller boundaries (45-180s), jitter distribution, test clock, and daily cap
- OutreachDispatcher orchestrator, CRM state updates (Cols A, O, U, Z), and Google Sheets sync
- Unified CLI subcommands (scrape, ingest, personalize, dispatch, pipeline) and argument parsing
"""

import io
import re
import urllib.parse
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from src.cli import build_parser, main
from src.config import SHEET_ID, SHEET_TAB
from src.crm.sheets_client import SheetsClient
from src.dispatcher import (
    DispatchResult,
    DispatchSummary,
    EmailClient,
    OutreachDispatcher,
    PacingController,
    SafetyGate,
    SafetyGateError,
    WhatsAppClient,
    apply_daily_cap,
    build_whatsapp_link,
    check_safety_gate,
    clean_email,
    compute_random_delay,
    create_mime_message,
    extract_clean_10digit_phone,
    filter_approved_drafts,
    is_phone_only_lead,
    is_valid_email,
    is_valid_pacing_delay,
    normalize_newlines,
    prompt_user_approval,
    require_confirmation,
    update_crm_dispatch_record,
    update_sheet_dispatch_state,
)
from src.models import CRMRecord, OutreachDraft


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_crm_record_email():
    """Valid CRMRecord with an email address for cold email dispatch."""
    return CRMRecord(
        row_index=14,
        lead_status="Not Contacted",
        priority="🔥 High",
        company_name="Lone Star Apex Roofing",
        website="None (No Website)",
        industry_niche="Storm Damage & Re-roofing",
        company_size="1-10",
        contact_first_name="Roofing Team",
        contact_last_name="Contractor",
        job_title="Owner / Contractor",
        work_email="contact@lonestarroofing.com",
        email_verification="Verified",
        linkedin_profile="",
        location="Tyler, TX (CST)",
        outreach_channel="Cold Email",
        est_deal_value=4500,
        notes_and_next_steps="Phone: (903) 807-0683. Candidate for website.",
    )


@pytest.fixture
def mock_crm_record_phone():
    """Valid CRMRecord with a phone-only work_email for WhatsApp fallback."""
    return CRMRecord(
        row_index=15,
        lead_status="Not Contacted",
        priority="🔥 High",
        company_name="General Roofing & Restoration",
        website="None (No Website)",
        industry_niche="Storm Damage & Re-roofing",
        company_size="1-10",
        contact_first_name="Roofing Team",
        contact_last_name="Contractor",
        job_title="Owner / Contractor",
        work_email="Call: (903) 807-0683",
        email_verification="Unverified",
        linkedin_profile="",
        location="Tyler, TX (CST)",
        outreach_channel="Cold Call",
        est_deal_value=4500,
        notes_and_next_steps="Phone: (903) 807-0683. Candidate for website.",
    )


@pytest.fixture
def mock_email_draft(mock_crm_record_email):
    """OutreachDraft ready for email dispatch."""
    return OutreachDraft(
        crm_record=mock_crm_record_email,
        icebreaker="Came across Lone Star Apex Roofing while reviewing storm damage contractors in Tyler.",
        offer_angle="Dominating local competitor search results for emergency roof repairs.",
        staged_email_subject="Emergency roof repair inquiries in Tyler - Lone Star Apex Roofing",
        staged_email_body="Hi Team,\n\nWe noticed your team is missing high-ticket storm repair leads in Tyler.\n\nBest,\nOutreach Team",
        staged_whatsapp_msg="Hi, saw your storm repair work in Tyler. Quick question regarding emergency repairs?",
        staged_wame_url="https://wa.me/19038070683?text=Hi",
        approval_status="Drafted / Ready for Review",
    )


@pytest.fixture
def mock_phone_draft(mock_crm_record_phone):
    """OutreachDraft ready for WhatsApp fallback dispatch."""
    return OutreachDraft(
        crm_record=mock_crm_record_phone,
        icebreaker="Came across General Roofing & Restoration in Tyler.",
        offer_angle="Emergency repair search volume capture.",
        staged_email_subject="Roof repair inquiries in Tyler",
        staged_email_body="Hi Team,\n\nBody here.\n\nBest,\nOutreach",
        staged_whatsapp_msg="Hi, saw your roofing work in Tyler. Open to a 2-min video?",
        staged_wame_url=build_whatsapp_link("9038070683", "Hi, saw your roofing work in Tyler. Open to a 2-min video?"),
        approval_status="Drafted / Ready for Review",
    )


# ===========================================================================
# 1. Safety Gate Unit Tests
# ===========================================================================

class TestSafetyGate:
    def test_default_approval_status_is_drafted(self, mock_email_draft):
        """Verify default status is 'Drafted / Ready for Review'."""
        assert mock_email_draft.approval_status == "Drafted / Ready for Review"

    def test_check_safety_gate_blocks_when_unconfirmed(self, mock_email_draft):
        """Verify safety gate blocks dispatch when confirmed is False."""
        assert check_safety_gate(mock_email_draft, confirmed=False) is False

    def test_check_safety_gate_permits_when_confirmed(self, mock_email_draft):
        """Verify safety gate allows dispatch when confirmed is True."""
        assert check_safety_gate(mock_email_draft, confirmed=True) is True

    def test_require_confirmation_raises_on_unconfirmed(self, mock_email_draft):
        """Verify require_confirmation raises SafetyGateError when confirmed=False."""
        with pytest.raises(SafetyGateError, match="Explicit user confirmation required"):
            require_confirmation(mock_email_draft, confirmed=False)

    def test_require_confirmation_passes_when_confirmed(self, mock_email_draft):
        """Verify require_confirmation returns True when confirmed=True."""
        assert require_confirmation(mock_email_draft, confirmed=True) is True

    def test_check_safety_gate_blocks_already_dispatched_lead(self, mock_email_draft):
        """Verify lead in 'Dispatched' status cannot be redispatched (idempotency)."""
        mock_email_draft.approval_status = "Dispatched"
        assert check_safety_gate(mock_email_draft, confirmed=True) is False
        with pytest.raises(SafetyGateError, match="already been dispatched"):
            check_safety_gate(mock_email_draft, confirmed=True, raise_on_error=True)

    def test_check_safety_gate_blocks_invalid_status(self, mock_email_draft):
        """Verify unrecognized status is blocked."""
        mock_email_draft.approval_status = "Unknown Stage"
        assert check_safety_gate(mock_email_draft, confirmed=True) is False
        with pytest.raises(SafetyGateError, match="Invalid approval status"):
            check_safety_gate(mock_email_draft, confirmed=True, raise_on_error=True)

    def test_filter_approved_drafts(self, mock_email_draft, mock_phone_draft):
        """Verify batch filtering only returns drafts passing the gate."""
        batch = [mock_email_draft, mock_phone_draft]
        assert len(filter_approved_drafts(batch, confirmed=False)) == 0
        assert len(filter_approved_drafts(batch, confirmed=True)) == 2

    def test_interactive_prompt_user_approval_yes(self, mock_email_draft):
        """Verify interactive prompt parses 'y' or 'yes' as True."""
        stream_in = io.StringIO("y\n")
        stream_out = io.StringIO()
        assert prompt_user_approval(mock_email_draft, stream_in=stream_in, stream_out=stream_out) is True

    def test_interactive_prompt_user_approval_no(self, mock_email_draft):
        """Verify interactive prompt parses 'n' or 'no' as False."""
        stream_in = io.StringIO("n\n")
        stream_out = io.StringIO()
        assert prompt_user_approval(mock_email_draft, stream_in=stream_in, stream_out=stream_out) is False

    def test_interactive_prompt_user_approval_empty_input(self, mock_email_draft):
        """Verify pressing Enter (empty input) defaults safely to False."""
        stream_in = io.StringIO("\n")
        stream_out = io.StringIO()
        assert prompt_user_approval(mock_email_draft, stream_in=stream_in, stream_out=stream_out) is False

    def test_interactive_prompt_user_approval_eof(self, mock_email_draft):
        """Verify EOFError (non-interactive pipe) safely defaults to False."""
        stream_in = io.StringIO("")  # Immediate EOF
        stream_out = io.StringIO()
        assert prompt_user_approval(mock_email_draft, stream_in=stream_in, stream_out=stream_out) is False

    def test_safety_gate_class_wrapper(self, mock_email_draft):
        """Verify SafetyGate class methods."""
        gate = SafetyGate(default_confirmed=False)
        assert gate.is_approved(mock_email_draft) is False
        assert gate.is_approved(mock_email_draft, confirmed=True) is True


# ===========================================================================
# 2. Email Client & Dry-Run Simulator Unit Tests
# ===========================================================================

class TestEmailClient:
    def test_clean_email_strips_whitespace_and_quotes(self):
        """Verify clean_email removes whitespace and surrounding quotes."""
        assert clean_email('  "contractor@roof.com"  ') == "contractor@roof.com"
        assert clean_email(" 'info@domain.net' ") == "info@domain.net"
        assert clean_email("user@test.org") == "user@test.org"

    def test_is_valid_email_positive(self):
        """Verify valid RFC 5322 emails."""
        assert is_valid_email("fixanyroof@gmail.com") is True
        assert is_valid_email("contractor.one+sales@roofing-co.org") is True

    def test_is_valid_email_negative(self):
        """Verify invalid emails are rejected."""
        assert is_valid_email("fixanyroofgmail.com") is False  # Missing @
        assert is_valid_email("roofer@domain") is False  # Missing TLD
        assert is_valid_email("Call: (903) 807-0683") is False
        assert is_valid_email("") is False

    def test_normalize_newlines_replaces_crlf(self):
        """Verify CRLF is converted to standard Unix LF."""
        raw = "Line 1\r\nLine 2\rLine 3"
        normalized = normalize_newlines(raw)
        assert "\r" not in normalized
        assert normalized == "Line 1\nLine 2\nLine 3"

    def test_create_mime_message(self):
        """Verify MIMEText structure headers and UTF-8 payload."""
        msg = create_mime_message(
            sender="outreach@company.com",
            recipient="fixanyroof@gmail.com",
            subject="Tyler Roof Repair",
            body="Hello body",
        )
        assert msg["To"] == "fixanyroof@gmail.com"
        assert msg["From"] == "outreach@company.com"
        assert msg["Subject"] == "Tyler Roof Repair"
        assert msg.get_payload(decode=True).decode("utf-8") == "Hello body"

    def test_email_client_dry_run_simulator_records_log(self):
        """Verify dry-run mode simulates dispatch and logs audit trail."""
        client = EmailClient(dry_run=True)
        res = client.send(
            recipient="fixanyroof@gmail.com",
            subject="Roof Repair Inquiry",
            body="Body content here",
        )
        assert res.success is True
        assert res.channel == "Cold Email"
        assert res.mode == "Dry-Run Simulator"
        assert res.recipient == "fixanyroof@gmail.com"
        assert res.subject == "Roof Repair Inquiry"
        assert len(client.audit_log) == 1
        assert client.audit_log[0].metadata.get("status") == "Simulated"

    def test_email_client_rejects_malformed_email(self):
        """Verify client rejects malformed recipient email gracefully."""
        client = EmailClient(dry_run=True)
        res = client.send(
            recipient="bad_email_format",
            subject="Test",
            body="Test",
        )
        assert res.success is False
        assert "Invalid email recipient format" in res.error

    def test_email_client_defaults_to_dry_run_when_credentials_absent(self):
        """Verify client safely falls back to dry-run when SMTP credentials missing."""
        client = EmailClient(smtp_host=None, smtp_user=None, dry_run=False)
        assert client.dry_run is True

    @patch("smtplib.SMTP")
    def test_email_client_live_smtp_success(self, mock_smtp):
        """Verify live SMTP sends email when credentials configured."""
        mock_instance = MagicMock()
        mock_smtp.return_value = mock_instance

        client = EmailClient(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pw",
            dry_run=False,
        )
        res = client.send("contractor@test.com", "Subject", "Body")
        assert res.success is True
        assert res.mode == "Live SMTP"
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("user", "pw")
        mock_instance.send_message.assert_called_once()


# ===========================================================================
# 3. WhatsApp Client Unit Tests
# ===========================================================================

class TestWhatsAppClient:
    def test_is_phone_only_lead(self):
        """Verify identification of phone-only contractor leads."""
        assert is_phone_only_lead("Call: (903) 807-0683") is True
        assert is_phone_only_lead("(903) 807-0683") is True
        assert is_phone_only_lead("user@roof.com") is False

    def test_extract_clean_10digit_phone_with_extension(self):
        """Verify stripping extensions like 'ext 102'."""
        assert extract_clean_10digit_phone("(903) 807-0683 ext 102") == "9038070683"
        assert extract_clean_10digit_phone("903-807-0683 x44") == "9038070683"
        assert extract_clean_10digit_phone("+1 (903) 807-0683") == "9038070683"

    def test_build_whatsapp_link_format(self):
        """Verify wa.me URL format and country code prepending."""
        link = build_whatsapp_link("9038070683", "Hello roofer")
        assert link.startswith("https://wa.me/19038070683?text=")

    def test_build_whatsapp_link_encodes_reserved_characters(self):
        """Verify special characters ?, &, = are percent encoded."""
        msg = "Need emergency repairs? Call us & save = 20% ROI"
        link = build_whatsapp_link("9038070683", msg)
        assert "%3F" in link  # ?
        assert "%26" in link  # &
        assert "%3D" in link  # =
        assert "%20" in link  # space

    def test_build_whatsapp_link_encodes_newlines_and_emojis(self):
        """Verify newlines encode to %0A and emojis encode safely."""
        msg = "Line 1\nLine 2 🔥"
        link = build_whatsapp_link("9038070683", msg)
        assert "%0A" in link
        assert "%F0%9F%94%A5" in link

    def test_whatsapp_client_send_dry_run(self):
        """Verify dry-run simulation of WhatsApp click-to-chat."""
        client = WhatsAppClient(dry_run=True)
        res = client.send("(903) 807-0683", "Quick question regarding roof repairs")
        assert res.success is True
        assert res.channel == "WhatsApp wa.me"
        assert res.mode == "Dry-Run WhatsApp"
        assert "https://wa.me/19038070683" in res.recipient
        assert len(client.audit_log) == 1


# ===========================================================================
# 4. Pacing Controller Unit Tests
# ===========================================================================

class TestPacingController:
    def test_compute_random_delay_within_45_to_180_seconds(self):
        """Verify delay is within 45.0 to 180.0 seconds."""
        for _ in range(50):
            d = compute_random_delay(45.0, 180.0)
            assert 45.0 <= d <= 180.0

    def test_compute_random_delay_jitter_distribution(self):
        """Verify delays are randomized and not constant."""
        delays = [compute_random_delay() for _ in range(10)]
        assert len(set(delays)) == 10

    def test_is_valid_pacing_delay_boundaries(self):
        """Verify exact boundaries 45.0 and 180.0."""
        assert is_valid_pacing_delay(45.0) is True
        assert is_valid_pacing_delay(180.0) is True
        assert is_valid_pacing_delay(44.9) is False
        assert is_valid_pacing_delay(180.1) is False

    def test_apply_daily_cap(self):
        """Verify daily cap slices batch correctly."""
        queue = list(range(40))
        assert len(apply_daily_cap(queue, cap=25)) == 25
        assert len(apply_daily_cap(queue, cap=10)) == 10
        assert len(apply_daily_cap(queue, cap=0)) == 0

    def test_pacing_controller_test_mode_simulated_clock(self):
        """Verify test mode updates simulated_elapsed instantly without sleeping."""
        controller = PacingController(test_mode=True, test_delay=1.0, daily_cap=5)
        d1 = controller.wait()
        d2 = controller.wait()
        assert controller.simulated_elapsed == 2.0
        assert len(controller.delays_history) == 2

    def test_pacing_controller_cap_tracking(self):
        """Verify can_dispatch and get_remaining_cap tracking."""
        controller = PacingController(daily_cap=2, test_mode=True)
        assert controller.can_dispatch() is True
        assert controller.get_remaining_cap() == 2

        controller.record_dispatch()
        assert controller.can_dispatch() is True
        assert controller.get_remaining_cap() == 1

        controller.record_dispatch()
        assert controller.can_dispatch() is False
        assert controller.get_remaining_cap() == 0


# ===========================================================================
# 5. OutreachDispatcher & CRM State Transition Unit Tests
# ===========================================================================

class TestOutreachDispatcher:
    def test_update_crm_dispatch_record_transitions(self, mock_crm_record_email):
        """Verify Col A, Col O, Col U transitions upon dispatch."""
        date_str = "2026-10-24"
        updated = update_crm_dispatch_record(
            mock_crm_record_email,
            channel="Cold Email",
            date_str=date_str,
        )
        assert updated.lead_status == "Contacted (Touch 1)"
        assert updated.touch_1_date == "2026-10-24"
        assert "Dispatched via Cold Email on 2026-10-24." in updated.notes_and_next_steps
        # Immutability check
        assert mock_crm_record_email.lead_status == "Not Contacted"
        # Deal value preservation check
        assert updated.est_deal_value == mock_crm_record_email.est_deal_value

    def test_dispatcher_single_email_dispatch(self, mock_email_draft):
        """Verify dispatching an approved email draft."""
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True)
        res = dispatcher.dispatch_single(mock_email_draft, confirmed=True)

        assert res is not None
        assert res.success is True
        assert res.channel == "Cold Email"
        assert mock_email_draft.approval_status == "Dispatched"
        assert mock_email_draft.crm_record.lead_status == "Contacted (Touch 1)"

    def test_dispatcher_single_whatsapp_fallback(self, mock_phone_draft):
        """Verify phone-only lead routes to WhatsApp fallback."""
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True)
        res = dispatcher.dispatch_single(mock_phone_draft, confirmed=True)

        assert res is not None
        assert res.success is True
        assert res.channel == "WhatsApp wa.me"
        assert mock_phone_draft.approval_status == "Dispatched"
        assert mock_phone_draft.crm_record.lead_status == "Contacted (Touch 1)"

    def test_dispatcher_blocks_unconfirmed_dispatch(self, mock_email_draft):
        """Verify dispatch_single returns None when confirmed is False."""
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True)
        res = dispatcher.dispatch_single(mock_email_draft, confirmed=False)
        assert res is None
        assert mock_email_draft.approval_status == "Drafted / Ready for Review"

    def test_dispatcher_batch_execution(self, mock_email_draft, mock_phone_draft):
        """Verify dispatch_batch handles multiple channels and reports summary."""
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=25)
        batch = [mock_email_draft, mock_phone_draft]

        summary = dispatcher.dispatch_batch(batch, confirmed=True)
        assert summary.total_drafts == 2
        assert summary.approved_count == 2
        assert summary.dispatched_email == 1
        assert summary.dispatched_whatsapp == 1
        assert summary.total_dispatched == 2
        assert summary.failed_count == 0

    def test_dispatcher_batch_halts_at_daily_cap(self, mock_email_draft):
        """Verify batch halts when daily cap is reached."""
        # Create 5 draft copies
        drafts = []
        for i in range(5):
            rec = mock_email_draft.crm_record.model_copy()
            rec.row_index = 14 + i
            d = mock_email_draft.model_copy(update={"crm_record": rec})
            drafts.append(d)

        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=2)
        summary = dispatcher.dispatch_batch(drafts, confirmed=True, cap=2)

        assert summary.total_dispatched == 2
        assert summary.skipped_count == 3

    def test_update_sheet_dispatch_state(self, mock_email_draft):
        """Verify Google Sheets cell updates for Cols A, O, U, Z."""
        sheets_mock = SheetsClient(offline_mode=True)
        res = update_sheet_dispatch_state(
            draft=mock_email_draft,
            channel="Cold Email",
            date_str="2026-10-24",
            sheets_client=sheets_mock,
            sheet_id=SHEET_ID,
            sheet_tab=SHEET_TAB,
        )
        assert "lead_status" in res
        assert "touch_1_date" in res
        assert "notes" in res
        assert "approval_status" in res


# ===========================================================================
# 6. Unified CLI Unit Tests
# ===========================================================================

class TestCLI:
    def test_cli_parser_has_all_subcommands(self):
        """Verify CLI parser recognizes scrape, ingest, personalize, dispatch, pipeline."""
        import argparse
        parser = build_parser()
        subparser_action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        choices = subparser_action.choices
        for expected in ["scrape", "ingest", "personalize", "dispatch", "pipeline"]:
            assert expected in choices

    def test_cli_dispatch_requires_confirm_flag(self):
        """Verify cli dispatch fails with code 1 if --confirm is not supplied."""
        rc = main(["dispatch", "--dry-run"])
        assert rc == 1

    def test_cli_dispatch_with_confirm_executes(self):
        """Verify cli dispatch succeeds with code 0 when --confirm is passed."""
        rc = main(["dispatch", "--dry-run", "--confirm", "--test-mode", "--cap", "5"])
        assert rc == 0

    def test_cli_pipeline_subcommand(self):
        """Verify pipeline subcommand executes cleanly."""
        rc = main(["pipeline", "--dry-run", "--confirm", "--test-mode", "--limit", "5"])
        assert rc == 0

    def test_cli_help_invocation(self):
        """Verify calling main with empty argv prints help and returns 0."""
        rc = main([])
        assert rc == 0
