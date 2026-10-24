"""
High-Level Google Sheets CRM Ingestion Workflow.

Orchestrates:
1. Reading existing CRM records from Google Sheet ('Leads Tracker'!A2:U)
2. Deduplication against existing contractors and intra-batch duplicates
3. Lead scoring and priority assignment (🔥 High, ⚡ Medium, ❄️ Low)
4. Converting leads to 21-column schema rows (Cols A through U)
5. Appending leads starting at Row 14, strictly preserving rows 2-13 and dashboard formulas
6. Returning structured audit and ingestion summaries
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from src.config import SHEET_ID, SHEET_TAB, START_ROW
from src.models import RawLead, QualifiedLead, CRMRecord
from src.crm.sheets_client import SheetsClient
from src.crm.schema import lead_to_crm_row, crm_row_to_record, validate_crm_row
from src.crm.lead_scorer import score_lead_record
from src.crm.dedup import CRMDeduplicator, parse_crm_rows


class CRMIngestor:
    """
    Ingestion engine responsible for safely writing qualified contractor leads
    into the Google Sheet CRM with deduplication and formula preservation.
    """

    def __init__(
        self,
        sheets_client: Optional[SheetsClient] = None,
        sheet_id: str = SHEET_ID,
        sheet_tab: str = SHEET_TAB,
        start_row: int = START_ROW,
    ) -> None:
        self.sheets_client = sheets_client or SheetsClient()
        self.sheet_id = sheet_id
        self.sheet_tab = sheet_tab
        self.start_row = start_row

    def get_existing_records(self) -> Tuple[List[List[Any]], int]:
        """
        Fetch existing CRM rows from the sheet.
        Returns (rows, next_available_row_index).
        """
        range_str = f"'{self.sheet_tab}'!A2:U500"
        existing_rows = self.sheets_client.read_range(self.sheet_id, range_str)

        # Count populated rows (where at least Col C Company Name is non-empty)
        populated_count = 0
        for r in existing_rows:
            if r and any(str(c).strip() for c in r):
                populated_count += 1

        # First append row is after all populated rows, but never lower than self.start_row (Row 14)
        next_available_row = max(self.start_row, populated_count + 2)
        return existing_rows, next_available_row

    def ingest(
        self,
        leads: List[Union[RawLead, QualifiedLead]],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute full CRM ingestion pipeline for candidate leads.
        """
        # 1. Read existing rows
        existing_rows, next_row = self.get_existing_records()

        # 2. Build deduplicator from existing CRM rows
        existing_names, existing_phones, _ = parse_crm_rows(existing_rows)
        deduplicator = CRMDeduplicator(existing_names=existing_names, existing_phones=existing_phones)

        # 3. Filter leads for duplicates
        unique_leads, duplicate_records = deduplicator.deduplicate(leads)

        if not unique_leads:
            return {
                "status": "success",
                "total_input": len(leads),
                "unique_ingested": 0,
                "duplicates_skipped": len(duplicate_records),
                "start_row": next_row,
                "end_row": next_row - 1,
                "duplicate_records": duplicate_records,
                "crm_records": [],
                "dry_run": dry_run,
            }

        # 4. Convert unique leads to 21-column rows and CRMRecords
        new_rows: List[List[Any]] = []
        crm_records: List[CRMRecord] = []
        current_row_idx = next_row

        for lead in unique_leads:
            # Score if not already scored
            scored_priority, scored_deal = score_lead_record(lead)
            if isinstance(lead, QualifiedLead) and lead.priority.startswith(("🔥", "⚡", "❄️")):
                priority = lead.priority
            else:
                priority = scored_priority

            row_data = lead_to_crm_row(
                lead,
                row_index=current_row_idx,
                override_priority=priority,
                override_deal_value=scored_deal,
            )
            validate_crm_row(row_data)
            new_rows.append(row_data)

            record = crm_row_to_record(row_data, row_index=current_row_idx)
            crm_records.append(record)
            current_row_idx += 1

        end_row_idx = current_row_idx - 1

        # 5. Write to Google Sheet if not dry run
        if not dry_run:
            write_range = f"'{self.sheet_tab}'!A{next_row}:U{end_row_idx}"
            self.sheets_client.update_range(self.sheet_id, write_range, new_rows)

        return {
            "status": "success",
            "total_input": len(leads),
            "unique_ingested": len(unique_leads),
            "duplicates_skipped": len(duplicate_records),
            "start_row": next_row,
            "end_row": end_row_idx,
            "duplicate_records": duplicate_records,
            "crm_records": crm_records,
            "dry_run": dry_run,
        }


def ingest_leads(
    leads: List[Union[RawLead, QualifiedLead]],
    sheets_client: Optional[SheetsClient] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Convenience functional wrapper to execute CRM lead ingestion."""
    ingestor = CRMIngestor(sheets_client=sheets_client)
    return ingestor.ingest(leads, dry_run=dry_run)
