"""
Staged Approval Safety Gate Module (Milestone 4 - Agent 4).

Enforces:
- Staged approval review mode before outbound outreach
- Default status: 'Drafted / Ready for Review' (Col Z)
- Dispatch requires explicit confirmation (confirmed=True via --confirm or prompt)
- Dispatches blocked or raises SafetyGateError if unconfirmed
- Prevents double-dispatching already dispatched leads
"""

import sys
import logging
from typing import Any, List, Optional
from src.models import OutreachDraft

logger = logging.getLogger(__name__)

# Valid approval states
STATUS_READY_FOR_REVIEW = "Drafted / Ready for Review"
STATUS_APPROVED = "Approved"
STATUS_DISPATCHED = "Dispatched"
PERMITTED_APPROVAL_STATUSES = {STATUS_READY_FOR_REVIEW, STATUS_APPROVED}


class SafetyGateError(Exception):
    """Raised when dispatch is blocked by the staged approval safety gate."""


def check_safety_gate(
    draft: OutreachDraft,
    confirmed: bool = False,
    raise_on_error: bool = False,
) -> bool:
    """
    Verify whether an OutreachDraft is approved for dispatch.

    Rules:
    1. If user has not provided explicit confirmation (confirmed=False), dispatch is blocked.
    2. If draft is already in 'Dispatched' status, dispatch is blocked (idempotency).
    3. Draft must be in 'Drafted / Ready for Review' or 'Approved' status.

    Returns:
        bool: True if draft passes safety gate and may be dispatched; False otherwise.

    Raises:
        SafetyGateError: If raise_on_error is True and dispatch is blocked.
    """
    if not confirmed:
        if raise_on_error:
            company = getattr(draft.crm_record, "company_name", "Unknown Contractor")
            raise SafetyGateError(
                f"Dispatch blocked for '{company}': Explicit user confirmation required (--confirm)."
            )
        return False

    current_status = getattr(draft, "approval_status", "")
    if current_status == STATUS_DISPATCHED:
        if raise_on_error:
            company = getattr(draft.crm_record, "company_name", "Unknown Contractor")
            raise SafetyGateError(
                f"Dispatch blocked for '{company}': Lead has already been dispatched."
            )
        return False

    if current_status not in PERMITTED_APPROVAL_STATUSES:
        if raise_on_error:
            company = getattr(draft.crm_record, "company_name", "Unknown Contractor")
            raise SafetyGateError(
                f"Dispatch blocked for '{company}': Invalid approval status '{current_status}'."
            )
        return False

    return True


def require_confirmation(draft: OutreachDraft, confirmed: bool) -> bool:
    """
    Enforce explicit confirmation on a draft, raising SafetyGateError on rejection.
    """
    return check_safety_gate(draft, confirmed=confirmed, raise_on_error=True)


def filter_approved_drafts(
    drafts: List[OutreachDraft],
    confirmed: bool = False,
) -> List[OutreachDraft]:
    """
    Filter a batch of drafts, retaining only those that pass safety gate checks.
    """
    return [d for d in drafts if check_safety_gate(d, confirmed=confirmed)]


def prompt_user_approval(
    draft: OutreachDraft,
    stream_in=None,
    stream_out=None,
) -> bool:
    """
    Prompt user interactively in CLI to approve or reject outreach.

    Safely handles:
    - Empty input ('') -> False (safe default)
    - 'n' or 'no' -> False
    - EOFError (Ctrl+D / non-interactive pipe) -> False
    - KeyboardInterrupt -> False
    - 'y' or 'yes' -> True
    """
    in_stream = stream_in or sys.stdin
    out_stream = stream_out or sys.stdout

    company = getattr(draft.crm_record, "company_name", "Contractor")
    recipient = getattr(draft.crm_record, "work_email", "Unknown")
    prompt_text = (
        f"\n[Safety Gate Review]\n"
        f"  Company:   {company}\n"
        f"  Recipient: {recipient}\n"
        f"  Subject:   {draft.staged_email_subject}\n"
        f"  Approve outbound dispatch? [y/N]: "
    )

    try:
        out_stream.write(prompt_text)
        out_stream.flush()
        line = in_stream.readline()
        if not line:
            return False
        choice = line.strip().lower()
        return choice in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False
    except Exception as e:
        logger.warning("Error reading interactive user approval: %s", e)
        return False


class SafetyGate:
    """
    Object-oriented safety gate wrapper for pipeline integration.
    """

    def __init__(self, default_confirmed: bool = False) -> None:
        self.default_confirmed = default_confirmed

    def is_approved(self, draft: OutreachDraft, confirmed: Optional[bool] = None) -> bool:
        c = self.default_confirmed if confirmed is None else confirmed
        return check_safety_gate(draft, confirmed=c)

    def enforce(self, draft: OutreachDraft, confirmed: Optional[bool] = None) -> bool:
        c = self.default_confirmed if confirmed is None else confirmed
        return require_confirmation(draft, confirmed=c)

    def filter_batch(
        self,
        drafts: List[OutreachDraft],
        confirmed: Optional[bool] = None,
    ) -> List[OutreachDraft]:
        c = self.default_confirmed if confirmed is None else confirmed
        return filter_approved_drafts(drafts, confirmed=c)
