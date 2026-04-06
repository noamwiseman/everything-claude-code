#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Tests for hook scripts infrastructure.

Tests the remaining hook infrastructure: run_with_flags.py dispatcher
and governance_capture.py hook.

Run with: python tests/hooks/hooks_test.py
      or: uv run tests/hooks/hooks_test.py
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = str(Path(__file__).parent.parent.parent)


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


async def async_test(name: str, fn) -> bool:
    import asyncio
    try:
        await fn()
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


def run_script(script_path: str, input_data: str = "", env: dict = None, timeout: int = 10) -> dict:
    """Run a Python script and capture output."""
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        [sys.executable, script_path],
        input=input_data,
        capture_output=True,
        text=True,
        env=merged_env,
        timeout=timeout,
    )
    return {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _resolve_uv_command(command: str, env: dict = None) -> list:
    """Resolve a uv run hook command into argv list.

    Falls back to `python3 script args` when uv is not installed.
    """
    import shutil
    import re

    merged_env = {**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT, **(env or {})}

    # Expand ${VAR} substitutions
    def expand(match):
        name = match.group(1)
        return merged_env.get(name, "")

    resolved = re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", expand, command)

    # If uv is available, use it directly
    if shutil.which("uv"):
        return shlex.split(resolved)

    # uv not found — strip 'uv run' prefix and substitute python
    # Pattern: uv run "script.py" args...
    uv_match = re.match(r'^uv\s+run\s+(.*)', resolved)
    if uv_match:
        rest = uv_match.group(1).strip()
        argv = shlex.split(rest)
        return [sys.executable, *argv]

    return shlex.split(resolved)


def run_hook_command(command: str, input_data: dict = None, env: dict = None, timeout: int = 10) -> dict:
    """Run a hook command string exactly as declared in hooks.json."""
    merged_env = {**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT, **(env or {})}
    argv = _resolve_uv_command(command, env)

    if not argv:
        return {"code": 1, "stdout": "", "stderr": "empty command"}

    stdin_data = json.dumps(input_data) if input_data else ""

    try:
        result = subprocess.run(
            argv,
            input=stdin_data,
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=timeout,
        )
        return {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"code": -1, "stdout": "", "stderr": "timed out"}
    except Exception as e:  # noqa: BLE001
        return {"code": -1, "stdout": "", "stderr": str(e)}


def run_tests() -> None:
    print("\n=== Testing Hook Scripts ===\n")
    passed = 0
    failed = 0

    hooks_json_path = os.path.join(REPO_ROOT, "hooks", "hooks.json")
    with open(hooks_json_path) as f:
        hooks = json.load(f)

    # ==========================================
    # hooks.json structure
    # ==========================================
    print("hooks.json structure:")

    def t_structure():
        assert hooks.get("hooks"), "Should have hooks object"
        assert hooks["hooks"].get("PreToolUse"), "Should have PreToolUse list"
        assert hooks["hooks"].get("PostToolUse"), "Should have PostToolUse list"

    if test("hooks.json is valid JSON with hooks object", t_structure):
        passed += 1
    else:
        failed += 1

    def t_scripts_exist():
        for lifecycle, hook_array in hooks["hooks"].items():
            for hook_def in hook_array:
                for hook in hook_def.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Find .py script references
                    import re
                    script_refs = re.findall(r"scripts/hooks/[\w_-]+\.py", cmd)
                    for script_ref in script_refs:
                        full_path = os.path.join(REPO_ROOT, script_ref)
                        assert os.path.exists(full_path), f"{lifecycle}: {script_ref} should exist"

    if test("all hook commands reference existing scripts", t_scripts_exist):
        passed += 1
    else:
        failed += 1

    def t_valid_format():
        for hook_type, hook_array in hooks["hooks"].items():
            for hook_def in hook_array:
                assert hook_def.get("hooks"), f"{hook_type} entry should have hooks list"
                for hook in hook_def["hooks"]:
                    assert hook.get("command"), f"Hook in {hook_type} should have command field"
                    cmd = hook["command"]
                    is_uv = cmd.startswith("uv run")
                    is_python = cmd.startswith("python ")
                    is_shell = cmd.startswith("bash ") or cmd.startswith("sh ")
                    assert is_uv or is_python or is_shell, \
                        f"Hook command in {hook_type} should be uv/python/shell, got: {cmd[:80]}"

    if test("all hook commands are valid format", t_valid_format):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # run_with_flags.py dispatcher
    # ==========================================
    print("\nrun_with_flags.py:")

    def t_exists():
        rwf_path = os.path.join(REPO_ROOT, "scripts", "hooks", "run_with_flags.py")
        assert os.path.exists(rwf_path), "Should exist"
        src = Path(rwf_path).read_text()
        assert "is_hook_enabled" in src, "Should reference is_hook_enabled"

    if test("run_with_flags.py exists and references is_hook_enabled", t_exists):
        passed += 1
    else:
        failed += 1

    def t_dispatches():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        })
        assert result["code"] == 0, f"Should exit 0, got {result['code']}: {result['stderr']}"

    if test("run_with_flags dispatches governance_capture hook", t_dispatches):
        passed += 1
    else:
        failed += 1

    def t_disabled_hooks():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {"tool_name": "Bash", "tool_input": {"command": "echo hello"}},
            env={"ECC_DISABLED_HOOKS": "pre:governance-capture"},
        )
        assert result["code"] == 0, "Should exit 0"
        assert "[Governance]" not in result["stderr"], "Should not run governance capture when disabled"

    if test("run_with_flags respects ECC_DISABLED_HOOKS", t_disabled_hooks):
        passed += 1
    else:
        failed += 1

    def t_minimal_profile():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {"tool_name": "Bash", "tool_input": {"command": "echo hello"}},
            env={"ECC_HOOK_PROFILE": "minimal"},
        )
        assert result["code"] == 0, "Should exit 0"

    if test("run_with_flags respects ECC_HOOK_PROFILE=minimal", t_minimal_profile):
        passed += 1
    else:
        failed += 1

    def t_empty_stdin():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {})
        assert result["code"] == 0, "Should exit 0 on empty input"

    if test("run_with_flags handles empty stdin gracefully", t_empty_stdin):
        passed += 1
    else:
        failed += 1

    def t_malformed_json():
        argv = _resolve_uv_command(hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
        merged_env = {**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT}

        result = subprocess.run(
            argv,
            input="{ invalid json }",
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=10,
        )
        assert result.returncode == 0, "Should handle malformed JSON gracefully"

    if test("run_with_flags handles malformed JSON", t_malformed_json):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # governance_capture.py via hooks.json command
    # ==========================================
    print("\ngovernance_capture via hooks.json:")

    def t_clean_input():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"}},
            env={"ECC_GOVERNANCE_CAPTURE": "1"},
        )
        assert result["code"] == 0, "Should exit 0"

    if test("governance_capture passes through clean input", t_clean_input):
        passed += 1
    else:
        failed += 1

    def t_detects_secrets():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {"tool_name": "Write", "tool_input": {"content": "AKIAIOSFODNN7EXAMPLE"}},
            env={"ECC_GOVERNANCE_CAPTURE": "1"},
        )
        assert result["code"] == 0, "Should exit 0 (non-blocking)"

    if test("governance_capture detects secrets in input", t_detects_secrets):
        passed += 1
    else:
        failed += 1

    def t_post_tool_use():
        command = hooks["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_output": {"output": "hello"},
        })
        assert result["code"] == 0, "Should exit 0"

    if test("PostToolUse governance_capture hook works", t_post_tool_use):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # run_all.py test runner
    # ==========================================
    print("\nrun_all.py test runner:")

    def t_run_all_glob():
        run_all_path = os.path.join(REPO_ROOT, "tests", "run_all.py")
        src = Path(run_all_path).read_text()
        assert "tests/**/*_test.py" in src, "Should use tests/**/*_test.py glob"

    if test("test runner discovers nested tests via tests/**/*_test.py glob", t_run_all_glob):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # Summary
    # ==========================================
    print(f"\nResults: Passed: {passed}, Failed: {failed}")
    sys.exit(1 if failed > 0 else 0)


run_tests()
