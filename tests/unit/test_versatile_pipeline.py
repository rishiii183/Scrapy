"""
Unit & Integration Tests for Versatile Open-Source Multi-Niche Pipeline & Interactive Wizard.

Verifies:
1. Dynamic query generation across diverse niches (plumbers, dentists, HVAC, electricians)
2. Trade specialty classification for non-roofing categories
3. Website filter modes ('missing_website', 'no_website_strict', 'social_only', 'all')
4. Interactive questionnaire wizard flow and responses via stream injection
5. CLI parameter parsing and dispatching for custom niches
"""

import io
import json
from pathlib import Path
import pytest

from src.scraper.query_catalog import (
    generate_queries_for_niche,
    get_all_queries,
    get_queries_by_state,
    get_default_query_catalog,
)
from src.scraper.filters import classify_website
from src.scraper.normalizer import classify_specialty, normalize_business_name
from src.personalizer.template_engine import TemplateEngine
from src.cli import build_parser, run_interactive_wizard, main


class TestVersatileQueryCatalog:
    def test_default_niche_returns_original_catalog(self):
        """Roofing default returns the exact 30 multi-state queries."""
        queries = generate_queries_for_niche("roofing")
        assert len(queries) == 30
        assert any("Tyler TX" in q.query for q in queries)

    def test_custom_niche_plumbing(self):
        """Plumbing niche generates localized plumber queries."""
        queries = generate_queries_for_niche("plumbers", states=["TX", "FL"])
        assert len(queries) > 0
        for q in queries:
            assert "plumber" in q.query.lower()
            assert q.state in ("TX", "FL")

    def test_custom_niche_dentist_california(self):
        """Dentist niche in CA generates dental queries."""
        queries = generate_queries_for_niche("dentist", states=["CA"])
        assert len(queries) > 0
        assert all("dentist" in q.query.lower() for q in queries)
        assert all(q.state == "CA" for q in queries)

    def test_get_queries_by_state_with_niche(self):
        """State query filter supports custom niche."""
        tx_hvac = get_queries_by_state("TX", niche="HVAC")
        assert len(tx_hvac) > 0
        assert all("hvac" in q.query.lower() for q in tx_hvac)
        assert all(q.state == "TX" for q in tx_hvac)


class TestVersatileSpecialtyClassification:
    def test_roofing_specialty_unchanged(self):
        """Roofing trade specialty retains standard mappings."""
        spec = classify_specialty("Tyler Hail Damage & Storm Repairs", niche="roofing")
        assert spec == "Storm Damage & Re-roofing"

    def test_plumbing_specialty_classification(self):
        """Plumbing classification handles emergency, drains, and water heaters."""
        assert classify_specialty("Express Emergency Plumbing & Leak", niche="plumbing") == "Emergency Plumbing & Leak Detection"
        assert classify_specialty("Rooter Drain Cleaning Pros", niche="plumbing") == "Drain Cleaning & Sewer Repair"
        assert classify_specialty("Apex Commercial Plumbing Services", niche="plumbing") == "Commercial Plumbing"
        assert classify_specialty("Standard Plumber LLC", niche="plumbing") == "Residential Plumbing"

    def test_hvac_specialty_classification(self):
        """HVAC classification handles heating, cooling, commercial."""
        assert classify_specialty("Commercial Chiller & HVAC Pros", niche="hvac") == "Commercial HVAC"
        assert classify_specialty("Emergency AC Repair Team", niche="hvac") == "Emergency AC & Heating Repair"
        assert classify_specialty("Reliable Heating & Furnace Co", niche="hvac") == "Heating & Furnace Repair"

    def test_dental_specialty_classification(self):
        """Dental classification handles cosmetic and family dentistry."""
        assert classify_specialty("Smile Cosmetic & Implant Studio", niche="dentist") == "Cosmetic & Implant Dentistry"
        assert classify_specialty("Downtown Family Dental Care", niche="dentist") == "General & Family Dentistry"

    def test_generic_unknown_niche_fallback(self):
        """Arbitrary niche cleanly formats as Residential/Commercial {Niche}."""
        assert classify_specialty("Ace Landscaping Pros", niche="landscaper") == "Residential Landscaper"
        assert classify_specialty("Industrial Landscaping Corp", niche="landscaper") == "Commercial Landscaper"


class TestWebsiteFilterModes:
    def test_filter_mode_missing_website(self):
        """Default mode qualifies None and social profiles only."""
        is_q, status, _ = classify_website(None, filter_mode="missing_website")
        assert is_q is True
        assert status == "None (No Website)"

        is_q, status, _ = classify_website("https://facebook.com/plumber", filter_mode="missing_website")
        assert is_q is True
        assert "Social Only" in status

        is_q, status, _ = classify_website("https://mycustomroofing.com", filter_mode="missing_website")
        assert is_q is False

    def test_filter_mode_no_website_strict(self):
        """Strict mode rejects even social media profiles."""
        is_q, _, _ = classify_website(None, filter_mode="no_website_strict")
        assert is_q is True

        is_q, _, _ = classify_website("https://facebook.com/plumber", filter_mode="no_website_strict")
        assert is_q is False

    def test_filter_mode_social_only(self):
        """Social only mode requires social profile links."""
        is_q, _, _ = classify_website(None, filter_mode="social_only")
        assert is_q is False

        is_q, _, _ = classify_website("https://instagram.com/dentist", filter_mode="social_only")
        assert is_q is True

    def test_filter_mode_all(self):
        """All mode qualifies businesses regardless of website."""
        is_q, _, _ = classify_website("https://mycustomsite.com", filter_mode="all")
        assert is_q is True


class TestVersatilePersonalizer:
    def test_personalizer_with_plumber_niche(self):
        """TemplateEngine renders tailored copy when niche is plumbing."""
        engine = TemplateEngine()
        context = {
            "company_name": "Apex Plumbing Pros",
            "city": "Austin",
            "state": "TX",
            "specialty": "Residential Plumbing & Drain",
            "niche": "plumbing",
        }
        res = engine.render_all(context)
        assert "Austin" in res["icebreaker"]
        assert "emergency plumbing repairs" in res["icebreaker"]
        assert "Plumbing Growth Team" in res["staged_email_body"]

    def test_personalizer_with_hvac_niche(self):
        """TemplateEngine renders tailored copy when niche is HVAC."""
        engine = TemplateEngine()
        context = {
            "company_name": "Cool Breeze Air",
            "city": "Miami",
            "state": "FL",
            "specialty": "Residential AC & HVAC",
            "niche": "hvac",
        }
        res = engine.render_all(context)
        assert "Miami" in res["icebreaker"]
        assert "urgent AC and heating repairs" in res["icebreaker"]
        assert "HVAC Growth Team" in res["staged_email_body"]


class TestInteractiveQuestionnaireWizard:
    def test_wizard_defaults(self, monkeypatch):
        """Interactive questionnaire proceeds with default values on empty enters."""
        # 5 empty lines to accept defaults
        user_input = "\n\n\n\n\n\n"
        stream_in = io.StringIO(user_input)
        stream_out = io.StringIO()

        rc = run_interactive_wizard(stream_in=stream_in, stream_out=stream_out)
        output = stream_out.getvalue()

        assert "UNIVERSAL GOOGLE MAPS & WEB LEAD PIPELINE" in output
        assert "Target Business Category / Niche:" in output
        assert "Starting Pipeline with Configuration:" in output
        assert "Niche:           roofers" in output
        assert rc == 0

    def test_wizard_custom_answers(self, monkeypatch):
        """Interactive questionnaire accepts custom niche, location, filter, and count."""
        # Inputs:
        # Niche: plumbers
        # Locations: TX FL
        # Data type: 1
        # Filter: 2 (no_website_strict)
        # Limit: 10
        # Flow: 2 (scrape only)
        user_input = "plumbers\nTX FL\n1\n2\n10\n2\n"
        stream_in = io.StringIO(user_input)
        stream_out = io.StringIO()

        rc = run_interactive_wizard(stream_in=stream_in, stream_out=stream_out)
        output = stream_out.getvalue()

        assert "Niche:           plumbers" in output
        assert "TX, FL" in output
        assert "no_website_strict" in output
        assert "10 leads" in output
        assert "Scrape Only" in output
        assert rc == 0


class TestCliSubcommandsWithNiche:
    def test_scrape_parser_supports_niche_and_filter(self):
        """Verify CLI parser parses --niche and --filter correctly."""
        parser = build_parser()
        args = parser.parse_args(["scrape", "--niche", "dentists", "--filter", "social_only", "--limit", "15"])
        assert args.niche == "dentists"
        assert args.filter == "social_only"
        assert args.limit == 15

    def test_pipeline_parser_supports_niche(self):
        """Verify pipeline subcommand parses --niche."""
        parser = build_parser()
        args = parser.parse_args(["pipeline", "--niche", "HVAC", "--dry-run"])
        assert args.niche == "HVAC"
        assert args.dry_run is True
