# Handoff Report: Milestone 1 Adversarial Challenge & Stress Testing

**Subagent**: `challenger_m1_2` (Adversarial Challenger)  
**Milestone**: Milestone 1: Google Maps Extraction Engine  
**Recipient**: Orchestrator (`ea620b15-fa32-4ce7-8b6f-715d76d0d59b`)  
**Working Directory**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\challenger_m1_2`  
**Date**: 2026-10-23  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

An empirical adversarial test suite was authored in `tests/test_m1_adversarial_stress.py` and executed against the Milestone 1 codebase using Python 3.15 in `.venv`.

**Execution Command**:
```powershell
& .\.venv\Scripts\python.exe -m pytest -v tests/test_m1_adversarial_stress.py
```
**Execution Summary**:
`6 failed, 8 passed in 0.29s` (Exit Code: 1).

### Specific Empirical Observations & Verbatim Errors:

#### 1. CRITICAL BUG: Phone Area Code Misinterpreted as Review Count
- **File**: `src/scraper/maps_extractor.py`, lines 103–110
- **Verbatim Code**:
  ```python
  # Alternate check if reviews formatted as: (45) or 45 reviews
  if review_count == 0:
      rev_match = re.search(r"\(([0-9,]+)\)", card_text)
      if rev_match:
          try:
              review_count = int(rev_match.group(1).replace(",", ""))
          except (ValueError, TypeError):
              pass
  ```
- **Observed Behavior**:
  When a card text represents an unreviewed or unrated contractor with a phone number in standard US format e.g. `(903) 555-1234`, `review_count` defaults to 0. `re.search(r"\(([0-9,]+)\)", card_text)` matches `(903)` from the telephone area code.
- **Verbatim Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestCardParserEdgeCases::test_missing_rating_does_not_misinterpret_phone_as_reviews
  assert 903 == 0
  where 903 = QualifiedLead(business_name='Ace Roofing', ..., review_count=903, priority='🔥 High').review_count
  ```
  Similarly, for phone area codes `(214)`, `(404)`, `(312)`, `(928)`, and `(850)`, `parse_card_data` sets `review_count` to 214, 404, 312, 928, and 850 respectively, and falsely classifies unreviewed businesses as `🔥 High` priority.

#### 2. Deduplication Leakage: Legal Suffixes Ignored in `RawLead.dedup_key`
- **File**: `src/models.py`, lines 50–56
- **Verbatim Code**:
  ```python
  @property
  def dedup_key(self) -> str:
      """Normalized deduplication key: 10-digit phone or normalized name + state."""
      if self.cleaned_phone and len(self.cleaned_phone) == 10:
          return self.cleaned_phone
      clean_name = re.sub(r"[^a-z0-9]", "", self.business_name.lower())
      return f"{clean_name}_{self.state.upper()}"
  ```
- **Observed Behavior**:
  When feeding 500 duplicate and near-duplicate records across 5 distinct businesses with empty/missing phone numbers (varied casing, punctuation, and legal suffixes like LLC, Inc, Corp, PLLC), `RawLead.dedup_key` produced 20 distinct keys instead of 5 (a 400% deduplication failure).
- **Verbatim Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestDeduplicationStress500::test_dedup_500_records_without_phone_exposes_suffix_vulnerability
  AssertionError: VULNERABILITY CONFIRMED: RawLead.dedup_key produced 20 unique keys for 5 businesses across 500 variants! Legal suffixes (LLC, Inc, Corp, PLLC) were not normalized.
  assert 20 == 5
  ```
  In `src/scraper/maps_extractor.py` line 266, `extract_multi_queries` relies directly on `lead.dedup_key`, causing cross-query deduplication to leak duplicate rows into downstream CRM ingestion whenever phone numbers are not captured.

#### 3. Deduplication Normalizer Omits 'PLLC'
- **File**: `src/scraper/normalizer.py`, lines 238–245
- **Verbatim Code**:
  ```python
  clean = re.sub(
      r"\b(llc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
      "",
      clean,
  )
  ```
- **Observed Behavior**:
  The regex omits `pllc` (Professional Limited Liability Company).
  `normalize_business_name('Summit Ridge Roofing PLLC')` evaluates to `'summitridgepllc'`, whereas `'Summit Ridge Roofing LLC'` evaluates to `'summitridge'`.
- **Verbatim Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestDeduplicationStress500::test_normalizer_pllc_suffix_omission
  AssertionError: VULNERABILITY CONFIRMED: normalize_business_name failed on 'PLLC'! base='summitridge', pllc='summitridgepllc'
  assert 'summitridge' == 'summitridgepllc'
  ```

#### 4. Missing State Validation in `RawLead` and `QualifiedLead`
- **File**: `src/models.py`, lines 36–48
- **Verbatim Code**:
  ```python
  @field_validator("state")
  @classmethod
  def validate_state(cls, v: str) -> str:
      v_clean = v.strip().upper()
      if len(v_clean) != 2:
          state_map = {
              "TEXAS": "TX", "FLORIDA": "FL", "OHIO": "OH",
              "GEORGIA": "GA", "ARIZONA": "AZ"
          }
          if v_clean in state_map:
              return state_map[v_clean]
      return v_clean
  ```
- **Observed Behavior**:
  The validator never raises `ValueError`. Invalid two-letter state codes (`"XX"`, `"ZZ"`, `"12"`), empty strings (`""`), and arbitrary strings (`"INVALID"`, `"CANADA"`, `"FOOBAR"`) are accepted silently without error.
- **Verbatim Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestPydanticSchemaValidation::test_invalid_states_rejected
  Failed: DID NOT RAISE ValidationError
  ```

#### 5. Missing Phone Validation in `RawLead` and `QualifiedLead`
- **File**: `src/models.py`, line 21
- **Verbatim Code**:
  ```python
  cleaned_phone: str = Field(..., description="10-digit normalized phone number (digits only)")
  ```
- **Observed Behavior**:
  There is no regex, length check, or validator. Invalid non-10-digit strings like `"123"`, `"12345678901"`, `"903-807-0683"`, `"abcdefghij"`, and `"555-HOME"` are accepted without error.
- **Verbatim Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestPydanticSchemaValidation::test_non_10_digit_cleaned_phones_rejected
  Failed: DID NOT RAISE ValidationError
  ```

### Passing Areas Verified:
- **Large Review Counts**: Correctly parses `500+` and `1,250` review counts and marks priority as `🔥 High`.
- **Missing Address Fallback**: Gracefully falls back to default city/state and municipal centroid ZIP (e.g. `75701`).
- **Centroid Coverage**: All 30 target query metros in TX, FL, OH, GA, AZ resolve to valid, non-zero 5-digit postal codes via `MUNICIPAL_CENTROIDS`.
- **Phone-Based Deduplication**: 500 record variants with identical 10-digit phones deduplicate with 100% precision (5 unique keys for 5 businesses).
- **Star Rating Range Validation**: Values `< 0.0` or `> 5.0` correctly raise Pydantic `ValidationError`.

---

## 2. Logic Chain

1. **Premise**: In R1 and R2, priority assignment relies on `review_count > 10` without a website to flag `🔥 High` priority leads.
2. **Step 1**: In `maps_extractor.py` lines 103–110, the regex `r"\(([0-9,]+)\)"` searches for parenthesized numbers in the entire card text when `review_count == 0`.
3. **Step 2**: Telephone numbers on Google Maps cards are formatted as `(XXX) XXX-XXXX`.
4. **Step 3**: The area code `(XXX)` matches the parenthesized review pattern. An unreviewed business with phone `(903) 555-1234` is assigned `review_count = 903` and marked as `🔥 High` priority.
5. **Deduplication Premise**: R2 acceptance criteria require zero duplicate rows.
6. **Step 4**: When telephone numbers are not extracted or missing, `RawLead.dedup_key` in `src/models.py` uses `re.sub(r"[^a-z0-9]", "", self.business_name.lower())`, completely omitting legal suffix stripping.
7. **Step 5**: 500 variants representing 5 entities generate 20 duplicate records in `lead.dedup_key`, which `extract_multi_queries` relies upon.
8. **Step 6**: Even `normalizer.normalize_business_name` omits `PLLC` from its suffix regex, causing `Summit Ridge Roofing PLLC` to collide as distinct from `Summit Ridge Roofing LLC`.
9. **Interface Contract Premise**: `PROJECT.md` defines `RawLead` as the strict boundary contract between M1 and M2, requiring 2-letter state codes and 10-digit phones.
10. **Step 7**: The validator in `src/models.py` lacks a state whitelist and phone format enforcement, allowing malformed records to contaminate downstream Google Sheets CRM ingestion.

---

## 3. Caveats

1. **Review-Only Constraint**: In accordance with the Teamwork agent contract, no implementation files (`src/models.py`, `src/scraper/maps_extractor.py`, `src/scraper/normalizer.py`) were modified by this agent.
2. **Existing Passing Tests**: The existing 91 tests in `tests/unit/test_scraper.py` passed previously only because they did not test unreviewed businesses with standard parenthesized phone numbers, nor did they assert rejection of invalid states or non-10-digit phones.
3. **Live Playwright Interaction**: Live browser scrolling was not exercised in this unit stress suite to maintain deterministic headless execution; mocking and pure card parser / normalizer functions were tested directly.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Milestone 1 cannot be approved in its current state due to 4 high-severity defects that compromise lead qualification accuracy and CRM deduplication integrity:

1. **Area Code Review Count Bug**: Unrated/zero-review contractors with standard US phone formats `(XXX) ...` are assigned their telephone area code (e.g. 903, 214, 404) as verified Google review count, falsely qualifying them as `🔥 High` priority.
2. **Legal Suffix Deduplication Failure**: `RawLead.dedup_key` does not strip legal suffixes (`LLC`, `Inc`, `Corp`, `PLLC`), resulting in duplicate rows in multi-query extraction.
3. **Missing `pllc` in Normalizer**: `normalize_business_name` omits `pllc` from its entity regex.
4. **Permissive Schema Validation**: `RawLead` and `QualifiedLead` fail to reject invalid US states and non-10-digit phones.

### Concrete Remediation Plan for Worker:
1. In `src/scraper/maps_extractor.py`:
   - Delete lines 103–110 that match `r"\(([0-9,]+)\)"` against raw card text, or ensure it excludes phone patterns / requires explicit review context (e.g. `r"\(([0-9,]+)\s*(?:reviews?)?\)"` strictly adjacent to the star rating).
2. In `src/models.py`:
   - Import `normalize_business_name` from `src.scraper.normalizer` and use it in `RawLead.dedup_key` property so legal suffixes are stripped uniformly.
   - Update `@field_validator("state")` to validate against a set of valid US state abbreviations (or `US_STATE_NAME_TO_CODE.values()`) and raise `ValueError` for invalid states.
   - Add a validator or field constraint for `cleaned_phone` in `RawLead` (e.g. `pattern=r"^([0-9]{10})?$"`) to reject non-10-digit phone strings while allowing empty string if phone is absent.
3. In `src/scraper/normalizer.py`:
   - Add `pllc` to `normalize_business_name` regex:
     `r"\b(llc|pllc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b"`

---

## 5. Verification Method

To independently reproduce and verify these findings:

```powershell
cd C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline
& .\.venv\Scripts\python.exe -m pytest -v tests/test_m1_adversarial_stress.py
```

**Expected Result Before Fixes**:
`6 failed, 8 passed in ~0.30s` with the exact tracebacks documented in Section 1.

**Invalidation / Acceptance Criteria**:
Once the worker implements the remediations above, running the command above will result in `14 passed in <1.0s` with zero failures.
