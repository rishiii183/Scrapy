# Milestone 2 Adversarial Challenge Report: Google Sheets CRM Ingestion & Deduplication

**Subagent**: `challenger_m2_1`  
**Working Directory**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\challenger_m2_1`  
**Target Milestone**: Milestone 2 (Google Sheets CRM Ingestion & Deduplication)  
**Authoritative Specifications**: `ORIGINAL_REQUEST.md` (R2), `PROJECT.md` (Feature 8)  
**Explicit Verdict**: **`REQUEST_CHANGES`**

---

## 1. Observation

### 1.1 Implementation Code Under Review
Inspected `src/crm/dedup.py` (lines 24–36):
```python
24: def normalize_phone(phone: Optional[str]) -> str:
25:     """
26:     Extract 10-digit normalized US phone number.
27:     - Strips all non-digit characters.
28:     - Strips leading US country code '1' if 11 digits.
29:     - Returns 10-digit string if valid; otherwise empty string or raw digits.
30:     """
31:     if not phone:
32:         return ""
33:     digits = re.sub(r"\D", "", str(phone))
34:     if len(digits) == 11 and digits.startswith("1"):
35:         digits = digits[1:]
36:     return digits if len(digits) == 10 else digits
```
And `src/crm/dedup.py` (lines 154–158):
```python
154:         phone = lead.get("cleaned_phone") or lead.get("phone", "")
155:         norm_p = normalize_phone(phone)
156:         if norm_p and len(norm_p) == 10 and norm_p in self.existing_phones:
157:             return True, f"Duplicate phone matched: {norm_p}"
```

In contrast, `src/scraper/normalizer.py` (lines 104–134) implemented:
```python
104: def clean_phone_10digit(raw_phone: Optional[str]) -> Optional[str]:
...
121:     if s.startswith("+") and not (s.startswith("+1") or s.startswith("+ 1")):
122:         return None
125:     s = re.split(r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+", s)[0]
126:     digits = re.sub(r"\D", "", s)
127:     if len(digits) == 11 and digits.startswith("1"):
128:         digits = digits[1:]
129:     if len(digits) == 10:
131:         if digits[0] in "23456789" and digits[3] in "23456789":
132:             return digits
133:     return None
```

### 1.2 Empirical Reproduction of Failures
An empirical test harness was authored at `tests/test_crm_adversarial_stress.py` and executed via `.\.venv\Scripts\python.exe -m pytest tests/test_crm_adversarial_stress.py -v`.

**Command**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_crm_adversarial_stress.py -v
```

**Verbatim Pytest Output**:
```text
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_phone_extensions_vulnerability[(817) 349-5911 ext 101]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_phone_extensions_vulnerability[(817) 349-5911 ext. 101]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_phone_extensions_vulnerability[(817) 349-5911 x4]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_phone_extensions_vulnerability[(817) 349-5911 extension 202]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_phone_extensions_vulnerability[(817) 349-5911 #12]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_non_nanp_numbers_vulnerability[012-345-6789]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_non_nanp_numbers_vulnerability[112-345-6789]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_non_nanp_numbers_vulnerability[817-049-5911]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_non_nanp_numbers_vulnerability[817-149-5911]
FAILED tests/test_crm_adversarial_stress.py::TestPhoneNormalizationEdgeCases::test_crm_deduplicator_extension_phone_leak
======================== 10 failed, 55 passed in 0.41s ========================
```

### 1.3 Verbatim Standalone Python Reproduction of Deduplication Leak
**Command**:
```powershell
.\.venv\Scripts\python.exe -c "
from src.crm.dedup import CRMDeduplicator

dedup = CRMDeduplicator(existing_names={'Apex Elite Roofing'}, existing_phones={'8173495911'})
candidate = {'business_name': 'Apex Elite Contractors', 'phone': '(817) 349-5911 ext 101'}
is_dup, reason = dedup.is_duplicate(candidate)
print('Is duplicate:', is_dup)
"
```

**Verbatim Output**:
```text
Is duplicate: False
```

The candidate roofer with phone `(817) 349-5911 ext 101` was **NOT** recognized as a duplicate despite the primary phone number `8173495911` existing in the CRM.

---

## 2. Logic Chain

1. **Premise 1 (Contract Requirement)**:
   Per `ORIGINAL_REQUEST.md` (R2) and `PROJECT.md` (Feature 8), the deduplication engine must "Deduplicate by normalized business name and phone number so no contractor is added twice." Furthermore, the dispatch instructions explicitly mandate testing phone normalization with extensions (`ext 101`, `x4`) and non-NANP invalid numbers.

2. **Premise 2 (Flawed Phone Stripping in `src/crm/dedup.py`)**:
   `normalize_phone` in `src/crm/dedup.py` uses `digits = re.sub(r"\D", "", str(phone))`.
   When passed a phone number with an extension such as `(817) 349-5911 ext 101` or `(817) 349-5911 x4`, the extension digits are not stripped; instead, they are concatenated into a 13-digit string (`8173495911101`) or an 11-digit string (`81734959114`).
   Because `len(digits) != 10` and `digits` does not start with US country code `1` followed by 10 digits, line 36 returns `digits` directly (13 or 11 digits).

3. **Premise 3 (Deduplication Bypass in `CRMDeduplicator`)**:
   In `CRMDeduplicator.is_duplicate`:
   ```python
   norm_p = normalize_phone(phone)
   if norm_p and len(norm_p) == 10 and norm_p in self.existing_phones:
       return True, f"Duplicate phone matched: {norm_p}"
   ```
   When candidate phone `norm_p` is `"8173495911101"`, `len(norm_p) == 10` evaluates to `False`. The phone match condition is completely bypassed. If the business name exhibits even slight variation (e.g. "Apex Elite Roofing" vs "Apex Elite Contractors"), `is_duplicate` returns `(False, "")`.

4. **Premise 4 (Acceptance of Invalid Non-NANP Numbers)**:
   In North American Numbering Plan (NANP), valid area codes and central office codes have format `NXX` where `N in [2-9]`.
   `normalize_phone` accepts invalid numbers such as `012-345-6789` and `817-049-5911` as valid 10-digit primary keys (`0123456789`, `8170495911`).

5. **Conclusion from Logic Chain**:
   The deduplication engine has a confirmed defect where contractor phone extensions bypass deduplication, violating R2 and Feature 8. Changes are required before Milestone 2 can be approved.

---

## 3. Caveats

- **Robust Areas Confirmed**:
  1. Company name normalization is exceptionally thorough: 19 corporate suffixes (`LLC`, `Inc`, `Corp`, `PLLC`, `LLP`, `Ltd`, `Co`, `Company`, `Corporation`, `Incorporated`, `Limited Liability Company`, chained suffixes `Co., LLC`, `Group, Inc.`), ampersand handling (`&` vs `and`), leading `The`, casing, and trailing conjunctions (`and`, `or`, `of`, `&`) all passed 100% of stress tests.
  2. Intra-batch duplicate elimination is fully effective for 100-lead batches (50 duplicate pairs eliminated).
  3. Cross-run deduplication and sheet row reloading are fully functional.
  4. 100-duplicate idempotency tests all passed cleanly (`unique_ingested == 0`, `duplicates_skipped == 100`).
- **Scope Limit**:
  This challenge is strictly scoped to Milestone 2 (`src/crm/dedup.py`). Scraper-level validation in `src/scraper/normalizer.py` was not faulted because `clean_phone_10digit` in M1 already implements correct extension stripping and NANP filtering. The issue is that `src/crm/dedup.py` implemented a substandard `normalize_phone` rather than leveraging or mirroring `clean_phone_10digit`.

---

## 4. Conclusion

**Verdict: `REQUEST_CHANGES`**

`src/crm/dedup.py` must be updated to address the following two issues:

1. **Strip Phone Extensions**:
   In `src/crm/dedup.py`, `normalize_phone` must strip extension patterns (`ext`, `ext.`, `x`, `extension`, `#` followed by digits) before extracting digits, or delegate directly to `clean_phone_10digit` from `src.scraper.normalizer`.
   - `normalize_phone("(817) 349-5911 ext 101")` must return `"8173495911"`.
   - `normalize_phone("(817) 349-5911 x4")` must return `"8173495911"`.
2. **Reject Non-NANP Numbers**:
   `normalize_phone` should reject numbers with invalid area codes or central office codes (`012-345-6789`, `817-049-5911`) so they are not treated as valid 10-digit primary keys.
3. **Ensure `CRMDeduplicator.is_duplicate` Matches Extension Variants**:
   Candidate leads with phone extensions must match existing CRM records sharing the same 10-digit base number.

Recommended implementation in `src/crm/dedup.py`:
```python
from src.scraper.normalizer import clean_phone_10digit

def normalize_phone(phone: Optional[str]) -> str:
    """Extract 10-digit normalized US phone number, stripping extensions and enforcing NANP."""
    if not phone:
        return ""
    clean = clean_phone_10digit(phone)
    if clean:
        return clean
    # Fallback for non-standard / raw inputs if not matching NANP:
    s = re.split(r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+", str(phone))[0]
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else digits
```

---

## 5. Verification Method

To independently verify the bug and evaluate the fix once applied:

1. **Run the Adversarial Test Suite**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_crm_adversarial_stress.py -v
   ```
   - *Current Result*: 10 failed, 55 passed.
   - *Required Result After Fix*: 65 passed, 0 failed.

2. **Run Standalone Extension Deduplication Check**:
   ```powershell
   .\.venv\Scripts\python.exe -c "
   from src.crm.dedup import CRMDeduplicator
   dedup = CRMDeduplicator(existing_names={'Apex Elite Roofing'}, existing_phones={'8173495911'})
   candidate = {'business_name': 'Apex Elite Contractors', 'phone': '(817) 349-5911 ext 101'}
   is_dup, reason = dedup.is_duplicate(candidate)
   print('Is duplicate:', is_dup, 'Reason:', reason)
   assert is_dup is True
   print('PASSED: Extension duplicate detected!')
   "
   ```
   - *Current Result*: `AssertionError: assert False is True`.
   - *Required Result After Fix*: Exits code 0 with `PASSED: Extension duplicate detected!`.

3. **Verify Existing Tests Remain Unbroken**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_crm.py -v
   .\.venv\Scripts\python.exe tests/run_all_tests.py
   ```
   - *Expected Result*: All 41 unit tests and all 203 E2E tests pass.
