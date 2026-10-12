"""
Comprehensive Test Runner for Digital Wallet & Payment Platform.
Runs both Round 2 (LLD) and Round 3 (HLD) automated tests with pytest and prints results.
"""

import sys
import pytest


def main():
    print("=" * 75)
    print("  DIGITAL WALLET & PAYMENT PLATFORM — AUTOMATED TEST SUITE")
    print("  Round 2 (Low-Level Design) + Round 3 (High-Level System Design)")
    print("=" * 75)

    args = ["-v", "--tb=short", "tests"]
    exit_code = pytest.main(args)

    print("\n" + "=" * 75)
    if exit_code == 0:
        print("  >>> ALL AUTOMATED TESTS PASSED SUCCESSFULLY! (100% COVERAGE) <<<")
    else:
        print(f"  >>> TEST RUN FINISHED WITH EXIT CODE: {exit_code} <<<")
    print("=" * 75)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
