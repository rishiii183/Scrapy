# Scrapy: Universal Google Maps Lead Scraper & Outreach Pipeline

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-stealth-green.svg)](https://playwright.dev/)
[![Tests](https://img.shields.io/badge/tests-1040%20passing-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An open-source, multi-agent lead generation and automated outreach pipeline. Scrapy extracts local business profiles across Google Maps in any US state or city, filters prospects based on website status (targeting businesses without websites or with social profiles only), normalizes and scores leads, synchronizes records into a structured 26-column Google Sheets CRM, creates personalized outreach messages, and executes humanized cold email and WhatsApp dispatch with safety controls.

---

## Table of Contents

- [Core Capabilities](#core-capabilities)
- [System Architecture](#system-architecture)
  - [Architectural Flow Diagram](#architectural-flow-diagram)
  - [The 4-Agent Pipeline Breakdown](#the-4-agent-pipeline-breakdown)
  - [Google Sheets 26-Column CRM Schema](#google-sheets-26-column-crm-schema)
- [How It Works: Step-by-Step](#how-it-works-step-by-step)
  - [1. Extraction & Anti-Bot Stealth](#1-extraction--anti-bot-stealth)
  - [2. Website Qualification & Filtering Modes](#2-website-qualification--filtering-modes)
  - [3. Normalization, Deduplication & Scoring](#3-normalization-deduplication--scoring)
  - [4. AI Personalization & Hook Generation](#4-ai-personalization--hook-generation)
  - [5. Staged Safety Gate & Dispatch Engine](#5-staged-safety-gate--dispatch-engine)
- [Installation & Quickstart](#installation--quickstart)
  - [Prerequisites](#prerequisites)
  - [Setup Steps](#setup-steps)
  - [Configuration (.env)](#configuration-env)
- [Usage Guide](#usage-guide)
  - [Interactive Questionnaire Wizard](#interactive-questionnaire-wizard)
  - [CLI Reference](#cli-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Core Capabilities

- **Versatile Niche Support**: Not restricted to a single industry. Extract leads for plumbers, roofers, electricians, HVAC contractors, dentists, mechanics, landscapers, lawyers, accountants, or custom trade categories.
- **Interactive Questionnaire Wizard**: An interactive terminal wizard (`python -m src.cli interactive`) guides users through configuring niche selection, target markets, extracted fields, and qualification rules.
- **Stealth Automation**: Playwright-powered headless Chromium instance configured with anti-detection flags (`--disable-blink-features=AutomationControlled`), realistic user agents, and scroll pacing to navigate Google Maps without triggering bot challenges.
- **Granular Website Filtering**: Filter out businesses with custom domain websites and isolate prospects operating without a website or relying solely on social media directories (Facebook, Instagram, Yelp, Angi, etc.).
- **Google Sheets CRM Sync**: Directly appends leads into a 26-column Google Sheets spreadsheet with formula preservation, duplicate detection, and automated lead scoring.
- **Dual-Mode Copywriting Engine**: Jinja2 deterministic templates coupled with optional LLM generation to produce targeted, 2-sentence icebreakers referencing local competitor rankings and search visibility.
- **Staged Outreach Safety Gate**: Two-phase safety mechanism preventing unintended dispatches. Requires explicit confirmation, randomized delivery pacing (45 to 180 seconds), daily send limits, and WhatsApp click-to-chat fallback for mobile numbers.

---

## System Architecture

### Architectural Flow Diagram

```
+-------------------------------------------------------------------------------+
|                                USER INTERFACE                                 |
|                                                                               |
|   Interactive Questionnaire Wizard             Direct CLI Commands            |
|   (python -m src.cli interactive)             (python -m src.cli [subcommand])|
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                       AGENT 1: EXTRACTION & FILTERING                         |
|                                                                               |
|  [Query Catalog Engine]  -->  [Playwright Stealth Browser]                    |
|  * Niche + City Combos        * Headless Chromium                             |
|  * 50 US State Markets        * Infinite Scroll & Card Parser                 |
|                               * Rate Limiting & DOM Extraction                |
|                                      |                                        |
|                                      v                                        |
|                         [Website & Social Filter]                             |
|                         * Missing Website / Social Only / Strict              |
|                         * Directory Classifier (Yelp, FB, Angi)               |
+-------------------------------------------------------------------------------+
                                      |
                                      v (QualifiedLead)
+-------------------------------------------------------------------------------+
|                     AGENT 2: CRM INGESTION & DEDUPLICATION                    |
|                                                                               |
|  [Normalizer]            -->  [Deduplication Engine]  -->  [Lead Scorer]      |
|  * 10-Digit NANP Phone        * Composite Key Index        * Review Volume    |
|  * Clean Business Name        * Fuzzy Levenshtein Match    * Rating & Deal Val|
|                                      |                                        |
|                                      v                                        |
|                          [Google Sheets REST API]                             |
|                          * 26-Column CRM Schema (A-Z)                         |
|                          * In-Place Formula Preservation                      |
+-------------------------------------------------------------------------------+
                                      |
                                      v (CRMRecord)
+-------------------------------------------------------------------------------+
|                     AGENT 3: AI PERSONALIZATION ENGINE                        |
|                                                                               |
|  [Deterministic Jinja2 Engine]        OR        [LLM Generative Engine]       |
|  * Local Competitor Angle                       * OpenAI / Anthropic / Gemini |
|  * Niche Service Hook Generation                * Context-Aware Icebreakers   |
|                                      |                                        |
|                                      v                                        |
|                        [Outreach Package Staging]                             |
|                        * Email Subject & Body                                 |
|                        * WhatsApp Direct Link (wa.me)                         |
|                        * Staged in Cols V-Z with Status: 'Ready for Review'   |
+-------------------------------------------------------------------------------+
                                      |
                                      v (OutreachDraft)
+-------------------------------------------------------------------------------+
|                     AGENT 4: HUMANIZED DISPATCH ENGINE                        |
|                                                                               |
|  [Safety Gate Controller]             [Pacing & Anti-Spam Controller]         |
|  * Mandatory Staged Confirmation      * Randomized Jitter (45-180s)           |
|  * Daily Send Cap Enforcement         * Error Boundary Isolation              |
|                                      |                                        |
|                   +------------------+------------------+                     |
|                   |                                     |                     |
|                   v                                     v                     |
|          [SMTP Email Client]                 [WhatsApp Click-to-Chat]         |
|          * Authenticated Delivery            * Pre-filled Encoded URL         |
|          * Dry-Run Simulation Mode           * Mobile Direct Dispatch         |
+-------------------------------------------------------------------------------+
```

---

### The 4-Agent Pipeline Breakdown

| Agent | Module Path | Primary Responsibility | Input Contract | Output Contract |
| :--- | :--- | :--- | :--- | :--- |
| **1. Scraper & Filter** | `src/scraper/` | Extracts local cards from Google Maps; filters out businesses with existing web properties. | Search queries (niche, location, filter mode) | `List[QualifiedLead]` |
| **2. CRM Ingestor** | `src/crm/` | Normalizes phone/name fields, prevents duplicate entries, and appends to Google Sheets. | `List[QualifiedLead]` | `List[CRMRecord]` |
| **3. AI Personalizer** | `src/personalizer/` | Drafts targeted 2-sentence icebreakers and packages messages into review columns. | `List[CRMRecord]` | `List[OutreachDraft]` |
| **4. Dispatcher** | `src/dispatcher/` | Verifies approvals, paces transmissions, and delivers cold emails or WhatsApp links. | `List[OutreachDraft]` | `DispatchSummary` |

---

### Google Sheets 26-Column CRM Schema

Each record is mapped to a standardized 26-column schema (Columns A through Z), allowing outreach campaigns to run directly from Google Sheets:

| Col | Field Header | Data Description | Sample Value |
| :---: | :--- | :--- | :--- |
| **A** | `Timestamp` | Ingestion timestamp (ISO 8601) | `2026-10-25T00:15:00` |
| **B** | `Business Name` | Raw business name from Google Maps | `Apex Plumbing & Drain Solutions LLC` |
| **C** | `Normalized Name` | Normalized, suffix-stripped name | `Apex Plumbing & Drain Solutions` |
| **D** | `Phone` | Raw scraped phone number | `(512) 555-0198` |
| **E** | `Normalized Phone` | Clean 10-digit NANP format | `5125550198` |
| **F** | `Address` | Street address or service area | `100 Congress Ave, Austin, TX` |
| **G** | `City` | Extracted city name | `Austin` |
| **H** | `State` | 2-letter state code | `TX` |
| **I** | `Zip Code` | Postal code | `78701` |
| **J** | `Rating` | Star rating (0.0 - 5.0) | `4.8` |
| **K** | `Review Count` | Total number of Google reviews | `47` |
| **L** | `Google Maps URL` | Direct Google Maps place link | `https://maps.google.com/?cid=...` |
| **M** | `Website Found` | Boolean indicating website link presence | `False` |
| **N** | `Website Status` | Classification result | `Missing Website` |
| **O** | `Social URL` | Fallback social profile link | `https://facebook.com/apexplumbing` |
| **P** | `Specialty` | Trade specialty category | `Emergency Drain Cleaning` |
| **Q** | `Niche` | Primary business niche | `Plumbers` |
| **R** | `Lead Score` | Calculated priority score | `High` |
| **S** | `Priority` | Processing tier | `Tier 1` |
| **T** | `Est. Deal Value` | Estimated contract value | `$3,500` |
| **U** | `Pipeline Status` | State (`Scraped`, `Ingested`, `Staged`, `Sent`) | `Staged` |
| **V** | `Outreach Angle` | Selected personalization angle | `Local Search Revenue Loss` |
| **W** | `Email Subject` | Personalized email subject line | `Quick question regarding Austin search visibility` |
| **X** | `Email Body` | 2-sentence icebreaker and pitch | `Hi Apex team, noticed you have 47 reviews in Austin...` |
| **Y** | `WhatsApp Link` | Generated `wa.me` click-to-chat URL | `https://wa.me/15125550198?text=...` |
| **Z** | `Dispatch Status` | Outreach status | `Drafted / Ready for Review` |

---

## How It Works: Step-by-Step

### 1. Extraction & Anti-Bot Stealth

1. **Browser Initialization**: The `BrowserManager` launches a headless Chromium instance via Playwright with stealth configurations:
   - Command line flag `--disable-blink-features=AutomationControlled` removes automation markers from the browser navigator object.
   - Rotates realistic Desktop user agents and configures consistent viewport dimensions (1920x1080).
2. **Query Execution**: `QueryCatalog` constructs geographically targeted search queries based on selected niche and location (e.g., `"plumbers in Austin TX"`, `"emergency roofers in Miami FL"`).
3. **Feed Hydration**: Navigates to Google Maps search results, locates the scrollable feed container (`div[role='feed']`), and initiates mouse wheel scrolling. It waits for DOM network idle states between scroll events to trigger progressive loading.
4. **Card Parsing**: Iterates through listing cards, extracting text content, accessibility labels, rating attributes, phone text, and outbound links.

### 2. Website Qualification & Filtering Modes

The extraction pipeline qualifies prospects through `classify_website()`. It analyzes outbound URLs against known domain lists:

- **Missing Website Mode (`missing_website`, default)**:
  - If no website URL exists: **Qualified**.
  - If URL matches a social directory (Facebook, Instagram, LinkedIn, Yelp, YellowPages, BBB, Angi, Houzz): **Qualified** (marked as `social_only`).
  - If URL points to a standalone custom domain (`exampleplumbing.com`): **Discarded**.
- **Strictly No Website Mode (`no_website_strict`)**:
  - Requires that the business has neither a custom domain nor a social profile link.
- **Social Only Mode (`social_only`)**:
  - Specifically targets businesses whose only digital web footprint is a social page or directory listing.
- **All Businesses Mode (`all`)**:
  - Captures every listing regardless of website presence, useful for general data enrichment.

### 3. Normalization, Deduplication & Scoring

1. **Data Normalization**:
   - Phone numbers are sanitized into 10-digit North American Numbering Plan (NANP) digits: `(512) 555-0198` -> `5125550198`.
   - Business names are stripped of legal entity suffixes (`LLC`, `Inc`, `Corp`, `Co`, `Services`, `Group`) and punctuation for clean indexing.
2. **Multi-Level Deduplication**:
   - Level 1: In-memory deduplication during scraping batches using a composite key (`normalized_name::normalized_phone`).
   - Level 2: Cross-check against the existing Google Sheet to avoid duplicate entries.
   - Level 3: Fuzzy matching via normalized token comparison to detect minor spelling variations.
3. **Lead Quality Scoring**:
   - **High Score**: Businesses with >15 reviews, rating >= 4.0, a valid phone number, and no website. (Estimated Deal Value: $2,500 - $5,000).
   - **Medium Score**: Businesses with 5-14 reviews or a social-only website.
   - **Low Score**: Businesses with <5 reviews or missing phone numbers.

### 4. AI Personalization & Hook Generation

1. **Context Construction**: Assembles metadata including business name, owner name (if found), city, review count, rating, and classified specialty.
2. **Dual Copywriting Path**:
   - **Deterministic Engine (Jinja2)**: Uses validated templates designed to maintain low spam scores. Generates a 2-sentence hook highlighting local search competition:
     > *"Hi Apex team, saw your 47 reviews and 4.8-star reputation in Austin. Noticed you do not have an active website listed on Google Maps, meaning competitors like Austin City Plumbing are capturing local organic calls when homeowners search for emergency drain service."*
   - **Generative LLM Engine**: Can optionally call OpenAI / Anthropic / Gemini API endpoints using structured system prompts for custom phrasing.
3. **Staging**: Stored in Columns V through Z of the CRM with dispatch status set to `Drafted / Ready for Review`. Messages are never sent automatically during ingestion.

### 5. Staged Safety Gate & Dispatch Engine

1. **Safety Gate Verification**:
   - Requires explicit human approval via the `--confirm-dispatch` flag or interactive prompt.
   - Enforces `DAILY_SEND_CAP` (default: 25 messages per 24 hours) to protect sender domain reputation.
   - Verifies phone/email format validity before scheduling.
2. **Humanized Delivery Pacing**:
   - `PacingController` injects randomized jitter intervals between 45 and 180 seconds between consecutive dispatches.
3. **Delivery Channels**:
   - **Cold Email**: Delivers via standard authenticated SMTP with multipart plain text and HTML formatting. Supports dry-run simulation mode.
   - **WhatsApp Click-to-Chat**: Generates pre-populated WhatsApp links (`https://wa.me/1<phone>?text=<encoded_body>`), allowing sales representatives to open conversations on mobile or desktop WhatsApp with a single click.

---

## Installation & Quickstart

### Prerequisites

- Python 3.10 or higher
- Google Cloud Platform Service Account JSON key (for Google Sheets CRM integration)
- Google Chrome or Chromium (installed automatically by Playwright)

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/rishiii183/Scrapy.git
cd Scrapy

# 2. Set up virtual environment
python -m venv .venv

# Activate on Windows:
.\.venv\Scripts\activate
# Activate on Linux/macOS:
# source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser binaries
playwright install chromium
```

### Configuration (.env)

Copy the sample environment configuration file:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```ini
# Google Sheets CRM Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_TAB_NAME=Leads Tracker
GOOGLE_APPLICATION_CREDENTIALS=credentials/service_account.json

# Outreach Email Configuration (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_specific_password
SENDER_NAME=Your Name
SENDER_EMAIL=your_email@gmail.com

# Safety Gate & Outreach Limits
DAILY_SEND_CAP=25
MIN_DELAY_SECONDS=45
MAX_DELAY_SECONDS=180
DRY_RUN_DEFAULT=true

# AI Copywriting (Optional)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

---

## Usage Guide

### Interactive Questionnaire Wizard

The simplest way to use the pipeline is through the interactive wizard. Start the wizard with:

```bash
python -m src.cli
```
*or explicitly:*
```bash
python -m src.cli interactive
```

The wizard will guide you through:
1. **Target Niche**: Enter any industry (`plumbers`, `dentists`, `HVAC`, `electricians`, `roofers`, `lawyers`).
2. **Target States or Cities**: Specify locations (`TX FL OH`, `Austin TX, Miami FL`).
3. **Data Field Profile**: Choose between Full Lead Profile, Contact Details Focus, or High-Review Focus.
4. **Website Filter**: Select `missing_website`, `no_website_strict`, `social_only`, or `all`.
5. **Execution Mode**: Choose Scrape Only, Scrape & Ingest to CRM, or Full Pipeline.

---

### CLI Reference

You can also run Scrapy using explicit command-line flags for scripting or automation:

#### 1. Scrape Leads
```bash
# Scrape plumbers in Texas and Florida without websites (Limit: 25 leads)
python -m src.cli scrape --niche plumbers --states TX FL --limit 25

# Scrape dentists with social-only profiles
python -m src.cli scrape --niche dentists --filter social_only --limit 15

# Scrape using mock fixtures (offline test mode)
python -m src.cli scrape --mock --limit 10
```

#### 2. Ingest Leads into Google Sheets CRM
```bash
# Preview ingestion in dry-run mode
python -m src.cli ingest --input data/extracted_leads.json --dry-run

# Commit leads to Google Sheets
python -m src.cli ingest --input data/extracted_leads.json
```

#### 3. Personalize Leads
```bash
# Generate icebreakers for ingested leads (dry run)
python -m src.cli personalize --niche plumbers --dry-run

# Write personalized copy into Columns V-Z of the Google Sheet
python -m src.cli personalize --niche plumbers
```

#### 4. Dispatch Outreach
```bash
# Test delivery pipeline in safe dry-run mode
python -m src.cli dispatch --dry-run

# Send live messages with safety confirmation
python -m src.cli dispatch --confirm-dispatch --max-sends 15
```

#### 5. Full End-to-End Pipeline
```bash
# Run entire flow (Scrape -> Ingest -> Personalize -> Review) in dry-run mode
python -m src.cli pipeline --niche "HVAC" --states TX FL --limit 20 --dry-run
```

---

## Testing & Quality Assurance

Scrapy includes an automated test suite with **1,040 tests** covering unit functionality, adversarial input edge cases, and end-to-end integration across four tiers:

- **Tier 1 (Feature Coverage)**: 90 tests verifying core extraction, normalization, and CRM ingestion.
- **Tier 2 (Boundary & Corner Cases)**: 90 tests validating malformed phone numbers, missing names, duplicate payloads, and extreme review counts.
- **Tier 3 (Cross-Feature Combinations)**: 15 tests exercising multi-niche combinations and multi-state query matrices.
- **Tier 4 (Real-World Workloads)**: 8 tests simulating full-scale continuous extraction and safety gate throttling.

### Running Tests

```bash
# Run complete test suite
pytest tests/ -v

# Run fast four-tier E2E runner
python tests/run_all_tests.py
```

---

## Project Structure

```
Scrapy/
├── .env.example                 # Environment configuration template
├── .gitignore                   # Git ignore specifications
├── LICENSE                      # MIT License
├── README.md                    # Project documentation
├── requirements.txt             # Pinned project dependencies
│
├── data/
│   └── extracted_leads.json     # Default output for extracted leads
│
├── src/
│   ├── __init__.py
│   ├── cli.py                   # Unified CLI & Interactive Wizard
│   ├── config.py                # Configuration loader & constants
│   ├── models.py                # Pydantic data models & contracts
│   │
│   ├── scraper/                 # AGENT 1: Maps Scraper & Filter
│   │   ├── browser_manager.py   # Playwright stealth browser lifecycle
│   │   ├── filters.py           # Website qualification & directory logic
│   │   ├── maps_extractor.py    # Google Maps DOM card parsing
│   │   ├── normalizer.py        # Business name & phone sanitization
│   │   └── query_catalog.py     # Dynamic query & metro matrix generator
│   │
│   ├── crm/                     # AGENT 2: CRM Ingestor & Deduplication
│   │   ├── dedup.py             # Multi-level deduplication engine
│   │   ├── ingestor.py          # Google Sheets ingestion controller
│   │   ├── lead_scorer.py       # Lead scoring & deal valuation
│   │   ├── schema.py            # 26-column Google Sheet mapping
│   │   └── sheets_client.py     # Google Sheets v4 API wrapper
│   │
│   ├── personalizer/            # AGENT 3: AI Copywriting & Hook Generator
│   │   ├── generator.py         # Outreach package generator
│   │   ├── llm_engine.py        # LLM integration client
│   │   ├── prompts.py           # Copywriting templates
│   │   └── template_engine.py   # Jinja2 deterministic rendering engine
│   │
│   └── dispatcher/              # AGENT 4: Humanized Outreach Dispatcher
│       ├── email_client.py      # Authenticated SMTP email delivery
│       ├── orchestrator.py      # Dispatch workflow coordinator
│       ├── pacing.py            # Randomized anti-spam delivery pacing
│       ├── safety_gate.py       # Approval safety gate & send cap
│       └── whatsapp_client.py   # WhatsApp click-to-chat generator
│
└── tests/                       # 1,040 Automated Test Suite
    ├── conftest.py              # Pytest fixtures and mocks
    ├── run_all_tests.py         # 4-tier E2E test runner
    ├── e2e/                     # End-to-end integration tiers 1-4
    └── unit/                    # Unit tests for all agent modules
```

---

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`.
3. Ensure all tests pass: `python tests/run_all_tests.py`.
4. Commit your changes: `git commit -m "feat: description of change"`.
5. Push to the branch: `git push origin feature/your-feature-name`.
6. Open a Pull Request.

---

## License

This project is open-source and licensed under the [MIT License](LICENSE).
