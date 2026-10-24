# Handoff Report: Milestone 1 Adversarial Fix Strategy (Challenger 2 Findings)

**Subagent**: `explorer_m1_r2_3` (Explorer / Investigation)  
**Milestone**: Milestone 1: Google Maps Extraction Engine  
**Recipient**: Orchestrator (`ea620b15-fa32-4ce7-8b6f-715d76d0d59b`)  
**Working Directory**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_3`  
**Date**: 2026-10-23  

---

## 1. Observation

Adversarial stress suite `tests/test_m1_adversarial_stress.py` was executed against the Milestone 1 codebase using Python 3.15 in `.venv`.

**Command**:
```powershell
& .\.venv\Scripts\python.exe -m pytest -v tests/test_m1_adversarial_stress.py
```

**Result**: `6 failed, 8 passed in 0.27s` (Exit Code 1).

### Empirical Observations & Verbatim Failure Points

#### Observation 1.1: Missing `pllc` in `src/scraper/normalizer.py`
- **File**: `src/scraper/normalizer.py`, lines 238–245
- **Current Code**:
  ```python
  clean = re.sub(
      r"\b(llc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
      "",
      clean,
  )
  clean = re.sub(r"[^a-z0-9]", "", clean)
  return clean.strip()
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestDeduplicationStress500::test_normalizer_pllc_suffix_omission
  AssertionError: VULNERABILITY CONFIRMED: normalize_business_name failed on 'PLLC'! base='summitridge', pllc='summitridgepllc'
  assert 'summitridge' == 'summitridgepllc'
    - summitridgepllc
    ?            ----
    + summitridge
  ```
- **Impact**: Roofing entities organized as Professional Limited Liability Companies (PLLC) are not stripped of the `pllc` suffix. Consequently, `"Summit Ridge Roofing PLLC"` (`summitridgepllc`) is treated as a completely different business than `"Summit Ridge Roofing LLC"` (`summitridge`), violating deduplication requirements.

#### Observation 1.2: Permissive State Validation in `src/models.py`
- **File**: `src/models.py`, lines 36–48
- **Current Code**:
  ```python
  @field_validator("state")
  @classmethod
  def validate_state(cls, v: str) -> str:
      v_clean = v.strip().upper()
      if len(v_clean) != 2:
          # If full state name was passed, allow standard US 2-letter mapping
          state_map = {
              "TEXAS": "TX", "FLORIDA": "FL", "OHIO": "OH",
              "GEORGIA": "GA", "ARIZONA": "AZ"
          }
          if v_clean in state_map:
              return state_map[v_clean]
      return v_clean
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestPydanticSchemaValidation::test_invalid_states_rejected
  Failed: DID NOT RAISE ValidationError
  ```
- **Impact**: Any two-letter string (e.g. `"XX"`, `"ZZ"`, `"12"`), empty string `""`, or non-mapped arbitrary string (e.g. `"INVALID"`, `"CANADA"`, `"FOOBAR"`) is accepted without error because `validate_state` never raises `ValueError`.

#### Observation 1.3: Permissive `cleaned_phone` Validation in `src/models.py`
- **File**: `src/models.py`, line 21
- **Current Code**:
  ```python
  cleaned_phone: str = Field(..., description="10-digit normalized phone number (digits only)")
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestPydanticSchemaValidation::test_non_10_digit_cleaned_phones_rejected
  Failed: DID NOT RAISE ValidationError
  ```
- **Impact**: `RawLead` does not constrain `cleaned_phone`. Malformed strings like `"123"`, `"12345678901"`, `"903-807-0683"`, `"abcdefghij"`, and `"555-HOME"` bypass schema validation without raising `ValidationError`. Note that `cleaned_phone` must still accept empty string `""` when phone is not listed on Google Maps (verified by `test_missing_phone_graceful_handling` and line 98 of `test_m1_adversarial_stress.py`).

#### Observation 1.4: Deduplication Leakage in `RawLead.dedup_key`
- **File**: `src/models.py`, lines 51–56
- **Current Code**:
  ```python
  @property
  def dedup_key(self) -> str:
      """Normalized deduplication key: 10-digit phone or normalized name + state."""
      if self.cleaned_phone and len(self.cleaned_phone) == 10:
          return self.cleaned_phone
      clean_name = re.sub(r"[^a-z0-9]", "", self.business_name.lower())
      return f"{clean_name}_{self.state.upper()}"
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestDeduplicationStress500::test_dedup_500_records_without_phone_exposes_suffix_vulnerability
  AssertionError: VULNERABILITY CONFIRMED: RawLead.dedup_key produced 20 unique keys for 5 businesses across 500 variants! Legal suffixes (LLC, Inc, Corp, PLLC) were not normalized.
  assert 20 == 5
  ```
- **Impact**: `RawLead.dedup_key` uses a naive regex `[^a-z0-9]` that does not strip legal suffixes, while `normalizer.get_dedup_key` already implements `normalize_business_name`. Because `maps_extractor.py:266` relies on `lead.dedup_key`, cross-query deduplication produces duplicate records for contractors without phone numbers.

#### Observation 1.5: Phone Area Code Misinterpreted as Review Count
- **File**: `src/scraper/maps_extractor.py`, lines 103–110
- **Current Code**:
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
- **Verbatim Failures**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestCardParserEdgeCases::test_missing_rating_does_not_misinterpret_phone_as_reviews
  assert 903 == 0

  FAILED tests/test_m1_adversarial_stress.py::TestCardParserEdgeCases::test_zero_reviews_explicit_text
  assert 903 == 0
  ```
- **Impact**: When a business has no star rating or 0 reviews, `\(([0-9,]+)\)` matches the phone area code `(903)` from `(903) 555-1234`, falsely setting `review_count = 903` and classifying unreviewed businesses as `🔥 High` priority.

#### Observation 1.6: Legacy Test Assertion in `tests/unit/test_scraper.py:107`
- **File**: `tests/unit/test_scraper.py`, line 107
- **Current Code**:
  ```python
  assert lead.dedup_key == "apexroofersllc_TX"
  ```
- **Impact**: This legacy unit test previously hardcoded the unnormalized string `"apexroofersllc_TX"`. Once `RawLead.dedup_key` is fixed to strip legal suffixes, `"Apex Roofers LLC"` normalizes to `"apexroofers_TX"`. Updating line 107 to `assert lead.dedup_key == "apexroofers_TX"` is required to ensure 100% unit test suite passing.

---

## 2. Logic Chain

1. **Root Cause Analysis of PLLC Omission**:
   - `normalize_business_name` in `src/scraper/normalizer.py:240` defines a regex word boundary pattern for legal entity suffixes.
   - The token `pllc` is absent from the group `(llc|inc|corp|corporation|co|ltd|company|...)`.
   - By inserting `pllc|` into this pattern, `normalize_business_name` removes `pllc` prior to non-alphanumeric character stripping.
   - Experimental execution confirmed: `"Summit Ridge Roofing PLLC"` and `"Summit Ridge Roofing LLC"` both normalize to `"summitridge"`.

2. **Root Cause Analysis of Permissive State Validation**:
   - `validate_state` in `src/models.py:36` only transformed full names if length was not 2, and returned `v_clean` unconditionally.
   - Any invalid two-letter string (`"XX"`, `"12"`, `""`) or non-target state name bypassed validation.
   - By validating against the set of 50 US state postal abbreviations plus DC (`VALID_US_STATES`), and mapping full state names using `US_STATE_NAME_TO_CODE`, invalid inputs will trigger `raise ValueError(...)`.
   - This complies with Pydantic's `@field_validator` contract and causes `ValidationError` to be raised whenever an invalid state is encountered.

3. **Root Cause Analysis of Permissive Phone Validation**:
   - `cleaned_phone` in `src/models.py:21` was declared as an unconstrained `str`.
   - The contract in `PROJECT.md` and R1 specifies: 10 digits (digits only) or empty string when no phone is available.
   - A `@field_validator("cleaned_phone")` enforcing `r"^[0-9]{10}$"` for non-empty values ensures that non-10-digit strings like `"123"`, `"12345678901"`, and `"903-807-0683"` raise `ValueError` (which Pydantic converts to `ValidationError` matching `"phone"`), while empty strings `""` are accepted for unlisted numbers.

4. **Root Cause Analysis of Deduplication Discrepancy**:
   - `src/scraper/normalizer.py` already contains a robust `get_dedup_key(phone_10, business_name, state)` function.
   - `RawLead.dedup_key` in `src/models.py:51` had an independent, naive implementation that bypassed `normalize_business_name`.
   - By delegating `RawLead.dedup_key` directly to `get_dedup_key(self.cleaned_phone, self.business_name, self.state)`, deduplication logic is centralized, and 500 variants across 5 businesses collapse to exactly 5 unique keys.

5. **Root Cause Analysis of Phone Area Code Misinterpretation**:
   - In `maps_extractor.py:104`, `re.search(r"\(([0-9,]+)\)", card_text)` runs on the full card text.
   - Standard US phone numbers are formatted as `(XXX) XXX-XXXX`.
   - When `review_count == 0`, `rev_match` captures the area code `XXX` as the review count.
   - By stripping the extracted phone string (`card_text.replace(raw_phone, "")`) and enforcing a negative lookahead `(?!\s*[0-9]{3})` before checking alternate review count patterns, area codes can never be parsed as review counts.

6. **Regression Verification**:
   - Simulating all proposed patches simultaneously resulted in:
     - `14 passed in 0.03s` on `tests/test_m1_adversarial_stress.py` (100% pass, 0 failures).
     - `203 passed in 0.28s` on `tests/e2e/` (100% pass, 0 regressions).
     - `91 passed in 1.15s` on `tests/unit/test_scraper.py` (after updating legacy assertion at line 107).

---

## 3. Caveats

1. **Read-Only Explorer Mandate**: Per the Teamwork agent contract, no source code files (`src/scraper/normalizer.py`, `src/models.py`, `src/scraper/maps_extractor.py`, `tests/unit/test_scraper.py`) were modified on disk during this investigation. The changes are delivered as actionable code snippets and diffs below for the Worker agent.
2. **Phone Validation on Empty Values**: `RawLead.cleaned_phone` must allow empty string `""` because Google Maps listings frequently omit phone numbers or provide unlisted contractor profiles. Requisite tests (`test_missing_phone_graceful_handling`, `test_dedup_500_records_without_phone_exposes_suffix_vulnerability`) rely on empty string phone support.
3. **Legacy Assertion in `test_scraper.py:107`**: The Worker agent must update `tests/unit/test_scraper.py:107` from `"apexroofersllc_TX"` to `"apexroofers_TX"` so the existing unit test suite passes alongside the adversarial suite.

---

## 4. Conclusion

The 4 issues identified by Challenger 2 can be cleanly resolved with localized, non-breaking modifications. Below is the exact implementation strategy.

### 4.1 Target Fix 1: `src/scraper/normalizer.py`
**Location**: Line 239–243  
**Action**: Add `pllc` (and `incorporated`, `limited`) to the legal entity regex in `normalize_business_name`.

```python
<<<<
    clean = re.sub(
        r"\b(llc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
        "",
        clean,
    )
====
    clean = re.sub(
        r"\b(pllc|llc|inc|incorporated|corp|corporation|co|ltd|limited|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
        "",
        clean,
    )
>>>>
```

### 4.2 Target Fix 2: `src/models.py`
**Location**: Imports, `RawLead` schema, validators, and `dedup_key` property.  
**Action**:
1. Import `get_dedup_key` and `US_STATE_NAME_TO_CODE` from `src.scraper.normalizer`.
2. Define `VALID_US_STATES` containing the 50 US state postal codes + DC.
3. Add `@field_validator("cleaned_phone")` to enforce 10-digit digits or empty string.
4. Strengthen `@field_validator("state")` to map state names and raise `ValueError` on any invalid state code.
5. Update `RawLead.dedup_key` to delegate to `get_dedup_key`.

#### Exact Code Replacement for `src/models.py`:
```python
# At the top of src/models.py:
from src.scraper.normalizer import get_dedup_key, US_STATE_NAME_TO_CODE

VALID_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC"
}
```

#### Inside `RawLead` class:
```python
    cleaned_phone: str = Field(default="", description="10-digit normalized phone number (digits only)")

    @field_validator("cleaned_phone")
    @classmethod
    def validate_cleaned_phone(cls, v: str) -> str:
        if v == "" or v is None:
            return ""
        v_str = str(v).strip()
        if not re.fullmatch(r"^[0-9]{10}$", v_str):
            raise ValueError(f"Invalid phone number: '{v}'. cleaned_phone must be a 10-digit numeric string or empty.")
        return v_str

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Invalid US state: state code cannot be empty.")
        v_clean = v.strip().upper()
        v_lower = v.strip().lower()
        if v_lower in US_STATE_NAME_TO_CODE:
            v_clean = US_STATE_NAME_TO_CODE[v_lower]
        if v_clean not in VALID_US_STATES:
            raise ValueError(f"Invalid US state code: '{v}'. Must be a valid two-letter US state.")
        return v_clean

    @property
    def dedup_key(self) -> str:
        """Normalized deduplication key: 10-digit phone or normalized name + state."""
        return get_dedup_key(self.cleaned_phone, self.business_name, self.state)
```

### 4.3 Target Fix 3: `src/scraper/maps_extractor.py` (Area Code Bug Remediation)
**Location**: `parse_card_data`, lines 102–110  
**Action**: Ensure phone area codes are not matched as review count when `review_count == 0`.

```python
<<<<
        # Alternate check if reviews formatted as: (45) or 45 reviews
        if review_count == 0:
            rev_match = re.search(r"\(([0-9,]+)\)", card_text)
            if rev_match:
                try:
                    review_count = int(rev_match.group(1).replace(",", ""))
                except (ValueError, TypeError):
                    pass
====
        # Alternate check if reviews formatted as: (45) or 45 reviews
        if review_count == 0:
            text_without_phone = card_text.replace(raw_phone, "") if raw_phone else card_text
            rev_match = re.search(r"\(([0-9,]+)\s*(?:reviews?)?\)(?!\s*[0-9]{3})", text_without_phone)
            if rev_match:
                try:
                    review_count = int(rev_match.group(1).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            else:
                rev_m2 = re.search(r"\b([0-9,]+)\s+reviews?\b", text_without_phone, re.IGNORECASE)
                if rev_m2:
                    try:
                        review_count = int(rev_m2.group(1).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
>>>>
```

### 4.4 Target Fix 4: `tests/unit/test_scraper.py`
**Location**: Line 107  
**Action**: Update legacy hardcoded string to reflect legal suffix stripping.
```python
<<<<
        assert lead.dedup_key == "apexroofersllc_TX"
====
        assert lead.dedup_key == "apexroofers_TX"
>>>>
```

---

## 5. Verification Method

Once the Worker implements the remediations above, execute the following commands to verify:

### 1. Verify Adversarial Stress Suite (Challenger 2 Suite)
```powershell
cd C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline
& .\.venv\Scripts\python.exe -m pytest -v tests/test_m1_adversarial_stress.py
```
**Expected Outcome**: `14 passed in <0.5s` (0 failed, exit code 0).

### 2. Verify Scraper Unit Tests
```powershell
& .\.venv\Scripts\python.exe -m pytest -v tests/unit/test_scraper.py
```
**Expected Outcome**: `91 passed in <1.5s` (0 failed, exit code 0).

### 3. Verify End-to-End Suite
```powershell
& .\.venv\Scripts\python.exe -m pytest -v tests/e2e/
```
**Expected Outcome**: `203 passed in <1.0s` (0 failed, exit code 0).

### Invalidation Conditions
- If any test in `TestCardParserEdgeCases` sets `review_count` to a non-zero area code (e.g. 903) for an unreviewed listing, the fix is invalid.
- If `TestDeduplicationStress500` produces more than 5 unique keys across 500 variants without phone numbers, legal suffix normalization remains broken.
- If `TestPydanticSchemaValidation` accepts `'XX'` or `'123'` without raising `ValidationError`, schema validation remains permissive.
