# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Shared hook enable/disable controls.

Controls:
- ECC_HOOK_PROFILE=minimal|standard|strict (default: standard)
- ECC_DISABLED_HOOKS=comma,separated,hook,ids
"""

import os
from typing import Optional

VALID_PROFILES = {"minimal", "standard", "strict"}


def normalize_id(value) -> str:
    """Normalize a hook ID to lowercase, trimmed string."""
    return str(value or "").strip().lower()


def get_hook_profile() -> str:
    """Get the current hook profile from environment."""
    raw = str(os.environ.get("ECC_HOOK_PROFILE", "standard")).strip().lower()
    return raw if raw in VALID_PROFILES else "standard"


def get_disabled_hook_ids() -> set:
    """Get the set of disabled hook IDs from environment."""
    raw = str(os.environ.get("ECC_DISABLED_HOOKS", ""))
    if not raw.strip():
        return set()
    return {normalize_id(v) for v in raw.split(",") if normalize_id(v)}


def parse_profiles(raw_profiles, fallback: Optional[list] = None) -> list:
    """Parse profiles from string, list, or None.

    Args:
        raw_profiles: Comma-separated string, list, or None
        fallback: Default profiles if raw_profiles is None or all invalid
    Returns:
        List of valid profile strings
    """
    if fallback is None:
        fallback = ["standard", "strict"]

    if raw_profiles is None:
        return list(fallback)

    if isinstance(raw_profiles, list):
        parsed = [
            str(v or "").strip().lower()
            for v in raw_profiles
            if str(v or "").strip().lower() in VALID_PROFILES
        ]
        return parsed if parsed else list(fallback)

    parsed = [
        v.strip().lower()
        for v in str(raw_profiles).split(",")
        if v.strip().lower() in VALID_PROFILES
    ]
    return parsed if parsed else list(fallback)


def is_hook_enabled(hook_id, options: Optional[dict] = None) -> bool:
    """Check if a hook is enabled based on profile and disabled list.

    Args:
        hook_id: The hook identifier
        options: Dict with optional 'profiles' key (comma-separated or list)
    Returns:
        True if the hook should run, False if it should be skipped
    """
    opts = options or {}
    id_ = normalize_id(hook_id)
    if not id_:
        return True

    disabled = get_disabled_hook_ids()
    if id_ in disabled:
        return False

    profile = get_hook_profile()
    allowed_profiles = parse_profiles(opts.get("profiles"))
    return profile in allowed_profiles
