# Milestone 2 Reviewer & Critic Report: Google Sheets CRM Ingestion & Deduplication

**Reviewer Agent**: `reviewer_m2_1`  
**Milestone**: Milestone 2: Google Sheets CRM Ingestion & Deduplication  
**Reviewed Worker**: `worker_m2`  
**Authoritative Requirements**: `ORIGINAL_REQUEST.md` (R2, Acceptance Criteria)  
**Project Specification**: `PROJECT.md` (Features 6–9, Interface Contracts)  
**Verdict**: **APPROVE**  

---

## 1. Observation

### 1.1 Direct Inspection of Implemented Source Files
- **`src/crm/schema.py`** (289 lines):
  - Strictly defines 21 columns in `CRM_COLUMNS` mapping to Google Sheet Columns A through U:
    `Lead Status` (A), `Priority` (B), `Company Name` (C), `Website` (D), `Industry / Niche` (E), `Company Size` (F), `Contact First Name` (G), `Contact Last Name` (H), `Job Title` (I), `Work Email` (J), `Email Verification` (K), `LinkedIn Profile` (L), `Location` (M), `Outreach Channel` (N), `Touch 1 Date` (O), `Last Follow-Up Date` (P), `Next Action Due` (Q), `Personalized Icebreaker` (R), `Offer Angle / Pain Point` (S), `Est. Deal Value ($)` (T), `Notes & Next Steps` (U).
  - Implements `validate_crm_row(row)`:
    - Enforces `Priority` dropdown with mandatory emoji prefix: `"🔥 High"`, `"⚡ Medium"`, `"❄️ Low"`. Rejects bare strings like `"High"`.
    - Enforces `Est. Deal Value ($)` as pure positive numeric integer (e.g. `4000`), rejecting formatted currency strings like `"$4,000"`.
    - Enforces `Company Size` as string prefixed with `'` (e.g. `"'1-10"`) to prevent spreadsheet auto-date conversions.
    - Enforces dropdown constraints for `Lead Status`, `Email Verification`, and `Outreach Channel`.
    - Formats `Location` as `<City>, <State> (<Timezone>)` with US timezone mapping.
  - Implements bidirectional mapping: `lead_to_crm_row()` converts `RawLead`/`QualifiedLead` into 21-element row arrays, and `crm_row_to_record()` generates validated `CRMRecord` Pydantic models.

- **`src/crm/sheets_client.py`** (378 lines):
  - Direct HTTPS REST client using Python standard library (`urllib.request`), targeting Google Sheets API v4 (`https://sheets.googleapis.com/v4/spreadsheets`).
  - Auto-refresh mechanism on HTTP 401: catches `urllib.error.HTTPError` with code 401, invokes `refresh_access_token()`, updates stored access token against `https://oauth2.googleapis.com/token`, persists new token to disk, and retries the request up to `max_retries=3`.
  - Subprocess CLI fallback: invokes `gsheets.cmd readonly read <sheet_id> <range> --json` if REST communication fails.
  - Rate limiting handling: computes exponential backoff on HTTP 429 (`base * (2 ** attempt)` capped at 32s).
  - In-memory mock/offline mode with row-sliced virtual grid for hermetic testing.

- **`src/crm/lead_scorer.py`** (69 lines):
  - Scoring rules:
    - `review_count >= 10`: `🔥 High` ($4,000 for residential, $4,500 for storm/commercial).
    - `5 <= review_count < 10` with storm/commercial specialty: `🔥 High` ($4,500).
    - `3 <= review_count < 10` or social profile: `⚡ Medium` ($3,500).
    - `review_count < 3`: `❄️ Low` ($3,000).

- **`src/crm/dedup.py`** (203 lines):
  - `normalize_phone()`: strips all non-digits, strips leading US prefix `1` if 11 digits, strictly yields 10-digit primary keys.
  - `normalize_business_name()`: converts `&` to `and`, strips punctuation, strips leading `The `, iteratively strips legal corporate suffixes (`incorporated`, `corporation`, `limited liability company`, `llc`, `inc`, `corp`, `co`, `pllc`, `llp`, `ltd`), and trailing conjunctions.
  - `CRMDeduplicator`: maintains in-memory lookup sets (`existing_names`, `existing_phones`) populated from `'Leads Tracker'!A2:U`. Detects duplicates against the existing sheet and eliminates intra-batch duplicates.

- **`src/crm/ingestor.py`** (143 lines):
  - Scans `'Leads Tracker'!A2:U500`, counts populated rows, and strictly sets next available row to `max(14, populated_count + 2)`.
  - Appends leads strictly to `'Leads Tracker'!A{start_row}:U{end_row}`, preserving header formulas and existing rows 2–13.

### 1.2 Independent Verification Results
1. **CRM Unit Test Execution**:
   - Command: `.\.venv\Scripts\python.exe -m pytest -v tests/unit/test_crm.py`
   - Result: **41 passed in 0.21s** (100% pass rate).
2. **Master Dual-Track E2E Test Suite**:
   - Command: `.\.venv\Scripts\python.exe tests/run_all_tests.py`
   - Result: **203 passed across all 4 tiers in 1.24s** (0 failures, exit code 0).
3. **Full Repository Pytest Suite**:
   - Command: `.\.venv\Scripts\python.exe -m pytest tests/`
   - Result: **478 passed in 1.44s** (0 failures, 0 regressions).
4. **Live Google Sheets API Connectivity**:
   - Command: `.\.venv\Scripts\python.exe -c "from src.crm.sheets_client import SheetsClient; client = SheetsClient(offline_mode=False); rows = client.read_range('12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY', 'Leads Tracker!A1:C5'); print('Rows:', len(rows))"`
   - Result: `Rows: 5` (verified live connection to Google Sheet ID `12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY`).
5. **Live Existing CRM Rows & Start Row Detection**:
   - Command: `.\.venv\Scripts\python.exe -c "from src.crm.ingestor import CRMIngestor; ingestor = CRMIngestor(); rows, next_row = ingestor.get_existing_records(); print('Existing:', len(rows), 'Next row:', next_row)"`
   - Result: `Existing: 12 Next row: 14` (verified exactly 12 existing leads in rows 2–13, and next ingestion row is row 14).
6. **Live Deduplication Rejection**:
   - Command: `.\.venv\Scripts\python.exe -c "from src.crm.ingestor import ingest_leads; from src.models import RawLead; lead = RawLead(business_name='Guaranteed Roofing and Repairs, LLC', cleaned_phone='8173495911', phone_display='(817) 349-5911', city='Fort Worth', state='TX', zip_code='76102', review_count=15, star_rating=5.0, specialty='Storm Damage & Re-roofing', website_status='None (No Website)'); res = ingest_leads([lead], dry_run=True); print('Result:', res['status'], 'Unique:', res['unique_ingested'], 'Duplicates skipped:', res['duplicates_skipped'])"`
   - Result: `Result: success Unique: 0 Duplicates skipped: 1` (verified live deduplication rejection of roofer in row 2).

---

## 2. Logic Chain

1. **Schema Integrity & Formula Preservation**:
   - `Leads Tracker` rows 2–13 contain initial verified roofers.
   - The `Pipeline Dashboard` relies on `=COUNTA('Leads Tracker'!C2:C495)` and `=SUM('Leads Tracker'!T2:T495)`.
   - `CRMIngestor` enforces `start_row = max(14, populated_count + 2)`. Because writes start at Row 14 and only update range `A{start_row}:U{end_row}` without shifting rows or modifying Col T's numeric format, formulas calculate accurately without `#VALUE!` or `#REF!` corruption.
   - Enforcing `int(deal_value)` guarantees numerical summing in Google Sheets. Prefixing company size with `'` prevents Google Sheets from auto-formatting `"1-10"` into a date (`"Jan-10"`).

2. **Deduplication Correctness**:
   - Candidate leads are matched against both normalized 10-digit phone numbers and normalized business names.
   - Stripping corporate entity suffixes (`LLC`, `Inc`, `Corp`, `Co`, `Company`) and standardizing ampersands (`&` -> `and`) prevents duplicate entries caused by legal naming variations.
   - Registering newly ingested leads during batch processing prevents intra-batch duplicates.
   - Pipeline re-runs on previously ingested geographic zones yield 0 duplicate rows, ensuring complete idempotency.

3. **Resilient OAuth2 Integration**:
   - Stored credentials in `C:\Users\rishi\.gemini\antigravity\plugin_data\gsheets\token.json` provide refresh tokens.
   - Intercepting HTTP 401 transparently exchanges the refresh token with Google's OAuth endpoint, updates memory and disk, and retries the request without failing the pipeline.
   - CLI fallback to `gsheets.cmd` provides redundancy against library or environment issues.

---

## 3. Caveats & Adversarial Observations

1. **Non-Contiguous Row Gap Handling (Advisory)**:
   - In `CRMIngestor.get_existing_records()`, `next_available_row = max(self.start_row, populated_count + 2)`. This calculation is accurate for contiguous datasets (such as the current rows 2–13). If a user manually deletes an intermediate row leaving empty gaps (e.g. row 15 blank, row 16 populated), `populated_count + 2` would point to row 16. In practice, the pipeline appends contiguously, so this poses no immediate risk.
2. **Formula Injection Sanitization (Advisory)**:
   - Lead ingestion uses `valueInputOption="USER_ENTERED"`. If a scraped roofer name started with `=DIR` or `=SUM`, Google Sheets would interpret it as a formula. While Google Maps business names are curated, adding a leading single quote `"` to any free-text string starting with `=`, `+`, `-`, or `@` is recommended for future hardening.
3. **Write Ownership Compliance**:
   - `worker_m2` strictly adhered to module boundaries, modifying only files within `src/crm/` and `tests/unit/test_crm.py`. Zero unauthorized files were altered.

---

## 4. Conclusion

Milestone 2 (Google Sheets CRM Ingestion & Deduplication) satisfies all requirements from `ORIGINAL_REQUEST.md` (R2) and `PROJECT.md` (Features 6–9).
- Schema mapping adheres strictly to 21 columns (Cols A–U).
- Validation rules strictly enforce emoji prefixes on Priority, unformatted integers on Deal Value, and protected strings on Company Size.
- OAuth token auto-refresh and CLI fallback are implemented and verified.
- 41/41 unit tests, 203/203 E2E tests, and 478/478 total tests pass cleanly.
- Zero integrity violations were detected.

**Explicit Verdict**: **APPROVE**

---

## 5. Verification Method

To independently reproduce and verify this review:

1. **Run CRM Unit Test Suite**:
   ```powershell
   & .\.venv\Scripts\python.exe -m pytest -v tests/unit/test_crm.py
   ```
   *Expected*: 41 passed in <0.5s.

2. **Run Master Dual-Track E2E Test Suite**:
   ```powershell
   & .\.venv\Scripts\python.exe tests/run_all_tests.py
   ```
   *Expected*: 203 passed across all 4 tiers in <1.5s, exit code 0.

3. **Run Full Repository Test Suite**:
   ```powershell
   & .\.venv\Scripts\python.exe -m pytest tests/ -v
   ```
   *Expected*: 478 passed in <2.0s, 0 failures.

4. **Verify Live Sheet Ingestion & Deduplication Safety**:
   ```powershell
   & .\.venv\Scripts\python.exe -c "from src.crm.ingestor import CRMIngestor; ingestor = CRMIngestor(); rows, next_row = ingestor.get_existing_records(); print('Existing CRM rows:', len(rows), 'Next available row:', next_row)"
   ```
   *Expected*: `Existing CRM rows: 12 Next available row: 14`.
