"""
Adversarial Stress Test Suite for Milestone 1: Google Maps Extraction Engine.
Conducted by challenger_m1_2.

Objectives tested:
1. Malformed card text (missing rating, 0 reviews, 500+ reviews, missing address, missing phone).
2. Service Area Businesses (SABs) with city/state only: verify MUNICIPAL_CENTROIDS fallback generates valid 5-digit ZIPs.
3. Deduplication stress test: feed 500 duplicate and near-duplicate contractor records (varied casing, punctuation, legal suffixes like LLC, Inc, Corp, PLLC). Verify 100% deduplication precision.
4. Pydantic schema validation: verify RawLead and QualifiedLead reject invalid states, out-of-range star ratings, and non-10-digit phones.
"""

import re
import pytest
from pydantic import ValidationError

from src.models import RawLead, QualifiedLead
from src.scraper.maps_extractor import GoogleMapsExtractor
from src.scraper.normalizer import (
    clean_phone_10digit,
    format_phone_display,
    parse_address,
    classify_specialty,
    normalize_business_name,
    get_dedup_key,
    MUNICIPAL_CENTROIDS,
    STATE_CENTROID_DEFAULTS,
)
from src.scraper.query_catalog import get_all_queries


# ==============================================================================
# Objective 1: Malformed Card Parsing Edge Cases
# ==============================================================================

class TestCardParserEdgeCases:
    """Stress-test GoogleMapsExtractor.parse_card_data with adversarial malformed inputs."""

    def test_missing_rating_does_not_misinterpret_phone_as_reviews(self):
        """
        CRITICAL VULNERABILITY TEST:
        When a card has no rating and 0 reviews, parse_card_data should NOT match
        the area code in '(903) 555-1234' as review_count=903 with '🔥 High' priority.
        """
        card_text = "Ace Roofing\n(903) 555-1234\nTyler, TX"
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            default_city="Tyler",
            default_state="TX",
        )
        assert lead is not None
        assert lead.star_rating == 0.0
        # If this fails, the parser has the area-code-as-review-count bug!
        assert lead.review_count == 0, f"Expected 0 reviews, but got {lead.review_count} (area code matched!)"
        assert lead.priority == "⚡ Medium", f"Expected Medium priority for 0 reviews, but got {lead.priority}"

    def test_zero_reviews_explicit_text(self):
        """Card explicitly stating '0 reviews' or '5.0 (0)'."""
        card1 = "Apex Roofing\n5.0 (0)\n(903) 555-1234\nTyler, TX"
        lead1 = GoogleMapsExtractor.parse_card_data(card1, default_city="Tyler", default_state="TX")
        assert lead1 is not None
        assert lead1.star_rating == 5.0
        assert lead1.review_count == 0
        assert lead1.priority == "⚡ Medium"

        card2 = "Apex Roofing\nNo reviews\n(903) 555-1234\nTyler, TX"
        lead2 = GoogleMapsExtractor.parse_card_data(card2, default_city="Tyler", default_state="TX")
        assert lead2 is not None
        assert lead2.star_rating == 0.0
        assert lead2.review_count == 0
        assert lead2.priority == "⚡ Medium"

    def test_large_review_counts_500_plus(self):
        """Verify 500+ reviews and 1,000+ formatted counts parse accurately as 🔥 High priority."""
        # 500+ formatted
        card1 = "Summit Roofing\n4.8 (500+)\n(903) 555-1234\nTyler, TX"
        lead1 = GoogleMapsExtractor.parse_card_data(card1, default_city="Tyler", default_state="TX")
        assert lead1 is not None
        assert lead1.review_count == 500
        assert lead1.priority == "🔥 High"

        # 1,250 with comma
        card2 = "Summit Roofing\n4.9 (1,250 reviews)\n(903) 555-1234\nTyler, TX"
        lead2 = GoogleMapsExtractor.parse_card_data(card2, default_city="Tyler", default_state="TX")
        assert lead2 is not None
        assert lead2.review_count == 1250
        assert lead2.priority == "🔥 High"

    def test_missing_address_centroid_fallback(self):
        """Card without address line falls back to default city/state centroid ZIP."""
        card = "Lone Star Roofing\n(903) 555-1234\nOpen 24 hours"
        lead = GoogleMapsExtractor.parse_card_data(card, default_city="Tyler", default_state="TX")
        assert lead is not None
        assert lead.city == "Tyler"
        assert lead.state == "TX"
        assert lead.zip_code == "75701"

    def test_missing_phone_graceful_handling(self):
        """Card without phone number extracts cleanly with empty phone strings."""
        card = "Unlisted Phone Roofing\n4.7 (35)\nTyler, TX"
        lead = GoogleMapsExtractor.parse_card_data(card, default_city="Tyler", default_state="TX")
        assert lead is not None
        assert lead.business_name == "Unlisted Phone Roofing"
        assert lead.cleaned_phone == ""
        assert lead.phone_display == ""
        assert lead.review_count == 35


# ==============================================================================
# Objective 2: Service Area Businesses (SABs) & MUNICIPAL_CENTROIDS Fallback
# ==============================================================================

class TestSABMunicipalCentroids:
    """Verify Service Area Business (SAB) centroid fallbacks across target states."""

    def test_all_catalog_target_queries_have_valid_centroids(self):
        """Every single query in query_catalog must resolve to a valid 5-digit ZIP."""
        queries = get_all_queries()
        assert len(queries) >= 30
        for q in queries:
            city, state, zip_code = parse_address("", default_city=q.city, default_state=q.state)
            assert len(zip_code) == 5, f"ZIP for {q.city}, {q.state} is not 5 digits: '{zip_code}'"
            assert zip_code.isdigit(), f"ZIP for {q.city}, {q.state} is not digits: '{zip_code}'"
            assert zip_code != "00000", f"Centroid lookup failed for target city {q.city}, {q.state}"

    def test_sab_city_state_only_variations(self):
        """City/state string variations in card text resolve to proper centroid ZIPs."""
        sab_inputs = [
            ("Tyler, TX", "Tyler", "TX", "75701"),
            ("Ocala, FL", "Ocala", "FL", "34471"),
            ("Canton, OH", "Canton", "OH", "44702"),
            ("Macon, GA", "Macon", "GA", "31201"),
            ("Flagstaff, AZ", "Flagstaff", "AZ", "86001"),
        ]
        for text, expected_city, expected_state, expected_zip in sab_inputs:
            c, s, z = parse_address(text)
            assert c.lower() == expected_city.lower()
            assert s == expected_state
            assert z == expected_zip

    def test_unlisted_city_in_target_state_uses_state_centroid(self):
        """An unlisted rural municipality defaults to the state default centroid ZIP."""
        for state, expected_default in STATE_CENTROID_DEFAULTS.items():
            _, s, z = parse_address("", default_city="RemoteRuralTown", default_state=state)
            assert s == state
            assert z == expected_default
            assert len(z) == 5 and z.isdigit()


# ==============================================================================
# Objective 3: Deduplication Stress Test with 500 Records
# ==============================================================================

class TestDeduplicationStress500:
    """Stress test deduplication precision against 500 duplicate and near-duplicate records."""

    def test_dedup_500_records_with_identical_phone(self):
        """When 10-digit phone number is present, 500 variants must deduplicate to exactly 5 entities."""
        base_names = [
            "Lone Star Roofing", "Summit Ridge Roofing", "Apex Pro Roofing",
            "Everguard Roofing Solutions", "Pinnacle Roof Systems"
        ]
        base_phones = ["9035551001", "9035551002", "9035551003", "9035551004", "9035551005"]
        suffixes = [
            "", " LLC", ", LLC", " - LLC", " Inc.", ", Inc.", " Corp", " Corp.",
            " Corporation", " Co.", " Co", " Ltd", " Ltd.", " Company", " PLLC",
            ", PLLC", " Services", " Solutions", " Contracting", " & Restoration"
        ]
        casings = [str.lower, str.upper, str.title, lambda s: "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(s))]

        unique_keys = set()
        for i in range(500):
            comp_idx = i % 5
            base = base_names[comp_idx]
            phone = base_phones[comp_idx]
            suf = suffixes[i % len(suffixes)]
            case_fn = casings[i % len(casings)]
            var_name = case_fn(f"{base}{suf}")

            lead = RawLead(
                business_name=var_name,
                cleaned_phone=phone,
                phone_display=format_phone_display(phone),
                city="Tyler",
                state="TX",
                zip_code="75701",
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )
            unique_keys.add(lead.dedup_key)

        assert len(unique_keys) == 5, f"Expected 5 unique keys with identical phone, got {len(unique_keys)}"

    def test_dedup_500_records_without_phone_exposes_suffix_vulnerability(self):
        """
        VULNERABILITY CHALLENGE:
        When phone is missing/empty, deduplication relies on business name + state.
        Verify whether RawLead.dedup_key properly strips legal suffixes like LLC, Inc, Corp, PLLC.
        """
        base_names = [
            "Lone Star Roofing", "Summit Ridge Roofing", "Apex Pro Roofing",
            "Everguard Roofing Solutions", "Pinnacle Roof Systems"
        ]
        suffixes = [
            "", " LLC", ", LLC", " - LLC", " Inc.", ", Inc.", " Corp", " Corp.",
            " Corporation", " Co.", " Co", " Ltd", " Ltd.", " Company", " PLLC",
            ", PLLC", " Services", " Solutions", " Contracting", " & Restoration"
        ]
        casings = [str.lower, str.upper, str.title]

        rawlead_keys = set()
        for i in range(500):
            comp_idx = i % 5
            base = base_names[comp_idx]
            suf = suffixes[i % len(suffixes)]
            case_fn = casings[i % len(casings)]
            var_name = case_fn(f"{base}{suf}")

            lead = RawLead(
                business_name=var_name,
                cleaned_phone="",
                phone_display="",
                city="Tyler",
                state="TX",
                zip_code="75701",
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )
            rawlead_keys.add(lead.dedup_key)

        # RawLead.dedup_key fails because it does not strip legal suffixes
        assert len(rawlead_keys) == 5, (
            f"VULNERABILITY CONFIRMED: RawLead.dedup_key produced {len(rawlead_keys)} unique keys "
            f"for 5 businesses across 500 variants! Legal suffixes (LLC, Inc, Corp, PLLC) were not normalized."
        )

    def test_normalizer_pllc_suffix_omission(self):
        """
        VULNERABILITY CHALLENGE:
        Verify whether normalizer.normalize_business_name strips 'PLLC' (Professional Limited Liability Company).
        """
        base_clean = normalize_business_name("Summit Ridge Roofing")
        llc_clean = normalize_business_name("Summit Ridge Roofing LLC")
        pllc_clean = normalize_business_name("Summit Ridge Roofing PLLC")

        assert base_clean == llc_clean, "normalize_business_name failed to strip LLC"
        # If this fails, PLLC is missing from the normalizer regex!
        assert base_clean == pllc_clean, (
            f"VULNERABILITY CONFIRMED: normalize_business_name failed on 'PLLC'! "
            f"base='{base_clean}', pllc='{pllc_clean}'"
        )


# ==============================================================================
# Objective 4: Pydantic Schema Validation Boundaries
# ==============================================================================

class TestPydanticSchemaValidation:
    """Stress-test RawLead and QualifiedLead schema validation contracts."""

    def test_invalid_states_rejected(self):
        """
        VULNERABILITY CHALLENGE:
        RawLead must reject non-existent or invalid US state codes (e.g. 'XX', 'ZZ', 'INVALID', '12', '').
        """
        invalid_states = ["XX", "ZZ", "INVALID", "12", "", "CANADA", "FOOBAR"]
        for st in invalid_states:
            with pytest.raises(ValidationError, match="state"):
                RawLead(
                    business_name="Test Roofing",
                    cleaned_phone="9038070683",
                    phone_display="(903) 807-0683",
                    city="Tyler",
                    state=st,
                    zip_code="75701",
                    specialty="Residential Roofing",
                    website_status="None (No Website)",
                )

    def test_out_of_range_star_ratings_rejected(self):
        """Verify star ratings outside 0.0 to 5.0 are rejected."""
        out_of_range = [-1.0, -0.01, 5.01, 10.0]
        for rating in out_of_range:
            with pytest.raises(ValidationError):
                RawLead(
                    business_name="Test Roofing",
                    cleaned_phone="9038070683",
                    phone_display="(903) 807-0683",
                    city="Tyler",
                    state="TX",
                    zip_code="75701",
                    star_rating=rating,
                    specialty="Residential Roofing",
                    website_status="None (No Website)",
                )

    def test_non_10_digit_cleaned_phones_rejected(self):
        """
        VULNERABILITY CHALLENGE:
        RawLead specifies cleaned_phone as '10-digit normalized phone number (digits only)'.
        Verify whether invalid non-10-digit phone strings are rejected by Pydantic.
        """
        invalid_phones = ["123", "12345678901", "903-807-0683", "abcdefghij", "555-HOME"]
        for ph in invalid_phones:
            with pytest.raises(ValidationError, match="phone"):
                RawLead(
                    business_name="Test Roofing",
                    cleaned_phone=ph,
                    phone_display=ph,
                    city="Tyler",
                    state="TX",
                    zip_code="75701",
                    specialty="Residential Roofing",
                    website_status="None (No Website)",
                )
