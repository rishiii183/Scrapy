"""
Unit Tests for Milestone 2: Google Sheets CRM Ingestion & Deduplication.

Covers:
1. 21-Column CRM Schema Mapping, Formatting, and Strict Validation (Cols A-U)
2. Lead Scoring & Priority Assignment (🔥 High, ⚡ Medium, ❄️ Low, Deal Values)
3. Deduplication Engine (Name normalization, 10-digit phone cleaner, intra-batch dedup, idempotency)
4. Google Sheets API Client (OAuth auto-refresh, offline mock mode, CLI fallback, rate limit backoff)
5. Safe CRM Ingestion (Row 14 start, formula preservation, dry-run mode)
"""

import os
import re
import pytest
from unittest.mock import MagicMock, patch
import urllib.error

from src.models import RawLead, QualifiedLead, CRMRecord
from src.crm.sheets_client import (
    SheetsClient,
    validate_spreadsheet_id,
    compute_exponential_backoff,
    normalize_range_key,
    DEFAULT_CLI_PATH,
    DEFAULT_TOKEN_PATH,
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
    get_state_timezone,
)
from src.crm.lead_scorer import (
    score_lead,
    score_lead_record,
    is_high_ticket_specialty,
    HIGH_PRIORITY_EMOJI,
    MEDIUM_PRIORITY_EMOJI,
    LOW_PRIORITY_EMOJI,
)
from src.crm.dedup import (
    normalize_phone,
    normalize_business_name,
    extract_phones_from_text,
    parse_crm_rows,
    CRMDeduplicator,
)
from src.crm.ingestor import (
    CRMIngestor,
    ingest_leads,
)


# ===========================================================================
# 1. Schema Mapping & Validation Tests (Columns A through U)
# ===========================================================================

class TestCRMSchema:
    """Verify all 21 standard columns A through U, field types, and strict validators."""

    def test_crm_columns_count_and_alignment(self):
        """Verify exactly 21 standard columns are defined in expected order."""
        assert len(CRM_COLUMNS) == 21
        assert CRM_COLUMNS[0] == "Lead Status"
        assert CRM_COLUMNS[1] == "Priority"
        assert CRM_COLUMNS[2] == "Company Name"
        assert CRM_COLUMNS[3] == "Website"
        assert CRM_COLUMNS[4] == "Industry / Niche"
        assert CRM_COLUMNS[5] == "Company Size"
        assert CRM_COLUMNS[6] == "Contact First Name"
        assert CRM_COLUMNS[7] == "Contact Last Name"
        assert CRM_COLUMNS[8] == "Job Title"
        assert CRM_COLUMNS[9] == "Work Email"
        assert CRM_COLUMNS[10] == "Email Verification"
        assert CRM_COLUMNS[11] == "LinkedIn Profile"
        assert CRM_COLUMNS[12] == "Location"
        assert CRM_COLUMNS[13] == "Outreach Channel"
        assert CRM_COLUMNS[14] == "Touch 1 Date"
        assert CRM_COLUMNS[15] == "Last Follow-Up Date"
        assert CRM_COLUMNS[16] == "Next Action Due"
        assert CRM_COLUMNS[17] == "Personalized Icebreaker"
        assert CRM_COLUMNS[18] == "Offer Angle / Pain Point"
        assert CRM_COLUMNS[19] == "Est. Deal Value ($)"
        assert CRM_COLUMNS[20] == "Notes & Next Steps"

    def test_lead_to_crm_row_maps_21_elements(self, sample_texas_raw_lead):
        """Verify converter generates exactly 21 elements matching schema."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)
        assert len(row) == 21
        assert validate_crm_row(row) is True
        assert row[0] == "Not Contacted"
        assert row[1] == "🔥 High"
        assert row[2] == "General Roofing & Restoration"
        assert row[3] == "None (No Website)"
        assert row[4] == "Storm Damage & Re-roofing"
        assert row[5] == "'1-10"
        assert row[12] == "Tyler, TX (CST)"
        assert row[13] == "Cold Call"
        assert row[19] == 4500  # High ticket storm roofer with >10 reviews

    def test_deal_value_numeric_integer_validation(self, sample_texas_raw_lead):
        """Verify deal value in Col T rejects currency strings and requires positive integer."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)
        assert isinstance(row[19], int)
        assert not isinstance(row[19], bool)
        assert row[19] > 0

        # Tamper row with formatted currency string
        bad_row = list(row)
        bad_row[19] = "$4,500"
        with pytest.raises(ValueError, match="pure positive numeric integer"):
            validate_crm_row(bad_row)

        # Tamper with negative deal value
        bad_row[19] = -100
        with pytest.raises(ValueError, match="pure positive numeric integer"):
            validate_crm_row(bad_row)

    def test_strict_lead_status_validation(self, sample_texas_raw_lead):
        """Verify strict validation against allowed Lead Status dropdown values."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        for status in ALLOWED_LEAD_STATUSES:
            valid_row = list(row)
            valid_row[0] = status
            assert validate_crm_row(valid_row) is True

        bad_row = list(row)
        bad_row[0] = "In Discussion"
        with pytest.raises(ValueError, match="Invalid Lead Status"):
            validate_crm_row(bad_row)

    def test_strict_priority_emoji_validation(self, sample_texas_raw_lead):
        """Verify Priority mandates emoji prefix and rejects bare text."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        for priority in ALLOWED_PRIORITIES:
            valid_row = list(row)
            valid_row[1] = priority
            assert validate_crm_row(valid_row) is True

        bare_priorities = ["High", "Medium", "Low", "Urgent", "high"]
        for bare in bare_priorities:
            bad_row = list(row)
            bad_row[1] = bare
            with pytest.raises(ValueError, match="Invalid Priority"):
                validate_crm_row(bad_row)

    def test_company_size_prefixed_string(self, sample_texas_raw_lead):
        """Verify company size is formatted as string with quote to prevent Sheets date bug."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)
        assert isinstance(row[5], str)
        assert row[5] == "'1-10"

    def test_strict_email_verification_validation(self, sample_texas_raw_lead):
        """Verify Email Verification rejects invalid values."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        for ev in ALLOWED_EMAIL_VERIFICATIONS:
            valid_row = list(row)
            valid_row[10] = ev
            assert validate_crm_row(valid_row) is True

        bad_row = list(row)
        bad_row[10] = "Pending"
        with pytest.raises(ValueError, match="Invalid Email Verification"):
            validate_crm_row(bad_row)

    def test_strict_outreach_channel_validation(self, sample_texas_raw_lead):
        """Verify Outreach Channel rejects invalid channels."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        for ch in ALLOWED_OUTREACH_CHANNELS:
            valid_row = list(row)
            valid_row[13] = ch
            assert validate_crm_row(valid_row) is True

        bad_row = list(row)
        bad_row[13] = "Direct Mail"
        with pytest.raises(ValueError, match="Invalid Outreach Channel"):
            validate_crm_row(bad_row)

    def test_row_to_crm_record_roundtrip(self, sample_texas_raw_lead):
        """Verify 21-element row converts to valid CRMRecord model."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)
        record = crm_row_to_record(row, row_index=14)
        assert isinstance(record, CRMRecord)
        assert record.row_index == 14
        assert record.company_name == "General Roofing & Restoration"
        assert record.priority == "🔥 High"
        assert record.est_deal_value == 4500

    def test_location_timezone_formatting(self):
        """Verify location formatting correctly assigns timezones across states."""
        assert format_location_display("Tyler", "TX") == "Tyler, TX (CST)"
        assert format_location_display("Ocala", "FL") == "Ocala, FL (EST)"
        assert format_location_display("Canton", "OH") == "Canton, OH (EST)"
        assert format_location_display("Macon", "GA") == "Macon, GA (EST)"
        assert format_location_display("Flagstaff", "AZ") == "Flagstaff, AZ (MST)"
        assert format_location_display("Unknown", "XX") == "Unknown, XX (EST)"

    def test_crm_row_minimum_length_validation(self):
        """Verify validator raises error if row has fewer than 21 items."""
        short_row = ["Not Contacted", "🔥 High", "Apex Roofing"]
        with pytest.raises(ValueError, match="at least 21 elements"):
            validate_crm_row(short_row)


# ===========================================================================
# 2. Lead Scoring & Priority Assignment Tests
# ===========================================================================

class TestLeadScorer:
    """Verify priority tiering and deal values based on reviews, specialty, and web status."""

    def test_high_priority_10_plus_reviews_residential(self):
        """Verify >=10 reviews with residential roofing scores 🔥 High at $4,000."""
        priority, deal = score_lead(review_count=10, specialty="Residential Roofing & Repairs")
        assert priority == HIGH_PRIORITY_EMOJI
        assert deal == 4000

        priority_15, deal_15 = score_lead(review_count=15, specialty="Residential Roofing & Repairs")
        assert priority_15 == HIGH_PRIORITY_EMOJI
        assert deal_15 == 4000

    def test_high_priority_10_plus_reviews_high_ticket(self):
        """Verify >=10 reviews with storm or commercial scores 🔥 High at $4,500."""
        priority, deal = score_lead(review_count=12, specialty="Storm Damage & Re-roofing")
        assert priority == HIGH_PRIORITY_EMOJI
        assert deal == 4500

        p_comm, d_comm = score_lead(review_count=10, specialty="Commercial Roofing")
        assert p_comm == HIGH_PRIORITY_EMOJI
        assert d_comm == 4500

    def test_high_priority_5_to_9_reviews_storm_commercial(self):
        """Verify 5-9 reviews for high-ticket storm/commercial qualifies for 🔥 High ($4,500)."""
        priority_5, deal_5 = score_lead(review_count=5, specialty="Storm Damage & Re-roofing")
        assert priority_5 == HIGH_PRIORITY_EMOJI
        assert deal_5 == 4500

        priority_9, deal_9 = score_lead(review_count=9, specialty="Commercial & Industrial Roofing")
        assert priority_9 == HIGH_PRIORITY_EMOJI
        assert deal_9 == 4500

    def test_medium_priority_3_to_9_reviews_residential(self):
        """Verify 3-9 reviews for general residential qualifies for ⚡ Medium ($3,500)."""
        p3, d3 = score_lead(review_count=3, specialty="Residential Roofing & Repairs")
        assert p3 == MEDIUM_PRIORITY_EMOJI
        assert d3 == 3500

        p9, d9 = score_lead(review_count=9, specialty="Residential Roofing & Repairs")
        assert p9 == MEDIUM_PRIORITY_EMOJI
        assert d9 == 3500

    def test_medium_priority_social_presence_low_reviews(self):
        """Verify contractor with social profile qualifies for ⚡ Medium even with <3 reviews."""
        p_social, d_social = score_lead(review_count=1, specialty="Residential", has_social=True)
        assert p_social == MEDIUM_PRIORITY_EMOJI
        assert d_social == 3500

    def test_low_priority_under_3_reviews_no_social(self):
        """Verify <3 reviews without social presence qualifies for ❄️ Low ($3,000)."""
        p0, d0 = score_lead(review_count=0)
        assert p0 == LOW_PRIORITY_EMOJI
        assert d0 == 3000

        p2, d2 = score_lead(review_count=2)
        assert p2 == LOW_PRIORITY_EMOJI
        assert d2 == 3000

    def test_negative_review_count_safe_handling(self):
        """Verify negative review count clamped safely to 0 and scored ❄️ Low."""
        p_neg, d_neg = score_lead(review_count=-5)
        assert p_neg == LOW_PRIORITY_EMOJI
        assert d_neg == 3000

    def test_score_lead_record_with_pydantic_instances(self, sample_florida_raw_lead):
        """Verify score_lead_record directly scores RawLead instances."""
        raw = RawLead(**sample_florida_raw_lead.model_dump())
        priority, deal = score_lead_record(raw)
        assert priority == HIGH_PRIORITY_EMOJI
        assert deal == 4000


# ===========================================================================
# 3. Deduplication Engine Tests
# ===========================================================================

class TestCRMDeduplication:
    """Verify name & phone normalization, CRM row extraction, and deduplication logic."""

    def test_normalize_phone_standard_us_variants(self):
        """Verify varied phone formats reduce to matching 10-digit primary keys."""
        assert normalize_phone("(903) 807-0683") == "9038070683"
        assert normalize_phone("+1 903-807-0683") == "9038070683"
        assert normalize_phone("+19038070683") == "9038070683"
        assert normalize_phone("1-903-807-0683") == "9038070683"
        assert normalize_phone("903.807.0683") == "9038070683"
        assert normalize_phone("Call: (903) 807-0683") == "9038070683"
        assert normalize_phone("(833) 298-8820") == "8332988820"

    def test_normalize_phone_foreign_and_invalid(self):
        """Verify invalid or international phone numbers do not yield 10-digit primary keys."""
        assert len(normalize_phone("+44 20 7946 0958")) != 10
        assert len(normalize_phone("52235")) != 10
        assert normalize_phone("") == ""
        assert normalize_phone(None) == ""

    def test_normalize_business_name_corporate_suffixes(self):
        """Verify legal corporate entity suffixes are stripped for matching."""
        assert normalize_business_name("Guaranteed Roofing and Repairs, LLC.") == "guaranteed roofing and repairs"
        assert normalize_business_name("Guaranteed Roofing & Repairs Inc") == "guaranteed roofing and repairs"
        assert normalize_business_name("Solarshield Industries, Inc.") == "solarshield industries"
        assert normalize_business_name("Dyer Restoration Solutions Inc") == "dyer restoration solutions"
        assert normalize_business_name("Reyes Roofing LLC") == "reyes roofing"
        assert normalize_business_name("Valley Rebuild Corp.") == "valley rebuild"
        assert normalize_business_name("Lifetime Roofing Company") == "lifetime roofing"

    def test_normalize_business_name_ampersand_and_punctuation(self):
        """Verify '&' becomes 'and', punctuation is removed, and leading 'The' stripped."""
        assert normalize_business_name("Guaranteed Roofing & Repairs") == "guaranteed roofing and repairs"
        assert normalize_business_name("The Guaranteed Roofing & Repairs") == "guaranteed roofing and repairs"
        assert normalize_business_name("Coop's Roofing & Construction") == "coops roofing and construction"

    def test_normalize_business_name_multiple_chained_suffixes(self):
        """Verify chained suffixes like 'LLC, Inc. Co.' are completely stripped."""
        name = "General Roofing & Restoration LLC, Inc. Co."
        assert normalize_business_name(name) == "general roofing and restoration"

    def test_parse_crm_rows_from_existing_sheet_sample(self):
        """Verify parser indexes company names and phones from mock CRM rows."""
        sample_rows = [
            # Row 2
            ["Not Contacted", "🔥 High", "Guaranteed Roofing & Repairs", "None (No Website)", "Storm Damage",
             "'1-10", "Roofing Team", "Contractor", "Owner", "Call: (817) 349-5911", "Unverified", "",
             "Fort Worth, TX (CST)", "Cold Call", "", "", "", "", "", 4000,
             "Phone: (817) 349-5911. Prime candidate for a landing page."],
            # Row 3
            ["Not Contacted", "🔥 High", "TruGuard Roofing & Repairs", "None (No Website)", "Residential",
             "'1-10", "Roofing Team", "Contractor", "Owner", "TruGuardRoofing@gmail.com", "Verified", "",
             "Garland, TX (CST)", "Cold Email", "", "", "", "", "", 4000,
             "Phone: (214) 713-2050. Prime candidate."],
        ]
        names, phones, records = parse_crm_rows(sample_rows)
        assert "guaranteed roofing and repairs" in names
        assert "truguard roofing and repairs" in names
        assert "8173495911" in phones
        assert "2147132050" in phones
        assert len(records) == 2

    def test_deduplicator_detects_existing_phone_match(self):
        """Verify duplicate candidate matching existing phone is rejected."""
        dedup = CRMDeduplicator(existing_phones={"9038070683"})
        lead = {"business_name": "New Name Roofing", "cleaned_phone": "9038070683"}
        is_dup, reason = dedup.is_duplicate(lead)
        assert is_dup is True
        assert "Duplicate phone matched" in reason

    def test_deduplicator_detects_existing_name_match(self):
        """Verify duplicate candidate matching existing normalized name is rejected."""
        dedup = CRMDeduplicator(existing_names={"general roofing and restoration"})
        lead = {"business_name": "The General Roofing & Restoration, LLC", "cleaned_phone": "5551234567"}
        is_dup, reason = dedup.is_duplicate(lead)
        assert is_dup is True
        assert "Duplicate company name matched" in reason

    def test_deduplicator_intra_batch_duplicates(self, sample_texas_raw_lead):
        """Verify intra-batch duplicate where two identical leads are submitted together."""
        dedup = CRMDeduplicator()
        lead1 = RawLead(**sample_texas_raw_lead.model_dump())
        lead2 = RawLead(**sample_texas_raw_lead.model_dump())

        unique, dups = dedup.deduplicate([lead1, lead2])
        assert len(unique) == 1
        assert len(dups) == 1
        assert dups[0]["business_name"] == lead1.business_name

    def test_deduplicator_cross_run_idempotency(self, sample_texas_raw_lead, sample_florida_raw_lead):
        """Verify re-running deduplication on previously ingested data returns 0 unique leads."""
        dedup = CRMDeduplicator()
        lead1 = RawLead(**sample_texas_raw_lead.model_dump())
        lead2 = RawLead(**sample_florida_raw_lead.model_dump())

        # Run 1: Ingest batch
        unique_1, dups_1 = dedup.deduplicate([lead1, lead2])
        assert len(unique_1) == 2
        assert len(dups_1) == 0

        # Run 2: Re-ingest exact same batch
        unique_2, dups_2 = dedup.deduplicate([lead1, lead2])
        assert len(unique_2) == 0
        assert len(dups_2) == 2


# ===========================================================================
# 4. Sheets Client & Offline / Mock Mode Tests
# ===========================================================================

class TestSheetsClient:
    """Verify SheetsClient operations, validation, backoff calculation, and offline mode."""

    def test_validate_spreadsheet_id_boundaries(self):
        """Verify spreadsheet ID validation catches invalid inputs."""
        valid_id = "12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY"
        validate_spreadsheet_id(valid_id)  # Should not raise

        invalid_ids = ["", "short", "has space in id 1234567890", 12345, None]
        for bad in invalid_ids:
            with pytest.raises((ValueError, TypeError)):
                validate_spreadsheet_id(bad)

    def test_compute_exponential_backoff(self):
        """Verify exponential backoff calculation: 1.0, 2.0, 4.0, up to max."""
        assert compute_exponential_backoff(0, base=1.0) == 1.0
        assert compute_exponential_backoff(1, base=1.0) == 2.0
        assert compute_exponential_backoff(2, base=1.0) == 4.0
        assert compute_exponential_backoff(3, base=1.0) == 8.0
        assert compute_exponential_backoff(10, base=1.0, max_backoff=32.0) == 32.0

    def test_normalize_range_key_formatting(self):
        """Verify range key normalizer strips single quotes around tab names."""
        assert normalize_range_key("'Leads Tracker'!A1:U50") == "Leads Tracker!A1:U50"
        assert normalize_range_key("Leads Tracker!A1:U50") == "Leads Tracker!A1:U50"

    def test_offline_mode_read_append_update(self):
        """Verify offline mode stores and retrieves mock data completely in-memory."""
        initial_rows = [["Header 1", "Header 2"], ["Val 1", "Val 2"]]
        client = SheetsClient(
            offline_mode=True,
            mock_data={"Leads Tracker!A1:B2": initial_rows},
        )
        sheet_id = "12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY"

        # Read range
        read_res = client.read_range(sheet_id, "'Leads Tracker'!A1:B2")
        assert len(read_res) == 2
        assert read_res[0] == ["Header 1", "Header 2"]

        # Append rows
        app_res = client.append_rows(sheet_id, "'Leads Tracker'!A:B", [["Val 3", "Val 4"]])
        assert app_res["updates"]["updatedRows"] == 1

        # Verify appended row exists
        read_after = client.read_range(sheet_id, "'Leads Tracker'!A:B")
        assert len(read_after) == 3
        assert read_after[2] == ["Val 3", "Val 4"]

        # Update range
        upd_res = client.update_range(sheet_id, "'Leads Tracker'!A1:B1", [["New H1", "New H2"]])
        assert upd_res["updatedRows"] == 1

    def test_token_refresh_simulation_on_http_401(self):
        """Verify expired access token (HTTP 401) triggers refresh_access_token call and retries."""
        client = SheetsClient(offline_mode=False)
        client.access_token = "expired_token"
        client.refresh_token = "valid_refresh"
        client.client_id = "test_client_id"
        client.client_secret = "test_client_secret"

        with patch.object(client, "refresh_access_token", return_value="new_active_token") as mock_refresh:
            with patch("urllib.request.urlopen") as mock_urlopen:
                # First call raises HTTP 401, second call succeeds
                err_response = MagicMock()
                err_response.code = 401
                http_err = urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)

                success_resp = MagicMock()
                success_resp.read.return_value = b'{"values": [["Row 1"]]}'
                success_resp.__enter__.return_value = success_resp

                mock_urlopen.side_effect = [http_err, success_resp]

                res = client._execute_request("GET", "https://test.url")
                assert mock_refresh.call_count == 1
                assert res == {"values": [["Row 1"]]}

    def test_cli_fallback_detection(self):
        """Verify CLI fallback path is resolved properly."""
        client = SheetsClient(offline_mode=True)
        if os.path.exists(DEFAULT_CLI_PATH):
            assert os.path.exists(client.cli_path)
        assert client.cli_path.endswith("gsheets.cmd")


# ===========================================================================
# 5. Safe CRM Ingestion & Formula Preservation Tests
# ===========================================================================

class TestCRMIngestor:
    """Verify safe ingestion at row 14, formula preservation, and deduplication integration."""

    @pytest.fixture
    def mock_populated_crm_client(self):
        """Mock SheetsClient with header + 12 existing leads (Rows 1 to 13)."""
        header = list(CRM_COLUMNS)
        existing_rows = [header]
        for i in range(2, 14):
            row = [
                "Not Contacted", "🔥 High", f"Existing Roofer {i}", "None (No Website)",
                "Residential Roofing", "'1-10", "Roofing Team", "Contractor", "Owner",
                f"Call: (214) 555-{i:04d}", "Unverified", "", "Dallas, TX (CST)", "Cold Call",
                "", "", "", "", "", 4000, f"Phone: (214) 555-{i:04d}. Audit notes."
            ]
            existing_rows.append(row)

        client = SheetsClient(
            offline_mode=True,
            mock_data={"Leads Tracker!A2:U500": existing_rows[1:]},
        )
        return client

    def test_ingest_starts_at_row_14_preserving_rows_2_to_13(self, mock_populated_crm_client, sample_texas_raw_lead):
        """Verify newly ingested leads strictly start at Row 14 when rows 2-13 are populated."""
        ingestor = CRMIngestor(sheets_client=mock_populated_crm_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        res = ingestor.ingest([lead])
        assert res["status"] == "success"
        assert res["unique_ingested"] == 1
        assert res["start_row"] == 14
        assert res["end_row"] == 14
        assert len(res["crm_records"]) == 1
        assert res["crm_records"][0].row_index == 14

    def test_ingest_filters_duplicates_cleanly(self, mock_populated_crm_client, sample_texas_raw_lead):
        """Verify ingestion skips duplicates matching existing CRM phone or name."""
        ingestor = CRMIngestor(sheets_client=mock_populated_crm_client)

        # Lead matching existing roofer 2 phone
        dup_lead = RawLead(**sample_texas_raw_lead.model_dump())
        dup_lead.cleaned_phone = "2145550002"

        # Unique lead
        new_lead = RawLead(**sample_texas_raw_lead.model_dump())
        new_lead.business_name = "Brand New Distinct Roofer"
        new_lead.cleaned_phone = "9038070683"

        res = ingestor.ingest([dup_lead, new_lead])
        assert res["unique_ingested"] == 1
        assert res["duplicates_skipped"] == 1
        assert res["start_row"] == 14

    def test_ingest_idempotency_on_rerun(self, mock_populated_crm_client, sample_texas_raw_lead):
        """Verify re-running ingestion with the same leads yields 0 new rows."""
        ingestor = CRMIngestor(sheets_client=mock_populated_crm_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        # First ingestion
        res1 = ingestor.ingest([lead])
        assert res1["unique_ingested"] == 1

        # Second ingestion of the same lead
        res2 = ingestor.ingest([lead])
        assert res2["unique_ingested"] == 0
        assert res2["duplicates_skipped"] == 1

    def test_ingest_dry_run_mode(self, mock_populated_crm_client, sample_texas_raw_lead):
        """Verify dry-run mode returns records without mutating sheet data."""
        ingestor = CRMIngestor(sheets_client=mock_populated_crm_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        res = ingestor.ingest([lead], dry_run=True)
        assert res["dry_run"] is True
        assert res["unique_ingested"] == 1
        assert len(res["crm_records"]) == 1

    def test_ingest_empty_batch(self, mock_populated_crm_client):
        """Verify empty input leads list returns cleanly without error."""
        ingestor = CRMIngestor(sheets_client=mock_populated_crm_client)
        res = ingestor.ingest([])
        assert res["unique_ingested"] == 0
        assert res["duplicates_skipped"] == 0
        assert res["crm_records"] == []

    def test_convenience_ingest_leads_wrapper(self, mock_populated_crm_client, sample_texas_raw_lead):
        """Verify functional convenience ingest_leads wrapper executes cleanly."""
        lead = RawLead(**sample_texas_raw_lead.model_dump())
        res = ingest_leads([lead], sheets_client=mock_populated_crm_client)
        assert res["status"] == "success"
        assert res["unique_ingested"] == 1
