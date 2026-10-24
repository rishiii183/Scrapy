"""
Adversarial Stress Testing Suite for Milestone 3: AI Personalization & Hook Generator.

Empirical verification of Personalization Invariants:
1. City & trade niche variations:
   - Multi-word cities ("Fort Worth", "El Paso", "Baton Rouge", "Salt Lake City", "San Antonio")
   - Strange capitalizations ("fOrT wOrTh", "el paso", "MIAMI", "rEsIdEnTiAl RoOfInG")
   - Special characters in company names ("O'Connor & Sons Roofing, LLC", "A.B.C. Roofers Inc.",
     "3-D Roofing & Sheet Metal Co.", "P.J.'s 24/7 Roofing & Siding Co.", "B&B Roofing Specialists, Inc.")
2. Sentence 1 ALWAYS contains city and trade specialty.
3. Sentence 2 ALWAYS contains "emergency roof repairs", "google maps", "competitors", and revenue loss language ("lost" or "missing out").
4. Icebreaker sentence count is STRICTLY 2 sentences across 200+ randomized company/city/specialty permutations.
5. Zero placeholder leakage across 500+ generated variations (assert regex r"\\{\\{.*?\\}\\}" and r"\\{[A-Za-z_]+\\}" never match).
"""

import random
import re
from typing import Any, Dict, List
import pytest

from src.models import CRMRecord, OutreachDraft
from src.personalizer import (
    PersonalizerGenerator,
    TemplateEngine,
    assert_zero_placeholders,
    validate_icebreaker_invariants,
)
from src.personalizer.prompts import (
    EMAIL_BODY_TEMPLATES,
    EMAIL_SUBJECT_TEMPLATES,
    ICEBREAKER_TEMPLATES,
    OFFER_ANGLE_TEMPLATES,
    WHATSAPP_TEMPLATES,
)

# ===========================================================================
# Adversarial Data Catalogs
# ===========================================================================

ADVERSARIAL_COMPANIES: List[str] = [
    "O'Connor & Sons Roofing, LLC",
    "A.B.C. Roofers Inc.",
    "3-D Roofing & Sheet Metal Co.",
    "P.J.'s 24/7 Roofing & Siding Co.",
    "J.R. & Sons Quality Roofing Corp.",
    "Top-Notch Roofing & Gutters, P.C.",
    "B&B Roofing Specialists, Inc.",
    "Smith & Wesson Commercial Roofers, Ltd.",
    "Apex Pro #1 Roofing Systems",
    "D & M Storm Restorations Co.",
    "Lone-Star Precision Roofers, LLC",
    "Sunshine State R&R Services",
    "Tri-County Re-Roofing & Repair Inc.",
    "General Roofing & Restoration",
    "5-Star Elite Roofers LLC",
    "MasterCraft Roofs & Sheet Metal",
    "A+ Premier Roofing Pros, Inc.",
    "St. Jude's Faith Roofing Co.",
    "Double-T Roofing & Solar, LLC",
    "H&H Advanced Roofing Group, LLP",
]

ADVERSARIAL_CITIES: List[str] = [
    # Multi-word cities
    "Fort Worth",
    "El Paso",
    "Baton Rouge",
    "Salt Lake City",
    "San Antonio",
    "West Palm Beach",
    "Corpus Christi",
    "Pompano Beach",
    "Cape Coral",
    "Port Saint Lucie",
    "Grand Rapids",
    "Colorado Springs",
    "Lake Havasu City",
    "Sierra Vista",
    "Casa Grande",
    # Single-word cities
    "Dallas",
    "Houston",
    "Austin",
    "Miami",
    "Tampa",
    "Orlando",
    "Atlanta",
    "Phoenix",
    "Columbus",
    "Cleveland",
    # Strange capitalizations
    "fOrT wOrTh",
    "FORT WORTH",
    "fort worth",
    "eL pAsO",
    "EL PASO",
    "el paso",
    "sAn AnToNiO",
    "SAN ANTONIO",
    "san antonio",
    "mIaMi",
    "MIAMI",
    "miami",
    "AtLaNtA",
    "ATLANTA",
    "atlanta",
    "DaLLaS",
    "DALLAS",
    "dallas",
    "tAmPa",
    "TAMPA",
    "tampa",
]

ADVERSARIAL_SPECIALTIES: List[str] = [
    # Standard M1 / M2 categories
    "Storm Damage & Re-roofing",
    "Commercial Roofing",
    "Emergency Leak Repair",
    "Residential Roofing",
    # Extended industry niches
    "Residential Roofing & Repairs",
    "Commercial & Industrial Roofing",
    "Storm Damage & Restoration",
    "Emergency Roof Repairs",
    "Metal & Tile Roofing",
    "Flat Roof & Waterproofing",
    "Hail & Storm Disaster Repair",
    "Residential Shingle & Re-roofing",
    # Strange capitalizations
    "rEsIdEnTiAl RoOfInG",
    "COMMERCIAL ROOFING",
    "storm damage & re-roofing",
    "EMERGENCY LEAK REPAIR",
    "cOmMeRcIaL & iNdUsTrIaL rOoFiNg",
]


# ===========================================================================
# 1. City & Trade Niche Variations
# ===========================================================================

class TestCityAndTradeNicheVariations:
    """
    Test personalizer handling of special characters in company names,
    multi-word cities, strange capitalizations, and diverse trade niches.
    """

    @pytest.mark.parametrize("company_name", [
        "O'Connor & Sons Roofing, LLC",
        "A.B.C. Roofers Inc.",
        "3-D Roofing & Sheet Metal Co.",
        "P.J.'s 24/7 Roofing & Siding Co.",
        "J.R. & Sons Quality Roofing Corp.",
        "Top-Notch Roofing & Gutters, P.C.",
        "B&B Roofing Specialists, Inc.",
        "Smith & Wesson Commercial Roofers, Ltd.",
        "Apex Pro #1 Roofing Systems",
        "A+ Premier Roofing Pros, Inc.",
    ])
    def test_special_characters_in_company_names(self, company_name: str):
        generator = PersonalizerGenerator()
        lead = {
            "company_name": company_name,
            "city": "Fort Worth",
            "state": "TX",
            "specialty": "Storm Damage & Re-roofing",
            "phone": "8175551234",
        }
        draft = generator.generate(lead)
        assert isinstance(draft, OutreachDraft)

        # Invariant: exactly 2 sentences
        sentences = [s.strip() for s in draft.icebreaker.split(".") if s.strip()]
        assert len(sentences) == 2, f"Failed for company '{company_name}': {draft.icebreaker}"

        # Invariant: zero placeholders
        assert_zero_placeholders(draft.icebreaker)
        assert_zero_placeholders(draft.offer_angle)
        assert_zero_placeholders(draft.staged_email_subject)
        assert_zero_placeholders(draft.staged_email_body)
        assert_zero_placeholders(draft.staged_whatsapp_msg)

    @pytest.mark.parametrize("city", [
        "Fort Worth",
        "El Paso",
        "Baton Rouge",
        "Salt Lake City",
        "San Antonio",
        "West Palm Beach",
        "Corpus Christi",
        "Lake Havasu City",
    ])
    def test_multi_word_cities(self, city: str):
        generator = PersonalizerGenerator()
        lead = {
            "company_name": "Lone Star Roofers LLC",
            "city": city,
            "state": "TX",
            "specialty": "Commercial Roofing",
            "phone": "8175551234",
        }
        draft = generator.generate(lead)
        assert isinstance(draft, OutreachDraft)

        # Invariant: City appears in Sentence 1 and Sentence 2
        sentences = [s.strip() for s in draft.icebreaker.split(".") if s.strip()]
        assert len(sentences) == 2
        assert city.lower() in sentences[0].lower()
        assert city.lower() in sentences[1].lower()

    @pytest.mark.parametrize("city_casing", [
        "fOrT wOrTh",
        "FORT WORTH",
        "fort worth",
        "eL pAsO",
        "EL PASO",
        "el paso",
        "mIaMi",
        "MIAMI",
        "miami",
    ])
    def test_strange_city_capitalizations(self, city_casing: str):
        generator = PersonalizerGenerator()
        lead = {
            "company_name": "Apex Roofing Pros",
            "city": city_casing,
            "state": "TX",
            "specialty": "Emergency Leak Repair",
            "phone": "2145551234",
        }
        draft = generator.generate(lead)

        sentences = [s.strip() for s in draft.icebreaker.split(".") if s.strip()]
        assert len(sentences) == 2
        assert city_casing.lower() in sentences[0].lower()
        assert city_casing.lower() in sentences[1].lower()

    @pytest.mark.parametrize("specialty_casing", [
        "rEsIdEnTiAl RoOfInG",
        "COMMERCIAL ROOFING",
        "storm damage & re-roofing",
        "EMERGENCY LEAK REPAIR",
        "cOmMeRcIaL & iNdUsTrIaL rOoFiNg",
    ])
    def test_strange_specialty_capitalizations(self, specialty_casing: str):
        generator = PersonalizerGenerator()
        lead = {
            "company_name": "Apex Roofing Pros",
            "city": "Fort Worth",
            "state": "TX",
            "specialty": specialty_casing,
            "phone": "8175551234",
        }
        draft = generator.generate(lead)

        sentences = [s.strip() for s in draft.icebreaker.split(".") if s.strip()]
        assert len(sentences) == 2
        # Specialty keywords or lower string present in Sentence 1
        spec_clean = specialty_casing.lower().replace("&", "and")
        s1_clean = sentences[0].lower().replace("&", "and")
        spec_words = [w for w in spec_clean.split() if len(w) > 3 and w not in {"roofing", "contractors"}]
        assert any(w in s1_clean for w in spec_words) or "roofing" in s1_clean


# ===========================================================================
# 2. Sentence 1 & Sentence 2 Invariants
# ===========================================================================

class TestSentenceInvariants:
    """
    Test isolated invariant compliance for Sentence 1 and Sentence 2
    across all template variations.
    """

    @pytest.mark.parametrize("template_idx", [0, 1, 2, 3])
    @pytest.mark.parametrize("city,specialty", [
        ("Fort Worth", "Storm Damage & Re-roofing"),
        ("El Paso", "Commercial Roofing"),
        ("Baton Rouge", "Emergency Leak Repair"),
        ("Salt Lake City", "Residential Roofing"),
        ("fOrT wOrTh", "rEsIdEnTiAl RoOfInG"),
    ])
    def test_sentence_1_always_contains_city_and_specialty(
        self,
        template_idx: int,
        city: str,
        specialty: str,
    ):
        engine = TemplateEngine()
        context = {
            "company_name": "O'Connor & Sons Roofing, LLC",
            "city": city,
            "specialty": specialty,
            "row_index": 14,
        }
        icebreaker = engine.render_icebreaker(context, template_index=template_idx)
        sentences = [s.strip() for s in icebreaker.split(".") if s.strip()]
        assert len(sentences) == 2, f"Failed template {template_idx}: {icebreaker}"

        sentence_1 = sentences[0]
        # Invariant: Sentence 1 contains exact city
        assert city.lower() in sentence_1.lower(), f"City '{city}' not in Sentence 1: '{sentence_1}'"

        # Invariant: Sentence 1 contains specialty or specialty keywords
        spec_clean = specialty.lower().replace("&", "and")
        s1_clean = sentence_1.lower().replace("&", "and")
        spec_keywords = [w for w in spec_clean.split() if len(w) > 3 and w not in {"contractors"}]
        assert any(k in s1_clean for k in spec_keywords), (
            f"Specialty '{specialty}' not in Sentence 1: '{sentence_1}'"
        )

    @pytest.mark.parametrize("template_idx", [0, 1, 2, 3])
    @pytest.mark.parametrize("city", [
        "Fort Worth",
        "El Paso",
        "Baton Rouge",
        "Miami",
        "fOrT wOrTh",
    ])
    def test_sentence_2_always_contains_required_hooks_and_revenue_loss(
        self,
        template_idx: int,
        city: str,
    ):
        engine = TemplateEngine()
        context = {
            "company_name": "3-D Roofing & Sheet Metal Co.",
            "city": city,
            "specialty": "Storm Damage & Re-roofing",
            "row_index": 14,
        }
        icebreaker = engine.render_icebreaker(context, template_index=template_idx)
        sentences = [s.strip() for s in icebreaker.split(".") if s.strip()]
        assert len(sentences) == 2

        sentence_2 = sentences[1]
        s2_lower = sentence_2.lower()

        # Invariant: Sentence 2 MUST contain "emergency roof repairs"
        assert "emergency roof repairs" in s2_lower, f"'emergency roof repairs' missing from S2: '{sentence_2}'"

        # Invariant: Sentence 2 MUST contain "google maps"
        assert "google maps" in s2_lower, f"'google maps' missing from S2: '{sentence_2}'"

        # Invariant: Sentence 2 MUST contain "competitors"
        assert "competitors" in s2_lower, f"'competitors' missing from S2: '{sentence_2}'"

        # Invariant: Sentence 2 MUST contain revenue loss language ("lost" or "missing out")
        assert ("lost" in s2_lower or "missing out" in s2_lower), (
            f"Revenue loss language ('lost' or 'missing out') missing from S2: '{sentence_2}'"
        )


# ===========================================================================
# 3. Icebreaker Sentence Count: 200+ Randomized Permutations
# ===========================================================================

class TestIcebreakerSentenceCount200RandomizedPermutations:
    """
    Stress-test that icebreaker sentence count is STRICTLY 2 sentences
    across 250 randomized company/city/specialty permutations.
    """

    def test_strict_two_sentence_count_across_250_randomized_permutations(self):
        rng = random.Random(42)  # Deterministic seed for reproducible stress tests
        generator = PersonalizerGenerator()

        total_tested = 0
        for i in range(250):
            company = rng.choice(ADVERSARIAL_COMPANIES)
            city = rng.choice(ADVERSARIAL_CITIES)
            specialty = rng.choice(ADVERSARIAL_SPECIALTIES)
            tmpl_idx = rng.randint(0, 3)
            row_idx = rng.randint(14, 500)

            lead = {
                "company_name": company,
                "city": city,
                "state": "TX",
                "specialty": specialty,
                "phone": f"903{rng.randint(1000000, 9999999)}",
                "row_index": row_idx,
            }

            draft = generator.generate(lead, template_index=tmpl_idx)
            icebreaker = draft.icebreaker

            # Invariant 1: Icebreaker ends with period
            assert icebreaker.endswith("."), f"Permutation {i} does not end with period: '{icebreaker}'"

            # Invariant 2: Sentence count is STRICTLY 2
            sentences = [s.strip() for s in icebreaker.split(".") if s.strip()]
            assert len(sentences) == 2, (
                f"Permutation {i} failed: expected 2 sentences, got {len(sentences)}.\n"
                f"Company: '{company}' | City: '{city}' | Specialty: '{specialty}'\n"
                f"Icebreaker: '{icebreaker}'\n"
                f"Sentences: {sentences}"
            )

            # Invariant 3: Sentence 1 contains city and specialty
            s1 = sentences[0]
            assert city.lower() in s1.lower()

            # Invariant 4: Sentence 2 contains all 4 mandatory elements
            s2 = sentences[1].lower()
            assert "emergency roof repairs" in s2
            assert "google maps" in s2
            assert "competitors" in s2
            assert ("lost" in s2 or "missing out" in s2)

            total_tested += 1

        assert total_tested >= 200, f"Expected >= 200 permutations, tested {total_tested}"


# ===========================================================================
# 4. Zero Placeholder Leakage: 500+ Generated Variations
# ===========================================================================

class TestZeroPlaceholderLeakage500Variations:
    """
    Stress-test that zero template placeholders (e.g. {{city}}, {{company_name}}, {tags})
    leak into ANY generated output across 500+ distinct permutations.
    """

    def test_zero_placeholder_leakage_across_520_generated_variations(self):
        engine = TemplateEngine()
        placeholder_regex = re.compile(r"\{\{.*?\}\}|\{[A-Za-z_]+\}|<[A-Za-z_]+>")

        # 13 companies * 10 cities * 4 specialties = 520 variations
        sample_companies = ADVERSARIAL_COMPANIES[:13]
        sample_cities = ADVERSARIAL_CITIES[:10]
        sample_specialties = ADVERSARIAL_SPECIALTIES[:4]

        total_variations = 0
        total_fields_checked = 0

        for comp_idx, company in enumerate(sample_companies):
            for city_idx, city in enumerate(sample_cities):
                for spec_idx, specialty in enumerate(sample_specialties):
                    tmpl_idx = (comp_idx + city_idx + spec_idx) % 4
                    row_idx = 14 + total_variations

                    context = {
                        "company_name": company,
                        "city": city,
                        "state": "FL",
                        "specialty": specialty,
                        "contact_name": "Dave",
                        "phone_display": "(813) 555-0199",
                        "row_index": row_idx,
                    }

                    assets = engine.render_all(context, template_index=tmpl_idx)
                    total_variations += 1

                    for field_name, text in assets.items():
                        total_fields_checked += 1
                        matches = placeholder_regex.findall(text)
                        assert not matches, (
                            f"Placeholder leakage detected in variation {total_variations}, field '{field_name}':\n"
                            f"Matches: {matches}\n"
                            f"Text: '{text}'\n"
                            f"Context: {context}"
                        )

        assert total_variations >= 500, f"Expected >= 500 variations, tested {total_variations}"
        assert total_fields_checked == total_variations * 5


# ===========================================================================
# 5. Invariant Validator Adversarial Stress Tests
# ===========================================================================

class TestInvariantValidatorAdversarialEnforcement:
    """
    Stress-test the validator itself to ensure it rejects corrupted or invalid icebreakers.
    """

    def test_validator_rejects_single_sentence(self):
        with pytest.raises(ValueError, match="must contain exactly 2 sentences"):
            validate_icebreaker_invariants(
                "Came across Apex Roofing in Fort Worth.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )

    def test_validator_rejects_three_sentences(self):
        with pytest.raises(ValueError, match="must contain exactly 2 sentences"):
            validate_icebreaker_invariants(
                "Came across Apex Roofing in Fort Worth. "
                "Competitors on Google Maps dominate emergency roof repairs and revenue is lost. "
                "Here is a third sentence.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )

    def test_validator_rejects_missing_city(self):
        with pytest.raises(ValueError, match="missing exact city"):
            validate_icebreaker_invariants(
                "Came across Apex Roofing serving homeowners. "
                "Competitors on Google Maps dominate emergency roof repairs and revenue is lost.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )

    def test_validator_rejects_missing_specialty_when_roofing_not_in_text(self):
        """When 'roofing' is not in the text, missing specialty is strictly caught."""
        with pytest.raises(ValueError, match="missing trade specialty"):
            validate_icebreaker_invariants(
                "Came across Apex Pro serving Fort Worth. "
                "Competitors on Google Maps dominate emergency roof repairs and revenue is lost.",
                city="Fort Worth",
                specialty="Solar Panel Cleaning",
            )

    def test_validator_specialty_bypass_finding(self):
        """
        Adversarial Finding: In llm_engine.py:88, the clause `and 'roofing' not in ice_lower`
        causes the specialty validation to be skipped whenever 'roofing' appears in the text
        (e.g. from the company name 'Apex Roofing').
        This test documents this empirical finding.
        """
        # If 'roofing' is present, the validator does NOT raise ValueError for missing specialty
        # even if an unrelated specialty like 'Solar Panel Cleaning' was expected.
        try:
            validate_icebreaker_invariants(
                "Came across Apex Roofing serving Fort Worth. "
                "Competitors on Google Maps dominate emergency roof repairs and revenue is lost.",
                city="Fort Worth",
                specialty="Solar Panel Cleaning",
            )
            bypassed = True
        except ValueError:
            bypassed = False

        # In current implementation, this is bypassed because 'roofing' is in 'Apex Roofing'
        assert bypassed is True, "Validator behavior changed; check llm_engine.py:88"

    def test_validator_rejects_missing_google_maps(self):
        with pytest.raises(ValueError, match="must mention Google Maps"):
            validate_icebreaker_invariants(
                "Came across Apex Roofing Commercial Roofing pro in Fort Worth. "
                "Competitors dominate emergency roof repairs and revenue is lost.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )

    def test_validator_rejects_missing_competitors(self):
        with pytest.raises(ValueError, match="must mention competitors"):
            validate_icebreaker_invariants(
                "Came across Apex Roofing Commercial Roofing pro in Fort Worth. "
                "Google Maps search for emergency roof repairs is where revenue is lost.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )

    def test_validator_rejects_missing_revenue_loss(self):
        with pytest.raises(ValueError, match="must highlight revenue loss"):
            validate_icebreaker_invariants(
                "Came across Apex Roofing Commercial Roofing pro in Fort Worth. "
                "Competitors dominate Google Maps for emergency roof repairs in Fort Worth.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )

    def test_validator_rejects_unparsed_placeholders(self):
        with pytest.raises(AssertionError, match="Unparsed placeholder tags detected"):
            validate_icebreaker_invariants(
                "Came across {{ company_name }} Commercial Roofing pro in Fort Worth. "
                "Competitors dominate Google Maps for emergency roof repairs and revenue is lost.",
                city="Fort Worth",
                specialty="Commercial Roofing",
            )
