"""
Adversarial Stress Test Suite for Milestone 2: Google Sheets CRM Ingestion & Deduplication.
Conducted by challenger_m2_1.

Objectives tested:
1. Company Name Normalization & Deduplication:
   - Legal suffixes: LLC, Inc, Corp, PLLC, LLP, Ltd, Co, Company, Corporation, Incorporated, Limited Liability Company, chained suffixes.
   - Ampersand vs 'and': '&' vs 'and', '& Sons' vs 'and Sons'.
   - Leading 'The': 'The ...' vs '...'.
   - Punctuation & casing: UPPERCASE, lowercase, Title Case, mIxEd CaSe, hyphens, periods, apostrophes.
   - Trailing conjunctions: 'and', 'or', 'of', '&'.
2. Phone Normalization:
   - US standard formats and 11-digit with +1.
   - Extensions: 'ext 101', 'ext. 101', 'x4', 'extension 202', '#12'.
   - Punctuation variants: dots, dashes, slashes, parens.
   - Non-NANP invalid numbers: leading 0/1 area codes, leading 0/1 central office codes.
   - Foreign / international and short numbers.
3. Cross-Run Deduplication & Intra-Batch Detection:
   - Intra-batch duplicate elimination with both phone and company name variants.
   - Intra-batch duplicate elimination with empty phones.
   - Cross-run deduplication across distinct pipeline runs.
4. Idempotency:
   - Re-running ingestion with 100 duplicate leads against CRM index must result in exactly 0 unique ingested leads.
   - Re-running with 100 variant duplicate leads (name variants, legal suffixes).
   - Re-running with 100 empty-phone duplicate leads.
"""

import pytest
from typing import Dict, List, Any

from src.models import RawLead, QualifiedLead
from src.crm.dedup import (
    normalize_phone,
    normalize_business_name,
    extract_phones_from_text,
    parse_crm_rows,
    CRMDeduplicator,
)
from src.crm.ingestor import CRMIngestor
from src.crm.sheets_client import SheetsClient


# ==============================================================================
# Objective 1: Company Name Normalization & Deduplication
# ==============================================================================

class TestCompanyNameVariants:
    """Stress-test business name normalization across legal suffixes, casing, punctuation, and conjunctions."""

    @pytest.mark.parametrize(
        "raw_name,expected_normalized",
        [
            ("Apex Roofing LLC", "apex roofing"),
            ("Apex Roofing, LLC", "apex roofing"),
            ("Apex Roofing Inc", "apex roofing"),
            ("Apex Roofing, Inc.", "apex roofing"),
            ("Apex Roofing Corp", "apex roofing"),
            ("Apex Roofing Corp.", "apex roofing"),
            ("Apex Roofing PLLC", "apex roofing"),
            ("Apex Roofing, PLLC", "apex roofing"),
            ("Apex Roofing LLP", "apex roofing"),
            ("Apex Roofing Ltd", "apex roofing"),
            ("Apex Roofing Ltd.", "apex roofing"),
            ("Apex Roofing Co", "apex roofing"),
            ("Apex Roofing Co.", "apex roofing"),
            ("Apex Roofing Company", "apex roofing"),
            ("Apex Roofing Corporation", "apex roofing"),
            ("Apex Roofing Incorporated", "apex roofing"),
            ("Apex Roofing Limited Liability Company", "apex roofing"),
            ("Apex Roofing Co., LLC", "apex roofing"),
            ("Apex Roofing Group, Inc.", "apex roofing group"),
        ],
    )
    def test_legal_suffixes_comprehensive(self, raw_name: str, expected_normalized: str):
        """Verify all major corporate and legal entity suffixes are stripped."""
        assert normalize_business_name(raw_name) == expected_normalized

    @pytest.mark.parametrize(
        "variant_a,variant_b",
        [
            ("Apex Roofing & Restoration", "Apex Roofing and Restoration"),
            ("Apex Roofing & Solar", "Apex Roofing and Solar"),
            ("Apex & Sons Roofing Co.", "Apex and Sons Roofing LLC"),
            ("Smith & Jones Roofers, Inc.", "Smith and Jones Roofers"),
        ],
    )
    def test_ampersand_vs_and(self, variant_a: str, variant_b: str):
        """Verify ampersand and 'and' normalize to identical canonical representation."""
        assert normalize_business_name(variant_a) == normalize_business_name(variant_b)

    @pytest.mark.parametrize(
        "raw_name,expected_normalized",
        [
            ("The Apex Roofing", "apex roofing"),
            ("The Apex Roofing LLC", "apex roofing"),
            ("The Premier Roofing Group Inc", "premier roofing group"),
            ("The 1st Choice Roofing", "1st choice roofing"),
        ],
    )
    def test_leading_the(self, raw_name: str, expected_normalized: str):
        """Verify leading 'The' is stripped cleanly."""
        assert normalize_business_name(raw_name) == expected_normalized

    @pytest.mark.parametrize(
        "raw_name,expected_normalized",
        [
            ("APEX ROOFING LLC", "apex roofing"),
            ("apex roofing inc", "apex roofing"),
            ("ApEx RoOfInG cOrP", "apex roofing"),
            ("O'Connor's Roofing LLC", "oconnors roofing"),
            ("A+ Roofing, Inc.", "a roofing"),
            ("Apex-Roofing LLC", "apexroofing"),  # Hyphen without spaces collapses to word
        ],
    )
    def test_casing_and_punctuation(self, raw_name: str, expected_normalized: str):
        """Verify case-insensitivity and punctuation stripping."""
        assert normalize_business_name(raw_name) == expected_normalized

    @pytest.mark.parametrize(
        "raw_name,expected_normalized",
        [
            ("Apex Roofing and", "apex roofing"),
            ("Apex Roofing &", "apex roofing"),
            ("Apex Roofing or", "apex roofing"),
            ("Apex Roofing of", "apex roofing"),
            ("The Apex Roofing and", "apex roofing"),
        ],
    )
    def test_trailing_conjunctions(self, raw_name: str, expected_normalized: str):
        """Verify trailing conjunctions (and, or, of, &) resulting from suffix stripping are cleaned."""
        assert normalize_business_name(raw_name) == expected_normalized


# ==============================================================================
# Objective 2: Phone Normalization & Edge Cases
# ==============================================================================

class TestPhoneNormalizationEdgeCases:
    """Stress-test phone normalization against US standards, extensions, non-NANP numbers, and malformed inputs."""

    @pytest.mark.parametrize(
        "raw_phone,expected_10",
        [
            ("(817) 349-5911", "8173495911"),
            ("817-349-5911", "8173495911"),
            ("817.349.5911", "8173495911"),
            ("817 349 5911", "8173495911"),
            ("+1 (817) 349-5911", "8173495911"),
            ("+18173495911", "8173495911"),
            ("1-817-349-5911", "8173495911"),
            ("18173495911", "8173495911"),
            ("817/349-5911", "8173495911"),
            ("Call: (817) 349-5911", "8173495911"),
            ("+1-(817)-349-5911", "8173495911"),
        ],
    )
    def test_us_standard_and_11_digit_with_plus_one(self, raw_phone: str, expected_10: str):
        """Verify standard 10-digit and 11-digit (+1) US phone numbers normalize to 10 digits."""
        assert normalize_phone(raw_phone) == expected_10

    @pytest.mark.parametrize(
        "phone_with_ext",
        [
            "(817) 349-5911 ext 101",
            "(817) 349-5911 ext. 101",
            "(817) 349-5911 x4",
            "(817) 349-5911 extension 202",
            "(817) 349-5911 #12",
        ],
    )
    def test_phone_extensions_vulnerability(self, phone_with_ext: str):
        """
        VULNERABILITY CHALLENGE:
        Verify whether normalize_phone strips extensions (ext 101, x4) or appends extension digits.
        In current dedup.py, re.sub(r'\\D', '', phone) produces >10 digits (e.g. 13 digits for ext 101).
        """
        norm = normalize_phone(phone_with_ext)
        # Expected behavior: should strip extension and yield primary 10-digit number '8173495911'
        # If this fails, normalize_phone leaks extension digits and breaks phone deduplication!
        assert norm == "8173495911", (
            f"VULNERABILITY CONFIRMED: normalize_phone failed on extension! "
            f"Input '{phone_with_ext}' returned '{norm}' instead of '8173495911'."
        )

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            "012-345-6789",  # Area code begins with 0 (Invalid in NANP)
            "112-345-6789",  # Area code begins with 1 (Invalid in NANP)
            "817-049-5911",  # Exchange code begins with 0 (Invalid in NANP)
            "817-149-5911",  # Exchange code begins with 1 (Invalid in NANP)
        ],
    )
    def test_non_nanp_numbers_vulnerability(self, invalid_phone: str):
        """
        VULNERABILITY CHALLENGE:
        Verify whether normalize_phone rejects invalid non-NANP numbers (where area code or central office code starts with 0 or 1).
        In current dedup.py, no NANP validation is performed.
        """
        norm = normalize_phone(invalid_phone)
        # Expected behavior: non-NANP numbers should not be treated as valid 10-digit primary keys
        assert norm != invalid_phone.replace("-", ""), (
            f"VULNERABILITY CONFIRMED: normalize_phone accepted invalid non-NANP number '{invalid_phone}' as valid 10-digit key '{norm}'."
        )

    def test_crm_deduplicator_extension_phone_leak(self):
        """
        CRITICAL VULNERABILITY CHALLENGE:
        When an existing CRM contractor has phone '8173495911', and a candidate contractor has
        the same phone with an extension '(817) 349-5911 ext 101', verify whether CRMDeduplicator
        catches the duplicate.
        """
        dedup = CRMDeduplicator(
            existing_names={"Apex Elite Roofing"},
            existing_phones={"8173495911"},
        )
        candidate = {
            "business_name": "Apex Elite Contractors",  # slightly different name
            "phone": "(817) 349-5911 ext 101",
        }
        is_dup, reason = dedup.is_duplicate(candidate)
        assert is_dup is True, (
            "VULNERABILITY CONFIRMED: CRMDeduplicator failed to detect duplicate contractor "
            "because candidate phone had an extension ('ext 101')!"
        )


# ==============================================================================
# Objective 3: Cross-Run & Intra-Batch Deduplication
# ==============================================================================

class TestIntraBatchAndCrossRunDeduplication:
    """Stress-test deduplication across batch operations and simulated multi-run cycles."""

    def test_intra_batch_duplicates_with_name_variants_and_phones(self):
        """Verify intra-batch duplicate detection catches 50 duplicate pairs in a 100-lead batch."""
        client = SheetsClient(offline_mode=True)
        ingestor = CRMIngestor(sheets_client=client)

        batch = []
        for i in range(50):
            # Lead A: original format
            batch.append(
                RawLead(
                    business_name=f"Summit Peak Roofing & Solar {i} LLC",
                    cleaned_phone=f"214555{i:04d}",
                    phone_display=f"(214) 555-{i:04d}",
                    city="Dallas",
                    state="TX",
                    zip_code="75201",
                    review_count=12,
                    star_rating=4.9,
                    specialty="Storm Damage & Re-roofing",
                    website_status="None (No Website)",
                )
            )
            # Lead B: duplicate variant in same batch
            batch.append(
                RawLead(
                    business_name=f"The Summit Peak Roofing and Solar {i}, Inc.",
                    cleaned_phone=f"214555{i:04d}",
                    phone_display=f"(214) 555-{i:04d}",
                    city="Dallas",
                    state="TX",
                    zip_code="75201",
                    review_count=12,
                    star_rating=4.9,
                    specialty="Storm Damage & Re-roofing",
                    website_status="None (No Website)",
                )
            )

        res = ingestor.ingest(batch, dry_run=False)
        assert res["total_input"] == 100
        assert res["unique_ingested"] == 50, f"Expected 50 unique ingested, got {res['unique_ingested']}"
        assert res["duplicates_skipped"] == 50, f"Expected 50 duplicates skipped, got {res['duplicates_skipped']}"

    def test_intra_batch_duplicates_empty_phones(self):
        """Verify intra-batch duplicate detection when phone is empty (100% name-based)."""
        client = SheetsClient(offline_mode=True)
        ingestor = CRMIngestor(sheets_client=client)

        suffixes = ["LLC", "Inc", "Corp", "PLLC", "LLP", "Ltd", "Co", "Company"]
        batch = []
        for i in range(50):
            s1 = suffixes[i % len(suffixes)]
            s2 = suffixes[(i + 1) % len(suffixes)]
            batch.append(
                RawLead(
                    business_name=f"Vanguard Roofing Solutions {i} {s1}",
                    cleaned_phone="",
                    phone_display="(Unlisted)",
                    city="Houston",
                    state="TX",
                    zip_code="77002",
                    review_count=15,
                    star_rating=5.0,
                    specialty="Commercial Roofing",
                    website_status="None (No Website)",
                )
            )
            batch.append(
                RawLead(
                    business_name=f"The Vanguard Roofing Solutions {i}, {s2}",
                    cleaned_phone="",
                    phone_display="(Unlisted)",
                    city="Houston",
                    state="TX",
                    zip_code="77002",
                    review_count=15,
                    star_rating=5.0,
                    specialty="Commercial Roofing",
                    website_status="None (No Website)",
                )
            )

        res = ingestor.ingest(batch, dry_run=False)
        assert res["total_input"] == 100
        assert res["unique_ingested"] == 50
        assert res["duplicates_skipped"] == 50

    def test_cross_run_deduplication(self):
        """Verify distinct pipeline run loads existing sheet rows and filters duplicates."""
        client = SheetsClient(offline_mode=True)
        ingestor_run1 = CRMIngestor(sheets_client=client)

        run1_leads = [
            RawLead(
                business_name=f"Metro Roofers {i} LLC",
                cleaned_phone=f"512555{i:04d}",
                phone_display=f"(512) 555-{i:04d}",
                city="Austin",
                state="TX",
                zip_code="78701",
                review_count=10,
                star_rating=4.8,
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )
            for i in range(10)
        ]
        res1 = ingestor_run1.ingest(run1_leads, dry_run=False)
        assert res1["unique_ingested"] == 10

        # Simulate second pipeline run with a new CRMIngestor reading existing rows
        ingestor_run2 = CRMIngestor(sheets_client=client)

        run2_leads = []
        # 5 exact duplicates
        for i in range(5):
            run2_leads.append(
                RawLead(
                    business_name=f"Metro Roofers {i} LLC",
                    cleaned_phone=f"512555{i:04d}",
                    phone_display=f"(512) 555-{i:04d}",
                    city="Austin",
                    state="TX",
                    zip_code="78701",
                    review_count=10,
                    star_rating=4.8,
                    specialty="Residential Roofing",
                    website_status="None (No Website)",
                )
            )
        # 5 variant duplicates
        for i in range(5, 10):
            run2_leads.append(
                RawLead(
                    business_name=f"The Metro Roofers {i}, Inc.",
                    cleaned_phone=f"512555{i:04d}",
                    phone_display=f"(512) 555-{i:04d}",
                    city="Austin",
                    state="TX",
                    zip_code="78701",
                    review_count=10,
                    star_rating=4.8,
                    specialty="Residential Roofing",
                    website_status="None (No Website)",
                )
            )
        # 5 new unique leads
        for i in range(10, 15):
            run2_leads.append(
                RawLead(
                    business_name=f"Lone Star New Roofers {i} LLC",
                    cleaned_phone=f"512555{i:04d}",
                    phone_display=f"(512) 555-{i:04d}",
                    city="Austin",
                    state="TX",
                    zip_code="78701",
                    review_count=10,
                    star_rating=4.8,
                    specialty="Residential Roofing",
                    website_status="None (No Website)",
                )
            )

        res2 = ingestor_run2.ingest(run2_leads, dry_run=False)
        assert res2["total_input"] == 15
        assert res2["unique_ingested"] == 5
        assert res2["duplicates_skipped"] == 10


# ==============================================================================
# Objective 4: Idempotency with 100 Duplicate Leads
# ==============================================================================

class TestIdempotency100Duplicates:
    """Verify strict idempotency: re-running ingestion with 100 duplicate leads yields exactly 0 unique ingested leads."""

    def test_idempotency_100_identical_leads(self):
        """Re-running ingestion with 100 identical leads results in 0 unique ingested and 100 skipped."""
        client = SheetsClient(offline_mode=True)
        ingestor = CRMIngestor(sheets_client=client)

        leads_100 = [
            RawLead(
                business_name=f"Pinnacle Craft Roofing {i}",
                cleaned_phone=f"817666{i:04d}",
                phone_display=f"(817) 666-{i:04d}",
                city="Fort Worth",
                state="TX",
                zip_code="76102",
                review_count=14,
                star_rating=4.9,
                specialty="Storm Damage & Re-roofing",
                website_status="None (No Website)",
            )
            for i in range(100)
        ]

        res1 = ingestor.ingest(leads_100, dry_run=False)
        assert res1["unique_ingested"] == 100

        # Run 2: Re-ingest exact same 100 leads
        res2 = ingestor.ingest(leads_100, dry_run=False)
        assert res2["unique_ingested"] == 0, f"Expected 0 unique ingested, got {res2['unique_ingested']}"
        assert res2["duplicates_skipped"] == 100, f"Expected 100 skipped, got {res2['duplicates_skipped']}"

    def test_idempotency_100_variant_leads(self):
        """Re-running ingestion with 100 variant duplicate leads (legal suffixes, 'The', casing) yields 0 unique ingested."""
        client = SheetsClient(offline_mode=True)
        ingestor = CRMIngestor(sheets_client=client)

        base_leads = [
            RawLead(
                business_name=f"Zenith Roofing {i}",
                cleaned_phone=f"817777{i:04d}",
                phone_display=f"(817) 777-{i:04d}",
                city="Fort Worth",
                state="TX",
                zip_code="76102",
                review_count=20,
                star_rating=5.0,
                specialty="Commercial Roofing",
                website_status="None (No Website)",
            )
            for i in range(100)
        ]
        res1 = ingestor.ingest(base_leads, dry_run=False)
        assert res1["unique_ingested"] == 100

        # Variant 100 duplicate leads
        variant_leads = [
            RawLead(
                business_name=f"The Zenith Roofing {i}, LLC" if i % 2 == 0 else f"ZENITH ROOFING {i}, INC.",
                cleaned_phone=f"817777{i:04d}",
                phone_display=f"(817) 777-{i:04d}",
                city="Fort Worth",
                state="TX",
                zip_code="76102",
                review_count=20,
                star_rating=5.0,
                specialty="Commercial Roofing",
                website_status="None (No Website)",
            )
            for i in range(100)
        ]

        res2 = ingestor.ingest(variant_leads, dry_run=False)
        assert res2["unique_ingested"] == 0
        assert res2["duplicates_skipped"] == 100

    def test_idempotency_100_empty_phone_leads(self):
        """Re-running ingestion with 100 leads with empty phones (100% name-based) yields 0 unique ingested."""
        client = SheetsClient(offline_mode=True)
        ingestor = CRMIngestor(sheets_client=client)

        base_leads = [
            RawLead(
                business_name=f"Atlas Roofing Systems {i}",
                cleaned_phone="",
                phone_display="(Unlisted)",
                city="Tyler",
                state="TX",
                zip_code="75701",
                review_count=8,
                star_rating=4.7,
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )
            for i in range(100)
        ]
        res1 = ingestor.ingest(base_leads, dry_run=False)
        assert res1["unique_ingested"] == 100

        # Variant 100 duplicate leads with empty phones
        variant_leads = [
            RawLead(
                business_name=f"The Atlas Roofing Systems {i}, LLC" if i % 2 == 0 else f"ATLAS ROOFING SYSTEMS {i}, CORP.",
                cleaned_phone="",
                phone_display="(Unlisted)",
                city="Tyler",
                state="TX",
                zip_code="75701",
                review_count=8,
                star_rating=4.7,
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )
            for i in range(100)
        ]

        res2 = ingestor.ingest(variant_leads, dry_run=False)
        assert res2["unique_ingested"] == 0
        assert res2["duplicates_skipped"] == 100
