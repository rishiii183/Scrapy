# Handoff Report — explorer_m1_r2_1: Milestone 1 Remediation Investigation

**Subagent**: `explorer_m1_r2_1` (Explorer)  
**Milestone**: Milestone 1 Remediation (R2)  
**Parent / Recipient**: Orchestrator (`ea620b15-fa32-4ce7-8b6f-715d76d0d59b`)  
**Working Directory**: `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_1`  
**Date**: 2026-10-23  
**Status**: Investigation Complete — Fix Strategy Formulated & Verified  

---

## 1. Observation

Adversarial stress tests authored in `tests/unit/test_adversarial_m1.py` were executed against the Milestone 1 scraper codebase using Python 3.15 in `.venv`.

**Execution Command**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_m1.py -v
```

**Verbatim Execution Summary**:
`17 failed, 112 passed in 0.45s` (Exit Code: 1).

### Itemized Failure Observations:

#### Defect 1: Scheme Case-Sensitivity Mangling & Social Page Disqualification
- **File & Lines**: `src/scraper/filters.py`, lines 65–72:
  ```python
  def clean_url_scheme(url: str) -> str:
      """Ensure URL has a parseable scheme for urlparse."""
      url = url.strip()
      if not url.startswith(("http://", "https://", "//")):
          url = "https://" + url
      elif url.startswith("//"):
          url = "https:" + url
      return url
  ```
- **Failing Tests**:
  - `FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[HTTPS://ROOFING.CONTRACTORS/SERVICES?Q=1-roofing.contractors]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[HTTP://WWW.FACEBOOK.COM/PROFILE-facebook.com]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[HTTPS://WWW.FACEBOOK.COM/PROFILE-facebook.com]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[hTtPs://wWw.RoOfInG.cOm/Path?param=VAL#sec-roofing.com]`
- **Verbatim Error & Behavior**:
  For uppercase URL `"HTTPS://WWW.FACEBOOK.COM/PROFILE"`, `url.startswith(...)` evaluates to `False`. The function prepends `"https://"`, creating `"https://HTTPS://WWW.FACEBOOK.COM/PROFILE"`. `urlparse` parses the hostname as `"https"`. Because `"https"` is not in `SOCIAL_AND_DIRECTORIES`, valid Facebook leads are disqualified as `Custom Website (https)`.

#### Defect 2: Outbound Redirector Leakage (Direct Acceptance Criteria Violation)
- **File & Lines**: `src/scraper/filters.py`, lines 15–62, 107–121, 144–163:
  `SOCIAL_AND_DIRECTORIES` whitelists `"google.com"`, `"facebook.com"`, `"youtube.com"`, `"linkedin.com"`.
- **Failing Tests**:
  - `FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.google.com/url?q=https://apexroofing.com-apexroofing.com]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.google.com/url?q=https%3A%2F%2Fapexroofing.com&sa=D-apexroofing.com]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://l.facebook.com/l.php?u=https%3A%2F%2Fapexroofing.com-apexroofing.com]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.youtube.com/redirect?q=https%3A%2F%2Fapexroofing.com-apexroofing.com]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fapexroofing.com-apexroofing.com]`
- **Verbatim Error**:
  `AssertionError: Redirector leak! https://www.google.com/url?q=https://apexroofing.com wraps custom domain 'apexroofing.com', but was classified as qualified: qual=True, status=None (No Website - Social Only)`
- **Behavior**:
  Wrapper redirect links point to custom domains (e.g., `apexroofing.com`). `classify_website` evaluates the wrapper's host domain (`google.com`, `facebook.com`), finds it in `SOCIAL_AND_DIRECTORIES`, and erroneously qualifies the contractor as `"None (No Website - Social Only)"`. This directly violates Acceptance Criterion R1 (`ORIGINAL_REQUEST.md` line 51): *"No contractor with a functioning custom domain (.com, .io, .net, .co) is marked as 'No Website'"*.

#### Defect 3: Acceptance of 10-Digit Foreign Numbers and Invalid NANP Area Codes
- **File & Lines**: `src/scraper/normalizer.py`, lines 104–118:
  ```python
  def clean_phone_10digit(raw_phone: Optional[str]) -> Optional[str]:
      if not raw_phone:
          return None
      digits = re.sub(r"\D", "", str(raw_phone))
      if len(digits) == 11 and digits.startswith("1"):
          digits = digits[1:]
      if len(digits) == 10:
          return digits
      return None
  ```
- **Failing Tests**:
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[+49 30 123456]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[+52 81 1234 56]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[+44 1234 5678]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[012-345-6789]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[111-222-3333]`
- **Verbatim Error**:
  `clean_phone_10digit erroneously accepted invalid NANP/foreign number '+49 30 123456' as valid US phone '4930123456'`
- **Behavior**:
  `clean_phone_10digit` only checked `len(digits) == 10`. It ignored international `+` prefixes with foreign country codes (+49 Germany, +52 Mexico, +44 UK) when total digits equal 10. Furthermore, it accepted area codes starting with `0` or `1`, violating North American Numbering Plan (NANP) specifications where area codes (NPA) and central office codes (NXX) must start with digits in `[2-9]`.

#### Defect 4: Standalone Phone Normalization Drops Numbers with Extensions
- **File & Lines**: `src/scraper/normalizer.py`, lines 112–117
- **Failing Tests**:
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_phone_with_extension_dropped[(903) 807-0683 ext. 101-9038070683]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_phone_with_extension_dropped[(903) 807-0683 x4-9038070683]`
  - `FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_phone_with_extension_dropped[+1 903-807-0683 extension 45-9038070683]`
- **Critical Discovery During Investigation**:
  Challenger 1's handoff suggested using `re.split(r"(?i)\s*(?:ext|x|extension|#)\b", str(raw_phone))[0]`.
  Empirical testing revealed that `\b` fails on `x4`: `re.search(r"x\b", "x4")` yields `None` because both `x` and `4` are word characters (`\w`). Consequently, Challenger 1's proposed regex failed to strip `x4`.
  The correct, verified pattern is: `r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+"`.

---

## 2. Logic Chain

1. **Acceptance Criteria Requirement**: `ORIGINAL_REQUEST.md` line 51 states: *"No contractor with a functioning custom domain (.com, .io, .net, .co) is marked as 'No Website'"*.
2. **From Observation 2**: URLs like `https://www.google.com/url?q=https://apexroofing.com` match `"google.com"` in `SOCIAL_AND_DIRECTORIES`. Without unwrapping the embedded target in query parameter `q`, the classifier marks the lead as `None (No Website - Social Only)`. This violates Acceptance Criteria R1.
3. **Qualification Requirement**: Legitimate social links (`HTTPS://WWW.FACEBOOK.COM/PROFILE`) must be qualified.
4. **From Observation 1**: Because `clean_url_scheme` was case-sensitive, it converted `HTTPS://...` into `https://HTTPS://...`, resulting in hostname `'https'`, which falsely rejected genuine social profiles.
5. **Downstream Interface Contract**: `models.py` specifies `cleaned_phone: str` (10-digit phone for US outreach and `https://wa.me/1<phone>`).
6. **From Observation 3 & 4**: Accepting foreign country codes or invalid area codes produces invalid WhatsApp URLs and corrupts CRM deduplication. Dropping extensions causes valid numbers to be discarded.
7. **Deduplication Normalizer Synergy (Challenger 2 Observation)**: `normalize_business_name` in `src/scraper/normalizer.py` lines 239–243 omits `pllc` from its entity regex. Adding `pllc` resolves `test_normalizer_pllc_suffix_omission` simultaneously.
8. **Conclusion**: Targeted fixes in `src/scraper/filters.py` and `src/scraper/normalizer.py` completely resolve all 17 adversarial failures without regressions.

---

## 3. Caveats

- **Read-Only Investigation**: As an Explorer agent, no source code in `src/` was modified directly. Complete proposed replacement files and a `.patch` file have been prepared in `.agents/teamwork/explorer_m1_r2_1/` for the implementation worker.
- **Scope Boundary**: Challenger 2 also noted issues in `src/models.py` (missing validation for state codes and phones) and `src/scraper/maps_extractor.py` (lines 103–110 matching area code as review count when rating is missing). While this report focuses primarily on `filters.py` and `normalizer.py` per dispatch instructions, we have ensured `normalizer.py` also includes the `pllc` suffix fix.

---

## 4. Conclusion & Recommended Fix Strategy

### 4.1 Fixes for `src/scraper/filters.py`

#### A. Case-Insensitive Scheme in `clean_url_scheme`
**Location**: `src/scraper/filters.py:65–72`

**Before**:
```python
def clean_url_scheme(url: str) -> str:
    """Ensure URL has a parseable scheme for urlparse."""
    url = url.strip()
    if not url.startswith(("http://", "https://", "//")):
        url = "https://" + url
    elif url.startswith("//"):
        url = "https:" + url
    return url
```

**After**:
```python
def clean_url_scheme(url: str) -> str:
    """Ensure URL has a parseable scheme for urlparse."""
    url = url.strip()
    lower_url = url.lower()
    if not (lower_url.startswith("http://") or lower_url.startswith("https://") or lower_url.startswith("//")):
        url = "https://" + url
    elif url.startswith("//"):
        url = "https:" + url
    return url
```

#### B. Outbound Redirector Unwrapper & Integration
**Location**: `src/scraper/filters.py:12` (add imports), new function after `clean_url_scheme`, and updates to `extract_domain` and `classify_website`.

**Imports update**:
```python
from urllib.parse import parse_qs, unquote, urlparse
```

**New Function**:
```python
def unwrap_redirector_target(url: Optional[str]) -> Optional[str]:
    """
    If URL is an outbound wrapper redirector (Google, Facebook, YouTube, LinkedIn),
    extract and return the embedded destination URL if present.
    """
    if not url or not url.strip():
        return None
    curr_url = url.strip()
    depth = 0
    while depth < 5:
        depth += 1
        try:
            parsed = urlparse(clean_url_scheme(curr_url))
            hostname = (parsed.hostname or "").lower()
            if any(wrapper in hostname for wrapper in ["google.com", "facebook.com", "youtube.com", "linkedin.com"]):
                qs = parse_qs(parsed.query)
                unwrapped = None
                for key in ["q", "u", "url"]:
                    if key in qs and qs[key]:
                        cand = unquote(qs[key][0]).strip()
                        if cand.lower().startswith(("http://", "https://", "//")):
                            unwrapped = cand
                            break
                if unwrapped and unwrapped != curr_url:
                    curr_url = unwrapped
                    continue
        except Exception:
            pass
        break
    return curr_url if curr_url != url.strip() else None
```

**Updated `extract_domain`**:
```python
def extract_domain(url: Optional[str]) -> str:
    """
    Extract the normalized lowercase hostname from a URL.
    Strips 'www.' and any port numbers.
    Unwraps outbound redirectors if present.
    """
    if not url or not url.strip():
        return ""
    try:
        target = unwrap_redirector_target(url)
        clean = clean_url_scheme(target or url)
        parsed = urlparse(clean)
        hostname = (parsed.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return ""
```

**Updated `classify_website`**:
```python
def classify_website(url: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """
    Classify a contractor's website link according to PROJECT.md interface contracts.
    
    Returns:
        (is_qualified, website_status, clean_url)
        - is_qualified: bool (True if candidate for outreach)
        - website_status: 'None (No Website)' or 'None (No Website - Social Only)' or 'Custom Website (<domain>)'
        - clean_url: sanitized URL or None
    """
    if is_no_website(url):
        return True, "None (No Website)", None

    clean_url = url.strip()
    target = unwrap_redirector_target(clean_url)
    effective_url = target if target else clean_url

    if is_social_or_directory(effective_url):
        return True, "None (No Website - Social Only)", effective_url

    domain = extract_domain(effective_url)
    return False, f"Custom Website ({domain})", clean_url
```

---

### 4.2 Fixes for `src/scraper/normalizer.py`

#### A. NANP Enforcement, Foreign Country Code Rejection, and Extension Stripping in `clean_phone_10digit`
**Location**: `src/scraper/normalizer.py:104–118`

**Before**:
```python
def clean_phone_10digit(raw_phone: Optional[str]) -> Optional[str]:
    """
    Extract exactly 10 digits from a US phone string.
    Strips leading country code '1' if 11 digits.
    Returns 10-digit string or None if invalid.
    """
    if not raw_phone:
        return None
    digits = re.sub(r"\D", "", str(raw_phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    return None
```

**After**:
```python
def clean_phone_10digit(raw_phone: Optional[str]) -> Optional[str]:
    """
    Extract exactly 10 digits from a US phone string.
    - Strips 'tel:' URI prefix if present.
    - Rejects foreign country codes (+44, +49, +52, etc.); only allows +1 for NANP.
    - Strips extensions (ext, x, extension, #).
    - Strips leading country code '1' if 11 digits.
    - Enforces North American Numbering Plan (NANP) rules:
      Area code (first digit) must be in [2-9]
      Central office exchange code (fourth digit) must be in [2-9]
    Returns 10-digit string or None if invalid.
    """
    if not raw_phone:
        return None
    s = str(raw_phone).strip()
    if s.lower().startswith("tel:"):
        s = s[4:].strip()
    # Reject international numbers with + prefix other than +1 (US/NANP)
    if s.startswith("+") and not (s.startswith("+1") or s.startswith("+ 1")):
        return None
    # Strip extension patterns: ext., ext, x, extension, # followed by digits
    s = re.split(r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+", s)[0]
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        # Enforce NANP area code and central office code rules: NXX-NXX-XXXX (N = 2-9)
        if digits[0] in "23456789" and digits[3] in "23456789":
            return digits
    return None
```

#### B. Bonus Deduplication Hardening: Include `pllc` in `normalize_business_name`
**Location**: `src/scraper/normalizer.py:239–243`

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

### 4.3 Prepared Artifacts

The following ready-to-use artifacts have been deposited in this agent's folder:
1. Unified Git Patch File:
   `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_1\m1_fixes.patch`
2. Full Proposed `filters.py`:
   `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_1\proposed_filters.py`
3. Full Proposed `normalizer.py`:
   `C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_1\proposed_normalizer.py`

---

## 5. Verification Method

### Step 1: Apply Changes
The worker can apply the unified patch directly:
```powershell
git apply C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\explorer_m1_r2_1\m1_fixes.patch
```
Or copy the proposed files directly into `src/scraper/`.

### Step 2: Run Adversarial Test Suite
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_m1.py -v
```
**Expected Result**: `129 passed, 0 failed in <0.5s`.

### Step 3: Run Full Scraper Test Suite (Regression Protection)
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_scraper.py -v
```
**Expected Result**: `91 passed, 0 failed in ~1.3s`.

### Step 4: Run Combined Test Verification
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_scraper.py tests/unit/test_adversarial_m1.py -v
```
**Expected Result**: `220 passed, 0 failed in ~1.5s`.

### Invalidation Conditions:
If any of the 17 previously failing tests in `tests/unit/test_adversarial_m1.py` fail, or if any of the 91 existing unit tests regress, this assessment is invalidated.
Empirical in-memory execution during this investigation confirmed **220 passed, 0 failed**.
