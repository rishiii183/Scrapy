# Handoff Report — challenger_m1_1: Milestone 1 Adversarial Verification

**Milestone**: Milestone 1: Google Maps Extraction Engine  
**Agent Role**: Empirical Challenger (`challenger_m1_1`)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

Adversarial stress-testing of Milestone 1 components was conducted using the project virtual environment `.\.venv\Scripts\python.exe` and recorded in `tests/unit/test_adversarial_m1.py`.

Execution of test suite:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_m1.py -v
```
Output:
```
=========================== short test summary info ===========================
FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[HTTPS://ROOFING.CONTRACTORS/SERVICES?Q=1-roofing.contractors]
FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[HTTP://WWW.FACEBOOK.COM/PROFILE-facebook.com]
FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[HTTPS://WWW.FACEBOOK.COM/PROFILE-facebook.com]
FAILED tests/unit/test_adversarial_m1.py::TestWebsiteFilteringAdversarial::test_bug_scheme_case_sensitivity[hTtPs://wWw.RoOfInG.cOm/Path?param=VAL#sec-roofing.com]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[+49 30 123456]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[+52 81 1234 56]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[+44 1234 5678]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[012-345-6789]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_foreign_or_invalid_nanp_accepted[111-222-3333]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_phone_with_extension_dropped[(903) 807-0683 ext. 101-9038070683]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_phone_with_extension_dropped[(903) 807-0683 x4-9038070683]
FAILED tests/unit/test_adversarial_m1.py::TestPhoneNormalizationAdversarial::test_bug_phone_with_extension_dropped[+1 903-807-0683 extension 45-9038070683]
FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.google.com/url?q=https://apexroofing.com-apexroofing.com]
FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.google.com/url?q=https%3A%2F%2Fapexroofing.com&sa=D-apexroofing.com]
FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://l.facebook.com/l.php?u=https%3A%2F%2Fapexroofing.com-apexroofing.com]
FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.youtube.com/redirect?q=https%3A%2F%2Fapexroofing.com-apexroofing.com]
FAILED tests/unit/test_adversarial_m1.py::TestRedirectorLeakageAdversarial::test_bug_social_redirector_leak[https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fapexroofing.com-apexroofing.com]
======================= 17 failed, 112 passed in 0.55s ========================
```

### Specific Defect Observations:

#### Defect 1: Scheme Case-Sensitivity Mangling & Social Page Rejection
- **File**: `src/scraper/filters.py`, lines 65–72:
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
- **Observed Behavior**:
  `classify_website('HTTPS://WWW.FACEBOOK.COM/PROFILE')` returns:
  `(False, 'Custom Website (https)', 'HTTPS://WWW.FACEBOOK.COM/PROFILE')`
- **Error**: `url.startswith(...)` is case-sensitive. When passed uppercase scheme `HTTPS://` or `HTTP://`, it prepends `https://`, transforming it into `https://HTTPS://WWW.FACEBOOK.COM/PROFILE`. `urlparse` parses the hostname as `'https'`. Because `'https'` is not in `SOCIAL_AND_DIRECTORIES`, valid Facebook/Instagram/TikTok social pages are disqualified as "Custom Website (https)".

#### Defect 2: Outbound Redirector Leakage (Direct Acceptance Criteria Violation)
- **File**: `src/scraper/filters.py`, lines 15–62, 107–121:
  `SOCIAL_AND_DIRECTORIES` whitelists `"google.com"`, `"facebook.com"`, `"youtube.com"`, `"linkedin.com"`.
- **Observed Behavior**:
  ```python
  classify_website('https://www.google.com/url?q=https://apexroofing.com')
  # Returns: (True, 'None (No Website - Social Only)', 'https://www.google.com/url?q=https://apexroofing.com')
  ```
- **Error**: When a Google Maps search card links to a Google or Facebook redirector (`google.com/url?q=...` or `l.facebook.com/l.php?u=...`) that targets a custom website (`apexroofing.com`), the classifier only evaluates the redirector hostname, completely missing the target custom domain. This directly violates Acceptance Criterion R1: *"No contractor with a functioning custom domain (.com, .io, .net, .co) is marked as 'No Website'"*.

#### Defect 3: Acceptance of 10-Digit Foreign Numbers and Invalid NANP Area Codes
- **File**: `src/scraper/normalizer.py`, lines 104–118:
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
- **Observed Behavior**:
  `clean_phone_10digit("+49 30 123456")` returns `'4930123456'` and formats to `'(493) 012-3456'`.
  `clean_phone_10digit("+52 81 1234 56")` returns `'5281123456'` and formats to `'(528) 112-3456'`.
  `clean_phone_10digit("012-345-6789")` returns `'0123456789'`.
  `clean_phone_10digit("111-222-3333")` returns `'1112223333'`.
- **Error**: `clean_phone_10digit` only validates `len(digits) == 10`. It fails to detect leading `+` with foreign country codes (+49 Germany, +52 Mexico, +44 UK) when total digits equal 10. Furthermore, it accepts area codes starting with `0` or `1`, which violates North American Numbering Plan (NANP) specifications where area codes (NPA) and central office codes (NXX) must start with digits `[2-9]`.

#### Defect 4: Standalone Phone Normalization Drops Numbers with Extensions
- **File**: `src/scraper/normalizer.py`, lines 112–117:
- **Observed Behavior**:
  `clean_phone_10digit('(903) 807-0683 ext. 101')` returns `None`.
  `clean_phone_10digit('(903) 807-0683 x4')` returns `None`.
- **Error**: `re.sub(r"\D", "", str(raw_phone))` removes the `"ext"`, but leaves the trailing extension digits, producing strings of 11–14 digits (e.g. `9038070683101`), which fails `len == 10` and causes `clean_phone_10digit` to return `None`.

---

## 2. Logic Chain

1. **Acceptance Criteria Requirement**: `ORIGINAL_REQUEST.md` line 51 and `PROJECT.md` line 105 strictly demand: *"No contractor with a functioning custom domain (.com, .io, .net, .co) is marked as 'No Website'"*.
2. **From Observation Defect 2**: A contractor whose link on Google Maps is wrapped in Google Search / Redirect URL (`https://www.google.com/url?q=https://apexroofing.com`) is classified by `filters.py:classify_website` as `is_qualified=True` with `website_status="None (No Website - Social Only)"`. Because `apexroofing.com` is a functioning custom `.com` domain, this is an empirical breach of the acceptance criteria.
3. **Acceptance Criteria Requirement**: The system must qualify contractors who have missing websites or ONLY valid social/directory pages (Facebook, Yelp, etc.).
4. **From Observation Defect 1**: A contractor whose Facebook URL begins with uppercase `HTTPS://WWW.FACEBOOK.COM/...` is mangled into `https://HTTPS://...` by `clean_url_scheme()`, extracting hostname `'https'`. This causes `classify_website` to label them `Custom Website (https)` and disqualify them, generating a false negative that drops genuine outreach targets.
5. **System Pipeline Requirement**: M1 feeds into M2 (CRM) and M4 (Outreach Dispatch via WhatsApp). In `models.py`, `OutreachDraft.staged_wame_url` builds `https://wa.me/1<cleaned_phone>?text=...`.
6. **From Observation Defect 3**: Foreign phone numbers summing to 10 digits (`+49 30 123456`, `+52 81 1234 56`) or NANP-invalid numbers (`012-345-6789`) are marked as valid 10-digit US numbers by `clean_phone_10digit`, resulting in invalid WhatsApp links like `https://wa.me/14930123456` being staged in the CRM.
7. **Conclusion Supported**: Milestone 1 cannot be approved in its current form due to these critical filtering and normalization bugs.

---

## 3. Caveats

- **Robust Areas Confirmed**:
  - All standard lowercase custom domains across diverse TLDs (`.com`, `.io`, `.net`, `.co`, `.org`, `.biz`, `.us`, `.roofing`, `.contractors`, `.build`, `.repair`, `.services`, `.solutions`, `.xyz`, `.online`, `.site`), IP addresses (IPv4 & IPv6), port numbers, query strings, and paths are correctly detected and rejected (31 tests passed).
  - Deceptive subdomains and phishing platforms (`facebook.com.attacker.com`, `yelp.com.phish.biz`, `evil.com/facebook.com`, `facebook.com:pass@evil.com`) are correctly detected and rejected (17 tests passed).
  - All 44 platforms in `SOCIAL_AND_DIRECTORIES` and their valid subdomains (`m.facebook.com`, `biz.yelp.com`, `pro.angi.com`, `*.business.site`) qualify correctly when presented in lowercase.
  - In `GoogleMapsExtractor.parse_card_data`, the DOM card regex `phone_match = re.search(r"(\+?1?[-.\s]?\(?[2-9][0-9]{2}\)?[-.\s]?[2-9][0-9]{2}[-.\s]?[0-9]{4})", card_text)` happens to isolate the 10-digit base number before any extension in the card text, mitigating Defect 4 within Maps card parsing. However, `clean_phone_10digit` in `normalizer.py` remains vulnerable when called directly by downstream modules.

---

## 4. Conclusion & Required Changes

**Verdict**: **REQUEST_CHANGES**

The implementation worker (`06c4e5f5-6cab-41db-8976-92cefde534ce`) must apply the following targeted fixes:

1. **Fix `clean_url_scheme` in `src/scraper/filters.py`**:
   Make scheme detection case-insensitive:
   ```python
   def clean_url_scheme(url: str) -> str:
       url = url.strip()
       lower_url = url.lower()
       if not (lower_url.startswith("http://") or lower_url.startswith("https://") or lower_url.startswith("//")):
           url = "https://" + url
       elif url.startswith("//"):
           url = "https:" + url
       return url
   ```

2. **Handle Open Redirectors & Wrapper URLs in `src/scraper/filters.py`**:
   Unwrap redirector target parameters (e.g. `q`, `u`, `url`) before checking `SOCIAL_AND_DIRECTORIES`:
   ```python
   from urllib.parse import parse_qs, unquote

   def unwrap_redirector_target(url: str) -> Optional[str]:
       parsed = urlparse(clean_url_scheme(url))
       hostname = (parsed.hostname or "").lower()
       if any(wrapper in hostname for wrapper in ["google.com", "facebook.com", "youtube.com", "linkedin.com"]):
           qs = parse_qs(parsed.query)
           for key in ["q", "u", "url"]:
               if key in qs and qs[key]:
                   target = unquote(qs[key][0])
                   if target.startswith(("http://", "https://")):
                       return target
       return None
   ```
   If a redirector wraps an external URL, evaluate `classify_website(target_url)` instead.

3. **Harden `clean_phone_10digit` in `src/scraper/normalizer.py`**:
   - Check if string starts with international prefix `+` (other than `+1`); if so, return `None`.
   - Strip phone extensions before digit extraction: `raw_clean = re.split(r"(?i)\s*(?:ext|x|extension|#)\b", str(raw_phone))[0]`.
   - Enforce NANP area code / central office code rules: `digits[0] in '23456789' and digits[3] in '23456789'`.

---

## 5. Verification Method

To verify these findings independently or to verify fixes after implementation:

1. Execute the comprehensive adversarial suite:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_m1.py -v
   ```
2. Invalidation Condition:
   When all 17 failing tests in `tests/unit/test_adversarial_m1.py` pass cleanly (129 passed, 0 failed), and existing unit/E2E suites still pass:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_scraper.py
   .\.venv\Scripts\python.exe tests/run_all_tests.py
   ```
