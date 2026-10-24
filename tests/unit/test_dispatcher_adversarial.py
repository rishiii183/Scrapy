"""
Adversarial Stress Test Suite for Milestone 4: Safety Gate, Approval Lock, Daily Caps, & Dry-Run.

Authored by: challenger_m4_1 (Empirical Challenger)
Focus Areas:
1. Safety Gate Bypass: Attempting outreach dispatch with status != 'Approved', unconfirmed requests,
   tampered statuses, already-dispatched leads, and interactive prompt bypasses.
2. Daily Send Limit Enforcement: Exceeding daily cap, zero/negative cap handling, multi-batch accumulation,
   pacing jitter distribution, and stateful controller reset.
3. Dry-Run Simulation Invariants: Verification of zero socket/HTTP network calls, safe fallback when
   SMTP credentials are missing, complete audit log retention, and side-effect isolation.
"""

import io
import re
import socket
import urllib.parse
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from src.cli import build_parser, main
from src.config import SHEET_ID, SHEET_TAB, DAILY_SEND_CAP
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
def base_crm_email():
    """Standard valid CRM record for Cold Email."""
    return CRMRecord(
        row_index=14,
        lead_status="Not Contacted",
        priority="🔥 High",
        company_name="Apex Elite Roofing",
        website="None (No Website)",
        industry_niche="Storm Damage & Re-roofing",
        company_size="1-10",
        contact_first_name="Roofing Team",
        contact_last_name="Contractor",
        job_title="Owner / Contractor",
        work_email="owner@apexeliteroofing.com",
        email_verification="Verified",
        linkedin_profile="",
        location="Tyler, TX (CST)",
        outreach_channel="Cold Email",
        est_deal_value=5000,
        notes_and_next_steps="Phone: (903) 555-0199. Candidate for website.",
    )


@pytest.fixture
def base_crm_phone():
    """Standard valid CRM record for phone-only WhatsApp fallback."""
    return CRMRecord(
        row_index=15,
        lead_status="Not Contacted",
        priority="🔥 High",
        company_name="Lone Star Storm Pros",
        website="None (No Website)",
        industry_niche="Storm Damage & Re-roofing",
        company_size="1-10",
        contact_first_name="Roofing Team",
        contact_last_name="Contractor",
        job_title="Owner / Contractor",
        work_email="Call: (903) 555-0288",
        email_verification="Unverified",
        linkedin_profile="",
        location="Tyler, TX (CST)",
        outreach_channel="Cold Call",
        est_deal_value=4500,
        notes_and_next_steps="Phone: (903) 555-0288. Candidate for website.",
    )


@pytest.fixture
def sample_email_draft(base_crm_email):
    """Standard OutreachDraft in 'Drafted / Ready for Review' status."""
    return OutreachDraft(
        crm_record=base_crm_email,
        icebreaker="Came across Apex Elite Roofing while researching storm damage specialists in Tyler.",
        offer_angle="Recovering emergency roof repair volume lost to ranking local competitors.",
        staged_email_subject="Emergency storm repair inquiries in Tyler - Apex Elite Roofing",
        staged_email_body="Hi Team,\n\nWe saw you have no website capturing organic Tyler search leads.\n\nBest,\nOutreach",
        staged_whatsapp_msg="Hi, saw your storm repair work in Tyler. Quick inquiry on roof repair jobs?",
        staged_wame_url="https://wa.me/19035550199?text=Hi",
        approval_status="Drafted / Ready for Review",
    )


@pytest.fixture
def sample_phone_draft(base_crm_phone):
    """Standard phone-only OutreachDraft for WhatsApp fallback."""
    return OutreachDraft(
        crm_record=base_crm_phone,
        icebreaker="Came across Lone Star Storm Pros while reviewing contractors in Tyler.",
        offer_angle="Capturing storm damage restoration searches in Smith County.",
        staged_email_subject="Storm restoration volume in Tyler",
        staged_email_body="Hi Team,\n\nWe noticed your team lacks a digital hub.\n\nBest,\nOutreach",
        staged_whatsapp_msg="Hi, saw your roofing work in Tyler. Quick question on storm repair jobs?",
        staged_wame_url=build_whatsapp_link("9035550288", "Hi, saw your roofing work in Tyler. Quick question on storm repair jobs?"),
        approval_status="Drafted / Ready for Review",
    )


def create_draft_batch(base_draft: OutreachDraft, count: int, start_row: int = 14):
    """Helper to generate a batch of unique drafts."""
    batch = []
    for i in range(count):
        rec = base_draft.crm_record.model_copy()
        rec.row_index = start_row + i
        rec.company_name = f"Contractor Company {i+1}"
        if "@" in rec.work_email:
            rec.work_email = f"lead_{i+1}@contractor{i+1}.com"
        else:
            rec.work_email = f"Call: (903) 555-{1000 + i}"
        d = base_draft.model_copy(update={"crm_record": rec})
        batch.append(d)
    return batch


# ===========================================================================
# Challenge 1: Safety Gate Bypass & Staged Review Approval Lock
# ===========================================================================

class TestAdversarialSafetyGate:
    """
    Stress-test safety gate approval locks against bypass attempts, corrupted states,
    and missing confirmation flags.
    """

    def test_bypass_unconfirmed_dispatch_single_strictly_blocked(self, sample_email_draft):
        """
        ATTACK: Attempt to dispatch single draft with confirmed=False.
        VERIFY: Dispatcher returns None, no email logged, lead remains untouched.
        """
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, default_confirmed=False)
        result = dispatcher.dispatch_single(sample_email_draft, confirmed=False)

        assert result is None
        assert sample_email_draft.approval_status == "Drafted / Ready for Review"
        assert sample_email_draft.crm_record.lead_status == "Not Contacted"
        assert len(dispatcher.email_client.audit_log) == 0
        assert dispatcher.pacing_controller.sent_count == 0

    def test_bypass_unconfirmed_batch_dispatch_strictly_blocked(self, sample_email_draft):
        """
        ATTACK: Pass 10 unconfirmed drafts into dispatch_batch.
        VERIFY: Zero leads dispatched, all 10 skipped, lead records unaltered.
        """
        batch = create_draft_batch(sample_email_draft, count=10)
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, default_confirmed=False)
        summary = dispatcher.dispatch_batch(batch, confirmed=False)

        assert summary.total_drafts == 10
        assert summary.approved_count == 0
        assert summary.total_dispatched == 0
        assert summary.skipped_count == 10
        assert len(summary.results) == 0

        # Verify all drafts remained uncontacted
        for d in batch:
            assert d.approval_status == "Drafted / Ready for Review"
            assert d.crm_record.lead_status == "Not Contacted"

    def test_bypass_exception_enforcement_raises_safety_gate_error(self, sample_email_draft):
        """
        ATTACK: Invoke require_confirmation and check_safety_gate(raise_on_error=True) without confirmation.
        VERIFY: SafetyGateError is raised with specific context (company name and --confirm).
        """
        with pytest.raises(SafetyGateError) as exc_info:
            require_confirmation(sample_email_draft, confirmed=False)
        assert "Apex Elite Roofing" in str(exc_info.value)
        assert "--confirm" in str(exc_info.value)

        with pytest.raises(SafetyGateError) as exc_info2:
            check_safety_gate(sample_email_draft, confirmed=False, raise_on_error=True)
        assert "Explicit user confirmation required" in str(exc_info2.value)

    def test_bypass_already_dispatched_lead_idempotency_lock(self, sample_email_draft):
        """
        ATTACK: Attempt to redispatch a draft that has already been dispatched, even with confirmed=True.
        VERIFY: Blocked by safety gate, preventing duplicate outreach / spamming contractors.
        """
        sample_email_draft.approval_status = "Dispatched"
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True)

        # check_safety_gate direct
        assert check_safety_gate(sample_email_draft, confirmed=True) is False

        # require_confirmation raise
        with pytest.raises(SafetyGateError, match="already been dispatched"):
            require_confirmation(sample_email_draft, confirmed=True)

        # dispatch_single call
        res = dispatcher.dispatch_single(sample_email_draft, confirmed=True)
        assert res is None
        assert len(dispatcher.email_client.audit_log) == 0

    @pytest.mark.parametrize("corrupted_status", [
        "Drafted",                     # Missing " / Ready for Review"
        "Pending",                     # Unrecognized stage
        "Rejected",                    # Rejected lead
        "In Review",                   # Intermediate non-standard stage
        "Awaiting Approval",           # Synonymous non-permitted stage
        "",                            # Empty string
        None,                          # Null status
        "Approved ",                   # Trailing whitespace
        "approved",                    # Lowercase mismatch
        "DRAFTED / READY FOR REVIEW",  # Uppercase mismatch
        "' OR '1'='1",                 # Injection attempt
        "<script>alert(1)</script>",   # XSS payload in status
    ])
    def test_bypass_corrupted_or_tampered_approval_status(self, sample_email_draft, corrupted_status):
        """
        ATTACK: Craft drafts with diverse invalid, tampered, or malformed approval statuses.
        VERIFY: check_safety_gate strictly blocks all unpermitted status values even when confirmed=True.
        """
        sample_email_draft.approval_status = corrupted_status

        assert check_safety_gate(sample_email_draft, confirmed=True) is False

        with pytest.raises(SafetyGateError) as exc:
            check_safety_gate(sample_email_draft, confirmed=True, raise_on_error=True)
        assert "Invalid approval status" in str(exc.value)

    @pytest.mark.parametrize("user_input,expected_decision", [
        ("", False),             # Empty enter
        ("   ", False),          # Spaces only
        ("n", False),            # Explicit no
        ("no", False),           # Explicit no
        ("NO", False),           # Uppercase no
        ("No", False),           # Mixed case no
        ("false", False),        # Boolean false string
        ("0", False),            # Numeric zero
        ("reject", False),       # Reject word
        ("maybe", False),        # Ambiguous
        ("yesss", False),        # Typo
        ("1", False),            # Numeric one
        ("true", False),         # Boolean true string
        ("proceed", False),      # Non-standard affirmative
        ("y", True),             # Valid lowercase y
        ("Y", True),             # Valid uppercase Y
        ("yes", True),           # Valid lowercase yes
        ("YES", True),           # Valid uppercase YES
        ("  yes  ", True),       # Trimmed valid yes
    ])
    def test_interactive_prompt_approval_boundaries(self, sample_email_draft, user_input, expected_decision):
        """
        ATTACK: Supply boundary, ambiguous, and deceptive inputs to interactive prompt_user_approval.
        VERIFY: Only exact trimmed 'y' or 'yes' (case-insensitive) approves; all others safely reject.
        """
        stream_in = io.StringIO(f"{user_input}\n")
        stream_out = io.StringIO()
        decision = prompt_user_approval(sample_email_draft, stream_in=stream_in, stream_out=stream_out)
        assert decision == expected_decision

    def test_cli_dispatch_unconfirmed_blocks_execution(self):
        """
        ATTACK: Run `src.cli dispatch` without `--confirm` flag.
        VERIFY: Exits with non-zero exit code (1) and does not dispatch.
        """
        rc = main(["dispatch", "--dry-run"])
        assert rc == 1

    def test_cli_pipeline_unconfirmed_pauses_before_dispatch(self):
        """
        ATTACK: Run `src.cli pipeline` without `--confirm` flag.
        VERIFY: Pipeline runs stages 1-3 safely, stages drafts in V-Z, but leaves dispatch paused.
        """
        rc = main(["pipeline", "--dry-run", "--test-mode", "--limit", "3"])
        assert rc == 0


# ===========================================================================
# Challenge 2: Daily Send Limit Enforcement & Stateful Pacing
# ===========================================================================

class TestAdversarialDailyCapAndPacing:
    """
    Stress-test daily cap enforcement under oversized workloads, zero/negative caps,
    multi-batch runs, and verify jitter distribution invariants.
    """

    def test_daily_cap_strictly_halts_batch_at_configured_limit(self, sample_email_draft):
        """
        ATTACK: Submit batch of 35 drafts when daily cap is 25.
        VERIFY: Exactly 25 are dispatched, remaining 10 are skipped, cap is respected.
        """
        batch = create_draft_batch(sample_email_draft, count=35)
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=25)

        summary = dispatcher.dispatch_batch(batch, confirmed=True, cap=25)

        assert summary.total_drafts == 35
        assert summary.approved_count == 35
        assert summary.total_dispatched == 25
        assert summary.skipped_count == 10
        assert summary.failed_count == 0

        # Invariant: total accounted equals total submitted
        assert summary.total_dispatched + summary.skipped_count == summary.total_drafts

        # First 25 are Dispatched, last 10 remain Drafted
        for d in batch[:25]:
            assert d.approval_status == "Dispatched"
            assert d.crm_record.lead_status == "Contacted (Touch 1)"
        for d in batch[25:]:
            assert d.approval_status == "Drafted / Ready for Review"
            assert d.crm_record.lead_status == "Not Contacted"

    def test_daily_cap_incremental_saturation(self, sample_email_draft):
        """
        ATTACK: Call dispatch_single 12 times in a loop with daily_cap=5.
        VERIFY: Calls 1-5 succeed; calls 6-12 return None and halt without dispatching.
        """
        batch = create_draft_batch(sample_email_draft, count=12)
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=5)

        results = []
        for d in batch:
            res = dispatcher.dispatch_single(d, confirmed=True)
            results.append(res)

        successful_dispatches = [r for r in results if r is not None and r.success]
        blocked_dispatches = [r for r in results if r is None]

        assert len(successful_dispatches) == 5
        assert len(blocked_dispatches) == 7
        assert dispatcher.pacing_controller.sent_count == 5
        assert dispatcher.pacing_controller.can_dispatch() is False
        assert dispatcher.pacing_controller.get_remaining_cap() == 0

    @pytest.mark.parametrize("invalid_cap", [0, -1, -50])
    def test_daily_cap_zero_and_negative_values_block_all_sends(self, sample_email_draft, invalid_cap):
        """
        ATTACK: Configure daily cap as 0 or negative integer.
        VERIFY: apply_daily_cap returns empty list, and dispatch_batch sends 0 items safely.
        """
        batch = create_draft_batch(sample_email_draft, count=5)
        sliced = apply_daily_cap(batch, cap=invalid_cap)
        assert len(sliced) == 0

        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=invalid_cap)
        summary = dispatcher.dispatch_batch(batch, confirmed=True, cap=invalid_cap)

        assert summary.total_dispatched == 0
        assert summary.skipped_count == 5

    def test_multi_batch_state_accumulation_across_runs(self, sample_email_draft):
        """
        ATTACK: Send multiple sequential batches through the same dispatcher instance (cap=10).
        VERIFY: State persists across batch calls; total sent does not exceed 10.
        """
        batch1 = create_draft_batch(sample_email_draft, count=6, start_row=14)
        batch2 = create_draft_batch(sample_email_draft, count=6, start_row=20)
        batch3 = create_draft_batch(sample_email_draft, count=6, start_row=26)

        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=10)

        # Batch 1: 6 submitted, all 6 dispatched
        s1 = dispatcher.dispatch_batch(batch1, confirmed=True)
        assert s1.total_dispatched == 6
        assert dispatcher.pacing_controller.get_remaining_cap() == 4

        # Batch 2: 6 submitted, only 4 dispatched, 2 skipped
        s2 = dispatcher.dispatch_batch(batch2, confirmed=True)
        assert s2.total_dispatched == 4
        assert s2.skipped_count == 2
        assert dispatcher.pacing_controller.get_remaining_cap() == 0

        # Batch 3: 6 submitted, 0 dispatched, 6 skipped
        s3 = dispatcher.dispatch_batch(batch3, confirmed=True)
        assert s3.total_dispatched == 0
        assert s3.skipped_count == 6

        # Total sent across all runs is capped at 10
        total_sent = s1.total_dispatched + s2.total_dispatched + s3.total_dispatched
        assert total_sent == 10
        assert dispatcher.pacing_controller.sent_count == 10

    def test_pacing_controller_reset_restores_capacity(self, sample_email_draft):
        """
        ATTACK: Saturate cap, reset controller, and attempt new dispatches.
        VERIFY: Reset restores clean state (sent_count=0) and permits new dispatches.
        """
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=3)
        b1 = create_draft_batch(sample_email_draft, count=3, start_row=14)
        dispatcher.dispatch_batch(b1, confirmed=True)
        assert dispatcher.pacing_controller.can_dispatch() is False

        # Reset controller
        dispatcher.pacing_controller.reset()
        assert dispatcher.pacing_controller.sent_count == 0
        assert dispatcher.pacing_controller.simulated_elapsed == 0.0
        assert dispatcher.pacing_controller.can_dispatch() is True
        assert dispatcher.pacing_controller.get_remaining_cap() == 3

        # New dispatches now succeed
        b2 = create_draft_batch(sample_email_draft, count=2, start_row=17)
        s2 = dispatcher.dispatch_batch(b2, confirmed=True)
        assert s2.total_dispatched == 2

    def test_randomized_pacing_delay_statistical_distribution(self):
        """
        ATTACK: Sample 1000 randomized delays from compute_random_delay(45.0, 180.0).
        VERIFY:
        - 100% of samples fall strictly within [45.0, 180.0]
        - Mean is near theoretical uniform expectation (112.5s +/- 10s)
        - Min sample is in lower quartile (<75s), Max sample is in upper quartile (>150s)
        - Jitter is continuous with no discrete clustering
        """
        samples = [compute_random_delay(45.0, 180.0) for _ in range(1000)]

        for s in samples:
            assert 45.0 <= s <= 180.0, f"Sample {s} out of bounds"

        mean_val = sum(samples) / len(samples)
        assert 102.5 <= mean_val <= 122.5, f"Mean delay {mean_val} outside expected range"

        assert min(samples) < 60.0, "Minimum sample did not explore lower boundary"
        assert max(samples) > 165.0, "Maximum sample did not explore upper boundary"

        # Unique value check (ensures continuous float jitter, not discrete integer)
        unique_samples = set(samples)
        assert len(unique_samples) > 990, "Delay generator exhibits duplicate/clustered values"

    def test_pacing_inverted_bounds_auto_correction(self):
        """
        ATTACK: Pass inverted boundaries min=180.0, max=45.0.
        VERIFY: Automatically swaps boundaries and returns a valid delay.
        """
        for _ in range(20):
            d = compute_random_delay(180.0, 45.0)
            assert 45.0 <= d <= 180.0


# ===========================================================================
# Challenge 3: Dry-Run Simulation Mode & Side-Effect Isolation
# ===========================================================================

class TestAdversarialDryRunAndSideEffects:
    """
    Stress-test dry-run isolation, network socket prevention, audit log completeness,
    and missing credentials fallback.
    """

    def test_dry_run_zero_socket_connections_intercepted(self, sample_email_draft, sample_phone_draft):
        """
        ATTACK: Place hostile intercepts on raw socket connection primitives.
        VERIFY: Dry-run batch execution makes ZERO socket connections.
        """
        def hostile_socket_connect(*args, **kwargs):
            raise RuntimeError("VIOLATION: Socket connect() attempted during dry-run simulation!")

        with patch("socket.socket.connect", side_effect=hostile_socket_connect), \
             patch("socket.create_connection", side_effect=hostile_socket_connect):

            dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=10)
            batch = [sample_email_draft, sample_phone_draft]

            summary = dispatcher.dispatch_batch(batch, confirmed=True)

            assert summary.total_dispatched == 2
            assert summary.dispatched_email == 1
            assert summary.dispatched_whatsapp == 1
            assert summary.failed_count == 0

    def test_dry_run_audit_log_completeness_and_veracity(self, sample_email_draft, sample_phone_draft):
        """
        ATTACK: Execute dry-run and inspect generated audit log records.
        VERIFY: Every simulated event has accurate UTC timestamp, mode, status, recipient, and body.
        """
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True)
        batch = [sample_email_draft, sample_phone_draft]

        summary = dispatcher.dispatch_batch(batch, confirmed=True)

        assert len(summary.results) == 2

        # 1. Email audit check
        email_res = next(r for r in summary.results if r.channel == "Cold Email")
        assert email_res.success is True
        assert email_res.mode == "Dry-Run Simulator"
        assert email_res.recipient == "owner@apexeliteroofing.com"
        assert "Emergency storm repair" in email_res.subject
        assert email_res.metadata.get("status") == "Simulated"
        # Validate timestamp format YYYY-MM-DD HH:MM:SSZ
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z$", email_res.timestamp)

        # 2. WhatsApp audit check
        wa_res = next(r for r in summary.results if r.channel == "WhatsApp wa.me")
        assert wa_res.success is True
        assert wa_res.mode == "Dry-Run WhatsApp"
        assert wa_res.recipient.startswith("https://wa.me/19035550288?text=")
        assert wa_res.metadata.get("status") == "Simulated Click"
        assert wa_res.metadata.get("phone") == "9035550288"

    def test_missing_credentials_safe_fallback_to_dry_run(self):
        """
        ATTACK: Request live SMTP mode (dry_run=False) with missing or empty SMTP credentials.
        VERIFY: EmailClient safely falls back to dry_run=True to prevent crashes or insecure attempts.
        """
        client1 = EmailClient(smtp_host=None, smtp_user=None, dry_run=False)
        assert client1.dry_run is True

        client2 = EmailClient(smtp_host="smtp.gmail.com", smtp_user="", dry_run=False)
        assert client2.dry_run is True

        client3 = EmailClient(smtp_host="", smtp_user="user@gmail.com", dry_run=False)
        assert client3.dry_run is True

    def test_sheets_client_offline_isolation_in_dry_run(self, sample_email_draft):
        """
        ATTACK: Run dispatch with offline SheetsClient.
        VERIFY: Cell updates are written to in-memory store without making Google Sheets REST API calls.
        """
        sheets_mock = SheetsClient(offline_mode=True)
        dispatcher = OutreachDispatcher(
            sheets_client=sheets_mock,
            dry_run=True,
            test_mode=True,
        )

        res = dispatcher.dispatch_single(sample_email_draft, confirmed=True, sync_sheet=True)

        assert res is not None
        assert res.success is True

        # Verify in-memory mock_data updates
        row = sample_email_draft.crm_record.row_index
        assert sheets_mock.mock_data.get(f"{SHEET_TAB}!A{row}") == [["Contacted (Touch 1)"]]
        assert sheets_mock.mock_data.get(f"{SHEET_TAB}!Z{row}") == [["Dispatched"]]
        assert sheets_mock.mock_data.get(f"{SHEET_TAB}!O{row}") == [[datetime.now(timezone.utc).strftime("%Y-%m-%d")]]


# ===========================================================================
# Cross-Feature & Invariant Adversarial Tests
# ===========================================================================

class TestCrossFeatureInvariants:
    """
    Test interaction invariants between Safety Gate, CRM state, Channel routing, and Pacing.
    """

    def test_crm_dispatch_record_immutability(self, base_crm_email):
        """
        VERIFY: update_crm_dispatch_record returns an updated copy and does not mutate the original.
        """
        original_status = base_crm_email.lead_status
        original_deal = base_crm_email.est_deal_value
        original_notes = base_crm_email.notes_and_next_steps

        updated = update_crm_dispatch_record(base_crm_email, channel="Cold Email", date_str="2026-10-24")

        # Original is unmodified
        assert base_crm_email.lead_status == original_status
        assert base_crm_email.notes_and_next_steps == original_notes

        # Updated record has expected transitions
        assert updated.lead_status == "Contacted (Touch 1)"
        assert updated.touch_1_date == "2026-10-24"
        assert updated.est_deal_value == original_deal
        assert "Dispatched via Cold Email on 2026-10-24." in updated.notes_and_next_steps

    def test_channel_routing_with_ambiguous_and_phone_only_leads(self, sample_email_draft, sample_phone_draft):
        """
        VERIFY: Dynamic routing logic correctly routes phone leads to WhatsApp and email leads to Cold Email.
        """
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True)

        # 1. Standard email -> Cold Email
        assert dispatcher.determine_channel(sample_email_draft) == "Cold Email"

        # 2. Standard phone -> WhatsApp wa.me
        assert dispatcher.determine_channel(sample_phone_draft) == "WhatsApp wa.me"

        # 3. Explicit override
        assert dispatcher.determine_channel(sample_email_draft, channel_override="wa") == "WhatsApp wa.me"
        assert dispatcher.determine_channel(sample_phone_draft, channel_override="email") == "Cold Email"

    def test_accounting_invariant_under_heterogeneous_batch(self, sample_email_draft, sample_phone_draft):
        """
        VERIFY: Across any mixed batch with approved, unapproved, dispatched, and capped leads,
        total_drafts == dispatched_email + dispatched_whatsapp + skipped_count + failed_count.
        """
        # Create 12 drafts with diverse statuses:
        # 4 Approved email drafts
        batch_approved_email = create_draft_batch(sample_email_draft, count=4, start_row=14)
        for d in batch_approved_email:
            d.approval_status = "Approved"

        # 4 Ready for Review phone drafts
        batch_ready_phone = create_draft_batch(sample_phone_draft, count=4, start_row=18)

        # 2 Already Dispatched drafts
        batch_dispatched = create_draft_batch(sample_email_draft, count=2, start_row=22)
        for d in batch_dispatched:
            d.approval_status = "Dispatched"

        # 2 Invalid status drafts
        batch_invalid = create_draft_batch(sample_email_draft, count=2, start_row=24)
        for d in batch_invalid:
            d.approval_status = "Pending"

        mixed_batch = batch_approved_email + batch_ready_phone + batch_dispatched + batch_invalid
        assert len(mixed_batch) == 12

        # Set cap to 5
        dispatcher = OutreachDispatcher(dry_run=True, test_mode=True, daily_cap=5)
        summary = dispatcher.dispatch_batch(mixed_batch, confirmed=True, cap=5)

        # Invariant verification
        total_accounted = summary.dispatched_email + summary.dispatched_whatsapp + summary.skipped_count + summary.failed_count
        assert total_accounted == summary.total_drafts == 12
        assert summary.total_dispatched == 5
        assert summary.skipped_count == 7
