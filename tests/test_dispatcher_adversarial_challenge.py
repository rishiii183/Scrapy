"""
Adversarial Empirical Challenge Suite for Milestone 4 (Outreach Dispatch Engine).

Author: challenger_m4_2
Scope:
1. WhatsApp Click-to-Chat URL Generation & Resilience:
   - Phone format variations: extensions, colons, spaces, #, x, +1 country codes, dashes, non-digits
   - RFC 3986 URL percent-encoding of message bodies (spaces, newlines, query reserved chars, emojis, unicode)
   - URL parameter isolation (no query parameter injection via & or =)
   - Browser safe length verification (>2048 chars)
2. Randomized Pacing Range & Time Acceleration:
   - Monte Carlo analysis (N=10,000) verifying strict adherence to [45.0, 180.0] seconds
   - Jitter distribution statistics (mean, variance, continuous float uniqueness)
   - Inverted and degenerate boundary handling
   - Zero wall-clock blocking in test mode (< 0.2s for 500 delays)
   - Daily send cap enforcement and countdown
3. CRM State Updates & Atomicity:
   - Dispatch success transitions: Column A -> 'Contacted (Touch 1)', Column O -> 'YYYY-MM-DD', Column U notes, Column Z -> 'Dispatched'
   - Column immutability: zero corruption of other lead fields
   - State preservation on safety gate rejection
   - State preservation on delivery failure
   - Exact Google Sheets range coordinates and API resilience
"""

import math
import random
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from src.config import DAILY_SEND_CAP, MAX_DELAY_SECONDS, MIN_DELAY_SECONDS, SHEET_ID, SHEET_TAB
from src.crm.sheets_client import SheetsClient
from src.dispatcher import (
    DispatchResult,
    DispatchSummary,
    EmailClient,
    OutreachDispatcher,
    PacingController,
    SafetyGate,
    WhatsAppClient,
    apply_daily_cap,
    build_whatsapp_link,
    compute_random_delay,
    extract_clean_10digit_phone,
    is_phone_only_lead,
    is_valid_pacing_delay,
    update_crm_dispatch_record,
    update_sheet_dispatch_state,
)
from src.models import CRMRecord, OutreachDraft


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def sample_crm_record():
    return CRMRecord(
        row_index=14,
        lead_status="Not Contacted",
        priority="High",
        company_name="Apex Roofing Texas",
        website="None (No Website)",
        industry_niche="Storm Damage & Re-roofing",
        company_size="1-10",
        contact_first_name="Roofing Team",
        contact_last_name="Contractor",
        job_title="Owner / Contractor",
        work_email="contact@apexroofingtx.com",
        email_verification="Verified",
        linkedin_profile="",
        location="Tyler, TX (CST)",
        outreach_channel="Cold Email",
        est_deal_value=4500,
        notes_and_next_steps="Phone: (903) 807-0683.",
    )


@pytest.fixture
def sample_phone_crm_record():
    return CRMRecord(
        row_index=15,
        lead_status="Not Contacted",
        priority="High",
        company_name="Lone Star Roofer Restoration",
        website="None (No Website)",
        industry_niche="Emergency Leak Repair",
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
        notes_and_next_steps="Phone: (903) 807-0683.",
    )


@pytest.fixture
def sample_draft(sample_crm_record):
    return OutreachDraft(
        crm_record=sample_crm_record,
        icebreaker="Saw your roofing work in Tyler, TX. Great local reputation.",
        offer_angle="Emergency leak search traffic in Tyler is going to competitors.",
        staged_email_subject="Quick question regarding Tyler roof repair leads",
        staged_email_body="Hi Team,\n\nWe noticed homeowners in Tyler searching for roofers aren't finding your page.",
        staged_whatsapp_msg="Hi Apex Roofing, noticed your business in Tyler lacks a web presence for emergency roof searches.",
        staged_wame_url="https://wa.me/19038070683?text=Hi",
        approval_status="Drafted / Ready for Review",
    )


@pytest.fixture
def sample_phone_draft(sample_phone_crm_record):
    return OutreachDraft(
        crm_record=sample_phone_crm_record,
        icebreaker="Saw your roofing work in Tyler, TX. Great local reputation.",
        offer_angle="Emergency leak search traffic in Tyler is going to competitors.",
        staged_email_subject="Quick question regarding Tyler roof repair leads",
        staged_email_body="Hi Team,\n\nWe noticed homeowners in Tyler searching for roofers aren't finding your page.",
        staged_whatsapp_msg="Hi Lone Star, noticed your business in Tyler lacks a web presence for emergency roof searches.",
        staged_wame_url="https://wa.me/19038070683?text=Hi",
        approval_status="Drafted / Ready for Review",
    )


# ===========================================================================
# 1. CHALLENGE 1: WhatsApp Click-to-Chat URL Resilience & RFC 3986 Encoding
# ===========================================================================

class TestChallenge1WhatsAppUrlResilience:
    """
    Adversarially tests WhatsApp click-to-chat URL generation across phone variations and payload encoding.
    """

    PHONE_VARIATIONS = [
        # Standard formats
        ("(903) 807-0683", "19038070683"),
        ("903-807-0683", "19038070683"),
        ("903.807.0683", "19038070683"),
        ("9038070683", "19038070683"),
        ("903 / 807 - 0683", "19038070683"),
        ("(903).807 - 0683", "19038070683"),
        # Country code variations
        ("+1 (903) 807-0683", "19038070683"),
        ("+1-903-807-0683", "19038070683"),
        ("+1.903.807.0683", "19038070683"),
        ("+1 903 807 0683", "19038070683"),
        ("+19038070683", "19038070683"),
        ("+ 1 (903) 807-0683", "19038070683"),
        ("1 (903) 807-0683", "19038070683"),
        ("1-903-807-0683", "19038070683"),
        ("19038070683", "19038070683"),
        # Extensions with varied syntax
        ("(903) 807-0683 ext 12", "19038070683"),
        ("(903) 807-0683 ext. 12", "19038070683"),
        ("(903) 807-0683 ext: 12", "19038070683"),
        ("(903) 807-0683 ext:12", "19038070683"),
        ("(903) 807-0683 ext : 12", "19038070683"),
        ("(903) 807-0683 ext.: 12", "19038070683"),
        ("(903) 807-0683 EXT 123", "19038070683"),
        ("(903) 807-0683 EXT: 123", "19038070683"),
        ("(903) 807-0683 extension 12", "19038070683"),
        ("(903) 807-0683 extension: 12", "19038070683"),
        ("(903) 807-0683 Extension: 45", "19038070683"),
        ("(903) 807-0683 x 12", "19038070683"),
        ("(903) 807-0683 x: 12", "19038070683"),
        ("(903) 807-0683 x:12", "19038070683"),
        ("(903) 807-0683 x401", "19038070683"),
        ("(903) 807-0683 X 505", "19038070683"),
        ("(903) 807-0683 X:789", "19038070683"),
        ("(903) 807-0683 # 12", "19038070683"),
        ("(903) 807-0683 #12", "19038070683"),
        ("(903) 807-0683 #: 12", "19038070683"),
        ("(903) 807-0683 #1234", "19038070683"),
        # Prefixes & text notations
        ("Call: (903) 807-0683", "19038070683"),
        ("Call: 903-807-0683 ext 12", "19038070683"),
        ("tel:+1-903-807-0683", "19038070683"),
        ("+1 (903) 807-0683 ext. 42", "19038070683"),
        ("+1-903-807-0683 x99", "19038070683"),
        ("+1 903 807 0683 ext: 501", "19038070683"),
    ]

    @pytest.mark.parametrize("phone_input,expected_phone_param", PHONE_VARIATIONS)
    def test_phone_cleaning_and_link_structure(self, phone_input: str, expected_phone_param: str):
        """Verify phone cleaning and resulting wa.me link for diverse phone inputs."""
        cleaned = extract_clean_10digit_phone(phone_input)
        assert len(cleaned) == 10
        assert cleaned == "9038070683"

        link = build_whatsapp_link(phone_input, "Hello roofer")
        expected_prefix = f"https://wa.me/{expected_phone_param}?text="
        assert link.startswith(expected_prefix), f"Link '{link}' does not start with '{expected_prefix}'"

        parsed = urllib.parse.urlparse(link)
        assert parsed.scheme == "https"
        assert parsed.netloc == "wa.me"
        assert parsed.path == f"/{expected_phone_param}"

    @pytest.mark.parametrize("invalid_input", [
        "",
        "   ",
        "NO_PHONE",
        "Call: none",
        "N/A",
        "---",
    ])
    def test_invalid_phone_inputs_graceful_handling(self, invalid_input):
        """Verify that non-numeric or empty phone strings fail gracefully in WhatsAppClient."""
        client = WhatsAppClient(dry_run=True)
        res = client.send(invalid_input, "Test message")
        assert res.success is False
        assert "invalid phone number" in res.error.lower()
        assert len(client.audit_log) == 1

    def test_none_phone_input_crashes_with_pydantic_validation_error(self):
        """
        Adversarial vulnerability proof:
        Passing phone=None to WhatsAppClient.send() causes an unhandled Pydantic ValidationError
        instead of returning DispatchResult(success=False).
        Root cause: src/dispatcher/whatsapp_client.py:108 sets recipient=phone where phone=None,
        violating DispatchResult schema (recipient: str is required non-optional).
        """
        import pydantic
        client = WhatsAppClient(dry_run=True)
        with pytest.raises(pydantic.ValidationError) as exc_info:
            client.send(None, "Test message")
        err_str = str(exc_info.value)
        assert "recipient" in err_str
        assert "Input should be a valid string" in err_str

    def test_short_phone_number_accepted_as_success_vulnerability(self):
        """
        Adversarial vulnerability proof:
        Passing short phone numbers (e.g. '12345' or '807-0683') causes WhatsAppClient to mark
        dispatch as success=True and generate invalid URLs (https://wa.me/12345).
        Root cause: src/dispatcher/whatsapp_client.py:48 has no-op return:
        'return digits if len(digits) == 10 else digits' which returns partial digits
        instead of rejecting invalid numbers or returning an empty string.
        """
        client = WhatsAppClient(dry_run=True)
        res = client.send("12345", "Test message")
        # Currently, this erroneously returns success=True with recipient https://wa.me/12345
        assert res.success is True
        assert res.recipient == "https://wa.me/12345?text=Test%20message"


    def test_rfc3986_encoding_reserved_query_characters(self):
        """
        Verify that characters reserved in URI query strings (?, &, =, #, /, %, +)
        do NOT cause query parameter injection or fragment splitting.
        """
        complex_msg = "Looking for repairs? Call us & mention code = ROOF#1 / 20% discount + bonus!"
        link = build_whatsapp_link("9038070683", complex_msg)

        parsed = urllib.parse.urlparse(link)
        assert parsed.fragment == "", "Fragment '#' was improperly treated as a URL fragment instead of encoded!"

        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        assert list(qs.keys()) == ["text"], f"Query string was corrupted into extra parameters: {list(qs.keys())}"

        # Verify decoded text exactly recovers original without loss or mutation
        extracted = qs["text"][0]
        assert extracted == complex_msg

        # Verify specific percent encodings
        assert "%3F" in link  # ?
        assert "%26" in link  # &
        assert "%3D" in link  # =
        assert "%23" in link  # #
        assert "%2F" in link  # /
        assert "%25" in link  # %
        assert "%2B" in link  # +

    def test_rfc3986_encoding_newlines_and_spaces(self):
        """Verify RFC 3986 percent-encoding of spaces (%20) and newlines (%0A, %0D%0A)."""
        msg = "Line 1\nLine 2\r\nLine 3 with   multiple   spaces."
        link = build_whatsapp_link("9038070683", msg)

        assert "%0A" in link
        assert "%0D%0A" in link
        assert "%20" in link

        unquoted = urllib.parse.unquote(link.split("?text=")[1])
        assert unquoted == msg

    def test_rfc3986_encoding_emojis_and_unicode_symbols(self):
        """Verify UTF-8 multi-byte emojis and typographical glyphs survive roundtrip perfectly."""
        msg = "🏠 Apex Roofing 🔨 Emergency leak detected! 🚨 Call now: 📈 +15% ROI 🔥 ⚡ 🎯 “Smart Quotes” & ‘Apostrophes’ — Em-dash."
        link = build_whatsapp_link("(903) 807-0683", msg)

        # Ensure no raw unicode outside ASCII exists in the URL query string
        try:
            link.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"Constructed wa.me URL contains unencoded non-ASCII characters: {e}")

        unquoted = urllib.parse.unquote(link.split("?text=")[1])
        assert unquoted == msg

    def test_adversarial_random_payload_roundtrip_fuzzing(self):
        """Fuzz 100 randomly generated messages with mixed symbols and ensure 100% roundtrip fidelity."""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ?&=#/%+:\n\r\t.,!@$^&*()_~<>{}[]\"'|\\`"
        emojis = ["🔥", "🚨", "🔨", "🏠", "⭐", "💰", "📈"]

        for seed in range(100):
            rng = random.Random(seed)
            length = rng.randint(10, 150)
            msg_chars = [rng.choice(alphabet) for _ in range(length)]
            for _ in range(rng.randint(0, 3)):
                msg_chars.insert(rng.randint(0, len(msg_chars)), rng.choice(emojis))
            random_msg = "".join(msg_chars)

            link = build_whatsapp_link("9038070683", random_msg)
            parsed = urllib.parse.urlparse(link)
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

            assert list(qs.keys()) == ["text"], f"Seed {seed} created unexpected keys: {qs.keys()}"
            assert qs["text"][0] == random_msg

    def test_browser_safe_length_warning(self, caplog):
        """Verify that wa.me URLs exceeding 2048 characters trigger a warning log."""
        long_msg = "A" * 2100
        with caplog.at_level("WARNING"):
            link = build_whatsapp_link("9038070683", long_msg)
            assert len(link) > 2048
            assert any("exceeds browser safe length" in record.message for record in caplog.records)


# ===========================================================================
# 2. CHALLENGE 2: Randomized Pacing Range & Time Acceleration
# ===========================================================================

class TestChallenge2RandomizedPacing:
    """
    Adversarially tests pacing delay boundaries [45, 180], statistical distribution,
    accelerated test-mode clock, and daily send cap enforcement.
    """

    def test_monte_carlo_delay_boundary_strictness(self):
        """
        Run Monte Carlo simulation of N=10,000 samples.
        Strictly verify that every single delay d satisfies 45.0 <= d <= 180.0.
        """
        n_samples = 10000
        delays = [compute_random_delay() for _ in range(n_samples)]

        min_val = min(delays)
        max_val = max(delays)

        assert min_val >= 45.0, f"Observed delay below minimum: {min_val} < 45.0"
        assert max_val <= 180.0, f"Observed delay above maximum: {max_val} > 180.0"

        # Continuous jitter assertion: all 10,000 float samples should be unique
        assert len(set(delays)) == n_samples, "Duplicate delays detected in continuous uniform distribution"

        # Statistical sanity checks for Uniform(45, 180)
        mean = sum(delays) / n_samples
        expected_mean = (45.0 + 180.0) / 2.0  # 112.5
        variance = sum((x - mean) ** 2 for x in delays) / n_samples
        std_dev = math.sqrt(variance)
        expected_std_dev = (180.0 - 45.0) / math.sqrt(12.0)  # ~38.97

        assert abs(mean - expected_mean) < 2.0, f"Mean delay {mean} drifted from expected {expected_mean}"
        assert abs(std_dev - expected_std_dev) < 2.0, f"Std dev {std_dev} drifted from expected {expected_std_dev}"

    def test_inverted_and_degenerate_pacing_inputs(self):
        """Verify resilience when min > max, min == max, or custom bounds are provided."""
        # Inverted bounds (180, 45) -> should swap gracefully
        inverted = compute_random_delay(180.0, 45.0)
        assert 45.0 <= inverted <= 180.0

        # Degenerate bounds (60, 60) -> should equal exactly 60.0
        degenerate = compute_random_delay(60.0, 60.0)
        assert degenerate == 60.0

        # Custom bounds (10, 20)
        custom = compute_random_delay(10.0, 20.0)
        assert 10.0 <= custom <= 20.0

    def test_is_valid_pacing_delay_edge_cases(self):
        """Verify boundary validator is_valid_pacing_delay."""
        assert is_valid_pacing_delay(45.0) is True
        assert is_valid_pacing_delay(180.0) is True
        assert is_valid_pacing_delay(112.5) is True
        assert is_valid_pacing_delay(44.999) is False
        assert is_valid_pacing_delay(180.001) is False
        assert is_valid_pacing_delay(0.0) is False
        assert is_valid_pacing_delay(-10.0) is False

    def test_pacing_controller_test_mode_instantaneous_execution(self):
        """
        Verify that test_mode=True executes instantaneously (<0.2s for 500 dispatches)
        without blocking the thread, while faithfully recording simulated elapsed time.
        """
        controller = PacingController(test_mode=True, test_delay=0.0)

        t_start = time.perf_counter()
        delays = [controller.wait() for _ in range(500)]
        t_elapsed = time.perf_counter() - t_start

        # 500 delays * 45s = minimum 22,500s (~6.2 hours) in production!
        # In test mode, this must take under 0.2 seconds.
        assert t_elapsed < 0.2, f"Pacing test mode blocked real time! Elapsed: {t_elapsed:.4f}s"

        # Verify simulated elapsed time tracks the sum of recorded delays
        assert len(delays) == 500
        assert all(45.0 <= d <= 180.0 for d in delays)
        assert abs(controller.simulated_elapsed - sum(delays)) < 1e-6
        assert len(controller.delays_history) == 500

    def test_daily_send_cap_enforcement_and_tracker(self):
        """Verify daily send cap boundary conditions, item slicing, and state tracking."""
        # 1. apply_daily_cap slicing
        items = list(range(50))
        assert len(apply_daily_cap(items, cap=25)) == 25
        assert len(apply_daily_cap(items, cap=10)) == 10
        assert len(apply_daily_cap(items, cap=0)) == 0
        assert len(apply_daily_cap(items, cap=-5)) == 0
        assert len(apply_daily_cap(items[:5], cap=25)) == 5

        # 2. Stateful controller cap tracking
        controller = PacingController(daily_cap=5, test_mode=True)
        assert controller.can_dispatch() is True
        assert controller.get_remaining_cap() == 5

        for i in range(5):
            assert controller.can_dispatch() is True
            assert controller.get_remaining_cap() == (5 - i)
            controller.record_dispatch()

        # At cap = 5
        assert controller.can_dispatch() is False
        assert controller.get_remaining_cap() == 0

        # Reset
        controller.reset()
        assert controller.can_dispatch() is True
        assert controller.get_remaining_cap() == 5
        assert controller.sent_count == 0


# ===========================================================================
# 3. CHALLENGE 3: CRM Updates and Atomicity
# ===========================================================================

class TestChallenge3CrmUpdatesAndAtomicity:
    """
    Adversarially tests CRM state updates upon dispatch:
    - Success: Column A updates to 'Contacted (Touch 1)', Column O records 'YYYY-MM-DD',
      Column U appends audit note, Column Z updates to 'Dispatched'.
    - Preservation: on rejection or failure, Column A and O remain unmutated.
    - Sheet sync: correct range coordinates ('Leads Tracker'!A{row}, O{row}, U{row}, Z{row}).
    """

    def test_crm_dispatch_record_immutability_and_state_transition(self, sample_crm_record):
        """Verify immutable transition of CRMRecord upon dispatch."""
        orig_dict = sample_crm_record.model_dump()
        today_str = "2026-10-24"

        updated = update_crm_dispatch_record(sample_crm_record, channel="Cold Email", date_str=today_str)

        # 1. State changes verified
        assert updated.lead_status == "Contacted (Touch 1)"
        assert getattr(updated, "touch_1_date") == today_str
        assert "Dispatched via Cold Email on 2026-10-24." in updated.notes_and_next_steps

        # 2. Immutability of other columns verified
        updated_dict = updated.model_dump()
        for field, orig_val in orig_dict.items():
            if field in {"lead_status", "notes_and_next_steps"}:
                continue
            assert updated_dict[field] == orig_val, f"Field '{field}' was unexpectedly corrupted: {updated_dict[field]} != {orig_val}"

        # 3. Original record was not mutated in-place
        assert sample_crm_record.lead_status == "Not Contacted"

    def test_orchestrator_successful_dispatch_updates_crm_and_sheet(self, sample_draft):
        """Verify end-to-end dispatch_single updates draft, CRMRecord, and Google Sheets."""
        mock_sheets = MagicMock(spec=SheetsClient)
        mock_sheets.update_range.return_value = {"updatedCells": 1}

        dispatcher = OutreachDispatcher(
            sheets_client=mock_sheets,
            dry_run=True,
            default_confirmed=True,
            test_mode=True,
        )

        res = dispatcher.dispatch_single(sample_draft, sync_sheet=True)

        assert res is not None
        assert res.success is True
        assert sample_draft.approval_status == "Dispatched"
        assert sample_draft.crm_record.lead_status == "Contacted (Touch 1)"
        assert getattr(sample_draft.crm_record, "touch_1_date") == datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Verify Google Sheet update calls
        assert mock_sheets.update_range.call_count == 4
        calls = mock_sheets.update_range.call_args_list

        # Col A
        assert calls[0].kwargs["range_str"] == f"'{SHEET_TAB}'!A14"
        assert calls[0].kwargs["values"] == [["Contacted (Touch 1)"]]

        # Col O
        assert calls[1].kwargs["range_str"] == f"'{SHEET_TAB}'!O14"
        assert calls[1].kwargs["values"] == [[datetime.now(timezone.utc).strftime("%Y-%m-%d")]]

        # Col U
        assert calls[2].kwargs["range_str"] == f"'{SHEET_TAB}'!U14"
        assert "Dispatched via Cold Email on" in calls[2].kwargs["values"][0][0]

        # Col Z
        assert calls[3].kwargs["range_str"] == f"'{SHEET_TAB}'!Z14"
        assert calls[3].kwargs["values"] == [["Dispatched"]]

    def test_orchestrator_safety_gate_rejection_preserves_state(self, sample_draft):
        """Verify that when safety gate blocks dispatch, no CRM state or sheet changes occur."""
        mock_sheets = MagicMock(spec=SheetsClient)

        dispatcher = OutreachDispatcher(
            sheets_client=mock_sheets,
            dry_run=True,
            default_confirmed=False,  # Unconfirmed -> blocked
            test_mode=True,
        )

        res = dispatcher.dispatch_single(sample_draft, confirmed=False, sync_sheet=True)

        assert res is None
        assert sample_draft.approval_status == "Drafted / Ready for Review"
        assert sample_draft.crm_record.lead_status == "Not Contacted"
        assert not hasattr(sample_draft.crm_record, "touch_1_date")
        mock_sheets.update_range.assert_not_called()

    def test_orchestrator_delivery_failure_preserves_state(self, sample_draft):
        """Verify that when delivery client returns failure, lead status is NOT marked contacted."""
        mock_sheets = MagicMock(spec=SheetsClient)
        failing_email_client = MagicMock(spec=EmailClient)
        failing_email_client.send.return_value = DispatchResult(
            success=False,
            channel="Cold Email",
            recipient="test@bad.com",
            subject="Sub",
            body="Body",
            timestamp="2026-10-24 12:00:00Z",
            mode="Dry-Run Simulator",
            error="SMTP connection timed out",
        )

        dispatcher = OutreachDispatcher(
            email_client=failing_email_client,
            sheets_client=mock_sheets,
            dry_run=True,
            default_confirmed=True,
            test_mode=True,
        )

        res = dispatcher.dispatch_single(sample_draft, sync_sheet=True)

        assert res is not None
        assert res.success is False
        # State must remain unmutated!
        assert sample_draft.approval_status == "Drafted / Ready for Review"
        assert sample_draft.crm_record.lead_status == "Not Contacted"
        assert not hasattr(sample_draft.crm_record, "touch_1_date")
        mock_sheets.update_range.assert_not_called()

    def test_sheets_api_exception_resilience(self, sample_draft, caplog):
        """Verify that a Google Sheets API exception does not crash the dispatcher."""
        mock_sheets = MagicMock(spec=SheetsClient)
        mock_sheets.update_range.side_effect = RuntimeError("Google Sheets API 503 Service Unavailable")

        dispatcher = OutreachDispatcher(
            sheets_client=mock_sheets,
            dry_run=True,
            default_confirmed=True,
            test_mode=True,
        )

        with caplog.at_level("ERROR"):
            res = dispatcher.dispatch_single(sample_draft, sync_sheet=True)
            assert res is not None
            assert res.success is True
            # In-memory draft was updated even though remote sync logged an error
            assert sample_draft.approval_status == "Dispatched"
            assert any("Failed to update Google Sheet dispatch state" in r.message for r in caplog.records)


# ===========================================================================
# 4. End-to-End Batch Workflow & Channel Routing Stress
# ===========================================================================

class TestChallengeBatchWorkflowStress:
    """Stress-tests batch dispatch with mixed channels, daily caps, and pacing."""

    def test_batch_dispatch_mixed_channels_with_cap(self, sample_draft, sample_phone_draft):
        """Verify dispatch_batch routes Cold Email vs WhatsApp correctly and enforces cap."""
        # Create a batch of 10 drafts (5 email, 5 phone)
        drafts: List[OutreachDraft] = []
        for i in range(5):
            d_email = sample_draft.model_copy(deep=True)
            d_email.crm_record.row_index = 14 + i
            drafts.append(d_email)

            d_phone = sample_phone_draft.model_copy(deep=True)
            d_phone.crm_record.row_index = 19 + i
            drafts.append(d_phone)

        # Set cap to 4
        pacing = PacingController(daily_cap=4, test_mode=True)
        dispatcher = OutreachDispatcher(
            pacing_controller=pacing,
            dry_run=True,
            default_confirmed=True,
            test_mode=True,
        )

        summary = dispatcher.dispatch_batch(drafts, confirmed=True, cap=4, sync_sheet=False)

        assert summary.total_drafts == 10
        assert summary.approved_count == 10
        assert summary.total_dispatched == 4
        assert summary.skipped_count == 6  # 6 capped out
        assert summary.dispatched_email == 2
        assert summary.dispatched_whatsapp == 2

        # Pacing: for 4 dispatches, 3 intervals are recorded (delay between items 1-4)
        assert len(pacing.delays_history) == 3
        assert all(45.0 <= d <= 180.0 for d in pacing.delays_history)

        # Verify first 4 drafts are marked Dispatched, remaining 6 are untouched
        for d in drafts[:4]:
            assert d.approval_status == "Dispatched"
            assert d.crm_record.lead_status == "Contacted (Touch 1)"
        for d in drafts[4:]:
            assert d.approval_status == "Drafted / Ready for Review"
            assert d.crm_record.lead_status == "Not Contacted"
