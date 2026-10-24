"""
Unit and Extraction Tests for Milestone 1: Google Maps Extraction Engine.

Covers:
- Pydantic models (RawLead, QualifiedLead, CRMRecord, OutreachDraft)
- Configuration & Chrome path resolution
- Website filtering & custom domain exclusion
- Phone number normalization & display formatting
- Address parsing & municipal centroid fallbacks for SABs
- Trade specialty classification
- Query catalog coverage across TX, FL, OH, GA, AZ
- Card DOM parsing, priority scoring, and deduplication
- Browser manager anti-bot flags and lifecycle
- Offline dataset verification of 25+ real leads
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.models import RawLead, QualifiedLead, CRMRecord, OutreachDraft
from src.config import (
    DEFAULT_BROWSER_ARGS,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
    TARGET_STATES,
    HIGH_PRIORITY_REVIEW_THRESHOLD,
    DAILY_SEND_CAP,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    SHEET_ID,
    START_ROW,
    get_chrome_executable,
)
from src.scraper.filters import (
    clean_url_scheme,
    extract_domain,
    is_no_website,
    is_social_or_directory,
    is_custom_domain,
    is_qualified_lead_website,
    classify_website,
    SOCIAL_AND_DIRECTORIES,
)
from src.scraper.normalizer import (
    clean_phone_10digit,
    format_phone_display,
    parse_address,
    classify_specialty,
    classify_specialty_key,
    normalize_business_name,
    get_dedup_key,
    MUNICIPAL_CENTROIDS,
)
from src.scraper.query_catalog import (
    TargetQuery,
    TARGET_QUERIES,
    get_all_queries,
    get_queries_by_state,
    get_default_query_catalog,
)
from src.scraper.browser_manager import BrowserManager
from src.scraper.maps_extractor import GoogleMapsExtractor


# ============================================================================
# 1. Pydantic Models & Interface Contracts
# ============================================================================

class TestModels:
    def test_raw_lead_valid_creation(self):
        lead = RawLead(
            business_name="General Roofing & Restoration",
            cleaned_phone="9038070683",
            phone_display="(903) 807-0683",
            city="Tyler",
            state="TX",
            zip_code="75701",
            review_count=13,
            star_rating=5.0,
            specialty="Storm Damage & Re-roofing",
            website_status="None (No Website)",
            website_url=None,
            place_url="https://www.google.com/maps/place/sample",
        )
        assert lead.business_name == "General Roofing & Restoration"
        assert lead.cleaned_phone == "9038070683"
        assert lead.phone_display == "(903) 807-0683"
        assert lead.dedup_key == "9038070683"
        assert lead.is_high_priority is True

    def test_raw_lead_dedup_key_fallback(self):
        lead = RawLead(
            business_name="Apex Roofers LLC",
            cleaned_phone="",
            phone_display="",
            city="Tyler",
            state="TX",
            zip_code="75701",
            review_count=3,
            star_rating=4.5,
            specialty="Residential Roofing",
            website_status="None (No Website)",
            place_url="",
        )
        assert lead.dedup_key == "apexroofers_TX"
        assert lead.is_high_priority is False

    def test_raw_lead_state_normalization(self):
        lead = RawLead(
            business_name="Lone Star Roofing",
            cleaned_phone="9035551234",
            phone_display="(903) 555-1234",
            city="Tyler",
            state="Texas",
            zip_code="75701",
            review_count=8,
            star_rating=4.7,
            specialty="Residential Roofing",
            website_status="None (No Website)",
        )
        assert lead.state == "TX"

    def test_qualified_lead_from_raw(self):
        raw = RawLead(
            business_name="El Sol Roofing",
            cleaned_phone="9033439074",
            phone_display="(903) 343-9074",
            city="Tyler",
            state="TX",
            zip_code="75701",
            review_count=27,
            star_rating=5.0,
            specialty="Residential Roofing",
            website_status="None (No Website - Social Only)",
            website_url="https://www.tiktok.com/@elsolroofing",
            place_url="https://maps.google.com/?cid=123",
        )
        qualified = QualifiedLead.from_raw(raw, search_query="roofing contractors Tyler TX")
        assert qualified.priority == "🔥 High"
        assert qualified.search_query == "roofing contractors Tyler TX"
        assert qualified.business_name == "El Sol Roofing"

    def test_crm_record_model_validation(self):
        record = CRMRecord(
            row_index=14,
            lead_status="Not Contacted",
            priority="🔥 High",
            company_name="General Roofing & Restoration",
            website="None (No Website)",
            industry_niche="Storm Damage & Re-roofing",
            company_size="1-10",
            contact_first_name="Roofing Team",
            contact_last_name="Contractor",
            job_title="Owner / Contractor",
            work_email="Call: (903) 807-0683",
            email_verification="Unverified",
            linkedin_profile="https://maps.google.com/test",
            location="Tyler, TX (CST)",
            outreach_channel="Cold Email",
            est_deal_value=4000,
            notes_and_next_steps="Phone: (903) 807-0683",
        )
        assert record.row_index == 14
        assert record.priority == "🔥 High"

    def test_crm_record_invalid_row_index(self):
        with pytest.raises(ValidationError):
            CRMRecord(
                row_index=10,  # Row index must be >= 14
                lead_status="Not Contacted",
                company_name="Test Co",
                industry_niche="Residential Roofing",
                work_email="test@example.com",
                location="Tyler, TX (CST)",
            )

    def test_outreach_draft_model(self):
        record = CRMRecord(
            row_index=14,
            lead_status="Not Contacted",
            priority="🔥 High",
            company_name="General Roofing",
            industry_niche="Storm Damage & Re-roofing",
            work_email="Call: (903) 807-0683",
            location="Tyler, TX (CST)",
        )
        draft = OutreachDraft(
            crm_record=record,
            icebreaker="Noticed your 5.0 star reputation in Tyler, TX.",
            offer_angle="Local competitors are capturing emergency roof repair search volume.",
            staged_email_subject="Quick question regarding Tyler roofing jobs",
            staged_email_body="Hi team,\n\nWe saw your great reviews...",
            staged_whatsapp_msg="Hi General Roofing, saw your reviews in Tyler...",
            staged_wame_url="https://wa.me/19038070683?text=Hi",
        )
        assert draft.approval_status == "Drafted / Ready for Review"
        assert "Tyler" in draft.icebreaker


# ============================================================================
# 2. Configuration Settings
# ============================================================================

class TestConfig:
    def test_config_paths_and_defaults(self):
        assert len(TARGET_STATES) == 5
        assert set(TARGET_STATES) == {"TX", "FL", "OH", "GA", "AZ"}
        assert HIGH_PRIORITY_REVIEW_THRESHOLD == 10
        assert DAILY_SEND_CAP == 25
        assert MIN_DELAY_SECONDS == 45
        assert MAX_DELAY_SECONDS == 180
        assert SHEET_ID == "12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY"
        assert START_ROW == 14

    def test_browser_arguments(self):
        assert "--no-sandbox" in DEFAULT_BROWSER_ARGS
        assert "--disable-blink-features=AutomationControlled" in DEFAULT_BROWSER_ARGS
        assert "--lang=en-US,en" in DEFAULT_BROWSER_ARGS
        assert "Mozilla" in DEFAULT_USER_AGENT
        assert DEFAULT_VIEWPORT["width"] == 1280
        assert DEFAULT_VIEWPORT["height"] == 900

    def test_chrome_executable_resolution(self):
        exe = get_chrome_executable()
        # On this system, Chrome is located at %LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
        assert exe is not None
        assert Path(exe).exists()
        assert "chrome.exe" in exe.lower() or "msedge.exe" in exe.lower()


# ============================================================================
# 3. Website Filters & Custom Domain Exclusion
# ============================================================================

class TestWebsiteFilters:
    @pytest.mark.parametrize("empty_val", [None, "", "   ", "none", "None", "N/A", "Add website"])
    def test_is_no_website(self, empty_val):
        assert is_no_website(empty_val) is True

    @pytest.mark.parametrize(
        "custom_url,domain",
        [
            ("https://hartmanroofinglubbock.com", "hartmanroofinglubbock.com"),
            ("http://www.gorooftech.com/services", "gorooftech.com"),
            ("https://kincaidroofing.net", "kincaidroofing.net"),
            ("https://austin-roofs.io", "austin-roofs.io"),
            ("https://dallascommercialroofing.co", "dallascommercialroofing.co"),
            ("https://ohioroofrepair.biz", "ohioroofrepair.biz"),
            ("https://floridaemergencyroofs.org", "floridaemergencyroofs.org"),
            ("www.azroofpro.us", "azroofpro.us"),
        ],
    )
    def test_custom_domains_strictly_excluded(self, custom_url, domain):
        assert is_no_website(custom_url) is False
        assert is_social_or_directory(custom_url) is False
        assert is_custom_domain(custom_url) is True
        assert is_qualified_lead_website(custom_url) is False

        is_qual, status, _ = classify_website(custom_url)
        assert is_qual is False
        assert status == f"Custom Website ({domain})"

    @pytest.mark.parametrize(
        "social_url,expected_status",
        [
            ("https://www.facebook.com/simmonsroofinginc/?ref=bookmarks", "None (No Website - Social Only)"),
            ("http://m.facebook.com/profile.php?id=123", "None (No Website - Social Only)"),
            ("https://www.instagram.com/canton_roofing/", "None (No Website - Social Only)"),
            ("https://www.tiktok.com/@elsolroofing", "None (No Website - Social Only)"),
            ("https://www.yelp.com/biz/high-elevation-roofing-flagstaff", "None (No Website - Social Only)"),
            ("https://www.bbb.org/us/tx/tyler/profile/roofing/sample", "None (No Website - Social Only)"),
            ("https://www.yellowpages.com/ocala-fl/mip/sample-roofing", "None (No Website - Social Only)"),
            ("https://www.angi.com/companylist/us/ga/macon/roofing.htm", "None (No Website - Social Only)"),
            ("https://nextdoor.com/pages/smith-roofing-canton-oh/", "None (No Website - Social Only)"),
            ("https://www.houzz.com/professionals/roofing/sample", "None (No Website - Social Only)"),
            ("https://www.manta.com/c/sample/fl-roofing", "None (No Website - Social Only)"),
            ("https://www.bark.com/en/us/company/sample/", "None (No Website - Social Only)"),
            ("https://sample.business.site", "None (No Website - Social Only)"),
        ],
    )
    def test_social_and_directory_platforms_qualified(self, social_url, expected_status):
        assert is_social_or_directory(social_url) is True
        assert is_custom_domain(social_url) is False
        assert is_qualified_lead_website(social_url) is True

        is_qual, status, url = classify_website(social_url)
        assert is_qual is True
        assert status == expected_status
        assert url == social_url

    def test_no_website_classification(self):
        is_qual, status, url = classify_website(None)
        assert is_qual is True
        assert status == "None (No Website)"
        assert url is None

        is_qual, status, url = classify_website("")
        assert is_qual is True
        assert status == "None (No Website)"
        assert url is None


# ============================================================================
# 4. Normalization (Phone, Address, Specialty, Dedup Key)
# ============================================================================

class TestNormalizer:
    @pytest.mark.parametrize(
        "raw_phone,expected_10",
        [
            ("(903) 807-0683", "9038070683"),
            ("903-807-0683", "9038070683"),
            ("903.807.0683", "9038070683"),
            ("+1 (903) 807-0683", "9038070683"),
            ("+19038070683", "9038070683"),
            ("1-903-807-0683", "9038070683"),
            ("903 807 0683", "9038070683"),
            ("9038070683", "9038070683"),
            ("(234) 360-6842", "2343606842"),
            ("(928) 522-3531", "9285223531"),
        ],
    )
    def test_clean_phone_10digit(self, raw_phone, expected_10):
        assert clean_phone_10digit(raw_phone) == expected_10

    @pytest.mark.parametrize("invalid_phone", [None, "", "123", "555-123", "abcdefghij", "+44 20 7946 0958"])
    def test_clean_phone_invalid_inputs(self, invalid_phone):
        assert clean_phone_10digit(invalid_phone) is None

    def test_format_phone_display(self):
        assert format_phone_display("9038070683") == "(903) 807-0683"
        assert format_phone_display("+1-903-807-0683") == "(903) 807-0683"
        assert format_phone_display(None) == ""

    def test_parse_address_with_full_street_and_zip(self):
        addr = "7922 S Broadway Ave, Tyler, TX 75703, United States"
        city, state, zip_code = parse_address(addr, default_city="Tyler", default_state="TX")
        assert city == "Tyler"
        assert state == "TX"
        assert zip_code == "75703"

    @pytest.mark.parametrize(
        "target_city,target_state,expected_zip",
        [
            ("Tyler", "TX", "75701"),
            ("Longview", "TX", "75601"),
            ("Ocala", "FL", "34471"),
            ("Gainesville", "FL", "32601"),
            ("Canton", "OH", "44702"),
            ("Akron", "OH", "44308"),
            ("Macon", "GA", "31201"),
            ("Warner Robins", "GA", "31088"),
            ("Flagstaff", "AZ", "86001"),
            ("Prescott", "AZ", "86301"),
        ],
    )
    def test_parse_address_service_area_business_centroid_fallbacks(self, target_city, target_state, expected_zip):
        # Service Area Businesses show only city and state with no street or ZIP
        sab_addr = f"{target_city}, {target_state}"
        city, state, zip_code = parse_address(sab_addr, default_city=target_city, default_state=target_state)
        assert city.lower() == target_city.lower()
        assert state == target_state
        assert zip_code == expected_zip

    def test_parse_address_empty_string_centroid_fallback(self):
        city, state, zip_code = parse_address("", default_city="Tyler", default_state="TX")
        assert city == "Tyler"
        assert state == "TX"
        assert zip_code == "75701"

    @pytest.mark.parametrize(
        "name,card_text,expected_key,expected_specialty",
        [
            ("General Roofing & Restoration", "Storm and hail damage repairs in East TX", "storm repair", "Storm Damage & Re-roofing"),
            ("Apex Commercial Roofing", "Specializing in TPO and flat roof systems", "commercial", "Commercial Roofing"),
            ("Emergency Roof Leak Pros", "24/7 emergency leak repair and waterproofing", "leak repair", "Emergency Leak Repair"),
            ("East Texas Roofing Services", "Complete residential shingle replacement", "residential", "Residential Roofing"),
            ("Hill Country Re-roofing", "Insurance claim restoration specialists", "storm repair", "Storm Damage & Re-roofing"),
        ],
    )
    def test_classify_specialty(self, name, card_text, expected_key, expected_specialty):
        assert classify_specialty_key(name, card_text) == expected_key
        assert classify_specialty(name, card_text) == expected_specialty

    def test_normalize_business_name(self):
        assert normalize_business_name("General Roofing & Restoration, LLC") == "general"
        assert normalize_business_name("Dyer Restoration Solutions Inc.") == "dyer"
        assert normalize_business_name("High Elevation Roofing Co.") == "highelevation"

    def test_get_dedup_key(self):
        assert get_dedup_key("9038070683", "General Roofing", "TX") == "9038070683"
        assert get_dedup_key(None, "High Elevation Roofing Co.", "AZ") == "highelevation_AZ"


# ============================================================================
# 5. Query Catalog
# ============================================================================

class TestQueryCatalog:
    def test_query_catalog_states_coverage(self):
        all_q = get_all_queries()
        assert len(all_q) >= 25
        states_in_catalog = {q.state for q in all_q}
        assert set(TARGET_STATES) == states_in_catalog

    def test_queries_by_state(self):
        tx_queries = get_queries_by_state("TX")
        assert len(tx_queries) >= 5
        assert all(q.state == "TX" for q in tx_queries)

    def test_default_query_catalog(self):
        default_q = get_default_query_catalog()
        assert len(default_q) == 5
        states = [q.state for q in default_q]
        assert set(states) == {"TX", "FL", "OH", "GA", "AZ"}


# ============================================================================
# 6. Google Maps Card Parser & Extractor Engine
# ============================================================================

class TestGoogleMapsExtractor:
    def test_parse_card_data_qualified_no_website(self):
        card_text = (
            "General Roofing & Restoration\n"
            "5.0 (13) · Roofing contractor\n"
            "Tyler, TX\n"
            "(903) 807-0683\n"
            "Storm damage repair and insurance restoration specialists"
        )
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="General Roofing & Restoration",
            website_href=None,
            place_href="https://www.google.com/maps/place/General+Roofing",
            default_city="Tyler",
            default_state="TX",
            search_query="roofing contractors Tyler TX",
        )
        assert lead is not None
        assert lead.business_name == "General Roofing & Restoration"
        assert lead.cleaned_phone == "9038070683"
        assert lead.phone_display == "(903) 807-0683"
        assert lead.city == "Tyler"
        assert lead.state == "TX"
        assert lead.zip_code == "75701"
        assert lead.star_rating == 5.0
        assert lead.review_count == 13
        assert lead.specialty == "Storm Damage & Re-roofing"
        assert lead.website_status == "None (No Website)"
        assert lead.website_url is None
        assert lead.priority == "🔥 High"

    def test_parse_card_data_qualified_social_profile(self):
        card_text = (
            "El Sol Roofing\n"
            "5.0 (27) · Roofing contractor\n"
            "Tyler, TX\n"
            "(903) 343-9074\n"
            "Residential shingle repairs"
        )
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="El Sol Roofing",
            website_href="https://www.tiktok.com/@elsolroofing",
            place_href="https://www.google.com/maps/place/El+Sol",
            default_city="Tyler",
            default_state="TX",
        )
        assert lead is not None
        assert lead.business_name == "El Sol Roofing"
        assert lead.website_status == "None (No Website - Social Only)"
        assert lead.website_url == "https://www.tiktok.com/@elsolroofing"
        assert lead.priority == "🔥 High"

    def test_parse_card_data_disqualifies_custom_domain(self):
        card_text = (
            "Hartman Roofing Lubbock\n"
            "4.9 (88) · Roofing contractor\n"
            "Lubbock, TX\n"
            "(806) 794-5555"
        )
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Hartman Roofing Lubbock",
            website_href="https://hartmanroofinglubbock.com",
            place_href="https://www.google.com/maps/place/Hartman",
            default_city="Lubbock",
            default_state="TX",
        )
        assert lead is None

    def test_parse_card_data_low_review_count_priority(self):
        card_text = (
            "Neighborhood Roof Patch\n"
            "4.5 (4) · Roofing contractor\n"
            "Ocala, FL\n"
            "(352) 555-0199"
        )
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Neighborhood Roof Patch",
            website_href=None,
            place_href="",
            default_city="Ocala",
            default_state="FL",
        )
        assert lead is not None
        assert lead.review_count == 4
        assert lead.priority == "⚡ Medium"

    def test_browser_manager_configuration(self):
        mgr = BrowserManager(headless=True)
        assert mgr.headless is True
        assert "--no-sandbox" in mgr.args
        assert "--disable-blink-features=AutomationControlled" in mgr.args
        assert mgr.executable_path is not None


# ============================================================================
# 7. Verification Against Technical Survey Verified Sample Dataset
# ============================================================================

class TestVerifiedSurveyDataset:
    def test_survey_leads_sample_integrity(self):
        """
        Verify that all 25 leads gathered during the technical survey in
        explorer_survey_1/verified_leads_sample.json satisfy all R1 criteria.
        """
        sample_path = (
            Path(__file__).resolve().parent.parent.parent
            / ".agents"
            / "teamwork"
            / "explorer_survey_1"
            / "verified_leads_sample.json"
        )
        assert sample_path.exists(), f"Survey sample dataset missing at {sample_path}"

        with open(sample_path, "r", encoding="utf-8") as f:
            sample_leads = json.load(f)

        assert len(sample_leads) >= 25, f"Expected >= 25 leads, got {len(sample_leads)}"

        # Validate that each sample entry transforms into valid RawLead and QualifiedLead
        qualified_leads = []
        high_priority_count = 0
        seen_dedup = set()

        for item in sample_leads:
            # Confirm no custom domains
            web_status = item.get("website_status", "")
            assert "Custom Website" not in web_status
            assert not any(web_status.endswith(ext) for ext in [".com", ".net", ".org", ".io", ".co"])

            phone_clean = clean_phone_10digit(item.get("phone")) or ""
            phone_disp = format_phone_display(phone_clean or item.get("phone"))

            city, state, zip_code = parse_address(
                item.get("city") + ", " + item.get("state"),
                default_city=item.get("city"),
                default_state=item.get("state"),
            )

            raw = RawLead(
                business_name=item["company_name"],
                cleaned_phone=phone_clean,
                phone_display=phone_disp,
                city=city,
                state=state,
                zip_code=zip_code,
                review_count=item.get("review_count", 0),
                star_rating=item.get("star_rating") or 0.0,
                specialty=classify_specialty(item["company_name"], item.get("primary_specialty", "")),
                website_status=(
                    "None (No Website - Social Only)"
                    if "Social" in web_status
                    else "None (No Website)"
                ),
                website_url=item.get("search_query") if "Social" in web_status else None,
                place_url="",
            )
            q_lead = QualifiedLead.from_raw(raw, search_query=item.get("search_query"))
            qualified_leads.append(q_lead)

            d_key = q_lead.dedup_key
            assert d_key not in seen_dedup, f"Duplicate lead found: {d_key}"
            seen_dedup.add(d_key)

            if q_lead.is_high_priority:
                high_priority_count += 1

        assert len(qualified_leads) >= 25
        # Technical survey observed >= 10 high priority leads (>10 reviews without a website)
        assert high_priority_count >= 10


# ============================================================================
# 8. Boundary Conditions & Extraction Mocking
# ============================================================================

class TestEdgeCasesAndMockScraper:
    def test_raw_lead_validation_boundaries(self):
        # Star rating > 5.0
        with pytest.raises(ValidationError):
            RawLead(
                business_name="Overrated Roofers",
                cleaned_phone="9038070683",
                phone_display="(903) 807-0683",
                city="Tyler",
                state="TX",
                zip_code="75701",
                review_count=10,
                star_rating=5.5,
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )

        # Star rating < 0.0
        with pytest.raises(ValidationError):
            RawLead(
                business_name="Negative Rating",
                cleaned_phone="9038070683",
                phone_display="(903) 807-0683",
                city="Tyler",
                state="TX",
                zip_code="75701",
                review_count=10,
                star_rating=-1.0,
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )

        # Negative review count
        with pytest.raises(ValidationError):
            RawLead(
                business_name="Negative Reviews",
                cleaned_phone="9038070683",
                phone_display="(903) 807-0683",
                city="Tyler",
                state="TX",
                zip_code="75701",
                review_count=-5,
                star_rating=4.0,
                specialty="Residential Roofing",
                website_status="None (No Website)",
            )

    def test_clean_url_schemes(self):
        assert clean_url_scheme("facebook.com") == "https://facebook.com"
        assert clean_url_scheme("//instagram.com/sample") == "https://instagram.com/sample"
        assert clean_url_scheme("http://yelp.com") == "http://yelp.com"
        assert clean_url_scheme("https://angi.com") == "https://angi.com"

    def test_parse_card_data_empty_name(self):
        lead = GoogleMapsExtractor.parse_card_data(
            card_text="",
            anchor_aria_label="",
            website_href=None,
        )
        assert lead is None

    def test_parse_card_data_no_phone_graceful(self):
        card_text = "Silent Roofers\n4.5 (8) · Roofing contractor\nMacon, GA"
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Silent Roofers",
            website_href=None,
            default_city="Macon",
            default_state="GA",
        )
        assert lead is not None
        assert lead.cleaned_phone == ""
        assert lead.phone_display == ""
        assert lead.city == "Macon"
        assert lead.state == "GA"
        assert lead.zip_code == "31201"

    def test_parse_card_data_large_review_count(self):
        card_text = (
            "Flagstaff Master Roofers\n"
            "4.9 (1,450) · Roofing contractor\n"
            "Flagstaff, AZ\n"
            "(928) 555-9988\n"
            "Specializing in metal and storm roof restoration"
        )
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Flagstaff Master Roofers",
            website_href=None,
            default_city="Flagstaff",
            default_state="AZ",
        )
        assert lead is not None
        assert lead.review_count == 1450
        assert lead.star_rating == 4.9
        assert lead.priority == "🔥 High"
        assert lead.specialty == "Storm Damage & Re-roofing"

    def test_extract_multi_queries_deduplication(self, monkeypatch):
        extractor = GoogleMapsExtractor()

        lead1 = QualifiedLead(
            business_name="Twin City Roofing",
            cleaned_phone="9038071111",
            phone_display="(903) 807-1111",
            city="Tyler",
            state="TX",
            zip_code="75701",
            review_count=15,
            star_rating=5.0,
            specialty="Storm Damage & Re-roofing",
            website_status="None (No Website)",
            priority="🔥 High",
        )
        lead2 = QualifiedLead(
            business_name="Twin City Roofing",
            cleaned_phone="9038071111",
            phone_display="(903) 807-1111",
            city="Tyler",
            state="TX",
            zip_code="75701",
            review_count=15,
            star_rating=5.0,
            specialty="Storm Damage & Re-roofing",
            website_status="None (No Website)",
            priority="🔥 High",
        )
        lead3 = QualifiedLead(
            business_name="Piney Woods Roofing",
            cleaned_phone="9038072222",
            phone_display="(903) 807-2222",
            city="Longview",
            state="TX",
            zip_code="75601",
            review_count=5,
            star_rating=4.5,
            specialty="Residential Roofing",
            website_status="None (No Website)",
            priority="⚡ Medium",
        )

        call_count = 0
        def mock_extract_for_query(target, max_scrolls=4, page=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [lead1]
            else:
                return [lead2, lead3]

        monkeypatch.setattr(extractor, "extract_for_query", mock_extract_for_query)

        # Mock browser manager to avoid real browser launch in unit test
        class DummyContext:
            def new_page(self): return "dummy_page"
            def close(self): pass
        class DummyBM:
            def start(self): return DummyContext()
            def new_page(self): return "dummy_page"
            def close(self): pass

        extractor.browser_manager = DummyBM()

        queries = [
            TargetQuery(query="q1", city="Tyler", state="TX", default_zip="75701"),
            TargetQuery(query="q2", city="Longview", state="TX", default_zip="75601"),
        ]

        results = extractor.extract_multi_queries(queries, target_count=10)
        assert len(results) == 2  # lead2 is deduplicated with lead1
        assert results[0].cleaned_phone == "9038071111"
        assert results[1].cleaned_phone == "9038072222"

    def test_browser_manager_context_manager(self):
        # Test BrowserManager starts and closes cleanly using context manager
        with BrowserManager(headless=True) as bm:
            assert bm._context is not None
            assert bm._browser is not None
            page = bm.new_page()
            assert page is not None
            page.close()
        # After exit, context and browser are cleaned up
        assert bm._context is None
        assert bm._browser is None

