#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Tests for scripts/lib/hook_flags.py

Run with: python tests/hooks/hook_flags_test.py
      or: uv run tests/hooks/hook_flags_test.py
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "lib"))

from hook_flags import (
    VALID_PROFILES,
    get_disabled_hook_ids,
    get_hook_profile,
    is_hook_enabled,
    normalize_id,
    parse_profiles,
)


def test(name: str, fn) -> bool:
    try:
        fn()
        print(f"  \u2713 {name}")
        return True
    except AssertionError as e:
        print(f"  \u2717 {name}")
        print(f"    Error: {e}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  \u2717 {name}")
        print(f"    Error: {e}")
        return False


@contextmanager
def with_env(vars_dict: dict):
    """Context manager to temporarily set/unset environment variables."""
    saved = {}
    for key, value in vars_dict.items():
        saved[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
    try:
        yield
    finally:
        for key, original in saved.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def run_tests() -> None:
    print("\n=== Testing hook_flags.py ===\n")
    passed = 0
    failed = 0

    # VALID_PROFILES tests
    print("VALID_PROFILES:")

    def t_is_set():
        assert isinstance(VALID_PROFILES, set)

    if test("is a set", t_is_set):
        passed += 1
    else:
        failed += 1

    def t_contains():
        assert "minimal" in VALID_PROFILES
        assert "standard" in VALID_PROFILES
        assert "strict" in VALID_PROFILES

    if test("contains minimal, standard, strict", t_contains):
        passed += 1
    else:
        failed += 1

    def t_size():
        assert len(VALID_PROFILES) == 3

    if test("contains exactly 3 profiles", t_size):
        passed += 1
    else:
        failed += 1

    # normalize_id tests
    print("\nnormalize_id:")

    def t_none():
        assert normalize_id(None) == ""

    if test("returns empty string for None", t_none):
        passed += 1
    else:
        failed += 1

    def t_empty():
        assert normalize_id("") == ""

    if test("returns empty string for empty string", t_empty):
        passed += 1
    else:
        failed += 1

    def t_trim():
        assert normalize_id("  hello  ") == "hello"

    if test("trims whitespace", t_trim):
        passed += 1
    else:
        failed += 1

    def t_lower():
        assert normalize_id("MyHook") == "myhook"

    if test("converts to lowercase", t_lower):
        passed += 1
    else:
        failed += 1

    def t_mixed():
        assert normalize_id("  My-Hook-ID  ") == "my-hook-id"

    if test("handles mixed case with whitespace", t_mixed):
        passed += 1
    else:
        failed += 1

    def t_number():
        assert normalize_id(123) == "123"

    if test("converts numbers to string", t_number):
        passed += 1
    else:
        failed += 1

    def t_whitespace_only():
        assert normalize_id("   ") == ""

    if test("returns empty string for whitespace-only input", t_whitespace_only):
        passed += 1
    else:
        failed += 1

    # get_hook_profile tests
    print("\nget_hook_profile:")

    def t_default():
        with with_env({"ECC_HOOK_PROFILE": None}):
            assert get_hook_profile() == "standard"

    if test("defaults to standard when env var not set", t_default):
        passed += 1
    else:
        failed += 1

    def t_minimal():
        with with_env({"ECC_HOOK_PROFILE": "minimal"}):
            assert get_hook_profile() == "minimal"

    if test("returns minimal when set to minimal", t_minimal):
        passed += 1
    else:
        failed += 1

    def t_standard():
        with with_env({"ECC_HOOK_PROFILE": "standard"}):
            assert get_hook_profile() == "standard"

    if test("returns standard when set to standard", t_standard):
        passed += 1
    else:
        failed += 1

    def t_strict():
        with with_env({"ECC_HOOK_PROFILE": "strict"}):
            assert get_hook_profile() == "strict"

    if test("returns strict when set to strict", t_strict):
        passed += 1
    else:
        failed += 1

    def t_case_insensitive():
        with with_env({"ECC_HOOK_PROFILE": "STRICT"}):
            assert get_hook_profile() == "strict"

    if test("is case-insensitive", t_case_insensitive):
        passed += 1
    else:
        failed += 1

    def t_trim_whitespace():
        with with_env({"ECC_HOOK_PROFILE": "  minimal  "}):
            assert get_hook_profile() == "minimal"

    if test("trims whitespace from env var", t_trim_whitespace):
        passed += 1
    else:
        failed += 1

    def t_invalid():
        with with_env({"ECC_HOOK_PROFILE": "invalid"}):
            assert get_hook_profile() == "standard"

    if test("defaults to standard for invalid value", t_invalid):
        passed += 1
    else:
        failed += 1

    def t_empty_profile():
        with with_env({"ECC_HOOK_PROFILE": ""}):
            assert get_hook_profile() == "standard"

    if test("defaults to standard for empty string", t_empty_profile):
        passed += 1
    else:
        failed += 1

    # get_disabled_hook_ids tests
    print("\nget_disabled_hook_ids:")

    def t_empty_set():
        with with_env({"ECC_DISABLED_HOOKS": None}):
            result = get_disabled_hook_ids()
            assert isinstance(result, set)
            assert len(result) == 0

    if test("returns empty set when env var not set", t_empty_set):
        passed += 1
    else:
        failed += 1

    def t_empty_str():
        with with_env({"ECC_DISABLED_HOOKS": ""}):
            assert len(get_disabled_hook_ids()) == 0

    if test("returns empty set for empty string", t_empty_str):
        passed += 1
    else:
        failed += 1

    def t_whitespace():
        with with_env({"ECC_DISABLED_HOOKS": "   "}):
            assert len(get_disabled_hook_ids()) == 0

    if test("returns empty set for whitespace-only string", t_whitespace):
        passed += 1
    else:
        failed += 1

    def t_single():
        with with_env({"ECC_DISABLED_HOOKS": "my-hook"}):
            result = get_disabled_hook_ids()
            assert len(result) == 1
            assert "my-hook" in result

    if test("parses single hook id", t_single):
        passed += 1
    else:
        failed += 1

    def t_multiple():
        with with_env({"ECC_DISABLED_HOOKS": "hook-a,hook-b,hook-c"}):
            result = get_disabled_hook_ids()
            assert len(result) == 3
            assert "hook-a" in result
            assert "hook-b" in result
            assert "hook-c" in result

    if test("parses multiple comma-separated hook ids", t_multiple):
        passed += 1
    else:
        failed += 1

    def t_trim_ids():
        with with_env({"ECC_DISABLED_HOOKS": " hook-a , hook-b "}):
            result = get_disabled_hook_ids()
            assert len(result) == 2
            assert "hook-a" in result
            assert "hook-b" in result

    if test("trims whitespace around hook ids", t_trim_ids):
        passed += 1
    else:
        failed += 1

    def t_lowercase_ids():
        with with_env({"ECC_DISABLED_HOOKS": "MyHook,ANOTHER"}):
            result = get_disabled_hook_ids()
            assert "myhook" in result
            assert "another" in result

    if test("normalizes hook ids to lowercase", t_lowercase_ids):
        passed += 1
    else:
        failed += 1

    def t_trailing_commas():
        with with_env({"ECC_DISABLED_HOOKS": "hook-a,,hook-b,"}):
            result = get_disabled_hook_ids()
            assert len(result) == 2
            assert "hook-a" in result
            assert "hook-b" in result

    if test("filters out empty entries from trailing commas", t_trailing_commas):
        passed += 1
    else:
        failed += 1

    # parse_profiles tests
    print("\nparse_profiles:")

    def t_null_input():
        assert parse_profiles(None) == ["standard", "strict"]

    if test("returns fallback for None input", t_null_input):
        passed += 1
    else:
        failed += 1

    def t_custom_fallback():
        assert parse_profiles(None, ["minimal"]) == ["minimal"]

    if test("uses custom fallback when provided", t_custom_fallback):
        passed += 1
    else:
        failed += 1

    def t_csv():
        assert parse_profiles("minimal,strict") == ["minimal", "strict"]

    if test("parses comma-separated string", t_csv):
        passed += 1
    else:
        failed += 1

    def t_single_str():
        assert parse_profiles("strict") == ["strict"]

    if test("parses single string value", t_single_str):
        passed += 1
    else:
        failed += 1

    def t_array():
        assert parse_profiles(["minimal", "standard"]) == ["minimal", "standard"]

    if test("parses list of profiles", t_array):
        passed += 1
    else:
        failed += 1

    def t_filter_invalid():
        assert parse_profiles("minimal,invalid,strict") == ["minimal", "strict"]

    if test("filters invalid profiles from string", t_filter_invalid):
        passed += 1
    else:
        failed += 1

    def t_filter_invalid_array():
        assert parse_profiles(["minimal", "bogus", "strict"]) == ["minimal", "strict"]

    if test("filters invalid profiles from list", t_filter_invalid_array):
        passed += 1
    else:
        failed += 1

    def t_all_invalid_str():
        assert parse_profiles("invalid,bogus") == ["standard", "strict"]

    if test("returns fallback when all string values are invalid", t_all_invalid_str):
        passed += 1
    else:
        failed += 1

    def t_all_invalid_array():
        assert parse_profiles(["invalid", "bogus"]) == ["standard", "strict"]

    if test("returns fallback when all list values are invalid", t_all_invalid_array):
        passed += 1
    else:
        failed += 1

    def t_case_str():
        assert parse_profiles("MINIMAL,STRICT") == ["minimal", "strict"]

    if test("is case-insensitive for string input", t_case_str):
        passed += 1
    else:
        failed += 1

    def t_case_array():
        assert parse_profiles(["MINIMAL", "STRICT"]) == ["minimal", "strict"]

    if test("is case-insensitive for list input", t_case_array):
        passed += 1
    else:
        failed += 1

    def t_trim_str():
        assert parse_profiles(" minimal , strict ") == ["minimal", "strict"]

    if test("trims whitespace in string input", t_trim_str):
        passed += 1
    else:
        failed += 1

    def t_null_in_array():
        assert parse_profiles([None, "strict"]) == ["strict"]

    if test("handles None values in list", t_null_in_array):
        passed += 1
    else:
        failed += 1

    # is_hook_enabled tests
    print("\nis_hook_enabled:")

    def t_default_enabled():
        with with_env({"ECC_HOOK_PROFILE": None, "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook") is True

    if test("returns True by default for a hook (standard profile)", t_default_enabled):
        passed += 1
    else:
        failed += 1

    def t_empty_id():
        with with_env({"ECC_HOOK_PROFILE": None, "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("") is True

    if test("returns True for empty hookId", t_empty_id):
        passed += 1
    else:
        failed += 1

    def t_null_id():
        with with_env({"ECC_HOOK_PROFILE": None, "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled(None) is True  # type: ignore[arg-type]

    if test("returns True for None hookId", t_null_id):
        passed += 1
    else:
        failed += 1

    def t_disabled():
        with with_env({"ECC_HOOK_PROFILE": None, "ECC_DISABLED_HOOKS": "my-hook"}):
            assert is_hook_enabled("my-hook") is False

    if test("returns False when hook is in disabled list", t_disabled):
        passed += 1
    else:
        failed += 1

    def t_disabled_case():
        with with_env({"ECC_HOOK_PROFILE": None, "ECC_DISABLED_HOOKS": "MY-HOOK"}):
            assert is_hook_enabled("my-hook") is False

    if test("disabled check is case-insensitive", t_disabled_case):
        passed += 1
    else:
        failed += 1

    def t_not_disabled():
        with with_env({"ECC_HOOK_PROFILE": None, "ECC_DISABLED_HOOKS": "other-hook"}):
            assert is_hook_enabled("my-hook") is True

    if test("returns True when hook is not in disabled list", t_not_disabled):
        passed += 1
    else:
        failed += 1

    def t_profile_mismatch():
        with with_env({"ECC_HOOK_PROFILE": "minimal", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook", {"profiles": "strict"}) is False

    if test("returns False when current profile is not in allowed profiles", t_profile_mismatch):
        passed += 1
    else:
        failed += 1

    def t_profile_match():
        with with_env({"ECC_HOOK_PROFILE": "strict", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook", {"profiles": "standard,strict"}) is True

    if test("returns True when current profile is in allowed profiles", t_profile_match):
        passed += 1
    else:
        failed += 1

    def t_single_profile():
        with with_env({"ECC_HOOK_PROFILE": "minimal", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook", {"profiles": "minimal"}) is True

    if test("returns True when current profile matches single allowed profile", t_single_profile):
        passed += 1
    else:
        failed += 1

    def t_disabled_overrides():
        with with_env({"ECC_HOOK_PROFILE": "strict", "ECC_DISABLED_HOOKS": "my-hook"}):
            assert is_hook_enabled("my-hook", {"profiles": "strict"}) is False

    if test("disabled hooks take precedence over profile match", t_disabled_overrides):
        passed += 1
    else:
        failed += 1

    def t_default_profiles():
        with with_env({"ECC_HOOK_PROFILE": "minimal", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook") is False

    if test("uses default profiles (standard, strict) when none specified", t_default_profiles):
        passed += 1
    else:
        failed += 1

    def t_standard_allowed():
        with with_env({"ECC_HOOK_PROFILE": "standard", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook") is True

    if test("allows standard profile by default", t_standard_allowed):
        passed += 1
    else:
        failed += 1

    def t_strict_allowed():
        with with_env({"ECC_HOOK_PROFILE": "strict", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook") is True

    if test("allows strict profile by default", t_strict_allowed):
        passed += 1
    else:
        failed += 1

    def t_array_profiles():
        with with_env({"ECC_HOOK_PROFILE": "minimal", "ECC_DISABLED_HOOKS": None}):
            assert is_hook_enabled("my-hook", {"profiles": ["minimal", "standard"]}) is True

    if test("accepts list profiles option", t_array_profiles):
        passed += 1
    else:
        failed += 1

    print(f"\nResults: Passed: {passed}, Failed: {failed}")
    sys.exit(1 if failed > 0 else 0)


run_tests()
