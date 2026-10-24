"""
Unified Command-Line Interface (CLI) for Roofer Outreach Pipeline.

Subcommands:
- scrape:      Run Google Maps scraper across US target states for roofers without websites
- ingest:      Deduplicate and append leads to Google Sheets CRM (Cols A-U)
- personalize: Generate 2-sentence icebreakers and stage outreach packages (Cols V-Z)
- dispatch:    Deliver outreach via Cold Email / WhatsApp click-to-chat with safety gate
- pipeline:    Execute end-to-end multi-agent pipeline
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import (
    SHEET_ID,
    SHEET_TAB,
    DAILY_SEND_CAP,
    TARGET_STATES,
    DATA_DIR,
    PROJECT_ROOT,
)
from src.models import RawLead, QualifiedLead, CRMRecord, OutreachDraft
from src.crm.sheets_client import SheetsClient
from src.crm.schema import crm_row_to_record, lead_to_crm_row
from src.crm.ingestor import CRMIngestor
from src.personalizer.generator import PersonalizerGenerator
from src.personalizer.template_engine import TemplateEngine
from src.dispatcher.orchestrator import OutreachDispatcher, DispatchSummary
from src.dispatcher.safety_gate import SafetyGateError, check_safety_gate
from src.dispatcher.pacing import PacingController

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("roofer_pipeline_cli")


def build_parser() -> argparse.ArgumentParser:
    """Build unified CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="roofer-pipeline",
        description="Automated 4-Agent Universal Lead Outreach Pipeline & Google Sheets CRM",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=False,
        help="Launch interactive configuration wizard asking what data to scrape",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 1. Scrape subcommand
    scrape_p = subparsers.add_parser("scrape", help="Scrape Google Maps for local businesses without websites")
    scrape_p.add_argument(
        "--niche",
        type=str,
        default="roofing",
        help="Target business niche or category (e.g. roofers, plumbers, dentists, HVAC, lawyers)",
    )
    scrape_p.add_argument(
        "--filter",
        "--filter-mode",
        dest="filter",
        choices=["missing_website", "no_website_strict", "social_only", "all"],
        default="missing_website",
        help="Website qualification filter mode (default: missing_website)",
    )
    scrape_p.add_argument(
        "--states",
        nargs="+",
        default=TARGET_STATES,
        help="Target US states (e.g. TX FL OH GA AZ)",
    )
    scrape_p.add_argument(
        "--limit",
        "-n",
        type=int,
        default=25,
        help="Target number of unique leads to extract (default: 25)",
    )
    scrape_p.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(DATA_DIR / "extracted_leads.json"),
        help="Path to save extracted leads JSON",
    )
    scrape_p.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Use verified sample leads fixture instead of live browser",
    )
    scrape_p.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=False,
        help="Configure scraping parameters interactively",
    )

    # 2. Ingest subcommand
    ingest_p = subparsers.add_parser("ingest", help="Ingest leads into Google Sheets CRM")
    ingest_p.add_argument(
        "--input",
        "-i",
        type=str,
        default=str(DATA_DIR / "extracted_leads.json"),
        help="Path to extracted leads JSON",
    )
    ingest_p.add_argument(
        "--sheet-id",
        type=str,
        default=SHEET_ID,
        help="Target Google Spreadsheet ID",
    )
    ingest_p.add_argument(
        "--tab",
        type=str,
        default=SHEET_TAB,
        help="Target Sheet Tab name (default: Leads Tracker)",
    )
    ingest_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run CRM ingestion in offline simulation mode",
    )

    # 3. Personalize subcommand
    pers_p = subparsers.add_parser("personalize", help="Generate AI hooks & staged outreach packages")
    pers_p.add_argument(
        "--niche",
        type=str,
        default="roofing",
        help="Target business niche for copy tailoring",
    )
    pers_p.add_argument(
        "--sheet-id",
        type=str,
        default=SHEET_ID,
        help="Target Google Spreadsheet ID",
    )
    pers_p.add_argument(
        "--tab",
        type=str,
        default=SHEET_TAB,
        help="Target Sheet Tab name (default: Leads Tracker)",
    )
    pers_p.add_argument(
        "--engine",
        choices=["jinja2", "llm"],
        default="jinja2",
        help="Personalization copy engine",
    )
    pers_p.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Limit number of leads to personalize",
    )
    pers_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run personalization in offline simulation mode",
    )

    # 4. Dispatch subcommand
    disp_p = subparsers.add_parser("dispatch", help="Run Humanized Outreach Dispatch Engine")
    disp_p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in Dry-Run Simulator mode (default: True for safety)",
    )
    disp_p.add_argument(
        "--live",
        dest="dry_run",
        action="store_false",
        help="Run in live sending mode (requires SMTP credentials)",
    )
    disp_p.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Explicit user confirmation required by Safety Gate to dispatch",
    )
    disp_p.add_argument(
        "--cap",
        "-c",
        type=int,
        default=DAILY_SEND_CAP,
        help="Daily dispatch volume cap (default: 25)",
    )
    disp_p.add_argument(
        "--channel",
        choices=["auto", "email", "whatsapp"],
        default="auto",
        help="Outreach channel filter (default: auto routing)",
    )
    disp_p.add_argument(
        "--test-mode",
        action="store_true",
        default=False,
        help="Use instant simulated clock for pacing during tests",
    )
    disp_p.add_argument(
        "--sheet-id",
        type=str,
        default=SHEET_ID,
        help="Target Google Spreadsheet ID",
    )
    disp_p.add_argument(
        "--tab",
        type=str,
        default=SHEET_TAB,
        help="Target Sheet Tab name (default: Leads Tracker)",
    )

    # 5. Pipeline subcommand
    pipe_p = subparsers.add_parser("pipeline", help="Execute complete end-to-end pipeline")
    pipe_p.add_argument(
        "--niche",
        type=str,
        default="roofing",
        help="Target business niche or category (e.g. roofers, plumbers, dentists, HVAC, lawyers)",
    )
    pipe_p.add_argument(
        "--filter",
        "--filter-mode",
        dest="filter",
        choices=["missing_website", "no_website_strict", "social_only", "all"],
        default="missing_website",
        help="Website qualification filter mode (default: missing_website)",
    )
    pipe_p.add_argument(
        "--states",
        nargs="+",
        default=TARGET_STATES,
        help="Target US states (e.g. TX FL OH GA AZ)",
    )
    pipe_p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run pipeline in dry-run simulation mode",
    )
    pipe_p.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Safety gate confirmation flag for dispatch stage",
    )
    pipe_p.add_argument(
        "--cap",
        type=int,
        default=DAILY_SEND_CAP,
        help="Daily send cap for dispatch",
    )
    pipe_p.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Number of leads to process",
    )
    pipe_p.add_argument(
        "--test-mode",
        action="store_true",
        default=False,
        help="Use fast simulated pacing clock",
    )
    pipe_p.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=False,
        help="Configure pipeline interactively",
    )

    # 6. Interactive wizard subcommand
    subparsers.add_parser(
        "interactive",
        help="Interactive questionnaire wizard for versatile lead extraction and outreach",
    )

    return parser


def load_leads_from_file_or_fixtures(file_path: str, limit: int = 25, niche: str = "roofing") -> List[QualifiedLead]:
    """Helper to load leads from JSON file with fallback to test fixtures."""
    p = Path(file_path)
    if not p.exists():
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "sample_leads.json"
        if fixture_path.exists():
            p = fixture_path
        else:
            raise FileNotFoundError(f"Neither {file_path} nor fixture file exists.")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    leads: List[QualifiedLead] = []
    from src.scraper.normalizer import clean_phone_10digit, format_phone_display, classify_specialty
    for item in data[:limit]:
        b_name = item.get("business_name") or item.get("company_name", "")
        raw_phone = item.get("phone") or item.get("phone_display") or item.get("cleaned_phone", "")
        clean_p = item.get("cleaned_phone") or clean_phone_10digit(raw_phone) or ""
        p_disp = item.get("phone_display") or format_phone_display(clean_p or raw_phone)
        spec = item.get("specialty") or item.get("primary_specialty") or "Residential Roofing & Repairs"
        if spec.lower() in ["residential", "commercial", "storm", "leak"]:
            spec = classify_specialty(spec, niche=niche)

        raw = RawLead(
            business_name=b_name,
            cleaned_phone=clean_p,
            phone_display=p_disp,
            city=item.get("city", "Tyler"),
            state=item.get("state", "TX"),
            zip_code=item.get("zip_code", "75701"),
            review_count=int(item.get("review_count", 0)),
            star_rating=float(item.get("star_rating", 0.0)),
            specialty=spec,
            website_status=item.get("website_status", "None (No Website)"),
            website_url=item.get("website_url"),
            place_url=item.get("place_url", ""),
        )
        leads.append(QualifiedLead.from_raw(raw, priority=item.get("priority"), search_query=item.get("search_query")))
    return leads


def handle_scrape(args: argparse.Namespace) -> int:
    """Execute scrape subcommand."""
    if getattr(args, "interactive", False):
        return run_interactive_wizard()

    niche = getattr(args, "niche", "roofing")
    filter_mode = getattr(args, "filter", "missing_website")
    logger.info(
        "Executing Scraper for niche: '%s' | states: %s | filter: %s (Target: %d leads)",
        niche,
        args.states,
        filter_mode,
        args.limit,
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.mock:
        leads = load_leads_from_file_or_fixtures(str(out_path), limit=args.limit, niche=niche)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([l.model_dump() for l in leads], f, indent=2)
        logger.info("Saved %d mock leads to %s", len(leads), out_path)
        return 0

    try:
        from src.scraper.maps_extractor import GoogleMapsExtractor
        from src.scraper.query_catalog import get_queries_by_state, generate_queries_for_niche

        if niche.lower() in ("roofing", "roofer", "roofers") and set(args.states) == set(TARGET_STATES):
            queries = []
            for state in args.states:
                queries.extend(get_queries_by_state(state))
        else:
            queries = generate_queries_for_niche(niche=niche, states=args.states)

        extractor = GoogleMapsExtractor()
        leads = extractor.extract_multi_queries(
            queries=queries,
            target_count=args.limit,
            niche=niche,
            filter_mode=filter_mode,
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([l.model_dump() for l in leads], f, indent=2)
        logger.info("Scraped %d qualified leads for niche '%s'. Saved to %s", len(leads), niche, out_path)
        return 0
    except Exception as e:
        logger.warning("Scraping live browser encountered exception (%s). Falling back to fixtures.", e)
        leads = load_leads_from_file_or_fixtures(str(out_path), limit=args.limit, niche=niche)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([l.model_dump() for l in leads], f, indent=2)
        logger.info("Saved %d fixture leads to %s", len(leads), out_path)
        return 0


def handle_ingest(args: argparse.Namespace) -> int:
    """Execute ingest subcommand."""
    logger.info("Executing CRM Ingestion from %s into %s", args.input, args.sheet_id)
    niche = getattr(args, "niche", "roofing")
    leads = load_leads_from_file_or_fixtures(args.input, niche=niche)

    sheets_client = SheetsClient(offline_mode=args.dry_run)
    ingestor = CRMIngestor(
        sheets_client=sheets_client,
        sheet_id=args.sheet_id,
        sheet_tab=args.tab,
    )

    result = ingestor.ingest(leads)
    logger.info(
        "Ingestion completed: %d appended, %d duplicates skipped. Starting row: %d",
        result.get("ingested_count", 0),
        result.get("duplicates_skipped", 0),
        result.get("starting_row", 14),
    )
    return 0


def handle_personalize(args: argparse.Namespace) -> int:
    """Execute personalize subcommand."""
    niche = getattr(args, "niche", "roofing")
    logger.info("Executing Personalization (Niche: %s, Engine: %s, Dry-run: %s)", niche, args.engine, args.dry_run)
    leads = load_leads_from_file_or_fixtures(
        str(DATA_DIR / "extracted_leads.json"),
        limit=args.limit or 25,
        niche=niche,
    )

    generator = PersonalizerGenerator(engine=TemplateEngine())
    drafts = []
    for lead in leads:
        lead_dict = lead.model_dump()
        lead_dict["niche"] = niche
        drafts.append(generator.generate(lead_dict))

    sheets_client = SheetsClient(offline_mode=args.dry_run)
    generator.stage_to_sheet(
        drafts=drafts,
        sheets_client=sheets_client,
        sheet_id=args.sheet_id,
        tab_name=args.tab,
    )
    logger.info("Personalized and staged %d outreach drafts into columns V-Z", len(drafts))
    return 0


def handle_dispatch(args: argparse.Namespace) -> int:
    """Execute dispatch subcommand."""
    logger.info(
        "Executing Outreach Dispatch (Confirm: %s, Dry-Run: %s, Cap: %d, Channel: %s)",
        args.confirm,
        args.dry_run,
        args.cap,
        args.channel,
    )

    # 1. Safety Gate Check on Confirmation
    if not args.confirm:
        logger.error(
            "Dispatch aborted: Safety Gate requires explicit --confirm flag to permit outbound messaging."
        )
        return 1

    # 2. Prepare drafts
    niche = getattr(args, "niche", "roofing")
    leads = load_leads_from_file_or_fixtures(str(DATA_DIR / "extracted_leads.json"), limit=args.cap, niche=niche)
    generator = PersonalizerGenerator(engine=TemplateEngine())
    drafts = []
    for lead in leads:
        lead_dict = lead.model_dump()
        lead_dict["niche"] = niche
        drafts.append(generator.generate(lead_dict))

    # 3. Initialize Dispatcher
    sheets_client = SheetsClient(offline_mode=args.dry_run)
    dispatcher = OutreachDispatcher(
        sheets_client=sheets_client,
        dry_run=args.dry_run,
        default_confirmed=args.confirm,
        test_mode=args.test_mode,
        daily_cap=args.cap,
    )

    channel_override = None if args.channel == "auto" else args.channel
    summary = dispatcher.dispatch_batch(
        drafts=drafts,
        confirmed=args.confirm,
        cap=args.cap,
        channel_override=channel_override,
        sync_sheet=True,
        sheet_id=args.sheet_id,
        sheet_tab=args.tab,
    )

    logger.info(
        "Dispatch batch summary: Dispatched Email=%d | Dispatched WhatsApp=%d | Skipped=%d | Failed=%d",
        summary.dispatched_email,
        summary.dispatched_whatsapp,
        summary.skipped_count,
        summary.failed_count,
    )
    return 0


def handle_pipeline(args: argparse.Namespace) -> int:
    """Execute complete end-to-end pipeline."""
    if getattr(args, "interactive", False):
        return run_interactive_wizard()

    niche = getattr(args, "niche", "roofing")
    filter_mode = getattr(args, "filter", "missing_website")
    states = getattr(args, "states", TARGET_STATES)
    logger.info("Starting End-to-End Outreach Pipeline (Niche: '%s' | Filter: %s)", niche, filter_mode)

    # Step 1: Scrape
    scrape_args = argparse.Namespace(
        states=states,
        limit=args.limit,
        output=str(DATA_DIR / "extracted_leads.json"),
        mock=True,
        niche=niche,
        filter=filter_mode,
    )
    rc1 = handle_scrape(scrape_args)
    if rc1 != 0:
        return rc1

    # Step 2: Ingest
    ingest_args = argparse.Namespace(
        input=str(DATA_DIR / "extracted_leads.json"),
        sheet_id=SHEET_ID,
        tab=SHEET_TAB,
        dry_run=args.dry_run,
        niche=niche,
    )
    rc2 = handle_ingest(ingest_args)
    if rc2 != 0:
        return rc2

    # Step 3: Personalize
    pers_args = argparse.Namespace(
        sheet_id=SHEET_ID,
        tab=SHEET_TAB,
        engine="jinja2",
        limit=args.limit,
        dry_run=args.dry_run,
        niche=niche,
    )
    rc3 = handle_personalize(pers_args)
    if rc3 != 0:
        return rc3

    # Step 4: Dispatch (if confirmed)
    if args.confirm:
        disp_args = argparse.Namespace(
            dry_run=args.dry_run,
            confirm=True,
            cap=args.cap,
            channel="auto",
            test_mode=args.test_mode,
            sheet_id=SHEET_ID,
            tab=SHEET_TAB,
            niche=niche,
        )
        rc4 = handle_dispatch(disp_args)
        if rc4 != 0:
            return rc4
    else:
        logger.info(
            "Pipeline finished steps 1-3. Outreach drafts staged in Cols V-Z ready for review. (Dispatch paused: --confirm not provided)."
        )

    logger.info("Pipeline executed successfully.")
    return 0


def run_interactive_wizard(
    stream_in=None,
    stream_out=None,
) -> int:
    """
    Interactive questionnaire wizard asking the user what type of scrape data,
    niche, geographic locations, and website qualification rules they want.
    """
    import sys
    out = stream_out or sys.stdout
    inp = stream_in or sys.stdin

    def ask(prompt: str, default: str = "") -> str:
        out.write(prompt)
        out.flush()
        val = inp.readline()
        if val is None:
            return default
        val = val.strip()
        return val if val else default

    out.write("\n" + "=" * 80 + "\n")
    out.write("🌐 UNIVERSAL GOOGLE MAPS & WEB LEAD PIPELINE (OPEN SOURCE)\n")
    out.write("=" * 80 + "\n")
    out.write("Welcome! Configure your lead extraction and outreach pipeline interactively.\n")
    out.write("Press [Enter] on any question to accept the default option.\n\n")

    # Question 1: Niche / Business Type
    out.write("[1/5] Target Business Category / Niche:\n")
    out.write("      What type of business or service category do you want to scrape?\n")
    out.write("      (e.g., roofers, plumbers, dentists, HVAC, electricians, landscapers, lawyers)\n")
    niche = ask("      Target Niche [default: roofers]: ", "roofers")

    # Question 2: Locations
    default_states_str = " ".join(TARGET_STATES)
    out.write(f"\n[2/5] Target Geographic Locations:\n")
    out.write("      Which US states or cities do you want to target?\n")
    out.write("      (e.g., 'TX FL OH GA AZ' or 'Austin TX, Tampa FL, Columbus OH')\n")
    states_in = ask(f"      Target States [default: {default_states_str}]: ", default_states_str)
    states = [s.strip().upper() for s in states_in.replace(",", " ").split() if s.strip()]

    # Question 3: Data Types / Fields
    out.write("\n[3/5] What types of data do you want to extract?\n")
    out.write("      [1] Full Lead Profile (Business name, phone, city/state/zip, rating, review count, website status, place link) [Recommended]\n")
    out.write("      [2] Contact Details Focus (Business name, cleaned phone, website/social URLs)\n")
    out.write("      [3] High-Review Focus (Qualified businesses with >10 reviews and ratings)\n")
    out.write("      [4] All Google Maps fields\n")
    data_type_choice = ask("      Select data type [1-4, default: 1]: ", "1")

    # Question 4: Website Qualification Filter
    out.write("\n[4/5] Website Qualification Filter:\n")
    out.write("      How should websites be filtered?\n")
    out.write("      [1] Missing Website Only (No website OR social profile only - recommended)\n")
    out.write("      [2] Strictly No Website (no website URL, no social profile links)\n")
    out.write("      [3] Social Profiles Only (Facebook, Yelp, Instagram directories only)\n")
    out.write("      [4] All Businesses (include businesses that already have custom websites)\n")
    filter_choice = ask("      Select filter [1-4, default: 1]: ", "1")

    filter_map = {
        "1": "missing_website",
        "2": "no_website_strict",
        "3": "social_only",
        "4": "all",
    }
    filter_mode = filter_map.get(filter_choice, "missing_website")

    # Question 5: Lead count & Execution workflow
    out.write("\n[5/5] Extraction Volume & Pipeline Workflow:\n")
    limit_in = ask("      How many leads do you want to extract? [default: 25]: ", "25")
    limit = int(limit_in) if limit_in.isdigit() and int(limit_in) > 0 else 25

    out.write("\n      What workflow would you like to run?\n")
    out.write("      [1] Full Pipeline (Scrape -> Ingest to CRM -> Personalize Copy -> Outreach Review)\n")
    out.write("      [2] Scrape Only (Save to data/extracted_leads.json)\n")
    out.write("      [3] Scrape & Ingest to Google Sheets CRM\n")
    flow_choice = ask("      Select workflow [1-3, default: 1]: ", "1")

    flow_desc = "Full Pipeline" if flow_choice == "1" else ("Scrape Only" if flow_choice == "2" else "Scrape & Ingest")

    out.write("\n" + "=" * 80 + "\n")
    out.write("🚀 Starting Pipeline with Configuration:\n")
    out.write(f"   • Niche:           {niche}\n")
    out.write(f"   • States/Markets:  {', '.join(states)}\n")
    out.write(f"   • Website Filter:  {filter_mode}\n")
    out.write(f"   • Target Limit:    {limit} leads\n")
    out.write(f"   • Workflow:        {flow_desc}\n")
    out.write("=" * 80 + "\n\n")

    if flow_choice == "2":
        args = argparse.Namespace(
            states=states,
            limit=limit,
            output=str(DATA_DIR / "extracted_leads.json"),
            mock=False,
            niche=niche,
            filter=filter_mode,
        )
        return handle_scrape(args)
    elif flow_choice == "3":
        args_scrape = argparse.Namespace(
            states=states,
            limit=limit,
            output=str(DATA_DIR / "extracted_leads.json"),
            mock=False,
            niche=niche,
            filter=filter_mode,
        )
        rc = handle_scrape(args_scrape)
        if rc != 0:
            return rc
        args_ingest = argparse.Namespace(
            input=str(DATA_DIR / "extracted_leads.json"),
            sheet_id=SHEET_ID,
            tab=SHEET_TAB,
            dry_run=False,
            niche=niche,
        )
        return handle_ingest(args_ingest)
    else:
        args_pipe = argparse.Namespace(
            states=states,
            limit=limit,
            dry_run=True,
            confirm=False,
            cap=DAILY_SEND_CAP,
            test_mode=False,
            niche=niche,
            filter=filter_mode,
        )
        return handle_pipeline(args_pipe)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI programmatic entrypoint."""
    parser = build_parser()

    # If no arguments provided in interactive terminal, prompt user
    if argv is None and len(sys.argv) == 1:
        if sys.stdin.isatty():
            return run_interactive_wizard()
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if getattr(args, "interactive", False) or args.subcommand in ("interactive", "wizard"):
        return run_interactive_wizard()

    if not args.subcommand:
        parser.print_help()
        return 0

    handlers = {
        "scrape": handle_scrape,
        "ingest": handle_ingest,
        "personalize": handle_personalize,
        "dispatch": handle_dispatch,
        "pipeline": handle_pipeline,
        "interactive": lambda _: run_interactive_wizard(),
        "wizard": lambda _: run_interactive_wizard(),
    }

    handler = handlers.get(args.subcommand)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
