# Handoff Report: Milestone 1 Remediation Round 2 — Explorer Investigation

**Subagent**: `explorer_m1_r2_2` (Teamwork Explorer)  
**Milestone**: Milestone 1: Google Maps Extraction Engine Remediation  
**Target Recipient**: Orchestrator (`ea620b15-fa32-4ce7-8b6f-715d76d0d59b`)  
**Working Directory**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_2`  
**Date**: 2026-10-23  
**Status**: COMPLETE (Read-Only Analysis & Exact Remediation Specification)  

---

## 1. Observation

A full empirical investigation was conducted against `tests/test_m1_adversarial_stress.py`, `src/scraper/maps_extractor.py`, `src/models.py`, `src/scraper/normalizer.py`, and `tests/unit/test_scraper.py`.

### Execution Baseline
Command:
```powershell
.\.venv\Scripts\python.exe -m pytest -v tests/test_m1_adversarial_stress.py
```
**Observed Result**: `6 failed, 8 passed in 0.31s` (Exit Code: 1).

### Specific Empirical Observations & Root Causes

#### 1. CRITICAL BUG: Phone Area Code Misinterpreted as Review Count
- **Target File**: `src/scraper/maps_extractor.py`, lines 103–110
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
- **Verbatim Failure Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestCardParserEdgeCases::test_missing_rating_does_not_misinterpret_phone_as_reviews
  assert 903 == 0
  where 903 = QualifiedLead(business_name='Ace Roofing', ..., review_count=903, priority='🔥 High').review_count
  ```
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestCardParserEdgeCases::test_zero_reviews_explicit_text
  assert 903 == 0
  where 903 = QualifiedLead(business_name='Apex Roofing', ..., review_count=903, priority='🔥 High').review_count
  ```
- **Root Cause**:
  When a Google Maps card has no rating or explicitly states "No reviews", `review_count` remains 0 after the primary rating regex check. The fallback regex `r"\(([0-9,]+)\)"` searches for any digits inside parentheses in the entire card text. When the card includes a standard US phone number formatted as `(903) 555-1234`, `rev_match` greedily captures `"903"`. As a result, `review_count` is set to 903. Because 903 exceeds `HIGH_PRIORITY_REVIEW_THRESHOLD` (10), `priority` is incorrectly assigned as `🔥 High` instead of `⚡ Medium`.

#### 2. Deduplication Leakage: Legal Suffixes Ignored in `RawLead.dedup_key`
- **Target File**: `src/models.py`, lines 50–57
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
- **Verbatim Failure Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestDeduplicationStress500::test_dedup_500_records_without_phone_exposes_suffix_vulnerability
  AssertionError: VULNERABILITY CONFIRMED: RawLead.dedup_key produced 20 unique keys for 5 businesses across 500 variants! Legal suffixes (LLC, Inc, Corp, PLLC) were not normalized.
  assert 20 == 5
  ```
- **Root Cause**:
  `RawLead.dedup_key` in `src/models.py` bypassed the project normalizer function `get_dedup_key()` / `normalize_business_name()` from `src/scraper/normalizer.py`. Instead, it implemented a naive `re.sub(r"[^a-z0-9]", "", self.business_name.lower())`. When a phone number is absent/empty, entities like `"Apex Pro Roofing LLC"`, `"Apex Pro Roofing Inc"`, `"Apex Pro Roofing Corp"`, and `"Apex Pro Roofing Solutions"` each produced distinct keys (`apexproroofingllc_TX`, `apexproroofinginc_TX`, etc.), leaking 20 duplicate records for 5 entities.

#### 3. Deduplication Normalizer Omits 'PLLC'
- **Target File**: `src/scraper/normalizer.py`, lines 238–245
- **Verbatim Code**:
  ```python
  clean = re.sub(
      r"\b(llc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
      "",
      clean,
  )
  ```
- **Verbatim Failure Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestDeduplicationStress500::test_normalizer_pllc_suffix_omission
  AssertionError: VULNERABILITY CONFIRMED: normalize_business_name failed on 'PLLC'! base='summitridge', pllc='summitridgepllc'
  assert 'summitridge' == 'summitridgepllc'
  ```
- **Root Cause**:
  `normalize_business_name()` stripped `llc`, `inc`, `corp`, etc., but omitted `pllc` (Professional Limited Liability Company). `"Summit Ridge Roofing PLLC"` normalized to `'summitridgepllc'` instead of `'summitridge'`.

#### 4. Missing State Validation in `RawLead`
- **Target File**: `src/models.py`, lines 36–48
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
- **Verbatim Failure Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestPydanticSchemaValidation::test_invalid_states_rejected
  Failed: DID NOT RAISE ValidationError
  ```
- **Root Cause**:
  The validator never raised `ValueError`. Invalid states (`"XX"`, `"ZZ"`, `"12"`, `""`, `"CANADA"`) were accepted silently, violating the strict contract that states must be valid 2-letter US postal abbreviations.

#### 5. Missing Phone Validation in `RawLead`
- **Target File**: `src/models.py`, line 21
- **Verbatim Code**:
  ```python
  cleaned_phone: str = Field(..., description="10-digit normalized phone number (digits only)")
  ```
- **Verbatim Failure Output**:
  ```
  FAILED tests/test_m1_adversarial_stress.py::TestPydanticSchemaValidation::test_non_10_digit_cleaned_phones_rejected
  Failed: DID NOT RAISE ValidationError
  ```
- **Root Cause**:
  There was no validator for `cleaned_phone`. Invalid strings like `"123"`, `"12345678901"`, `"903-807-0683"`, and `"abcdefghij"` were accepted without raising `ValidationError`.

#### 6. Unit Test Regression Hazard in `tests/unit/test_scraper.py`
- **Target File**: `tests/unit/test_scraper.py`, line 107
- **Verbatim Code**:
  ```python
  def test_raw_lead_dedup_key_fallback(self):
      lead = RawLead(
          business_name="Apex Roofers LLC",
          cleaned_phone="", ...
      )
      assert lead.dedup_key == "apexroofersllc_TX"
  ```
- **Observation**:
  `tests/unit/test_scraper.py:107` previously tested the un-normalized bug. Once `RawLead.dedup_key` correctly strips `LLC`, `lead.dedup_key` evaluates to `"apexroofers_TX"`. The assertion in line 107 must be updated to `"apexroofers_TX"` to prevent a false unit test failure.

---

## 2. Logic Chain

1. **Qualification Integrity**: Under R1 and R2 (`ORIGINAL_REQUEST.md` line 32), contractors with `review_count > 10` without a website must be scored `🔥 High` priority, whereas zero-review contractors must be scored `⚡ Medium`.
2. **Observation 1 Tracing**: Card text without ratings (e.g. unreviewed contractor `"Ace Roofing\n(903) 555-1234"`) reaches `maps_extractor.py:103` with `review_count == 0`. The fallback pattern `r"\(([0-9,]+)\)"` matches the area code `(903)`, setting `review_count = 903` and marking unreviewed leads as `🔥 High`.
3. **Remediation for 1**: By updating the review count logic in `maps_extractor.py` to:
   - Enhance the rating regex to capture ratings with star symbols and counts: `r"([1-5]\.[0-9])(?:\s*(?:stars?|★))?\s*(?:\(?\s*([0-9,]+)\+?(?:\s*reviews?)?\s*\)?)?"`
   - Require explicit review keywords when fallback matching: `r"\b([0-9,]+)\s+reviews?\b"`
   area codes in `(XXX) XXX-XXXX` phone patterns are never captured as review counts.
4. **CRM Deduplication Integrity**: R2 (`ORIGINAL_REQUEST.md` line 31, 55) mandates zero duplicate rows.
5. **Observation 2 & 3 Tracing**: Multi-query extraction in `maps_extractor.py:266` relies on `lead.dedup_key`. In `src/models.py:55`, `RawLead.dedup_key` does not call `normalize_business_name()`, producing 20 distinct keys across 500 variants of 5 businesses. Furthermore, `normalizer.py:239` omitted `pllc`.
6. **Remediation for 2 & 3**: By importing `get_dedup_key` into `src/models.py` and delegating `RawLead.dedup_key` to `get_dedup_key(self.cleaned_phone, self.business_name, self.state)`, and adding `pllc` to `normalize_business_name()`, all 500 variants deduplicate with 100% precision (exactly 5 keys).
7. **Interface Contract Enforcement**: `PROJECT.md` line 138-151 defines `RawLead` as the typed boundary contract between M1 and M2, requiring 2-letter state codes and 10-digit phones.
8. **Observation 4 & 5 Tracing**: `src/models.py` lacked validation for `state` and `cleaned_phone`.
9. **Remediation for 4 & 5**: Adding `@field_validator("state")` validating against the 50 US state codes (using `US_STATE_NAME_TO_CODE`) and `@field_validator("cleaned_phone")` validating that `cleaned_phone` is either empty `""` or exactly 10 digits (`len == 10 and isdigit()`) enforces the interface contract and rejects invalid inputs with `ValidationError`.

---

## 3. Caveats

1. **Read-Only Explorer Discipline**: In strict compliance with the Teamwork explorer archetype, zero source files in `src/` or `tests/` were modified by this agent. All proposed code changes are provided as diff snippets and as a `.patch` artifact in `.agents/teamwork/explorer_m1_r2_2/proposed_fixes.patch`.
2. **Complementary Challenger 1 Fixes**: Challenger 1 identified separate URL scheme case-sensitivity, open redirectors (`google.com/url?q=...`), and NANP phone normalizer edge cases in `src/scraper/filters.py` and `src/scraper/normalizer.py`. The fixes recommended here for Challenger 2 do not conflict with Challenger 1; they are fully orthogonal and mutually reinforcing.
3. **Test Assertion Alignment in `test_scraper.py`**: The change in `tests/unit/test_scraper.py:107` from `"apexroofersllc_TX"` to `"apexroofers_TX"` is an intentional update to align the unit test with proper deduplication semantics.

---

## 4. Conclusion & Recommended Fix Strategy

The worker agent (`06c4e5f5-6cab-41db-8976-92cefde534ce`) should apply the following exact modifications across 4 files:

### Target 1: `src/scraper/maps_extractor.py` (Lines 87–110)

**Before**:
```python
        # 4. Star Rating and Review Count
        star_rating = 0.0
        review_count = 0
        rating_match = re.search(r"([1-5]\.[0-9])\s*(?:\(?\s*([0-9,]+)\s*\)?|stars?)", card_text)
        if rating_match:
            try:
                star_rating = float(rating_match.group(1))
            except (ValueError, TypeError):
                star_rating = 0.0
            if rating_match.group(2):
                try:
                    review_count = int(rating_match.group(2).replace(",", ""))
                except (ValueError, TypeError):
                    review_count = 0

        # Alternate check if reviews formatted as: (45) or 45 reviews
        if review_count == 0:
            rev_match = re.search(r"\(([0-9,]+)\)", card_text)
            if rev_match:
                try:
                    review_count = int(rev_match.group(1).replace(",", ""))
                except (ValueError, TypeError):
                    pass
```

**After**:
```python
        # 4. Star Rating and Review Count
        star_rating = 0.0
        review_count = 0
        rating_match = re.search(
            r"([1-5]\.[0-9])(?:\s*(?:stars?|★))?\s*(?:\(?\s*([0-9,]+)\+?(?:\s*reviews?)?\s*\)?)?",
            card_text,
            re.IGNORECASE,
        )
        if rating_match:
            try:
                star_rating = float(rating_match.group(1))
            except (ValueError, TypeError):
                star_rating = 0.0
            if rating_match.group(2):
                try:
                    review_count = int(rating_match.group(2).replace(",", ""))
                except (ValueError, TypeError):
                    review_count = 0

        # Alternate check for explicit review mentions (e.g. "45 reviews" or "(45 reviews)")
        # Standalone numbers in parentheses like "(903)" MUST NOT match as they represent phone area codes
        if review_count == 0:
            rev_match = re.search(r"\b([0-9,]+)\s+reviews?\b", card_text, re.IGNORECASE)
            if rev_match:
                try:
                    review_count = int(rev_match.group(1).replace(",", ""))
                except (ValueError, TypeError):
                    pass
```

---

### Target 2: `src/models.py` (Lines 10–58)

**Before**:
```python
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RawLead(BaseModel):
...
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

    @property
    def dedup_key(self) -> str:
        """Normalized deduplication key: 10-digit phone or normalized name + state."""
        if self.cleaned_phone and len(self.cleaned_phone) == 10:
            return self.cleaned_phone
        clean_name = re.sub(r"[^a-z0-9]", "", self.business_name.lower())
        return f"{clean_name}_{self.state.upper()}"
```

**After**:
```python
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from src.scraper.normalizer import get_dedup_key, US_STATE_NAME_TO_CODE

VALID_US_STATES = set(US_STATE_NAME_TO_CODE.values())


class RawLead(BaseModel):
...
    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        v_clean = v.strip().upper()
        if not v_clean:
            raise ValueError("State code cannot be empty. Must be a valid 2-letter US state code.")
        if v_clean.lower() in US_STATE_NAME_TO_CODE:
            return US_STATE_NAME_TO_CODE[v_clean.lower()]
        if v_clean in VALID_US_STATES:
            return v_clean
        raise ValueError(
            f"Invalid US state: '{v}'. Must be a valid 2-letter US state code (e.g. TX, FL, OH, GA, AZ)."
        )

    @field_validator("cleaned_phone")
    @classmethod
    def validate_cleaned_phone(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            return ""
        if len(v_clean) != 10 or not v_clean.isdigit():
            raise ValueError(
                f"Invalid phone number: '{v}'. cleaned_phone must be empty or exactly 10 digits."
            )
        return v_clean

    @property
    def dedup_key(self) -> str:
        """Normalized deduplication key: 10-digit phone or normalized name + state."""
        return get_dedup_key(self.cleaned_phone, self.business_name, self.state)
```

---

### Target 3: `src/scraper/normalizer.py` (Line 240)

**Before**:
```python
    clean = re.sub(
        r"\b(llc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
        "",
        clean,
    )
```

**After**:
```python
    clean = re.sub(
        r"\b(llc|pllc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions)\b",
        "",
        clean,
    )
```

---

### Target 4: `tests/unit/test_scraper.py` (Line 107)

**Before**:
```python
        assert lead.dedup_key == "apexroofersllc_TX"
```

**After**:
```python
        assert lead.dedup_key == "apexroofers_TX"
```

---

## 5. Verification Method

### Step 1: Adversarial Stress Test Verification
Execute the Challenger 2 adversarial suite:
```powershell
cd C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline
.\.venv\Scripts\python.exe -m pytest -v tests/test_m1_adversarial_stress.py
```
**Expected Outcome**: `14 passed in <0.5s` (0 failures).

### Step 2: Unit Test Suite Verification
Execute the existing Milestone 1 unit tests:
```powershell
.\.venv\Scripts\python.exe -m pytest -v tests/unit/test_scraper.py
```
**Expected Outcome**: `91 passed in ~1.0s` (0 failures).

### Step 3: Full E2E Test Suite Verification
Execute the master multi-tier test runner:
```powershell
.\.venv\Scripts\python.exe tests/run_all_tests.py
```
**Expected Outcome**: `All 203 E2E tests passed cleanly across all 4 tiers` (Exit Code: 0).

### In-Memory Verification Result
An in-memory patched test run was executed during investigation to prove efficacy prior to handoff:
- `tests/test_m1_adversarial_stress.py`: **14/14 passed**
- `tests/run_all_tests.py`: **203/203 passed**
- Machine-applicable patch file generated at:
  `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_2\proposed_fixes.patch`
