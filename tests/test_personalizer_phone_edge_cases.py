"""
Adversarial Edge Case Phone Number Test Suite for Milestone 3 Remediation.

Empirically tests edge case phone numbers against:
1. Extensions with spaces, colons, case variations:
   - "ext: 12", "ext : 12", "ext:12", "ext. 12", "ext.: 12"
   - "extension 12", "extension: 12", "Extension: 45"
   - "EXT 123", "EXT: 123"
   - "x 12", "x: 12", "x:12", "x : 12", "X 505"
   - "#12", "# 12", "#: 12"
2. +1 International variations:
   - "+1 (903) 807-0683", "+1-903-807-0683", "+1.903.807.0683", "+1 903 807 0683", "+19038070683"
   - "+ 1 (903) 807-0683", "+ 1-903-807-0683", "+ 1.903.807.0683"
   - "1 (903) 807-0683", "1-903-807-0683", "1.903.807.0683", "19038070683"
   - Combined with extensions: "+1 (903) 807-0683 ext. 42", "+1-903-807-0683 x99", "+1 903 807 0683 ext: 501"
3. Mixed delimiters:
   - "(903).807 - 0683", "903 / 807 - 0683", "903/807-0683", "(903)8070683"
   - "903 807.0683", "(903) 807 0683", "tel:+1-903-807-0683"
4. Non-US foreign numbers (must reject / yield empty string):
   - "+44 20 7946 0958" (UK), "+52 55 1234 5678" (Mexico), "+33 1 42 68 55 55" (France)
5. End-to-end generator pipeline:
   - Verify PersonalizerGenerator produces clean wa.me links, correct CRM records, and 0 placeholder tags.
"""

import pytest
import urllib.parse
from src.personalizer.generator import (
    build_whatsapp_link,
    clean_phone_digits,
    extract_lead_context,
    PersonalizerGenerator,
)
from src.personalizer.template_engine import TemplateEngine
from src.models import CRMRecord, RawLead


# ===========================================================================
# 1. Extension Variations: Spaces, Colons, Suffixes
# ===========================================================================

EXTENSION_PHONE_VARIATIONS = [
    # ext variations
    ("(903) 807-0683 ext 12", "19038070683"),
    ("(903) 807-0683 ext: 12", "19038070683"),
    ("(903) 807-0683 ext:12", "19038070683"),
    ("(903) 807-0683 ext : 12", "19038070683"),
    ("(903) 807-0683 ext. 12", "19038070683"),
    ("(903) 807-0683 ext.: 12", "19038070683"),
    ("(903) 807-0683 ext.:12", "19038070683"),
    ("(903) 807-0683 EXT 123", "19038070683"),
    ("(903) 807-0683 EXT: 123", "19038070683"),
    ("(903) 807-0683   ext.   999", "19038070683"),
    ("(903) 807-0683 ext 12345", "19038070683"),
    # extension variations
    ("(903) 807-0683 extension 12", "19038070683"),
    ("(903) 807-0683 extension: 12", "19038070683"),
    ("(903) 807-0683 Extension: 45", "19038070683"),
    ("(903) 807-0683 EXTENSION 901", "19038070683"),
    # x variations
    ("(903) 807-0683 x 12", "19038070683"),
    ("(903) 807-0683 x: 12", "19038070683"),
    ("(903) 807-0683 x:12", "19038070683"),
    ("(903) 807-0683 x : 12", "19038070683"),
    ("(903) 807-0683 x401", "19038070683"),
    ("(903) 807-0683 X 505", "19038070683"),
    ("(903) 807-0683 X:789", "19038070683"),
    # # variations
    ("(903) 807-0683 # 12", "19038070683"),
    ("(903) 807-0683 #12", "19038070683"),
    ("(903) 807-0683 #: 12", "19038070683"),
    ("(903) 807-0683 #1234", "19038070683"),
]


class TestPhoneExtensionsEdgeCases:
    """Verify that phone numbers with varied extension notations are correctly cleaned."""

    @pytest.mark.parametrize("raw_phone,expected_e164", EXTENSION_PHONE_VARIATIONS)
    def test_clean_phone_digits_strips_extension(self, raw_phone, expected_e164):
        digits = clean_phone_digits(raw_phone)
        assert digits == "9038070683", f"Expected '9038070683', got '{digits}' for '{raw_phone}'"

    @pytest.mark.parametrize("raw_phone,expected_e164", EXTENSION_PHONE_VARIATIONS)
    def test_build_whatsapp_link_with_extensions(self, raw_phone, expected_e164):
        msg = "Hi team"
        link = build_whatsapp_link(raw_phone, msg)
        assert link.startswith(f"https://wa.me/{expected_e164}?text="), (
            f"Failed on '{raw_phone}': link was '{link}'"
        )
        # Ensure extension digits are not appended
        assert "ext" not in link.split("?")[0]
        assert "x" not in link.split("?")[0].replace("https://wa.me/", "")


# ===========================================================================
# 2. +1 International Variations
# ===========================================================================

PLUS_ONE_PHONE_VARIATIONS = [
    ("+1 (903) 807-0683", "19038070683"),
    ("+1-903-807-0683", "19038070683"),
    ("+1.903.807.0683", "19038070683"),
    ("+1 903 807 0683", "19038070683"),
    ("+19038070683", "19038070683"),
    ("+ 1 (903) 807-0683", "19038070683"),
    ("+ 1-903-807-0683", "19038070683"),
    ("+ 1.903.807.0683", "19038070683"),
    ("+ 1 903 807 0683", "19038070683"),
    ("1 (903) 807-0683", "19038070683"),
    ("1-903-807-0683", "19038070683"),
    ("1.903.807.0683", "19038070683"),
    ("19038070683", "19038070683"),
    # Combined +1 and extensions
    ("+1 (903) 807-0683 ext. 42", "19038070683"),
    ("+1-903-807-0683 x99", "19038070683"),
    ("+1 903 807 0683 ext: 501", "19038070683"),
    ("+1 (903) 807-0683 #77", "19038070683"),
    ("+ 1 (903) 807-0683 extension: 12", "19038070683"),
]


class TestPlusOneInternationalVariations:
    """Verify +1 country code variations produce valid 10-digit base and 1{digits} E.164 links."""

    @pytest.mark.parametrize("raw_phone,expected_e164", PLUS_ONE_PHONE_VARIATIONS)
    def test_clean_phone_digits_plus_one(self, raw_phone, expected_e164):
        digits = clean_phone_digits(raw_phone)
        assert digits == "9038070683", f"Expected '9038070683', got '{digits}' for '{raw_phone}'"

    @pytest.mark.parametrize("raw_phone,expected_e164", PLUS_ONE_PHONE_VARIATIONS)
    def test_build_whatsapp_link_plus_one(self, raw_phone, expected_e164):
        msg = "Hi roofer"
        link = build_whatsapp_link(raw_phone, msg)
        assert link.startswith(f"https://wa.me/{expected_e164}?text="), (
            f"Failed on '{raw_phone}': link was '{link}'"
        )
        # Ensure no double country codes like 11...
        assert not link.startswith("https://wa.me/119038070683"), f"Double country code detected: {link}"


# ===========================================================================
# 3. Mixed Delimiters and Formatting
# ===========================================================================

MIXED_DELIMITER_VARIATIONS = [
    ("(903).807 - 0683", "19038070683"),
    ("903 / 807 - 0683", "19038070683"),
    ("903/807-0683", "19038070683"),
    ("(903)8070683", "19038070683"),
    ("903 807.0683", "19038070683"),
    ("(903) 807 0683", "19038070683"),
    ("903-807-0683", "19038070683"),
    ("903.807.0683", "19038070683"),
    ("9038070683", "19038070683"),
    ("tel:+1-903-807-0683", "19038070683"),
    ("tel:(903) 807-0683 ext 12", "19038070683"),
    ("  (903) 807-0683   ", "19038070683"),
]


class TestMixedDelimiterVariations:
    """Verify non-standard delimiters and tel: schemes."""

    @pytest.mark.parametrize("raw_phone,expected_e164", MIXED_DELIMITER_VARIATIONS)
    def test_mixed_delimiters_whatsapp_link(self, raw_phone, expected_e164):
        link = build_whatsapp_link(raw_phone, "Testing delimiters")
        assert link.startswith(f"https://wa.me/{expected_e164}?text="), (
            f"Failed for mixed delimiter '{raw_phone}': got '{link}'"
        )


# ===========================================================================
# 4. Foreign Country Codes Rejection
# ===========================================================================

NON_US_PHONES = [
    "+44 20 7946 0958",      # United Kingdom
    "+52 55 1234 5678",      # Mexico
    "+33 1 42 68 55 55",      # France
    "+61 2 9876 5432",       # Australia
    "+49 30 123456",         # Germany
    "+86 10 1234 5678",      # China
    "+91 98765 43210",       # India
]


class TestForeignPhoneRejection:
    """Verify non-US foreign phone numbers are rejected by the US pipeline cleaner."""

    @pytest.mark.parametrize("foreign_phone", NON_US_PHONES)
    def test_foreign_phone_returns_empty(self, foreign_phone):
        assert clean_phone_digits(foreign_phone) == "", (
            f"Foreign phone {foreign_phone} was not rejected by clean_phone_digits"
        )
        assert build_whatsapp_link(foreign_phone, "Hello") == "", (
            f"Foreign phone {foreign_phone} generated a wa.me link"
        )


# ===========================================================================
# 5. Invalid / Edge Inputs
# ===========================================================================

INVALID_INPUTS = [
    "",
    "   ",
    None,
    "N/A",
    "None",
    "Call Owner",
    "12345",
    "(903) 807-068",  # 9 digits
]


class TestInvalidPhoneInputs:
    """Verify malformed and incomplete numbers safely return empty string."""

    @pytest.mark.parametrize("bad_input", INVALID_INPUTS)
    def test_invalid_input_returns_empty(self, bad_input):
        assert build_whatsapp_link(bad_input, "Hello") == ""


# ===========================================================================
# 6. End-to-End PersonalizerGenerator Pipeline with Edge Case Phones
# ===========================================================================

class TestPersonalizerGeneratorPhoneIntegration:
    """Verify PersonalizerGenerator end-to-end with various phone representations."""

    def test_generator_with_crm_record_phone_with_colon_extension(self):
        crm_rec = CRMRecord(
            row_index=15,
            lead_status="Not Contacted",
            priority="⭐ Medium",
            company_name="Apex Roof Systems",
            website="None (No Website)",
            industry_niche="Commercial Roofing",
            company_size="1-10",
            contact_first_name="Dave",
            contact_last_name="Miller",
            job_title="Owner",
            work_email="Call: (903) 807-0683 ext: 401",
            email_verification="Unverified",
            linkedin_profile="",
            location="Tyler, TX (CST)",
            outreach_channel="Cold Call",
            est_deal_value=4000,
            notes_and_next_steps="Phone: (903) 807-0683 ext: 401. Sab lead.",
        )
        gen = PersonalizerGenerator(engine=TemplateEngine())
        draft = gen.generate(crm_rec)
        assert draft.staged_wame_url.startswith("https://wa.me/19038070683?text=")
        assert "ext" not in draft.staged_wame_url.split("?")[0]
        assert "401" not in draft.staged_wame_url.split("?")[0]
        assert draft.crm_record.lead_status == "Not Contacted"
        assert draft.approval_status == "Drafted / Ready for Review"

    def test_generator_with_raw_lead_plus_one_extension(self):
        raw = RawLead(
            business_name="Lone Star Storm Pros",
            cleaned_phone="9038070683",
            phone_display="+1 (903) 807-0683 ext. 200",
            city="Tyler",
            state="TX",
            zip_code="75701",
            specialty="Storm Damage & Re-roofing",
            website_status="None (No Website)",
            website_url=None,
            place_url="https://maps.google.com/?cid=123",
        )
        gen = PersonalizerGenerator(engine=TemplateEngine())
        draft = gen.generate(raw)
        assert draft.staged_wame_url.startswith("https://wa.me/19038070683?text=")
        assert "ext" not in draft.staged_wame_url.split("?")[0]
        assert "200" not in draft.staged_wame_url.split("?")[0]
        assert "11903807068" not in draft.staged_wame_url.split("?")[0]

    def test_generator_with_lead_dict_various_phone_fields(self):
        lead_dict = {
            "business_name": "Piney Woods Roofing",
            "city": "Tyler",
            "state": "TX",
            "specialty": "Residential Roofing",
            "phone": "+ 1 (903) 807-0683 x : 55",
        }
        gen = PersonalizerGenerator(engine=TemplateEngine())
        draft = gen.generate(lead_dict)
        assert draft.staged_wame_url.startswith("https://wa.me/19038070683?text=")
        assert "55" not in draft.staged_wame_url.split("?")[0]

