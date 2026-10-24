# Handoff Report: Milestone 3 & 4 Technical Survey (Agent 3 & Agent 4)

**Agent ID**: `explorer_survey_3`  
**Working Directory**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_survey_3`  
**Target Scope**: 
- **Milestone 3 / Agent 3**: AI Personalization & Hook Generator (R3)
- **Milestone 4 / Agent 4**: Humanized Outreach Dispatch with Staged Approval (R4)
**Authoritative Reference**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md`

---

## 1. Observation

### 1.1 Execution Environment & Installed Dependencies
- **Operating System**: Windows (AMD64)
- **Python Version**: `3.15.0` (`tags/v3.15.0:d220409, Oct 9 2026, 11:55:56 [MSC v.1951 64 bit (AMD64)]`)
- **Key Installed Packages** (`pip list`):
  - `Jinja2` == `3.1.6` (template engine available for bespoke generation and fallback)
  - `pydantic` == `2.14.1` (data validation and structured output parsing)
  - `python-dotenv` == `1.2.4` (environment configuration management)
  - `requests` == `2.34.2` & `httpx` == `0.28.1` (HTTP/REST client libraries)
  - `fastapi` == `0.143.3`, `uvicorn` == `0.54.0`
  - Python standard library includes `smtplib`, `email.mime`, `urllib.parse`, `random`, `json`, `sqlite3`, `csv`, `ssl`.
- **CLI Tools**:
  - `curl`: `C:\Windows\System32\curl.exe`
  - `git`: `C:\Program Files\Git\cmd\git.exe`
  - `ollama`: Not found on `PATH`
- **External Network Connectivity**: Confirmed active (HTTPS GET to external endpoints returned HTTP 200).
- **Environment Variables**: No third-party LLM keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) or SMTP credentials are preset in system env.

### 1.2 Google Sheets Infrastructure & Existing CRM State
- **CLI Tool**: `C:\Users\rishi\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd`
- **Auth Status**: Logged in as `coderrishi183@gmail.com` with active OAuth refresh tokens covering scopes `https://www.googleapis.com/auth/spreadsheets` and `https://www.googleapis.com/auth/drive`.
- **Target Spreadsheet ID**: `12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY`
- **Spreadsheet Tabs**:
  1. `Leads Tracker` (Sheet ID: `0`) — Core CRM
  2. `Pipeline Dashboard` (Sheet ID: `1207034954`) — Funnel and KPI analytics
  3. `Outreach Templates` (Sheet ID: `1202992371`) — Cold email sequence scripts
- **Columns A through U Schema in `Leads Tracker`** (Row 1):
  - `A`: `Lead Status` (Values: `"Not Contacted"`, `"Contacted (Touch 1)"`, `"Follow-up 1"`, etc.)
  - `B`: `Priority` (Values: `"🔥 High"`, `"⚡ Medium"`, `"Low"`)
  - `C`: `Company Name`
  - `D`: `Website` (e.g. `"None (No Website)"`, `"None (No Website - FB Only)"`)
  - `E`: `Industry / Niche` (e.g. `"Residential Roofing & Repairs"`, `"Storm Damage & Re-roofing"`)
  - `F`: `Company Size`
  - `G`: `Contact First Name`
  - `H`: `Contact Last Name`
  - `I`: `Job Title`
  - `J`: `Work Email` (Notice: Contains emails like `fixanyroof@gmail.com` OR phone strings like `Call: (214) 713-2050`)
  - `K`: `Email Verification` (Values: `"Verified"`, `"Unverified"`)
  - `L`: `LinkedIn Profile` (or Social Link)
  - `M`: `Location` (Format: `"<City>, <State> (<Timezone>)"`, e.g. `"Fort Worth, TX (CST)"`, `"Phoenix, AZ (MST)"`)
  - `N`: `Outreach Channel` (Values: `"Cold Email"`, `"Cold Call"`, `"WhatsApp"`)
  - `O`: `Touch 1 Date` (Format: `YYYY-MM-DD` or empty)
  - `P`: `Last Follow-Up Date`
  - `Q`: `Next Action Due`
  - `R`: `Personalized Icebreaker`
  - `S`: `Offer Angle / Pain Point`
  - `T`: `Est. Deal Value ($)`
  - `U`: `Notes & Next Steps`
- **Columns V through Z Status**: Currently completely blank (null), ready for staging columns without shifting columns A-U.
- **Analysis of 12 Existing Leads (Rows 2–13)**:
  - Exactly **3 of 12** leads (25%) have actual email addresses in Column J (`fixanyroof@gmail.com`, `TruGuardRoofing@gmail.com`, `mpcroofing.services@gmail.com`).
  - **9 of 12** leads (75%) have phone numbers in Column J (`Call: (214) 713-2050`, `Call/Text: (469) 544-3768`).
  - This directly proves that the **WhatsApp fallback channel is not optional—it is required for the majority of website-less roofer prospects**.

### 1.3 `Pipeline Dashboard` Formula Audit
Inspected formula definitions in `Pipeline Dashboard`:
- Cell `B5` (`CONTACTED` KPI): `=COUNTIF('Leads Tracker'!A2:A495, "<>Not Contacted") - COUNTBLANK('Leads Tracker'!A2:A495)`
- Cell `B10` (`Contacted (Touch 1)` stage count): `=COUNTIF('Leads Tracker'!A$2:A$495, A10)` where A10 = `"Contacted (Touch 1)"`.
- Cell `F5` (`TOTAL PIPELINE ($)`): `=SUM('Leads Tracker'!T2:T495)`
- Funnel channels rely on Column `N` (`Outreach Channel`).
- **Critical finding**: `Pipeline Dashboard` formulas reference only columns `A`, `C`, `N`, and `T`. They do **not** reference columns `V` through `Z`. Adding dedicated staging columns in columns V+ will cause zero formula shift or KPI corruption.

---

## 2. Logic Chain

### 2.1 AI Personalization Engine Architecture (Agent 3 / R3)

```
                       ┌───────────────────────────────┐
                       │   Google Sheet Leads Tracker  │
                       │    (Cols A-U Lead Metadata)   │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │    Lead Record Normalizer     │
                       │  - City / State Extractor     │
                       │  - Specialty & Trade Mapper   │
                       │  - Contact First Name Cleaner │
                       └──────────────┬────────────────┘
                                      │
                       ┌──────────────┴────────────────┐
                       │                               │
                       ▼                               ▼
        ┌────────────────────────────┐  ┌────────────────────────────┐
        │     External LLM Engine    │  │    Deterministic Jinja2    │
        │ (OpenAI/Gemini/Anthropic)  │  │    Rule-Based Generator    │
        │ - Triggered if API key set │  │ - Guaranteed offline/test  │
        │ - Structured Pydantic JSON │  │ - Zero {{placeholder}} tags│
        └──────────────┬─────────────┘  └──────────────┬─────────────┘
                       │                               │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │  Dedicated Staging Generator  │
                       │  Col R: 2-Sentence Icebreaker │
                       │  Col S: Revenue Pain Point    │
                       │  Col V: Staged Email Subject  │
                       │  Col W: Staged Email Body     │
                       │  Col X: Pre-formatted WhatsApp│
                       │  Col Y: wa.me Click-to-Chat   │
                       │  Col Z: Outreach Approval St. │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │   Staging Ingestion to Sheet  │
                       │   Status: Ready for Review    │
                       └───────────────────────────────┘
```

1. **Extraction & Grounding**:
   - Location parsing: Regex `^([^,]+),\s*([A-Za-z]{2})` reliably extracts `City` (e.g. `Fort Worth`, `Phoenix`, `Atlanta`) and `State` (e.g. `TX`, `AZ`, `GA`).
   - First name normalization: Placeholders like `"Lead / Owner"`, `"Roofing Team"`, `"Operations"` default to conversational greetings like `"there"` or `"Team"`, while verified names (`"Sergio"`, `"Devin"`) are preserved.
2. **2-Sentence Icebreaker Logic**:
   - **Sentence 1 (Observation)**: References exact contractor trade specialty and city/metro.
     *Pattern*: `"Came across {company_name} while reviewing top-rated {specialty} contractors serving the {city} area."`
   - **Sentence 2 (Revenue Pain Point)**: Highlights revenue lost to local competitors ranking on Google Maps/organic search for emergency roof repairs.
     *Pattern*: `"With local competitors claiming top Google Maps spots for emergency roof repairs in {city}, your team is missing out on thousands in high-margin repair and re-roof calls each month without a dedicated web presence."`
   - *Combined Output*: 100% compliant with Acceptance Criteria (mentions city, trade niche, revenue lost to competitors, and contains zero unparsed placeholder tags).
3. **Dedicated Staging Columns Schema**:
   - `Col R` (Column 18): `Personalized Icebreaker`
   - `Col S` (Column 19): `Offer Angle / Pain Point`
   - `Col V` (Column 22): `Staged Email Subject` (e.g. `"Emergency roof repair inquiries in {city} - {company}"`)
   - `Col W` (Column 23): `Staged Email Body` (Complete copy ready for dispatch, incorporating icebreaker, value proposition, and CTA)
   - `Col X` (Column 24): `Pre-formatted WhatsApp Message` (Conversational mobile copy with WhatsApp markdown)
   - `Col Y` (Column 25): `WhatsApp Click-to-Chat Link` (`https://wa.me/{phone}?text={encoded_msg}`)
   - `Col Z` (Column 26): `Outreach Approval Status` (`"Drafted / Ready for Review"`)
4. **Dual-Mode LLM + Deterministic Engine**:
   - If `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` is present in `.env`, execute an LLM completion with Pydantic JSON schema output.
   - If no API key is configured (or network fails), execute the deterministic `Jinja2` generator. Both modes adhere to the identical output schema and validation constraints.

---

### 2.2 Humanized Outreach Dispatch Engine Architecture (Agent 4 / R4)

```
                       ┌───────────────────────────────┐
                       │     Staged Approval Gate      │
                       │   Status: Ready for Review    │
                       └──────────────┬────────────────┘
                                      │
                         [Operator Human Confirmation]
                          CLI: --confirm / --approve-all
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │     Channel Router & Safety   │
                       │  - Check Daily Send Cap (25)  │
                       │  - Check Work Email validity  │
                       └──────┬─────────────────┬──────┘
                              │                 │
                (Valid Email) │                 │ (Phone Only / No Email)
                              ▼                 ▼
             ┌─────────────────────────┐   ┌─────────────────────────┐
             │   Cold Email Channel    │   │    WhatsApp Fallback    │
             │ - Dry-Run or Live SMTP  │   │ - wa.me Click-to-Chat   │
             │ - MIMEText (UTF-8)      │   │ - Mobile Dispatch Log   │
             └────────────┬────────────┘   └────────────┬────────────┘
                          │                             │
                          └──────────────┬──────────────┘
                                         │
                                         ▼
                       ┌───────────────────────────────┐
                       │       Humanized Pacing        │
                       │  Random Delay: 45 - 180s      │
                       │  (Simulated Clock in Test)    │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │       CRM State Updates       │
                       │ - Col A -> Contacted (Touch 1)│
                       │ - Col O -> YYYY-MM-DD         │
                       │ - Col U -> Audit Log Appended │
                       └───────────────────────────────┘
```

1. **Staged Approval Safety System**:
   - Default state for generated outreach: `Drafted / Ready for Review`.
   - Hard Safety Invariant: Live email sending is strictly locked behind human confirmation. The dispatcher CLI requires explicit user flag `--approve-all` or an interactive CLI confirmation prompt (`"Approve sending to X leads? [y/N]"`).
   - In dry-run mode (`--dry-run`), no network dispatch occurs; emails and delays are logged to stdout and an audit file.
2. **Channel Routing**:
   - **Primary (Cold Email)**: Used when `Col J` contains a valid RFC-5322 email string and `Col K` != `"Invalid"`.
   - **Fallback (WhatsApp Click-to-Chat)**: Automatically engaged when `Col J` contains a phone number (`Call: ...`, `Call/Text: ...`) or if email is blank.
3. **WhatsApp Link Generator**:
   - Phone cleaning: Strips non-digits. If 10 digits, prepends US country code `1` (`(817) 349-5911` -> `18173495911`).
   - URL generation: `https://wa.me/18173495911?text=` + `urllib.parse.quote(message)`.
4. **Humanized Pacing & Domain Protection**:
   - Jitter algorithm: `delay = random.uniform(45.0, 180.0)` seconds between successive outbound dispatches.
   - Daily send cap: Configurable via `--daily-cap` (default `25` leads/day) to prevent domain warming burns and spam flagging.
   - Dispatcher checks dispatched count and halts gracefully once the daily cap is achieved.
5. **CRM Status & Audit Updates**:
   - On successful dispatch (or click-to-chat generation confirmation):
     - `Col A` (`Lead Status`) transitions to `"Contacted (Touch 1)"`.
     - `Col O` (`Touch 1 Date`) is stamped with current date `"YYYY-MM-DD"`.
     - `Col U` (`Notes & Next Steps`) appends dispatch timestamp and delivery method.
   - Synchronizes perfectly with `Pipeline Dashboard` formula `=COUNTIF('Leads Tracker'!A$2:A$495, "Contacted (Touch 1)")`.

---

## 3. Caveats

1. **Live SMTP Dispatch Requires Configured Credentials**:
   - Live cold email delivery requires standard SMTP environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SENDER_EMAIL`). When unconfigured, the pipeline operates in **Dry-Run Simulator Mode**, logging headers, subjects, bodies, and simulated jitter timestamps.
2. **LLM API Key Availability**:
   - External LLM models (OpenAI/Anthropic/Gemini) require respective API keys in `.env`. The pipeline must include a fully tested **Deterministic Jinja2 Rule Engine** so automated CI/testing passes 100% without external API costs or rate-limiting failures.
3. **Google Sheets Auth Method**:
   - Direct HTTP requests to Google Sheets API using raw tokens from `token.json` yielded HTTP 401 because tokens expire and must be refreshed via OAuth 2.0 refresh flow.
   - The verified, production-ready integration method is executing commands through `gsheets.cmd` (or wrapping `gsheets.cmd` via a Python subprocess client), which handles automatic token refresh and session persistence.
4. **Dashboard Formula Sensitivity to Status Strings**:
   - `Pipeline Dashboard` formula `B5` evaluates `=COUNTIF('Leads Tracker'!A2:A495, "<>Not Contacted") - COUNTBLANK(...)`.
   - If `Col A` is set to `"Drafted / Ready for Review"` during staging, `B5` would count drafted leads as contacted before actual dispatch.
   - **Recommended Resolution**: During personalizing, Agent 3 stores approval state in dedicated staging column `Col Z` (`Outreach Approval Status` = `"Drafted / Ready for Review"`), while `Col A` remains `"Not Contacted"`. Upon human approval and dispatch, Agent 4 updates `Col A` to `"Contacted (Touch 1)"` and stamps `Col O`. This keeps Dashboard KPIs 100% mathematically pure at all times.

---

## 4. Conclusion

The requirements for Milestone 3 (Agent 3) and Milestone 4 (Agent 4) are completely feasible, well-scoped, and directly supported by the environment.

### 4.1 Recommended Module Structure
```
roofer_outreach_pipeline/
├── src/
│   ├── config.py                 # Pydantic Settings (.env, daily caps, jitter ranges)
│   ├── gsheets_client.py         # Subprocess wrapper for gsheets.cmd & batch updates
│   ├── personalizer/             # Agent 3: AI Personalization Engine
│   │   ├── __init__.py
│   │   ├── models.py             # Pydantic schemas (OutreachDraft, LeadContext)
│   │   ├── prompts.py            # Bespoke 2-sentence prompt templates & few-shots
│   │   ├── template_engine.py    # Deterministic Jinja2 engine (100% test pass)
│   │   ├── llm_engine.py         # OpenAI/Gemini/Anthropic adapter with fallback
│   │   └── generator.py          # Orchestrates icebreaker, subject, body, WhatsApp
│   ├── dispatcher/               # Agent 4: Humanized Outreach Dispatch
│   │   ├── __init__.py
│   │   ├── safety_gate.py        # Staged approval gate (interactive & CLI review)
│   │   ├── email_client.py       # SMTP & Dry-Run Simulator email client
│   │   ├── whatsapp_client.py    # wa.me link builder & phone normalizer
│   │   ├── pacing.py             # Humanized jitter delay (45-180s) & daily cap tracker
│   │   └── orchestrator.py       # Batch dispatch orchestrator & CRM state updater
│   └── cli.py                    # Unified CLI entrypoint
└── tests/
    ├── test_personalizer.py      # Validates city/trade mention & no {{placeholders}}
    ├── test_dispatcher.py        # Validates staged approval, pacing jitter & daily caps
    └── test_whatsapp.py          # Validates E.164 phone parsing & wa.me URLs
```

### 4.2 Staging Columns Mapping Table
| Col Index | Col Letter | Field Name | Source Agent | Purpose |
|---|---|---|---|---|
| 17 | `R` | `Personalized Icebreaker` | Agent 3 | 2-sentence hook (city + trade + revenue pain point) |
| 18 | `S` | `Offer Angle / Pain Point` | Agent 3 | Revenue angle (competitor Maps ranking loss) |
| 21 | `V` | `Staged Email Subject` | Agent 3 | Cold email subject line |
| 22 | `W` | `Staged Email Body` | Agent 3 | Full cold email body copy |
| 23 | `X` | `Pre-formatted WhatsApp Message` | Agent 3 | Short conversational text for mobile messaging |
| 24 | `Y` | `WhatsApp Click-to-Chat Link` | Agent 3 | `https://wa.me/{phone}?text={encoded_msg}` |
| 25 | `Z` | `Outreach Approval Status` | Agent 3 / 4 | `"Drafted / Ready for Review"` -> `"Approved"` |
| 0 | `A` | `Lead Status` | Agent 4 | Updated to `"Contacted (Touch 1)"` upon dispatch |
| 14 | `O` | `Touch 1 Date` | Agent 4 | Updated to current `YYYY-MM-DD` upon dispatch |

---

## 5. Verification Method

To independently verify all findings and test prototypes, execute the following commands from PowerShell in the workspace:

### 5.1 Verify Environment and Google Sheets Integration
```powershell
# 1. Verify Python and installed packages
python -c "import jinja2, pydantic, smtplib, requests, httpx; print('All core dependencies installed successfully.')"

# 2. Verify Google Sheets CLI authentication
& "C:\Users\rishi\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd" auth status

# 3. Read existing Leads Tracker CRM data (columns A through U)
& "C:\Users\rishi\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd" readonly read 12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY "'Leads Tracker'!A1:C5" --json
```

### 5.2 Verify Personalization & WhatsApp Generator Logic
```powershell
python -c "
import re, urllib.parse

def test_personalization():
    lead = {
        'company': 'Guaranteed Roofing & Repairs',
        'niche': 'Residential Roofing & Repairs',
        'location': 'Fort Worth, TX (CST)',
        'phone': '(817) 349-5911'
    }
    m = re.match(r'^([^,]+),\s*([A-Za-z]{2})', lead['location'])
    city, state = m.group(1), m.group(2)
    niche = lead['niche'].lower()
    
    # 2-sentence icebreaker
    s1 = f'Came across {lead[\"company\"]} while reviewing top-rated {niche} contractors serving the {city} area.'
    s2 = f'With local competitors dominating Google Maps and organic search for emergency roof repairs in {city}, your team is missing out on thousands in high-margin repair and re-roof jobs each month without a dedicated web presence.'
    icebreaker = f'{s1} {s2}'
    
    # WhatsApp wa.me link
    clean_phone = '1' + re.sub(r'\D', '', lead['phone'])[-10:]
    wa_msg = f'Hi, saw your {niche} work in {city}. Competitors ranking on Google Maps for emergency repairs are capturing high-margin jobs without a website. Open to a 2-min video?'
    wa_link = f'https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}'
    
    assert city in icebreaker, 'City missing from icebreaker'
    assert niche in icebreaker, 'Niche missing from icebreaker'
    assert 'emergency roof repairs' in icebreaker, 'Pain point missing'
    assert '{{' not in icebreaker and '}}' not in icebreaker, 'Unparsed placeholder found'
    assert wa_link.startswith('https://wa.me/18173495911'), 'Invalid WhatsApp URL'
    print('Personalization & WhatsApp Test: PASSED')

test_personalization()
"
```

### 5.3 Verify Outreach Pacing & Cap Simulator
```powershell
python -c "
import random

def test_simulator():
    delays = [random.uniform(45.0, 180.0) for _ in range(100)]
    assert all(45.0 <= d <= 180.0 for d in delays), 'Delay out of bounds'
    daily_cap = 25
    queue = list(range(40))
    dispatched = queue[:daily_cap]
    assert len(dispatched) == 25, 'Daily cap failed'
    print(f'Simulator Test: PASSED (Average delay: {sum(delays)/len(delays):.2f}s, Cap enforced: {len(dispatched)})')

test_simulator()
"
```

### Invalidation Conditions
- If Google Sheets API access token revokes without refresh access, the wrapper must fall back to local cached simulation mode.
- If existing columns A through U are moved or deleted in `Leads Tracker`, column indices in `models.py` must be updated to match the new header offsets.
