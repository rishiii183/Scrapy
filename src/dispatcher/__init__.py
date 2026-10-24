"""
Milestone 4: Humanized Outreach Dispatch Engine with Staged Approval (Agent 4).

Provides:
- SafetyGate, SafetyGateError, check_safety_gate, require_confirmation, prompt_user_approval
- EmailClient, DispatchResult, clean_email, is_valid_email, create_mime_message
- WhatsAppClient, build_whatsapp_link, is_phone_only_lead, extract_clean_10digit_phone
- PacingController, compute_random_delay, is_valid_pacing_delay, apply_daily_cap
- OutreachDispatcher, DispatchSummary, update_crm_dispatch_record, update_sheet_dispatch_state
"""

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

from src.dispatcher.orchestrator import (
    OutreachDispatcher,
    DispatchSummary,
    update_crm_dispatch_record,
    update_sheet_dispatch_state,
)

__all__ = [
    "SafetyGate",
    "SafetyGateError",
    "check_safety_gate",
    "require_confirmation",
    "filter_approved_drafts",
    "prompt_user_approval",
    "STATUS_READY_FOR_REVIEW",
    "STATUS_APPROVED",
    "STATUS_DISPATCHED",
    "EmailClient",
    "DispatchResult",
    "clean_email",
    "is_valid_email",
    "normalize_newlines",
    "create_mime_message",
    "WhatsAppClient",
    "build_whatsapp_link",
    "is_phone_only_lead",
    "extract_clean_10digit_phone",
    "PacingController",
    "compute_random_delay",
    "is_valid_pacing_delay",
    "apply_daily_cap",
    "OutreachDispatcher",
    "DispatchSummary",
    "update_crm_dispatch_record",
    "update_sheet_dispatch_state",
]
