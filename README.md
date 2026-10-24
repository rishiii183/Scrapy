# 🌐 Scrapy — Universal Google Maps Lead Scraper & AI Outreach Pipeline

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-stealth-green.svg)](https://playwright.dev/)
[![Tests](https://img.shields.io/badge/tests-1040%20passing-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An automated, open-source 4-agent lead generation and cold outreach pipeline. Discovers local businesses across US cities on Google Maps, filters strictly by website status (e.g. no website or social profiles only), synchronizes verified leads into a central Google Sheets CRM, drafts bespoke personalized value propositions, and delivers humanized cold email and WhatsApp click-to-chat outreach.

---

## 🚀 Key Features

- **🎯 Any Niche or Industry**: General pipeline designed for any trade or local service—plumbers, roofers, HVAC, dentists, electricians, mechanics, landscapers, lawyers, and more.
- **🧙‍♂️ Interactive Questionnaire Wizard**: Simply launch `python -m src.cli` and an interactive CLI asks which niche, locations, data fields, and website filters you want to extract.
- **🔍 Anti-Bot Google Maps Scraper**: Playwright Chromium automation with browser stealth flags (`--disable-blink-features=AutomationControlled`), infinite scroll hydration, card DOM parsing, and NANP 10-digit phone cleaner.
- **🛡️ Strict Website Qualification Filters**:
  - `missing_website` (default): Captures businesses with no website OR only social/directory pages (Facebook, Yelp, Angi, etc.), discarding custom domains.
  - `no_website_strict`: Captures strictly businesses without any website or social URL.
  - `social_only`: Focuses exclusively on businesses whose only presence is a social profile.
  - `all`: Extracts all discovered businesses regardless of website status.
- **📊 Google Sheets CRM Ingestion & Deduplication**: Appends leads into your Google Sheet, preserving formula ranges and deduplicating by normalized business name and phone number.
- **✍️ AI Personalization Engine**: Dual-engine (deterministic Jinja2 + LLM) generating 2-sentence icebreakers highlighting local competitor rankings on Google Maps and organic search revenue loss.
- **📬 Humanized Outreach & Safety Gate**: Staged review mode (`Drafted / Ready for Review`), randomized anti-spam jitter delays (45–180s), daily send caps, and automatic WhatsApp `wa.me` fallback for mobile phone numbers.

---

## 📦 Architecture

```
[Agent 1: Extraction Engine]
    ├── Playwright Stealth Browser
    ├── Multi-State Query Catalog (TX, FL, OH, GA, AZ, CA, NY, etc.)
    └── Website & Social Qualification Filters
           │
           ▼ (QualifiedLead)
[Agent 2: CRM Ingestor & Deduplicator]
    ├── Business Name & 10-Digit Phone Normalizer
    ├── Formula-Preserving Google Sheets REST Client
    └── Lead Scoring (High, Medium, Low + Deal Value)
           │
           ▼ (CRMRecord)
[Agent 3: AI Personalizer & Hook Generator]
    ├── Deterministic Jinja2 / LLM Engine
    ├── 2-Sentence Icebreaker & Competitor Revenue Loss Hook
    └── Staging into Columns V–Z (Email Subject, Body, WhatsApp URL)
           │
           ▼ (OutreachDraft)
[Agent 4: Humanized Outreach Dispatcher]
    ├── Staged Approval Safety Gate (Confirmation Required)
    ├── Cold Email SMTP Client & Dry-Run Simulator
    ├── WhatsApp Click-to-Chat Fallback (wa.me)
    └── Humanized Delay Pacing (45–180s) & Daily Send Caps
```

---

## 🛠️ Quickstart Installation

### 1. Clone the repository
```bash
git clone https://github.com/rishiii183/Scrapy.git
cd Scrapy
```

### 2. Create and activate a virtual environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## 🎮 Usage Guide

### Mode 1: Interactive Questionnaire Wizard (Recommended)
Run the pipeline without arguments to launch the step-by-step interactive configuration:

```bash
python -m src.cli
```
*Or explicitly:*
```bash
python -m src.cli interactive
```

You will be prompted:
1. **Target Niche**: Enter any category (`plumbers`, `roofers`, `dentists`, `HVAC`, `electricians`, etc.).
2. **Locations**: Target states or cities (`TX FL OH`, `Austin TX, Miami FL`, etc.).
3. **Data Fields**: Full profile, contact focus, or high-review leads.
4. **Website Filter**: Missing website only, strictly no website, social only, or all businesses.
5. **Execution Flow**: Scrape only, Scrape & Ingest to CRM, or Full Pipeline.

---

### Mode 2: Non-Interactive CLI Commands

#### Scrape Google Maps for Any Niche
```bash
# Scrape plumbers in Texas and Florida without websites (Limit: 25)
python -m src.cli scrape --niche plumbers --states TX FL --limit 25

# Scrape dentists with social-only profiles
python -m src.cli scrape --niche dentists --filter social_only --limit 15

# Quick test with offline mock fixtures
python -m src.cli scrape --mock --limit 10
```

#### Ingest Leads into Google Sheets CRM
```bash
python -m src.cli ingest --input data/extracted_leads.json --dry-run
```

#### Generate Personalized Outreach Copy
```bash
python -m src.cli personalize --niche plumbers --dry-run
```

#### Run Full End-to-End Pipeline
```bash
# Full dry-run simulation
python -m src.cli pipeline --niche "HVAC" --states TX FL --dry-run

# Full pipeline with staged review
python -m src.cli pipeline --niche plumbers --limit 20
```

---

## 🧪 Testing & Verification

The test suite contains **1,040 automated tests** covering all features, edge cases, boundaries, and adversarial challenges.

```bash
# Run full test suite
pytest tests/ -v

# Run 4-tier master E2E test runner
python tests/run_all_tests.py
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
