# Project: Roofer Outreach Pipeline

## Architecture
The Roofer Outreach Pipeline is an automated, production-grade 4-agent system engineered to identify high-value roofing contractors without websites, ingest and deduplicate them in Google Sheets CRM, generate hyper-personalized revenue pain-point angles, and dispatch staged outreach safely via Email and WhatsApp fallback.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         ROOFER OUTREACH PIPELINE                               │
└────────────────────────────────────────────────────────────────────────────────┘
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
┌───────────────────────────────┐               ┌────────────────────────────────┐
│    IMPLEMENTATION TRACK       │               │      E2E TESTING TRACK         │
│  - M1: Maps Extractor         │               │  - Test Harness & Runner       │
│  - M2: Sheets CRM & Dedup     │               │  - Tier 1: Feature Coverage    │
│  - M3: AI Personalization     │               │  - Tier 2: Boundary / Edge     │
│  - M4: Staged Outreach Disp.  │               │  - Tier 3: Pairwise Combos     │
│  - Final: 100% E2E + T5 Hard. │               │  - Tier 4: Real-world Scenarios│
└────────────┬──────────────────┘               └───────────────┬────────────────┘
             │                                                  │
             │                                                  ▼
             │                                           [TEST_READY.md]
             ▼                                                  │
┌───────────────────────────────────────────────────────────────┴────────────────┐
│  Final Milestone: Pass 100% E2E Suite (Tiers 1-4) & Tier 5 Adversarial Hardening│
└────────────────────────────────────────────────────────────────────────────────┘
```

### Module Data Flow
```
[Google Maps Search via Playwright]
                 │
                 ▼ (Raw Extracted Contractor Records)
[M1: Scraper & Website Filter] (Discards custom domains, captures No Website & Socials)
                 │
                 ▼ (Validated Leads: Name, Phone, City, State, ZIP, Rating, Reviews, Specialty)
[M2: CRM Ingest & Deduplication] (Normalizes Name & Phone, checks existing CRM, scores Priority)
                 │
                 ▼ (Appends to Google Sheet 'Leads Tracker' Cols A-U at Row 14+)
[M3: AI Personalization Engine] (Generates 2-sentence hook, revenue pain point, stages V-Z)
                 │
                 ▼ (Staged Records in Col V-Z: Subject, Body, WhatsApp Msg, wa.me Link)
[M4: Staged Outreach Dispatch] (Human approval gate -> Cold Email / wa.me -> Jitter -> CRM update)
```

## Code Layout
```
roofer_outreach_pipeline/
├── .venv/                         # Project virtual environment (Python 3.15 + Playwright)
├── src/
│   ├── __init__.py
│   ├── config.py                  # Global config, env settings, paths, daily caps, pacing
│   ├── models.py                  # Pydantic schemas (RawLead, QualifiedLead, CRMRecord, OutreachDraft)
│   ├── gsheets_client.py          # Direct Google Sheets API client with OAuth auto-refresh & CLI fallback
│   ├── scraper/                   # Milestone 1: Agent 1
│   │   ├── __init__.py
│   │   ├── browser_manager.py     # Playwright Chromium / Chrome launcher with anti-bot flags
│   │   ├── maps_extractor.py      # Search runner, infinite scroll, and DOM card parser
│   │   ├── filters.py             # Domain classifier (.com/.io vs social/directory blocklist)
│   │   ├── normalizer.py          # Phone cleaner, address/ZIP centroid mapper, specialty classifier
│   │   └── query_catalog.py       # Seeded metro queries for target US states (TX, FL, OH, GA, AZ)
│   ├── crm/                       # Milestone 2: Agent 2
│   │   ├── __init__.py
│   │   ├── dedup.py               # Business name & phone normalization & deduplication engine
│   │   ├── lead_scorer.py         # Priority scoring (🔥 High, ⚡ Medium, ❄️ Low) & Deal Value
│   │   ├── schema.py              # 21-column schema mapping (A through U) & validation checks
│   │   └── ingestor.py            # Append operations starting at Row 14, preserving formulas
│   ├── personalizer/              # Milestone 3: Agent 3
│   │   ├── __init__.py
│   │   ├── prompts.py             # 2-sentence icebreaker & emergency roof repair pain-point templates
│   │   ├── template_engine.py     # Deterministic Jinja2 rule generator (100% offline testable)
│   │   ├── llm_engine.py          # External LLM provider adapter with fallback
│   │   └── generator.py           # Populates Cols R, S and staging Cols V through Z
│   ├── dispatcher/                # Milestone 4: Agent 4
│   │   ├── __init__.py
│   │   ├── safety_gate.py         # Staged review gate (Drafted -> Approved requiring --confirm)
│   │   ├── email_client.py        # MIME email client (SMTP + Dry-Run Simulator)
│   │   ├── whatsapp_client.py     # wa.me click-to-chat URL builder & phone encoder
│   │   ├── pacing.py              # Humanized randomized delay (45-180s) & daily cap enforcement
│   │   └── orchestrator.py        # Outbound dispatch executor & Lead Status / Touch 1 Date updater
│   └── cli.py                     # Unified CLI entrypoint with subcommands (scrape, ingest, personalize, dispatch, pipeline)
├── tests/                         # E2E & Integration Test Track
│   ├── e2e/
│   │   ├── test_tier1_features.py
│   │   ├── test_tier2_boundaries.py
│   │   ├── test_tier3_pairwise.py
│   │   └── test_tier4_workloads.py
│   ├── unit/
│   │   ├── test_scraper.py
│   │   ├── test_crm.py
│   │   ├── test_personalizer.py
│   │   └── test_dispatcher.py
│   └── run_all_tests.py
├── PROJECT.md
└── ORIGINAL_REQUEST.md
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Playwright Chrome Scraper | Headless Chrome with anti-bot flags navigating Google Maps search feeds | M1 | R1, Survey |
| 2 | Multi-State Search Catalog | Targeted metro queries for TX, FL, OH, GA, AZ yielding >=25 distinct roofers | M1 | R1, Acceptance Criteria |
| 3 | Core Data Field Extraction | Extract business name, phone, city, state, zip, review count, rating, specialty | M1 | R1 |
| 4 | Strict Website Filtering | Discard custom domains (.com, .io, .net, .co); capture No Website & Socials | M1 | R1, Acceptance Criteria |
| 5 | Trade Specialty Classifier | Categorize into residential, commercial, storm repair, leak repair | M1 | R1, Survey |
| 6 | Google Sheets OAuth & Client | Direct REST API integration with token auto-refresh and CLI fallback | M2 | R2, Survey |
| 7 | 21-Column CRM Schema Ingestion | Append leads into Leads Tracker Cols A–U preserving formula ranges A2:T495 | M2 | R2, Acceptance Criteria |
| 8 | Business Name & Phone Deduplication | Normalize legal suffixes/punctuation and 10-digit phones; zero duplicate rows | M2 | R2, Acceptance Criteria |
| 9 | Lead Scoring & Priority Tagging | Assign 🔥 High (>10 reviews without website), ⚡ Medium, ❄️ Low, and deal value | M2 | R2, Survey |
| 10 | 2-Sentence Icebreaker Generator | Mention exact city/metro, specialty, and competitor Maps ranking revenue loss | M3 | R3, Acceptance Criteria |
| 11 | Zero Placeholder Assurance | Guarantee 0 unparsed tags ({{City}}, {{Name}}) in final generated copy | M3 | R3, Acceptance Criteria |
| 12 | Staging Columns Storage | Store subject, body, WhatsApp message, wa.me link, approval status in Cols V–Z | M3 | R3, Survey |
| 13 | Dual-Engine Architecture | External LLM with deterministic Jinja2 fallback for 100% offline reliability | M3 | R3, Survey |
| 14 | Staged Approval Safety Gate | Default status Drafted / Ready for Review; require explicit confirmation to send | M4 | R4, Acceptance Criteria |
| 15 | Cold Email Channel & Simulator | SMTP email dispatcher with dry-run simulator logging dispatches | M4 | R4, Acceptance Criteria |
| 16 | WhatsApp Click-to-Chat Fallback | Generate pre-populated `https://wa.me/<phone>?text=<msg>` for phone-only leads | M4 | R4, Acceptance Criteria |
| 17 | Humanized Pacing & Daily Cap | Random 45–180s delay between dispatches and configurable daily send limit (25) | M4 | R4, Acceptance Criteria |
| 18 | CRM Dispatch State Updater | Automatically update Col A to `Contacted (Touch 1)` and Col O to `Touch 1 Date` | M4 | R4 |
| 19 | E2E Test Suite (Tiers 1–4) | Requirement-driven test suite with >=11×N test cases covering all features | E2E Track | Acceptance Criteria |
| 20 | Final Integration & Adversarial Hardening | Pass 100% E2E tests + Tier 5 white-box challenger hardening | Final Milestone | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Google Maps Extraction Engine | Scraper, browser manager, website filter, multi-state catalog, normalizer | none | DONE (437 tests passing, Gate PASS) |
| M2 | Google Sheets CRM & Deduplication | Sheets API client, deduplication engine, schema mapping, lead scoring | M1 interface | DONE (564 tests passing, Gate PASS) |
| M3 | AI Personalization & Hook Generator | 2-sentence icebreaker, revenue pain point, staging columns V–Z, dual engine | M2 interface | DONE (840 tests passing, Gate PASS) |
| M4 | Humanized Outreach Dispatch Engine | Staged approval gate, cold email + simulator, wa.me fallback, pacing, status update | M3 interface | DONE (1,021 tests passing, Gate PASS) |
| E2E | E2E Testing Suite (Tiers 1–4) | Opaque-box test harness, runner, and test cases covering all 18 features | none | DONE (203 tests passing, TEST_READY.md published) |
| M-Final | Final Verification & Hardening | Phase 1: 100% pass of E2E suite; Phase 2: Tier 5 adversarial coverage hardening | M1, M2, M3, M4, E2E | DONE (100% E2E pass, 1,021 tests, CLEAN audit) |

## Interface Contracts

### M1 (Scraper) ↔ M2 (CRM Ingestion)
```python
# Output of M1 / Input to M2
class RawLead(BaseModel):
    business_name: str              # e.g. "General Roofing & Restoration"
    cleaned_phone: str              # e.g. "9038070683" (10 digits)
    phone_display: str              # e.g. "(903) 807-0683"
    city: str                       # e.g. "Tyler"
    state: str                      # e.g. "TX"
    zip_code: str                   # e.g. "75701"
    review_count: int               # e.g. 13
    star_rating: float              # e.g. 5.0
    specialty: str                  # e.g. "Storm Damage & Re-roofing"
    website_status: str             # "None (No Website)" or "None (No Website - Social Only)"
    website_url: Optional[str]      # None or social directory URL
    place_url: str                  # Google Maps URL
```

### M2 (CRM Ingestion) ↔ M3 (Personalization)
```python
# Output of M2 / Input to M3
class CRMRecord(BaseModel):
    row_index: int                  # 1-indexed row number in Google Sheet (e.g. 14)
    lead_status: str                # "Not Contacted"
    priority: str                   # "🔥 High", "⚡ Medium", "❄️ Low"
    company_name: str               # "General Roofing & Restoration"
    website: str                    # "None (No Website)"
    industry_niche: str             # "Storm Damage & Re-roofing"
    company_size: str               # "1-10"
    contact_first_name: str         # "Roofing Team" or name
    contact_last_name: str          # "Contractor"
    job_title: str                  # "Owner / Contractor"
    work_email: str                 # email or "Call: (903) 807-0683"
    email_verification: str         # "Verified" or "Unverified"
    linkedin_profile: str           # Maps place URL or social
    location: str                   # "Tyler, TX (CST)"
    outreach_channel: str           # "Cold Email" or "Cold Call"
    est_deal_value: int             # 4000
    notes_and_next_steps: str       # "Phone: (903) 807-0683..."
```

### M3 (Personalization) ↔ M4 (Outreach Dispatch)
```python
# Output of M3 / Input to M4
class OutreachDraft(BaseModel):
    crm_record: CRMRecord
    icebreaker: str                 # 2-sentence personalized hook
    offer_angle: str                # Specific competitor revenue loss angle
    staged_email_subject: str       # Cold email subject
    staged_email_body: str          # Formatted cold email body
    staged_whatsapp_msg: str        # Formatted mobile copy
    staged_wame_url: str            # https://wa.me/19038070683?text=...
    approval_status: str            # "Drafted / Ready for Review"
```

### M4 (Outreach Dispatch) ↔ CRM State
Upon approved dispatch:
- Column A (`Lead Status`): Transition from `"Not Contacted"` to `"Contacted (Touch 1)"`.
- Column O (`Touch 1 Date`): Stamp current UTC date `"YYYY-MM-DD"`.
- Column U (`Notes & Next Steps`): Append `"Dispatched via <channel> on <date>."`.
- Staging Column Z (`Outreach Approval Status`): Transition from `"Drafted / Ready for Review"` to `"Dispatched"`.
