"""
Adversarial Stress Test Suite for Milestone 2: CRM Schema Integrity & Formula Safety.

Empirically challenges:
1. Exact 21-Column invariant (Cols A through U) across conversions and writes.
2. Edge-case inputs: empty fields, null values, special characters, unicode emojis, extreme review counts, unusual timezones.
3. Est. Deal Value (Col T): strictly rejects string-formatted values (e.g. "$4,000") and requires positive integers.
4. Priority (Col B): strictly rejects bare strings (e.g. "High", "Low") without mandatory emoji prefix.
5. Row appending safety: never writes to or shifts rows 2-13; preserves header and dashboard formulas.
"""

import pytest
from typing import Any, List
from unittest.mock import MagicMock

from src.models import RawLead, QualifiedLead, CRMRecord
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
    HIGH_PRIORITY_EMOJI,
    MEDIUM_PRIORITY_EMOJI,
    LOW_PRIORITY_EMOJI,
)
from src.crm.ingestor import CRMIngestor, ingest_leads
from src.crm.sheets_client import SheetsClient


# ===========================================================================
# 1. Exact 21-Column (Cols A through U) Invariant
# ===========================================================================

class TestAdversarial21Columns:
    """Verify that every generated CRM row strictly adheres to exactly 21 columns."""

    def test_lead_to_crm_row_exact_21_length(self, sample_texas_raw_lead):
        """Verify lead_to_crm_row outputs exactly 21 items for diverse states."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)
        assert len(row) == 21, f"Expected 21 columns, got {len(row)}"

    def test_crm_columns_schema_definition(self):
        """Verify CRM_COLUMNS defines exactly 21 headers A through U."""
        assert len(CRM_COLUMNS) == 21
        expected_cols = [
            "Lead Status", "Priority", "Company Name", "Website", "Industry / Niche",
            "Company Size", "Contact First Name", "Contact Last Name", "Job Title",
            "Work Email", "Email Verification", "LinkedIn Profile", "Location",
            "Outreach Channel", "Touch 1 Date", "Last Follow-Up Date", "Next Action Due",
            "Personalized Icebreaker", "Offer Angle / Pain Point", "Est. Deal Value ($)",
            "Notes & Next Steps"
        ]
        assert CRM_COLUMNS == expected_cols

    def test_validate_crm_row_rejects_under_21_columns(self, sample_texas_raw_lead):
        """Verify validate_crm_row rejects rows with fewer than 21 columns."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        for cut_idx in [0, 1, 5, 10, 15, 20]:
            short_row = row[:cut_idx]
            with pytest.raises(ValueError, match="at least 21 elements"):
                validate_crm_row(short_row)

    def test_ingestor_write_range_spans_exactly_columns_a_through_u(self, sample_texas_raw_lead):
        """Verify update_range receives an A{row}:U{row} range."""
        mock_client = SheetsClient(offline_mode=True)
        ingestor = CRMIngestor(sheets_client=mock_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        res = ingestor.ingest([lead])
        assert res["status"] == "success"
        start_row = res["start_row"]
        end_row = res["end_row"]

        # Verify offline storage recorded the range A:U
        expected_range_key = f"Leads Tracker!A{start_row}:U{end_row}"
        assert expected_range_key in mock_client.mock_data
        stored_rows = mock_client.mock_data[expected_range_key]
        assert len(stored_rows) == 1
        assert len(stored_rows[0]) == 21


# ===========================================================================
# 2. Edge-Case Inputs (Special Chars, Emojis, Extremes, Timezones)
# ===========================================================================

class TestAdversarialEdgeCaseInputs:
    """Adversarially challenge data sanitization, Unicode handling, and injection."""

    def test_special_characters_in_business_name(self, sample_texas_raw_lead):
        """Verify business names with quotes, HTML, SQL, and formulas are processed safely."""
        adversarial_names = [
            'Coop\'s "Elite" & Brothers Roofing LLC',
            '<script>alert("xss")</script> Roofing Inc.',
            "DROP TABLE roofers; -- O'Reilly Roofing",
            "=SUM(A1:A10) Roofers Corp",
            "+1-800-ROOFERS Co.",
            "-500 Emergency Roof Leak Repair",
            "@TwitterRoofing Team",
            "A&B\\C/D*E?F[G] Roofing",
            "Tabs\tand\nNewlines\rRoofing",
        ]
        for adv_name in adversarial_names:
            lead_dict = sample_texas_raw_lead.model_dump()
            lead_dict["business_name"] = adv_name
            raw = RawLead(**lead_dict)
            row = lead_to_crm_row(raw, row_index=14)
            assert len(row) == 21
            assert validate_crm_row(row) is True
            assert row[2] == adv_name.strip()
            record = crm_row_to_record(row, row_index=14)
            assert record.company_name == adv_name.strip()

    def test_unicode_and_emojis_in_fields(self, sample_texas_raw_lead):
        """Verify Unicode characters, foreign alphabets, and emojis don't crash schema validation."""
        lead_dict = sample_texas_raw_lead.model_dump()
        lead_dict["business_name"] = "🔥 Top Notch Roofing 🔨 & Solar ⚡ LLC"
        lead_dict["city"] = "São José"
        lead_dict["specialty"] = "Coberturas & Reparación de Techos 🏠"

        raw = RawLead(**lead_dict)
        row = lead_to_crm_row(raw, row_index=14, icebreaker="Olá! Ótimo trabalho 🌟", offer_angle="Proteção contra chuva 🌧️")
        assert len(row) == 21
        assert validate_crm_row(row) is True
        assert "🔥 Top Notch Roofing 🔨 & Solar ⚡ LLC" in row[2]
        assert "São José, TX (CST)" in row[12]
        assert "Coberturas & Reparación de Techos 🏠" in row[4]
        assert row[17] == "Olá! Ótimo trabalho 🌟"
        assert row[18] == "Proteção contra chuva 🌧️"

    def test_empty_and_null_edge_cases(self, sample_texas_raw_lead):
        """Verify empty optional fields and null fallbacks handle safely."""
        lead_dict = sample_texas_raw_lead.model_dump()
        lead_dict["cleaned_phone"] = ""
        lead_dict["website_url"] = None
        lead_dict["place_url"] = ""

        raw = RawLead(**lead_dict)
        row = lead_to_crm_row(raw, row_index=14)
        assert len(row) == 21
        assert validate_crm_row(row) is True
        # Col J (Work Email) should reflect phone display or fallback
        assert "Call:" in row[9]
        # Col L (LinkedIn / Profile) should be empty string
        assert row[11] == ""
        # Col R & S (Icebreaker & Offer Angle) should default to empty string
        assert row[17] == ""
        assert row[18] == ""

    def test_null_cells_in_validate_crm_row_raise_descriptive_errors(self, sample_texas_raw_lead):
        """Verify passing None in critical cells raises descriptive ValueError."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        base_row = lead_to_crm_row(raw, row_index=14)

        # Null Lead Status (Col A)
        row_null_status = list(base_row)
        row_null_status[0] = None
        with pytest.raises(ValueError, match="Invalid Lead Status"):
            validate_crm_row(row_null_status)

        # Null Priority (Col B)
        row_null_priority = list(base_row)
        row_null_priority[1] = None
        with pytest.raises(ValueError, match="Invalid Priority"):
            validate_crm_row(row_null_priority)

        # Null Company Size (Col F)
        row_null_size = list(base_row)
        row_null_size[5] = None
        with pytest.raises(ValueError, match="Company Size must be a string"):
            validate_crm_row(row_null_size)

        # Null Email Verification (Col K)
        row_null_ev = list(base_row)
        row_null_ev[10] = None
        with pytest.raises(ValueError, match="Invalid Email Verification"):
            validate_crm_row(row_null_ev)

        # Null Outreach Channel (Col N)
        row_null_channel = list(base_row)
        row_null_channel[13] = None
        with pytest.raises(ValueError, match="Invalid Outreach Channel"):
            validate_crm_row(row_null_channel)

        # Null Deal Value (Col T)
        row_null_deal = list(base_row)
        row_null_deal[19] = None
        with pytest.raises(ValueError, match="Invalid Est. Deal Value"):
            validate_crm_row(row_null_deal)

    def test_extreme_review_counts_scoring_and_conversion(self, sample_texas_raw_lead):
        """Verify boundary and extreme review counts: 0, 1, 2, 3, 5, 9, 10, 100, 1000000."""
        cases = [
            (0, "Residential Roofing & Repairs", LOW_PRIORITY_EMOJI, 3000),
            (1, "Residential Roofing & Repairs", LOW_PRIORITY_EMOJI, 3000),
            (2, "Residential Roofing & Repairs", LOW_PRIORITY_EMOJI, 3000),
            (3, "Residential Roofing & Repairs", MEDIUM_PRIORITY_EMOJI, 3500),
            (5, "Storm Damage & Re-roofing", HIGH_PRIORITY_EMOJI, 4500),
            (9, "Residential Roofing & Repairs", MEDIUM_PRIORITY_EMOJI, 3500),
            (10, "Residential Roofing & Repairs", HIGH_PRIORITY_EMOJI, 4000),
            (10, "Commercial Roofing", HIGH_PRIORITY_EMOJI, 4500),
            (100, "Commercial Roofing", HIGH_PRIORITY_EMOJI, 4500),
            (10000, "Residential Roofing & Repairs", HIGH_PRIORITY_EMOJI, 4000),
            (1000000, "Storm Damage & Re-roofing", HIGH_PRIORITY_EMOJI, 4500),
        ]
        for count, specialty, expected_priority, expected_deal in cases:
            p, d = score_lead(review_count=count, specialty=specialty)
            assert p == expected_priority
            assert d == expected_deal

            lead_dict = sample_texas_raw_lead.model_dump()
            lead_dict["review_count"] = count
            lead_dict["specialty"] = specialty
            raw = RawLead(**lead_dict)
            row = lead_to_crm_row(raw, row_index=14)
            assert row[1] == expected_priority
            assert row[19] == expected_deal
            assert isinstance(row[19], int)
            assert validate_crm_row(row) is True

    def test_unusual_timezones_and_state_variations(self):
        """Verify state timezone resolutions and fallbacks."""
        # Standard target states
        assert get_state_timezone("TX") == "CST"
        assert get_state_timezone("FL") == "EST"
        assert get_state_timezone("OH") == "EST"
        assert get_state_timezone("GA") == "EST"
        assert get_state_timezone("AZ") == "MST"

        # Case normalization and whitespace
        assert get_state_timezone("  tx  ") == "CST"
        assert get_state_timezone("fl") == "EST"

        # Non-target states fall back gracefully to EST without crashing
        assert get_state_timezone("CA") == "EST"
        assert get_state_timezone("WA") == "EST"
        assert get_state_timezone("CO") == "EST"
        assert get_state_timezone("") == "EST"
        assert get_state_timezone(None) == "EST"

        # Location string formatting
        loc_tx = format_location_display("Tyler", "TX")
        assert loc_tx == "Tyler, TX (CST)"
        loc_az = format_location_display("Flagstaff", "AZ")
        assert loc_az == "Flagstaff, AZ (MST)"
        loc_fl = format_location_display("Ocala", "FL")
        assert loc_fl == "Ocala, FL (EST)"


# ===========================================================================
# 3. Est. Deal Value (Col T) Strict Integer Safety & Formula Protection
# ===========================================================================

class TestAdversarialDealValueFormulaSafety:
    """Verify Col T strictly enforces integers to protect =SUM(T14:T) formulas."""

    def test_col_t_rejects_string_formatted_currency(self, sample_texas_raw_lead):
        """Verify formatted currency strings like '$4,000' or '$4500' are rejected."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        invalid_currency_strings = [
            "$4,000",
            "$4500",
            "$3,500.00",
            "4000",
            "4,500",
            "USD 4000",
            "4000 USD",
            "4k",
        ]
        for bad_val in invalid_currency_strings:
            bad_row = list(row)
            bad_row[19] = bad_val
            with pytest.raises(ValueError, match="pure positive numeric integer"):
                validate_crm_row(bad_row)

    def test_col_t_rejects_floats_and_booleans(self, sample_texas_raw_lead):
        """Verify floats, booleans (bool is subclass of int in Python), and negative numbers are rejected."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        invalid_types = [
            4000.0,
            4500.50,
            True,       # Critical: isinstance(True, int) is True in Python!
            False,      # Critical: isinstance(False, int) is True in Python!
            0,          # Zero deal value
            -1,         # Negative deal value
            -4000,      # Negative deal value
            None,
            [4000],
            {"value": 4000},
        ]
        for bad_val in invalid_types:
            bad_row = list(row)
            bad_row[19] = bad_val
            with pytest.raises(ValueError, match="pure positive numeric integer"):
                validate_crm_row(bad_row)

    def test_lead_to_crm_row_rejects_bad_override_deal_value(self, sample_texas_raw_lead):
        """Verify lead_to_crm_row raises error when bad deal value override is given."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())

        # String currency override raises ValueError on int conversion
        with pytest.raises(ValueError):
            lead_to_crm_row(raw, override_deal_value="$4,000")

        # Negative int override raises ValueError in validate_crm_row
        with pytest.raises(ValueError, match="pure positive numeric integer"):
            lead_to_crm_row(raw, override_deal_value=-500)


# ===========================================================================
# 4. Priority (Col B) Strict Emoji Prefix Validation
# ===========================================================================

class TestAdversarialPriorityEmojiValidation:
    """Verify Priority in Col B strictly mandates emoji prefix and rejects bare text."""

    def test_col_b_rejects_bare_strings(self, sample_texas_raw_lead):
        """Verify bare strings like 'High', 'Low', 'Medium' are strictly rejected."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        bare_strings = [
            "High",
            "high",
            "HIGH",
            "Medium",
            "medium",
            "Low",
            "low",
            "Urgent",
            "Standard",
            "Critical",
            "High 🔥",  # Reversed emoji
            "🔥High",   # Missing space
            "⚡Medium",  # Missing space
            "❄️Low",   # Missing space
            "",
            None,
        ]
        for bare in bare_strings:
            bad_row = list(row)
            bad_row[1] = bare
            with pytest.raises(ValueError, match="Invalid Priority"):
                validate_crm_row(bad_row)

    def test_col_b_accepts_valid_emoji_priorities(self, sample_texas_raw_lead):
        """Verify only the three canonical emoji-prefixed strings pass validation."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())
        row = lead_to_crm_row(raw, row_index=14)

        valid_priorities = ["🔥 High", "⚡ Medium", "❄️ Low"]
        for p in valid_priorities:
            valid_row = list(row)
            valid_row[1] = p
            assert validate_crm_row(valid_row) is True

    def test_lead_to_crm_row_auto_prefixes_unprefixed_priorities(self, sample_texas_raw_lead):
        """Verify lead_to_crm_row safely auto-prefixes bare priorities if provided as overrides."""
        raw = RawLead(**sample_texas_raw_lead.model_dump())

        row_high = lead_to_crm_row(raw, override_priority="High")
        assert row_high[1] == "🔥 High"

        row_low = lead_to_crm_row(raw, override_priority="low")
        assert row_low[1] == "❄️ Low"

        row_med = lead_to_crm_row(raw, override_priority="Medium")
        assert row_med[1] == "⚡ Medium"


# ===========================================================================
# 5. Row Appending Safety & Preservation of Rows 2-13 & Formulas
# ===========================================================================

class TestAdversarialRowAppendingSafety:
    """Verify ingestion never writes below row 14 and never shifts or mutates rows 2-13."""

    def test_empty_sheet_starts_strictly_at_row_14(self, sample_texas_raw_lead):
        """Verify ingestion into a completely empty sheet starts at Row 14 (not Row 2)."""
        mock_client = SheetsClient(offline_mode=True, mock_data={"Leads Tracker!A2:U500": []})
        ingestor = CRMIngestor(sheets_client=mock_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        res = ingestor.ingest([lead])
        assert res["start_row"] == 14
        assert res["end_row"] == 14
        assert res["crm_records"][0].row_index == 14

    def test_partially_filled_rows_2_to_6_starts_strictly_at_row_14(self, sample_texas_raw_lead):
        """Verify ingestion when rows 2-6 have data still starts at Row 14, protecting rows 7-13."""
        partial_rows = [
            ["Not Contacted", "🔥 High", f"Seed Roofer {i}", "None", "Roofing", "'1-10",
             "Team", "Contractor", "Owner", "Call: 555-0000", "Unverified", "", "Dallas, TX (CST)",
             "Cold Call", "", "", "", "", "", 4000, "Notes"]
            for i in range(2, 7)
        ]
        mock_client = SheetsClient(offline_mode=True, mock_data={"Leads Tracker!A2:U500": partial_rows})
        ingestor = CRMIngestor(sheets_client=mock_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        res = ingestor.ingest([lead])
        assert res["start_row"] == 14
        assert res["end_row"] == 14

    def test_fully_filled_rows_2_to_13_starts_strictly_at_row_14(self, sample_texas_raw_lead):
        """Verify ingestion when all rows 2 to 13 are filled starts at Row 14."""
        filled_rows = [
            ["Not Contacted", "🔥 High", f"Seed Roofer {i}", "None", "Roofing", "'1-10",
             "Team", "Contractor", "Owner", f"Call: (555) 000-{i:04d}", "Unverified", "",
             "Dallas, TX (CST)", "Cold Call", "", "", "", "", "", 4000, f"Notes {i}"]
            for i in range(2, 14)
        ]
        assert len(filled_rows) == 12

        mock_client = SheetsClient(offline_mode=True, mock_data={"Leads Tracker!A2:U500": filled_rows})
        ingestor = CRMIngestor(sheets_client=mock_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        res = ingestor.ingest([lead])
        assert res["start_row"] == 14
        assert res["end_row"] == 14

    def test_ingestion_past_row_14_increments_monotonically(self, sample_texas_raw_lead, sample_florida_raw_lead):
        """Verify subsequent ingestions append consecutively without overwriting previous data."""
        # 12 seed rows (rows 2-13) + 3 previous leads (rows 14-16)
        existing_rows = [
            ["Not Contacted", "🔥 High", f"Contractor {i}", "None", "Roofing", "'1-10",
             "Team", "Contractor", "Owner", f"Call: (555) 000-{i:04d}", "Unverified", "",
             "Dallas, TX (CST)", "Cold Call", "", "", "", "", "", 4000, f"Notes {i}"]
            for i in range(2, 17)
        ]
        assert len(existing_rows) == 15

        mock_client = SheetsClient(offline_mode=True, mock_data={"Leads Tracker!A2:U500": existing_rows})
        ingestor = CRMIngestor(sheets_client=mock_client)

        lead1 = RawLead(**sample_texas_raw_lead.model_dump())
        lead2 = RawLead(**sample_florida_raw_lead.model_dump())

        res = ingestor.ingest([lead1, lead2])
        # 15 existing rows -> next available row is 15 + 2 = 17
        assert res["start_row"] == 17
        assert res["end_row"] == 18
        assert res["unique_ingested"] == 2
        assert res["crm_records"][0].row_index == 17
        assert res["crm_records"][1].row_index == 18

    def test_existing_rows_2_to_13_remain_completely_unmutated(self, sample_texas_raw_lead):
        """Verify that rows 2 through 13 in the sheet grid are not modified during ingestion."""
        seed_rows = [
            ["Not Contacted", "🔥 High", f"IMMUTABLE_ROOFER_{i}", "None", "Roofing", "'1-10",
             "Team", "Contractor", "Owner", f"Call: (555) 999-{i:04d}", "Unverified", "",
             "Dallas, TX (CST)", "Cold Call", "", "", "", "", "", 4000, f"Dashboard Formula Reference {i}"]
            for i in range(2, 14)
        ]
        mock_client = SheetsClient(
            offline_mode=True,
            mock_data={"Leads Tracker!A2:U13": seed_rows, "Leads Tracker!A2:U500": seed_rows}
        )
        ingestor = CRMIngestor(sheets_client=mock_client)
        lead = RawLead(**sample_texas_raw_lead.model_dump())

        ingestor.ingest([lead])

        # Verify that rows 2-13 in the grid are identical to original seed
        grid = mock_client._tab_grids["Leads Tracker"]
        # grid index 0 is row 1 (or empty padding), index 1 is row 2
        for i in range(2, 14):
            grid_row = grid[i - 1]
            assert grid_row[2] == f"IMMUTABLE_ROOFER_{i}"
            assert grid_row[19] == 4000

        # Newly appended row at row 14 (grid index 13)
        assert grid[13][2] == "General Roofing & Restoration"
        assert grid[13][19] == 4500
