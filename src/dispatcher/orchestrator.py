"""
Outreach Dispatch Engine Orchestrator (Milestone 4 - Agent 4).

Coordinates:
1. Staged approval gate verification before outbound messaging
2. Humanized delay pacing between consecutive dispatches
3. Daily send cap enforcement to safeguard sender domain reputation
4. Dynamic channel routing (Cold Email primary with WhatsApp click-to-chat fallback)
5. Comprehensive CRM state transitions:
   - Column A (Lead Status): 'Not Contacted' -> 'Contacted (Touch 1)'
   - Column O (Touch 1 Date): Current UTC date 'YYYY-MM-DD'
   - Column U (Notes & Next Steps): Appends 'Dispatched via <channel> on <date>.'
   - Staging Column Z (Outreach Approval Status): 'Drafted / Ready for Review' -> 'Dispatched'
6. Synchronization with Google Sheet CRM via SheetsClient
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.config import SHEET_ID, SHEET_TAB, DAILY_SEND_CAP
from src.crm.sheets_client import SheetsClient
from src.dispatcher.email_client import DispatchResult, EmailClient, is_valid_email
from src.dispatcher.pacing import PacingController, apply_daily_cap
from src.dispatcher.safety_gate import SafetyGate, check_safety_gate
from src.dispatcher.whatsapp_client import WhatsAppClient, is_phone_only_lead
from src.models import CRMRecord, OutreachDraft

logger = logging.getLogger(__name__)


class DispatchSummary(BaseModel):
    """
    Consolidated summary report of an outreach dispatch batch.
    """
    total_drafts: int = Field(default=0, description="Total drafts queued for dispatch")
    approved_count: int = Field(default=0, description="Total drafts passing safety gate")
    dispatched_email: int = Field(default=0, description="Leads successfully dispatched via Cold Email")
    dispatched_whatsapp: int = Field(default=0, description="Leads successfully dispatched via WhatsApp")
    failed_count: int = Field(default=0, description="Leads that failed sending")
    skipped_count: int = Field(default=0, description="Leads blocked by safety gate or cap")
    results: List[DispatchResult] = Field(default_factory=list, description="Individual dispatch results")

    @property
    def total_dispatched(self) -> int:
        """Total successful dispatches across all channels."""
        return self.dispatched_email + self.dispatched_whatsapp


def update_crm_dispatch_record(
    record: CRMRecord,
    channel: str,
    date_str: Optional[str] = None,
) -> CRMRecord:
    """
    Perform immutable CRM state transition upon approved dispatch (Feature 18):
    - Col A -> 'Contacted (Touch 1)'
    - Col O -> YYYY-MM-DD date stamp
    - Col U -> Appends 'Dispatched via <channel> on <date>.'
    Preserves all other CRM columns (Priority, Deal Value, Location, etc.).
    """
    today_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record_dict = record.model_dump()

    record_dict["lead_status"] = "Contacted (Touch 1)"
    prev_notes = record_dict.get("notes_and_next_steps", "")
    stamp = f"Dispatched via {channel} on {today_str}."
    record_dict["notes_and_next_steps"] = f"{prev_notes} {stamp}".strip()

    updated = CRMRecord(**record_dict)
    object.__setattr__(updated, "touch_1_date", today_str)
    return updated


def update_sheet_dispatch_state(
    draft: OutreachDraft,
    channel: str,
    date_str: str,
    sheets_client: SheetsClient,
    sheet_id: str = SHEET_ID,
    sheet_tab: str = SHEET_TAB,
) -> Dict[str, Any]:
    """
    Persist updated dispatch states into Google Sheet CRM:
    - Col A: Lead Status
    - Col O: Touch 1 Date
    - Col U: Notes & Next Steps
    - Col Z: Outreach Approval Status
    """
    row_idx = draft.crm_record.row_index
    results: Dict[str, Any] = {}

    # 1. Update Col A (Lead Status)
    res_a = sheets_client.update_range(
        sheet_id=sheet_id,
        range_str=f"'{sheet_tab}'!A{row_idx}",
        values=[["Contacted (Touch 1)"]],
    )
    results["lead_status"] = res_a

    # 2. Update Col O (Touch 1 Date)
    res_o = sheets_client.update_range(
        sheet_id=sheet_id,
        range_str=f"'{sheet_tab}'!O{row_idx}",
        values=[[date_str]],
    )
    results["touch_1_date"] = res_o

    # 3. Update Col U (Notes & Next Steps)
    res_u = sheets_client.update_range(
        sheet_id=sheet_id,
        range_str=f"'{sheet_tab}'!U{row_idx}",
        values=[[draft.crm_record.notes_and_next_steps]],
    )
    results["notes"] = res_u

    # 4. Update Col Z (Approval Status)
    res_z = sheets_client.update_range(
        sheet_id=sheet_id,
        range_str=f"'{sheet_tab}'!Z{row_idx}",
        values=[["Dispatched"]],
    )
    results["approval_status"] = res_z

    return results


class OutreachDispatcher:
    """
    Orchestrator for Humanized Outreach Dispatch Engine adhering to Milestone 4.
    """

    def __init__(
        self,
        email_client: Optional[EmailClient] = None,
        whatsapp_client: Optional[WhatsAppClient] = None,
        pacing_controller: Optional[PacingController] = None,
        sheets_client: Optional[SheetsClient] = None,
        safety_gate: Optional[SafetyGate] = None,
        dry_run: bool = True,
        default_confirmed: bool = False,
        test_mode: bool = False,
        daily_cap: int = DAILY_SEND_CAP,
    ) -> None:
        self.dry_run = dry_run
        self.default_confirmed = default_confirmed
        self.test_mode = test_mode

        self.email_client = email_client or EmailClient(dry_run=self.dry_run)
        self.whatsapp_client = whatsapp_client or WhatsAppClient(dry_run=self.dry_run)
        self.pacing_controller = pacing_controller or PacingController(
            daily_cap=daily_cap,
            test_mode=self.test_mode,
        )
        self.sheets_client = sheets_client
        self.safety_gate = safety_gate or SafetyGate(default_confirmed=self.default_confirmed)

    def determine_channel(
        self,
        draft: OutreachDraft,
        channel_override: Optional[str] = None,
    ) -> str:
        """
        Determine whether lead should receive Cold Email or WhatsApp click-to-chat.
        """
        if channel_override:
            clean_override = channel_override.strip().lower()
            if "email" in clean_override:
                return "Cold Email"
            if "wa" in clean_override or "chat" in clean_override or "call" in clean_override:
                return "WhatsApp wa.me"

        # Check work_email in CRM record
        work_email = draft.crm_record.work_email
        if is_phone_only_lead(work_email):
            return "WhatsApp wa.me"

        if is_valid_email(work_email):
            return "Cold Email"

        return "WhatsApp wa.me"

    def dispatch_single(
        self,
        draft: OutreachDraft,
        confirmed: Optional[bool] = None,
        channel_override: Optional[str] = None,
        sync_sheet: bool = True,
        apply_pacing: bool = False,
        sheet_id: str = SHEET_ID,
        sheet_tab: str = SHEET_TAB,
    ) -> Optional[DispatchResult]:
        """
        Safely execute dispatch for a single OutreachDraft.
        """
        is_conf = self.default_confirmed if confirmed is None else confirmed

        # 1. Safety Gate Check
        if not check_safety_gate(draft, confirmed=is_conf):
            logger.warning(
                "Dispatch blocked by safety gate for: %s",
                draft.crm_record.company_name,
            )
            return None

        # 2. Check Daily Cap
        if not self.pacing_controller.can_dispatch():
            logger.warning("Daily send cap reached. Halting dispatch.")
            return None

        # 3. Optional pacing delay
        if apply_pacing:
            self.pacing_controller.wait()

        # 4. Route Channel
        channel = self.determine_channel(draft, channel_override=channel_override)

        # 5. Execute Dispatch
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if channel == "Cold Email":
            result = self.email_client.send(
                recipient=draft.crm_record.work_email,
                subject=draft.staged_email_subject,
                body=draft.staged_email_body,
            )
        else:
            phone = draft.crm_record.work_email
            if phone.startswith("Call:"):
                phone = phone.replace("Call:", "").strip()
            result = self.whatsapp_client.send(
                phone=phone,
                message=draft.staged_whatsapp_msg,
                wame_url=draft.staged_wame_url,
            )

        # 6. Update State if Successful
        if result.success:
            self.pacing_controller.record_dispatch()
            draft.approval_status = "Dispatched"
            draft.crm_record = update_crm_dispatch_record(
                draft.crm_record,
                channel=channel,
                date_str=today_str,
            )

            # Sync to Google Sheets if requested and client available
            if sync_sheet and self.sheets_client is not None:
                try:
                    update_sheet_dispatch_state(
                        draft=draft,
                        channel=channel,
                        date_str=today_str,
                        sheets_client=self.sheets_client,
                        sheet_id=sheet_id,
                        sheet_tab=sheet_tab,
                    )
                except Exception as e:
                    logger.error("Failed to update Google Sheet dispatch state: %s", e)

        return result

    def dispatch_batch(
        self,
        drafts: List[OutreachDraft],
        confirmed: Optional[bool] = None,
        cap: Optional[int] = None,
        channel_override: Optional[str] = None,
        sync_sheet: bool = True,
        sheet_id: str = SHEET_ID,
        sheet_tab: str = SHEET_TAB,
    ) -> DispatchSummary:
        """
        Execute dispatch across a batch of staged OutreachDrafts.
        Enforces safety gate, daily send cap, and humanized delay pacing.
        """
        summary = DispatchSummary(total_drafts=len(drafts))
        is_conf = self.default_confirmed if confirmed is None else confirmed

        # 1. Filter drafts through safety gate
        eligible_drafts: List[OutreachDraft] = []
        for d in drafts:
            if check_safety_gate(d, confirmed=is_conf):
                eligible_drafts.append(d)
            else:
                summary.skipped_count += 1

        summary.approved_count = len(eligible_drafts)

        # 2. Enforce Daily Cap
        effective_cap = cap if cap is not None else self.pacing_controller.get_remaining_cap()
        capped_queue = apply_daily_cap(eligible_drafts, cap=effective_cap)
        capped_out_count = len(eligible_drafts) - len(capped_queue)
        summary.skipped_count += capped_out_count

        # 3. Process dispatch queue
        for i, draft in enumerate(capped_queue):
            if not self.pacing_controller.can_dispatch():
                summary.skipped_count += (len(capped_queue) - i)
                break

            # Pacing wait between dispatches (skip before first dispatch)
            if i > 0:
                self.pacing_controller.wait()

            res = self.dispatch_single(
                draft=draft,
                confirmed=True,
                channel_override=channel_override,
                sync_sheet=sync_sheet,
                apply_pacing=False,
                sheet_id=sheet_id,
                sheet_tab=sheet_tab,
            )

            if res is not None:
                summary.results.append(res)
                if res.success:
                    if res.channel == "Cold Email":
                        summary.dispatched_email += 1
                    else:
                        summary.dispatched_whatsapp += 1
                else:
                    summary.failed_count += 1
            else:
                summary.skipped_count += 1

        return summary
