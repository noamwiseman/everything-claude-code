#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Run all Python tests.

Usage: python tests/run_all.py
   or: uv run tests/run_all.py
"""

import os
import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
REPO_ROOT = TESTS_DIR.parent
TEST_GLOB = "tests/**/*_test.py"

BOX_W = 58


def box_line(s: str) -> str:
    return f"\u2551{s.ljust(BOX_W)}\u2551"


def matches_test_glob(relative_path: str) -> bool:
    normalized = relative_path.replace(os.sep, "/")
    return bool(re.match(r"^tests/(?:.+/)?[^/]+_test\.py$", normalized))


def walk_files(directory: Path, acc: list = None) -> list:
    if acc is None:
        acc = []
    for entry in sorted(directory.iterdir()):
        if entry.is_dir():
            walk_files(entry, acc)
        elif entry.is_file():
            acc.append(entry)
    return acc


def discover_test_files() -> list:
    return [
        f.relative_to(TESTS_DIR)
        for f in walk_files(TESTS_DIR)
        if matches_test_glob(str(f.relative_to(REPO_ROOT)))
    ]


test_files = discover_test_files()

print("\u2554" + "\u2550" * BOX_W + "\u2557")
print(box_line("           Everything Claude Code - Test Suite"))
print("\u255a" + "\u2550" * BOX_W + "\u255d")
print()

if not test_files:
    print(f"\u2717 No test files matched {TEST_GLOB}")
    sys.exit(1)

total_passed = 0
total_failed = 0

for test_file in test_files:
    test_path = TESTS_DIR / test_file
    display_path = str(test_file).replace(os.sep, "/")

    if not test_path.exists():
        print(f"WARNING Skipping {display_path} (file not found)")
        continue

    print(f"\n\u2501\u2501\u2501 Running {display_path} \u2501\u2501\u2501")

    result = subprocess.run(
        [sys.executable, str(test_path)],
        capture_output=True,
        text=True,
    )

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    # Show both stdout and stderr so hook warnings are visible
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="")

    combined = stdout + stderr
    passed_match = re.search(r"Passed:\s*(\d+)", combined)
    failed_match = re.search(r"Failed:\s*(\d+)", combined)

    if passed_match:
        total_passed += int(passed_match.group(1))
    if failed_match:
        total_failed += int(failed_match.group(1))

    if result.returncode != 0 and not failed_match:
        print(f"\u2717 {display_path} exited with status {result.returncode}")
        total_failed += 1

total_tests = total_passed + total_failed

print("\n\u2554" + "\u2550" * BOX_W + "\u2557")
print(box_line("                     Final Results"))
print("\u2560" + "\u2550" * BOX_W + "\u2563")
print(box_line(f"  Total Tests: {str(total_tests).rjust(4)}"))
print(box_line(f"  Passed:      {str(total_passed).rjust(4)}  \u2713"))
print(box_line(f"  Failed:      {str(total_failed).rjust(4)}  {'✗' if total_failed > 0 else ' '}"))
print("\u255a" + "\u2550" * BOX_W + "\u255d")

sys.exit(1 if total_failed > 0 else 0)
