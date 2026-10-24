"""
Adversarial and Empirical Stress-Testing Suite for Milestone 1: Google Maps Extraction Engine.

Author: challenger_m1_1 (Empirical Challenger)
Target: src/scraper/filters.py, src/scraper/normalizer.py, src/scraper/maps_extractor.py

Covers:
1. Website Filtering (src/scraper/filters.py):
   - Diverse custom domains (.com, .io, .net, .co, .org, .biz, .us, .roofing, .contractors, uppercase, paths, query params, port numbers, IP addresses)
   - Deceptive social URLs (fake subdomains, phishing domains, userinfo, path tricks)
   - Valid social directories (all 44 entries in SOCIAL_AND_DIRECTORIES)
   - Social wrapper redirectors (Google, Facebook, YouTube, LinkedIn)
   - Edge case inputs (malformed schemes, javascript:void(0), about:blank, tel:, mailto:)

2. Phone Normalization (src/scraper/normalizer.py):
   - Valid standard US formats
   - Varied formats (slashes, excessive spacing, tel: URI)
   - Extensions (ext, x, extension, #)
   - Vanity letters in numbers (1-800-ROOF-PRO)
   - International country codes (+52 Mexico, +44 UK, +49 Germany, etc.)
   - 7-digit local numbers
   - 11-digit numbers without leading 1
   - Invalid area codes violating North American Numbering Plan (0xx, 1xx)

3. Card Parser Integration (src/scraper/maps_extractor.py):
   - End-to-end extraction behavior under adversarial inputs
"""

import pytest
from src.scraper.filters import (
    classify_website,
    clean_url_scheme,
    extract_domain,
    is_custom_domain,
    is_no_website,
    is_qualified_lead_website,
    is_social_or_directory,
    SOCIAL_AND_DIRECTORIES,
)
from src.scraper.normalizer import (
    clean_phone_10digit,
    format_phone_display,
    normalize_business_name,
    get_dedup_key,
    parse_address,
)
from src.scraper.maps_extractor import GoogleMapsExtractor


# ============================================================================
# Section 1: Website Filtering Adversarial Stress-Tests
# ============================================================================

class TestWebsiteFilteringAdversarial:
    """Adversarial stress-testing of website qualification and domain extraction."""

    # 1.1 Diverse Custom Domains (Lowercase / Standard Schemes)
    @pytest.mark.parametrize(
        "custom_url,expected_domain",
        [
            ("http://lone-star-roofing.com", "lone-star-roofing.com"),
            ("https://austin-roofs.io", "austin-roofs.io"),
            ("https://kincaidroofing.net", "kincaidroofing.net"),
            ("https://dallascommercialroofing.co", "dallascommercialroofing.co"),
            ("https://floridaemergencyroofs.org", "floridaemergencyroofs.org"),
            ("http://ohioroofrepair.biz", "ohioroofrepair.biz"),
            ("https://azroofpro.us", "azroofpro.us"),
            ("https://superior.roofing", "superior.roofing"),
            ("https://dfw.contractors", "dfw.contractors"),
            ("https://midlandroofs.build", "midlandroofs.build"),
            ("https://lonestar.construction", "lonestar.construction"),
            ("https://fixmyroof.repair", "fixmyroof.repair"),
            ("https://pro-roofing.services", "pro-roofing.services"),
            ("https://elite-solutions.solutions", "elite-solutions.solutions"),
            ("https://budget-roofs.xyz", "budget-roofs.xyz"),
            ("https://tyler-roofing.online", "tyler-roofing.online"),
            ("https://coolroofs.site", "coolroofs.site"),
            ("roofing.com", "roofing.com"),
            ("https://roofing.com/residential/flint-tx", "roofing.com"),
            ("https://roofing.com?ref=maps&source=google", "roofing.com"),
            ("http://roofing.com:8080/index.html", "roofing.com"),
            ("https://roofing.com:443/portal", "roofing.com"),
            ("http://192.168.1.50", "192.168.1.50"),
            ("http://10.0.0.1:8000/dashboard", "10.0.0.1"),
            ("http://[2001:db8::1]", "2001:db8::1"),
            ("residential.apexroofing.com", "residential.apexroofing.com"),
            ("https://roofing.co.uk", "roofing.co.uk"),
            ("https://roofing.com.mx", "roofing.com.mx"),
            ("https://roofing.us.com", "roofing.us.com"),
        ],
    )
    def test_custom_domains_are_strictly_disqualified(self, custom_url, expected_domain):
        """All variations of active custom domains must be rejected from outreach."""
        assert is_custom_domain(custom_url) is True
        assert is_qualified_lead_website(custom_url) is False

        is_qual, status, url = classify_website(custom_url)
        assert is_qual is False
        assert status == f"Custom Website ({expected_domain})"
        assert url == custom_url.strip()

    # 1.2 Deceptive Social URLs (Subdomain spoofing, phishing, userinfo, path tricks)
    @pytest.mark.parametrize(
        "deceptive_url,expected_extracted_domain",
        [
            ("https://facebook.com.attacker.com", "facebook.com.attacker.com"),
            ("https://facebook.com.roofingcompany.com", "facebook.com.roofingcompany.com"),
            ("https://facebook.com-login.com", "facebook.com-login.com"),
            ("https://facebook.com.fake.org/profile", "facebook.com.fake.org"),
            ("https://facebook.co", "facebook.co"),
            ("https://facebook.org", "facebook.org"),
            ("https://facebook-profile.net", "facebook-profile.net"),
            ("https://m-facebook.com", "m-facebook.com"),
            ("https://yelp.com.phish.biz", "yelp.com.phish.biz"),
            ("https://bbb.org.malicious.com", "bbb.org.malicious.com"),
            ("https://instagram.com.scam.io", "instagram.com.scam.io"),
            ("https://angi.com.evil.co", "angi.com.evil.co"),
            ("https://tiktok.com.hacker.com", "tiktok.com.hacker.com"),
            ("https://evil.com/facebook.com", "evil.com"),
            ("https://evil.com?target=facebook.com", "evil.com"),
            ("https://evil.com#facebook.com", "evil.com"),
            ("https://facebook.com:secret@evil.com", "evil.com"),
            ("https://notfacebook.com", "notfacebook.com"),
        ],
    )
    def test_deceptive_social_urls_disqualified(self, deceptive_url, expected_extracted_domain):
        """Spoofed social subdomains and phishing domains must NOT qualify as social directories."""
        assert is_social_or_directory(deceptive_url) is False
        assert is_custom_domain(deceptive_url) is True
        assert is_qualified_lead_website(deceptive_url) is False

        is_qual, status, url = classify_website(deceptive_url)
        assert is_qual is False
        assert status == f"Custom Website ({expected_extracted_domain})"

    # 1.3 Valid Social & Directory Platforms
    def test_all_social_and_directories_whitelisted(self):
        """Every platform in SOCIAL_AND_DIRECTORIES must qualify with status 'None (No Website - Social Only)'."""
        for target in SOCIAL_AND_DIRECTORIES:
            url = f"https://www.{target}/contractor-profile"
            is_qual, status, clean = classify_website(url)
            assert is_qual is True, f"Failed for {target}"
            assert status == "None (No Website - Social Only)", f"Wrong status for {target}: {status}"
            assert clean == url

    # 1.4 Valid Subdomains of Social Platforms
    @pytest.mark.parametrize(
        "social_subdomain_url",
        [
            "https://m.facebook.com/simmonsroofinginc",
            "https://biz.yelp.com/biz/123",
            "https://profile.bbb.org/company/sample",
            "https://pro.angi.com/contractor/99",
            "https://pro.homeadvisor.com/c/123",
            "https://pro.thumbtack.com/contractor",
            "https://business.instagram.com/sample",
            "https://vt.tiktok.com/ZSsample",
            "https://contractor.business.site",
        ],
    )
    def test_social_subdomains_qualified(self, social_subdomain_url):
        """Legitimate subdomains of whitelisted platforms must qualify."""
        is_qual, status, url = classify_website(social_subdomain_url)
        assert is_qual is True
        assert status == "None (No Website - Social Only)"
        assert url == social_subdomain_url

    # 1.5 Absent Website Placeholders
    @pytest.mark.parametrize(
        "placeholder",
        [None, "", "   ", "none", "None", "NONE", "n/a", "N/A", "no website", "No Website", "Add website", "null", "undefined"],
    )
    def test_absent_website_placeholders(self, placeholder):
        """Absence of website must qualify with status 'None (No Website)' and URL None."""
        assert is_no_website(placeholder) is True
        assert is_qualified_lead_website(placeholder) is True
        is_qual, status, clean_url = classify_website(placeholder)
        assert is_qual is True
        assert status == "None (No Website)"
        assert clean_url is None

    # 1.6 Malformed / Non-HTTP Schemes
    @pytest.mark.parametrize(
        "non_http",
        [
            "javascript:void(0)",
            "javascript:;",
            "about:blank",
            "#",
            "tel:9038070683",
            "mailto:owner@roof.com",
            "data:text/html,test",
        ],
    )
    def test_non_http_schemes_disqualified(self, non_http):
        """Non-HTTP pseudo-URLs should not qualify as valid social profiles."""
        is_qual, status, url = classify_website(non_http)
        assert is_qual is False

    # 1.7 BUG REPRODUCTION: Scheme Case-Sensitivity
    @pytest.mark.parametrize(
        "uppercase_url,expected_domain",
        [
            ("HTTPS://ROOFING.CONTRACTORS/SERVICES?Q=1", "roofing.contractors"),
            ("HTTP://WWW.FACEBOOK.COM/PROFILE", "facebook.com"),
            ("HTTPS://WWW.FACEBOOK.COM/PROFILE", "facebook.com"),
            ("hTtPs://wWw.RoOfInG.cOm/Path?param=VAL#sec", "roofing.com"),
        ],
    )
    def test_bug_scheme_case_sensitivity(self, uppercase_url, expected_domain):
        """
        [EMPIRICAL BUG REPRODUCTION 1]
        clean_url_scheme() checks url.startswith(('http://', 'https://', '//')) case-sensitively.
        Uppercase schemes like 'HTTPS://' cause 'https://' to be prepended, yielding 'https://HTTPS://...',
        which parses the domain as 'https' and incorrectly disqualifies uppercase Facebook URLs!
        """
        extracted = extract_domain(uppercase_url)
        assert extracted == expected_domain, (
            f"clean_url_scheme is case-sensitive! Expected domain '{expected_domain}', got '{extracted}'"
        )


# ============================================================================
# Section 2: Phone Normalization Adversarial Stress-Tests
# ============================================================================

class TestPhoneNormalizationAdversarial:
    """Adversarial stress-testing of phone number cleaning and display formatting."""

    # 2.1 Standard US Phone Numbers
    @pytest.mark.parametrize(
        "valid_phone,expected_10",
        [
            ("(903) 807-0683", "9038070683"),
            ("903-807-0683", "9038070683"),
            ("903.807.0683", "9038070683"),
            ("+1 (903) 807-0683", "9038070683"),
            ("+19038070683", "9038070683"),
            ("1-903-807-0683", "9038070683"),
            ("903 807 0683", "9038070683"),
            ("9038070683", "9038070683"),
            ("19038070683", "9038070683"),
            ("  (903)  807 - 0683  ", "9038070683"),
            ("(903)807-0683", "9038070683"),
            ("903/807/0683", "9038070683"),
            ("tel:903-807-0683", "9038070683"),
        ],
    )
    def test_valid_us_phone_cleaning(self, valid_phone, expected_10):
        """Standard US phone variations must normalize to exactly 10 digits."""
        assert clean_phone_10digit(valid_phone) == expected_10
        assert format_phone_display(valid_phone) == "(903) 807-0683"

    # 2.2 7-digit Local Numbers (Missing Area Code)
    @pytest.mark.parametrize("local_phone", ["807-0683", "8070683", "807.0683", "(local) 807-0683"])
    def test_7digit_phone_returns_none(self, local_phone):
        """7-digit numbers cannot be used for US national outreach and must return None."""
        assert clean_phone_10digit(local_phone) is None

    # 2.3 11-digit Numbers Without Leading '1'
    @pytest.mark.parametrize(
        "invalid_11digit",
        ["20380706831", "52811234567", "90380706831", "44123456789"]
    )
    def test_11digit_without_leading_1_returns_none(self, invalid_11digit):
        """11-digit numbers not beginning with country code 1 must return None."""
        assert clean_phone_10digit(invalid_11digit) is None

    # 2.4 International Numbers
    @pytest.mark.parametrize(
        "intl_phone",
        [
            "+52 55 1234 5678",  # Mexico (12 digits)
            "+44 20 7946 0958",  # UK (12 digits)
            "+33 1 42 68 55 55", # France (11 digits, starts with 33)
        ],
    )
    def test_international_multi_digit_phone_returns_none(self, intl_phone):
        """Foreign international phone numbers with != 10 digits return None."""
        assert clean_phone_10digit(intl_phone) is None

    # 2.5 BUG REPRODUCTION: 10-Digit Foreign Numbers & Invalid NANP Area Codes Accepted
    @pytest.mark.parametrize(
        "invalid_nanp_or_foreign",
        [
            "+49 30 123456",     # Germany (+49 country code + 8 digits = 10 digits)
            "+52 81 1234 56",    # Mexico (+52 country code + 8 digits = 10 digits)
            "+44 1234 5678",     # UK (+44 country code + 8 digits = 10 digits)
            "012-345-6789",      # NANP violation: Area code starts with 0
            "111-222-3333",      # NANP violation: Area code starts with 1
        ],
    )
    def test_bug_foreign_or_invalid_nanp_accepted(self, invalid_nanp_or_foreign):
        """
        [EMPIRICAL BUG REPRODUCTION 2]
        clean_phone_10digit() only checks len(digits) == 10.
        It does not validate NANP rules (area codes cannot start with 0 or 1),
        nor does it check for foreign country codes like +49, +52, +44 when total digits happen to be 10!
        """
        cleaned = clean_phone_10digit(invalid_nanp_or_foreign)
        assert cleaned is None, (
            f"clean_phone_10digit erroneously accepted invalid NANP/foreign number '{invalid_nanp_or_foreign}' as valid US phone '{cleaned}'"
        )

    # 2.6 BUG REPRODUCTION: Phone Extensions Dropped
    @pytest.mark.parametrize(
        "ext_phone,expected_base",
        [
            ("(903) 807-0683 ext. 101", "9038070683"),
            ("(903) 807-0683 x4", "9038070683"),
            ("+1 903-807-0683 extension 45", "9038070683"),
        ],
    )
    def test_bug_phone_with_extension_dropped(self, ext_phone, expected_base):
        """
        [EMPIRICAL BUG REPRODUCTION 3]
        clean_phone_10digit() strips non-digits including 'ext', appending extension digits
        and resulting in > 10 digits, which returns None and drops valid contractor phone numbers!
        """
        cleaned = clean_phone_10digit(ext_phone)
        assert cleaned == expected_base, (
            f"clean_phone_10digit dropped phone with extension '{ext_phone}', returned {cleaned} instead of '{expected_base}'"
        )

    # 2.7 Degenerate & Extreme Inputs
    @pytest.mark.parametrize(
        "degenerate",
        [None, "", "   ", "abc", "123", "9999999999999999999", "!@#$%^&*()"]
    )
    def test_degenerate_phone_inputs(self, degenerate):
        """Degenerate inputs must safely return None without crashing."""
        assert clean_phone_10digit(degenerate) is None


# ============================================================================
# Section 3: Social & Search Redirector Leakage Stress-Tests
# ============================================================================

class TestRedirectorLeakageAdversarial:
    """Stress-test wrapper redirectors on social & search platforms."""

    @pytest.mark.parametrize(
        "redirect_url,destination_domain",
        [
            ("https://www.google.com/url?q=https://apexroofing.com", "apexroofing.com"),
            ("https://www.google.com/url?q=https%3A%2F%2Fapexroofing.com&sa=D", "apexroofing.com"),
            ("https://l.facebook.com/l.php?u=https%3A%2F%2Fapexroofing.com", "apexroofing.com"),
            ("https://www.youtube.com/redirect?q=https%3A%2F%2Fapexroofing.com", "apexroofing.com"),
            ("https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fapexroofing.com", "apexroofing.com"),
        ],
    )
    def test_bug_social_redirector_leak(self, redirect_url, destination_domain):
        """
        [EMPIRICAL BUG REPRODUCTION 4]
        When a contractor's website link on Google Maps points to an outbound wrapper redirect
        (e.g. google.com/url?q=https://apexroofing.com or l.facebook.com/l.php?u=...),
        the filter extracts 'google.com' or 'facebook.com', which matches SOCIAL_AND_DIRECTORIES.
        The contractor is thus marked as 'None (No Website - Social Only)', violating the
        Acceptance Criteria: 'No contractor with a functioning custom domain (.com, .io, .net, .co) is marked as No Website'.
        """
        is_qual, status, url = classify_website(redirect_url)
        assert is_qual is False, (
            f"Redirector leak! {redirect_url} wraps custom domain '{destination_domain}', "
            f"but was classified as qualified: qual={is_qual}, status={status}"
        )


# ============================================================================
# Section 4: End-to-End Extraction Engine Adversarial Integration
# ============================================================================

class TestExtractionCardParserAdversarial:
    """Stress-test GoogleMapsExtractor.parse_card_data with adversarial payloads."""

    def test_custom_domain_never_extracted(self):
        """Under no circumstances should a card with a custom domain return a QualifiedLead."""
        payloads = [
            ("Apex Roofing", "https://apexroofing.com"),
            ("Dallas Roof Co", "https://dallasroofing.co"),
            ("Lubbock Storm Repair", "http://lubbockstorm.net/about"),
            ("Buckeye Roofing", "https://buckeyeroofing.biz"),
            ("Canton Roofers", "https://canton.roofing"),
        ]
        for name, site in payloads:
            card_text = f"{name}\n5.0 (20) · Roofing contractor\nTyler, TX\n(903) 807-0683"
            lead = GoogleMapsExtractor.parse_card_data(
                card_text=card_text,
                anchor_aria_label=name,
                website_href=site,
                default_city="Tyler",
                default_state="TX",
            )
            assert lead is None, f"Failed to reject custom domain for {name} ({site})"

    def test_social_lead_successfully_extracted(self):
        """A contractor with only a social profile must be extracted as QualifiedLead."""
        card_text = "Piney Woods Roofing\n4.9 (18) · Roofing contractor\nTyler, TX\n(903) 555-0199"
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Piney Woods Roofing",
            website_href="https://www.facebook.com/pineywoodsroofing",
            default_city="Tyler",
            default_state="TX",
        )
        assert lead is not None
        assert lead.business_name == "Piney Woods Roofing"
        assert lead.website_status == "None (No Website - Social Only)"
        assert lead.website_url == "https://www.facebook.com/pineywoodsroofing"
        assert lead.priority == "🔥 High"

    def test_missing_phone_still_extracts_address_and_rating(self):
        """Contractor without phone number is still extracted with municipal centroid ZIP fallback."""
        card_text = "Silent Shingle Pros\n4.8 (12) · Roofing contractor\nMacon, GA"
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Silent Shingle Pros",
            website_href=None,
            default_city="Macon",
            default_state="GA",
        )
        assert lead is not None
        assert lead.business_name == "Silent Shingle Pros"
        assert lead.cleaned_phone == ""
        assert lead.city == "Macon"
        assert lead.state == "GA"
        assert lead.zip_code == "31201"  # Municipal centroid for Macon, GA

    def test_card_with_phone_extension_extracts_base_number(self):
        """
        Verify that GoogleMapsExtractor's card regex extracts the base 10-digit number
        even when the card text contains an extension.
        """
        card_text = "Pro Roofers LLC\n5.0 (22) · Roofing contractor\nTyler, TX\n(903) 807-0683 ext. 101"
        lead = GoogleMapsExtractor.parse_card_data(
            card_text=card_text,
            anchor_aria_label="Pro Roofers LLC",
            website_href=None,
            default_city="Tyler",
            default_state="TX",
        )
        assert lead is not None
        assert lead.cleaned_phone == "9038070683"
        assert lead.phone_display == "(903) 807-0683"
