"""
Milestone 2: Google Sheets CRM Ingestion & Deduplication Module.

Provides:
- SheetsClient: Direct REST API client with OAuth auto-refresh and CLI fallback
- CRMSchema: 21-column schema definitions (Cols A through U) and strict validators
- LeadScorer: Priority and deal value calculations (🔥 High, ⚡ Medium, ❄️ Low)
- CRMDeduplicator: Business name & 10-digit phone deduplication against CRM records
- CRMIngestor: End-to-end ingestion starting at Row 14 preserving formulas
"""

from src.crm.sheets_client import (
    SheetsClient,
    validate_spreadsheet_id,
    compute_exponential_backoff,
)
from src.crm.schema import (
    CRM_COLUMNS,
    ALLOWED_LEAD_STATUSES,
    ALLOWED_PRIORITIES,
    ALLOWED_EMAIL_VERIFICATIONS,
    ALLOWED_OUTREACH_CHANNELS,
    validate_crm_row,
    lead_to_crm_row,
    crm_row_to_record,
    format_location_display,
)
from src.crm.lead_scorer import (
    score_lead,
    score_lead_record,
    is_high_ticket_specialty,
)
from src.crm.dedup import (
    CRMDeduplicator,
    normalize_business_name,
    normalize_phone,
    parse_crm_rows,
)
from src.crm.ingestor import (
    CRMIngestor,
    ingest_leads,
)

__all__ = [
    "SheetsClient",
    "validate_spreadsheet_id",
    "compute_exponential_backoff",
    "CRM_COLUMNS",
    "ALLOWED_LEAD_STATUSES",
    "ALLOWED_PRIORITIES",
    "ALLOWED_EMAIL_VERIFICATIONS",
    "ALLOWED_OUTREACH_CHANNELS",
    "validate_crm_row",
    "lead_to_crm_row",
    "crm_row_to_record",
    "format_location_display",
    "score_lead",
    "score_lead_record",
    "is_high_ticket_specialty",
    "CRMDeduplicator",
    "normalize_business_name",
    "normalize_phone",
    "parse_crm_rows",
    "CRMIngestor",
    "ingest_leads",
]
