# Test Infrastructure Documentation (TEST_INFRA.md)

**Project**: Roofer Outreach Pipeline  
**Track**: Dual Track E2E Testing  
**Status**: 100% Implemented & Verified  
**Total E2E Test Cases**: 203  
**Overall Execution Time**: ~1.25s  

---

## 1. Test Architecture

The Roofer Outreach Pipeline test harness implements a dual-track testing architecture that operates independently from, yet integrates directly with, the implementation track (Milestones M1 through M4).

```
┌────────────────────────────────────────────────────────────────────────┐
│                      DUAL-TRACK E2E TEST ARCHITECTURE                  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [ tests/run_all_tests.py ] (Master Test Runner & Quality Gate)        │
│          │                                                             │
│          ├──► Tier 1: Feature Coverage (90 tests across 18 features)   │
│          ├──► Tier 2: Boundary & Corner Cases (90 tests)               │
│          ├──► Tier 3: Cross-Feature Combinations (15 pairwise tests)   │
│          └──► Tier 4: Real-World Scenarios (8 multi-state workloads)   │
│                                                                        │
│          ▲                                                             │
│          │ Bound to                                                    │
│  [ tests/e2e/contract_oracle.py ] (Authoritative Specification Oracle)  │
│          │                                                             │
│          ├── Interface Contract Schemas (RawLead, CRMRecord, Draft)    │
│          ├── Mathematical Rules (Lead Scoring, Deal Values, Delays)    │
│          └── Live Module Dynamic Inspection (src.* integration)        │
│                                                                        │
│          ▲                                                             │
│          │ Grounded by                                                 │
│  [ tests/fixtures/sample_leads.json ] (25 Real Verified US Roofers)    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities:
1. **`tests/run_all_tests.py`**: CLI entrypoint orchestrating full or tier-specific execution, reporting test counts, execution durations, pass/fail matrices, and asserting zero defects.
2. **`tests/e2e/contract_oracle.py`**: Encodes the exact specifications, mathematical rules, and interface schemas defined in `PROJECT.md` and `ORIGINAL_REQUEST.md`. Serves as the authoritative ground-truth oracle for all test assertions.
3. **`tests/conftest.py`**: Session and test-level fixtures providing verified lead records, Texas, Florida, Ohio, Georgia, Arizona contractor profiles, sample CRM rows, and staged outreach packages.
4. **`tests/fixtures/sample_leads.json`**: Authoritative dataset of 25 real verified roofing contractors discovered on Google Maps across 5 states lacking websites.

---

## 2. Test Methodology & Derivation Sources

Every test case derives its inputs and expected outputs strictly from authoritative specifications:
- **`ORIGINAL_REQUEST.md`**: Core business rules (R1-R4), Google Sheet ID `12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY`, Leads Tracker schema (columns A-U), high priority threshold (>10 reviews without website), 2-sentence icebreaker formula, and humanized jitter delays (45-180s).
- **`PROJECT.md`**: 18-feature inventory, module data flow, and interface contracts (`RawLead`, `QualifiedLead`, `CRMRecord`, `OutreachDraft`).
- **Explorer Survey Handoffs**:
  - `explorer_survey_1`: Real Google Maps DOM card attributes, anti-bot flags, and 25 verified roofer profiles across 5 US states.
  - `explorer_survey_2`: Exact 21-column schema, strict data validation lists (`🔥 High`, `⚡ Medium`, `❄️ Low`), and `Pipeline Dashboard` formula bindings (`A2:A495`, `C2:C495`, `T2:T495`).
  - `explorer_survey_3`: Staging columns (V-Z), 75% phone-only ratio triggering WhatsApp fallback, and humanized pacing safety constraints.

---

## 3. Feature Coverage Matrix (18 Features × 4 Tiers)

| # | Feature Name | Tier 1 (Coverage) | Tier 2 (Boundaries) | Tier 3 (Pairwise) | Tier 4 (Workload) | Total Tests |
|:---:|---|:---:|:---:|:---:|:---:|:---:|
| **1** | Playwright Chrome Scraper | 5 | 5 | 2 | 2 | **14** |
| **2** | Multi-State Search Catalog | 5 | 5 | 1 | 5 | **16** |
| **3** | Core Data Field Extraction | 5 | 5 | 2 | 5 | **17** |
| **4** | Strict Website Filtering | 5 | 5 | 2 | 2 | **14** |
| **5** | Trade Specialty Classifier | 5 | 5 | 2 | 5 | **17** |
| **6** | Google Sheets OAuth & Client | 5 | 5 | 1 | 2 | **13** |
| **7** | 21-Column CRM Schema Ingestion | 5 | 5 | 2 | 3 | **15** |
| **8** | Business Name & Phone Dedup | 5 | 5 | 2 | 2 | **14** |
| **9** | Lead Scoring & Priority Tagging | 5 | 5 | 2 | 5 | **17** |
| **10** | 2-Sentence Icebreaker Generator | 5 | 5 | 2 | 5 | **17** |
| **11** | Zero Placeholder Assurance | 5 | 5 | 1 | 5 | **16** |
| **12** | Staging Columns Storage (V–Z) | 5 | 5 | 2 | 2 | **14** |
| **13** | Dual-Engine Architecture | 5 | 5 | 1 | 1 | **12** |
| **14** | Staged Approval Safety Gate | 5 | 5 | 2 | 2 | **14** |
| **15** | Cold Email Channel & Simulator | 5 | 5 | 2 | 2 | **14** |
| **16** | WhatsApp Click-to-Chat Fallback | 5 | 5 | 2 | 3 | **15** |
| **17** | Humanized Pacing & Daily Cap | 5 | 5 | 2 | 2 | **14** |
| **18** | CRM Dispatch State Updater | 5 | 5 | 2 | 2 | **14** |
| **TOTAL** | **Full Suite** | **90** | **90** | **15** | **8** | **203** |

---

## 4. Test Execution Commands

### Run Master Test Runner (All 4 Tiers)
```powershell
cd C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline
.\.venv\Scripts\python.exe tests/run_all_tests.py
```

### Run Specific Tiers
```powershell
# Tier 1 only (Feature Coverage, 90 tests)
.\.venv\Scripts\python.exe tests/run_all_tests.py --tier 1

# Tier 2 only (Boundary & Corner Cases, 90 tests)
.\.venv\Scripts\python.exe tests/run_all_tests.py --tier 2

# Tier 3 only (Cross-Feature Pairwise Interactions, 15 tests)
.\.venv\Scripts\python.exe tests/run_all_tests.py --tier 3

# Tier 4 only (Real-World Application Scenarios, 8 tests)
.\.venv\Scripts\python.exe tests/run_all_tests.py --tier 4
```

### Run Directly via Pytest
```powershell
.\.venv\Scripts\pytest.exe tests/e2e/ -v
```

---

## 5. Quality Gates & Thresholds

| Quality Gate | Minimum Requirement | Verified Result | Status |
|---|---|---|:---:|
| **Tier 1 Coverage** | $\ge 5$ test cases per feature (90 total) | 90 tests | PASS |
| **Tier 2 Boundaries** | $\ge 5$ test cases per feature (90 total) | 90 tests | PASS |
| **Tier 3 Pairwise** | Cross-feature pipeline boundary interactions | 15 tests | PASS |
| **Tier 4 Workloads** | Multi-state real-world contractor profiles | 8 tests | PASS |
| **Total Test Count** | $\ge 198$ tests | 203 tests | PASS |
| **Failure Rate** | 0% (Zero tolerance for test failures) | 0 failed | PASS |
| **Execution Speed** | Full suite execution under 5.0 seconds | 1.27 seconds | PASS |
| **Placeholder Safety**| Zero unparsed `{{...}}` tags in generated copy | 0 tags found | PASS |
| **Dedup Guarantee** | Zero duplicate rows on re-running geographic area | 0 duplicate rows | PASS |

---

## 6. Escalation Protocol

As a Test Writer under Dual Track E2E Testing rules:
1. **Scope Boundaries**: Test writers write and modify test code and test fixtures only (`tests/`). Never edit implementation code (`src/`).
2. **Defect Escalation**: When a test fails due to an implementation defect in `src/`, document:
   - Failing test name and exact assertion error
   - Input payload and observed vs expected behavior
   - Reference contract in `PROJECT.md` or `contract_oracle.py`
   - Escalate directly to the orchestrator or relevant milestone worker (`worker_m1` - `worker_m4`).
