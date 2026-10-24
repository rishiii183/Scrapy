"""
Deduplication Engine and Normalization for Google Sheets CRM Ingestion.

Provides:
- Infallible 10-digit US phone normalization
- Legal corporate entity suffix stripping and business name normalization
- In-memory index of existing CRM rows from Leads Tracker
- Intra-batch and cross-run deduplication
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from src.models import RawLead, QualifiedLead
from src.scraper.normalizer import (
    clean_phone_10digit,
    normalize_business_name as scraper_normalize_business_name,
)

ENTITY_SUFFIXES = [
    "incorporated", "corporation", "limited liability company",
    "limited liability partnership", "limited partnership",
    "limited", "company", "corp", "pllc", "llc", "llp", "inc", "ltd", "co"
]
ENTITY_PATTERN = r"\b(" + "|".join(ENTITY_SUFFIXES) + r")\b$"


def normalize_phone(phone: Optional[str]) -> str:
    """
    Extract 10-digit normalized US phone number.
    - Strips extension patterns (ext 101, x4, etc.)
    - Rejects foreign country codes and invalid non-NANP numbers
    - Enforces North American Numbering Plan (NANP) format
    Delegates to clean_phone_10digit from src.scraper.normalizer.
    Returns 10-digit string if valid; otherwise empty string.
    """
    if not phone:
        return ""
    clean = clean_phone_10digit(phone)
    return clean if (clean and len(clean) == 10) else ""


def normalize_business_name(name: Optional[str]) -> str:
    """
    Normalize business name by removing ampersands, punctuation, leading 'the',
    and corporate entity suffixes (LLC, Inc, Corp, Co, PLLC, etc.).
    Preserves core trade words for precise matching.
    """
    if not name:
        return ""
    n = str(name).lower().strip()
    n = re.sub(r"\s*&\s*", " and ", n)
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"^the\s+", "", n)

    while True:
        cleaned = re.sub(ENTITY_PATTERN, "", n).strip()
        if cleaned == n or not cleaned:
            break
        n = cleaned

    n = re.sub(r"\b(and|or|of)\b$", "", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def extract_phones_from_text(text: str) -> List[str]:
    """Find all potential US phone numbers in text and normalize to 10 digits."""
    if not text:
        return []
    matches = re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
    results = []
    for m in matches:
        norm = normalize_phone(m)
        if len(norm) == 10:
            results.append(norm)
    return results


def parse_crm_rows(rows: List[List[Any]]) -> Tuple[Set[str], Set[str], List[Dict[str, Any]]]:
    """
    Parse rows from Leads Tracker (starting from row 2 onwards).
    Extracts normalized company names and phone numbers.
    Returns:
    - existing_names: Set[str] of normalized business names
    - existing_phones: Set[str] of 10-digit phone strings
    - parsed_records: List[Dict] with per-row debug information
    """
    existing_names: Set[str] = set()
    existing_phones: Set[str] = set()
    parsed_records: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        if not row:
            continue
        # Company Name is Col C (index 2)
        company_name = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        # Work Email is Col J (index 9)
        work_email = str(row[9]).strip() if len(row) > 9 and row[9] is not None else ""
        # Notes & Next Steps is Col U (index 20)
        notes = str(row[20]).strip() if len(row) > 20 and row[20] is not None else ""

        norm_name = normalize_business_name(company_name)
        scraper_norm_name = scraper_normalize_business_name(company_name)

        # Extract phone from Notes & Next Steps or Work Email
        extracted_phones = extract_phones_from_text(notes + " " + work_email)

        if norm_name:
            existing_names.add(norm_name)
        if scraper_norm_name:
            existing_names.add(scraper_norm_name)

        for p in extracted_phones:
            existing_phones.add(p)

        parsed_records.append({
            "row_index": idx,
            "company_name": company_name,
            "norm_name": norm_name,
            "phones": extracted_phones,
        })

    return existing_names, existing_phones, parsed_records


class CRMDeduplicator:
    """
    Deduplication engine managing known CRM contractors and filtering
    candidate leads to prevent duplicate rows.
    """

    def __init__(
        self,
        existing_names: Optional[Set[str]] = None,
        existing_phones: Optional[Set[str]] = None,
    ) -> None:
        self.existing_names: Set[str] = set(existing_names or [])
        self.existing_phones: Set[str] = set(existing_phones or [])

    def load_from_rows(self, rows: List[List[Any]]) -> int:
        """Parse raw CRM rows and index all business names and phone numbers."""
        names, phones, _ = parse_crm_rows(rows)
        self.existing_names.update(names)
        self.existing_phones.update(phones)
        return len(names) + len(phones)

    def is_duplicate(self, lead: Union[RawLead, QualifiedLead, Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Check if a candidate lead already exists in the CRM index.
        Returns (is_duplicate: bool, reason: str).
        """
        if isinstance(lead, dict):
            name = lead.get("business_name") or lead.get("company_name", "")
            phone = lead.get("cleaned_phone") or lead.get("phone", "")
        else:
            name = lead.business_name
            phone = lead.cleaned_phone

        norm_p = normalize_phone(phone)
        if norm_p and len(norm_p) == 10 and norm_p in self.existing_phones:
            return True, f"Duplicate phone matched: {norm_p}"

        norm_n = normalize_business_name(name)
        if norm_n and norm_n in self.existing_names:
            return True, f"Duplicate company name matched: '{norm_n}'"

        scraper_n = scraper_normalize_business_name(name)
        if scraper_n and scraper_n in self.existing_names:
            return True, f"Duplicate company name (scraper key) matched: '{scraper_n}'"

        return False, ""

    def deduplicate(
        self,
        leads: List[Union[RawLead, QualifiedLead]],
    ) -> Tuple[List[Union[RawLead, QualifiedLead]], List[Dict[str, Any]]]:
        """
        Filter candidate leads, eliminating duplicates against existing CRM records
        and preventing intra-batch duplicates.
        Returns (unique_leads, duplicate_records).
        """
        unique_leads: List[Union[RawLead, QualifiedLead]] = []
        duplicate_records: List[Dict[str, Any]] = []

        for lead in leads:
            is_dup, reason = self.is_duplicate(lead)
            if is_dup:
                duplicate_records.append({
                    "business_name": lead.business_name,
                    "cleaned_phone": lead.cleaned_phone,
                    "reason": reason,
                })
            else:
                unique_leads.append(lead)
                # Register into active index to prevent subsequent intra-batch duplicates
                norm_p = normalize_phone(lead.cleaned_phone)
                if norm_p and len(norm_p) == 10:
                    self.existing_phones.add(norm_p)
                norm_n = normalize_business_name(lead.business_name)
                if norm_n:
                    self.existing_names.add(norm_n)
                scraper_n = scraper_normalize_business_name(lead.business_name)
                if scraper_n:
                    self.existing_names.add(scraper_n)

        return unique_leads, duplicate_records
