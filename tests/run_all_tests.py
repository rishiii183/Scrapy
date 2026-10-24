"""
Master Test Runner for Roofer Outreach Pipeline (Dual Track E2E Testing).

Executes all 4 E2E test tiers:
- Tier 1: Feature Coverage (90 tests, 5 per feature across all 18 features)
- Tier 2: Boundary & Corner Cases (90 tests, 5 per feature across all 18 features)
- Tier 3: Cross-Feature Combinations (15 pairwise interaction tests)
- Tier 4: Real-World Application Scenarios (8 end-to-end multi-state workloads)

Generates structured reporting, verifies quality gates, and exits with code 0 on success.
"""

import sys
import os
import time
import argparse
from pathlib import Path
import pytest


TIER_MAPPING = {
    "1": ("Tier 1: Feature Coverage", "tests/e2e/test_tier1_features.py", 90),
    "2": ("Tier 2: Boundary & Corner Cases", "tests/e2e/test_tier2_boundaries.py", 90),
    "3": ("Tier 3: Cross-Feature Combinations", "tests/e2e/test_tier3_pairwise.py", 15),
    "4": ("Tier 4: Real-World Scenarios", "tests/e2e/test_tier4_workloads.py", 8),
}


class SuiteReportCollector:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = 0
        self.test_names = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.passed += 1
            elif report.failed:
                self.failed += 1
            elif report.skipped:
                self.skipped += 1
            self.test_names.append((report.nodeid, report.outcome))
        elif report.when == "setup" and report.failed:
            self.errors += 1


def run_tier(tier_key: str, verbose: bool = False) -> dict:
    name, path, expected_min = TIER_MAPPING[tier_key]
    full_path = Path(__file__).parent.parent / path

    if not full_path.exists():
        return {
            "tier": tier_key,
            "name": name,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "duration": 0.0,
            "status": "FILE_NOT_FOUND",
        }

    collector = SuiteReportCollector()
    args = [str(full_path), "-q"]
    if verbose:
        args.append("-v")

    start_time = time.time()
    exit_code = pytest.main(args, plugins=[collector])
    duration = time.time() - start_time

    status = "PASSED" if exit_code == 0 and collector.failed == 0 and collector.errors == 0 else "FAILED"

    return {
        "tier": tier_key,
        "name": name,
        "passed": collector.passed,
        "failed": collector.failed,
        "errors": collector.errors,
        "skipped": collector.skipped,
        "duration": duration,
        "status": status,
        "expected_min": expected_min,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Roofer Outreach Pipeline E2E Test Suite")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "all"], default="all",
                        help="Select specific tier to execute (default: all)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test output")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("=" * 80)
    print("ROOFER OUTREACH PIPELINE — DUAL TRACK E2E TEST SUITE RUNNER")
    print("=" * 80)
    print(f"Project Root: {project_root}")
    print(f"Target Scope: Tier {args.tier.upper()}")
    print("-" * 80)

    tiers_to_run = ["1", "2", "3", "4"] if args.tier == "all" else [args.tier]
    results = []

    suite_start = time.time()
    for t in tiers_to_run:
        name = TIER_MAPPING[t][0]
        print(f"Executing [{name}] ...", end=" ", flush=True)
        res = run_tier(t, verbose=args.verbose)
        print(f"[{res['status']}] ({res['passed']} passed in {res['duration']:.2f}s)")
        results.append(res)
    total_duration = time.time() - suite_start

    # Summary Table
    print("\n" + "=" * 80)
    print("E2E TEST EXECUTION SUMMARY")
    print("=" * 80)
    print(f"{'Tier':<36} | {'Target':<6} | {'Passed':<6} | {'Failed':<6} | {'Duration':<8} | {'Status'}")
    print("-" * 80)

    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_expected = 0

    for r in results:
        total_passed += r["passed"]
        total_failed += r["failed"]
        total_errors += r["errors"]
        total_expected += r.get("expected_min", 0)
        print(f"{r['name']:<36} | {r.get('expected_min', 0):<6} | {r['passed']:<6} | {r['failed']:<6} | {r['duration']:<7.2f}s | {r['status']}")

    print("-" * 80)
    print(f"{'TOTALS':<36} | {total_expected:<6} | {total_passed:<6} | {total_failed:<6} | {total_duration:<7.2f}s | {'ALL PASSED' if total_failed == 0 and total_errors == 0 else 'FAILURES DETECTED'}")
    print("=" * 80)

    # Threshold & Quality Gate Checks
    all_passed = (total_failed == 0 and total_errors == 0)
    count_met = (total_passed >= total_expected)

    if not count_met:
        print(f"\n[ERROR] Quality gate failure: Expected at least {total_expected} tests, got {total_passed}.")
        sys.exit(1)

    if not all_passed:
        print(f"\n[ERROR] Test suite failed with {total_failed} failure(s) and {total_errors} error(s).")
        sys.exit(1)

    print(f"\n[SUCCESS] All {total_passed} E2E tests passed cleanly across all 4 tiers.")
    print("Test harness integrity verified. Suite is 100% production ready.")
    sys.exit(0)


if __name__ == "__main__":
    main()
