#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Integration tests for hook scripts.

Tests hook behavior in realistic scenarios with proper input/output handling.
Covers: run_with_flags.py dispatcher, governance_capture.py hook.

Run with: python tests/integration/hooks_test.py
      or: uv run tests/integration/hooks_test.py
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = str(Path(__file__).parent.parent.parent)


async def async_test(name: str, fn) -> bool:
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


def _resolve_command(command: str, env: dict = None) -> list:
    """Resolve a uv run hook command string to argv.

    Falls back to `python3 script args` when uv is not installed.
    """
    import shutil
    import re

    merged_env = {**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT, **(env or {})}

    def expand(match):
        return merged_env.get(match.group(1), "")

    resolved = re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", expand, command)

    # If uv is available, use it directly
    if shutil.which("uv"):
        return shlex.split(resolved)

    # uv not found — strip 'uv run' prefix and substitute python
    uv_match = re.match(r'^uv\s+run\s+(.*)', resolved)
    if uv_match:
        rest = uv_match.group(1).strip()
        argv = shlex.split(rest)
        return [sys.executable, *argv]

    return shlex.split(resolved)


def run_hook_command(command: str, input_data: dict = None, env: dict = None, timeout: int = 10) -> dict:
    """Run a hook command string as declared in hooks.json."""
    merged_env = {**os.environ, "CLAUDE_PLUGIN_ROOT": REPO_ROOT, **(env or {})}
    argv = _resolve_command(command, env)

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


def run_hook_with_input(script_path: str, input_data: dict = None, env: dict = None, timeout: float = 10) -> dict:
    """Run a Python hook script directly with input."""
    merged_env = {**os.environ, **(env or {})}
    stdin_data = json.dumps(input_data) if input_data else ""

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            input=stdin_data,
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=timeout,
        )
        return {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        raise TimeoutError(f"Hook timed out after {elapsed:.1f}s")


def run_tests() -> None:
    print("\n=== Hook Integration Tests ===\n")
    passed = 0
    failed = 0

    hooks_json_path = os.path.join(REPO_ROOT, "hooks", "hooks.json")
    with open(hooks_json_path) as f:
        hooks = json.load(f)

    def t(name: str, fn) -> bool:
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

    # ==========================================
    # Input Format Tests
    # ==========================================
    print("Hook Input Format Handling:")

    def test_empty_stdin():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {})
        assert result["code"] == 0, f"Should exit 0, got {result['code']}"

    if t("hooks handle empty stdin gracefully", test_empty_stdin):
        passed += 1
    else:
        failed += 1

    def test_malformed_json():
        argv = _resolve_command(hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
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

    if t("hooks handle malformed JSON input", test_malformed_json):
        passed += 1
    else:
        failed += 1

    def test_valid_input():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello", "file_path": "/test/path.py"},
        })
        assert result["code"] == 0, "Should parse and process input"

    if t("hooks parse valid tool_input correctly", test_valid_input):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # Exit Code Tests
    # ==========================================
    print("\nHook Exit Codes:")

    def test_clean_exit():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        })
        assert result["code"] == 0, "Non-blocking hook should exit 0"

    if t("governance_capture exits 0 for clean commands", test_clean_exit):
        passed += 1
    else:
        failed += 1

    def test_dangerous_exit():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {"tool_name": "Bash", "tool_input": {"command": "git push --force"}},
            env={"ECC_GOVERNANCE_CAPTURE": "1"},
        )
        assert result["code"] == 0, "Governance capture is non-blocking"

    if t("governance_capture exits 0 even for dangerous commands", test_dangerous_exit):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # Realistic Scenarios
    # ==========================================
    print("\nRealistic Scenarios:")

    def test_write_with_secrets():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/app/.env",
                    "content": "AWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE\nDB_PASSWORD=hunter2",
                },
            },
            env={"ECC_GOVERNANCE_CAPTURE": "1"},
        )
        assert result["code"] == 0, "Should process without blocking"

    if t("PreToolUse governance hook processes Write with secrets", test_write_with_secrets):
        passed += 1
    else:
        failed += 1

    def test_post_tool_output():
        command = hooks["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(
            command,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "cat /etc/passwd"},
                "tool_output": {"output": "root:x:0:0:root:/root:/bin/bash"},
            },
            env={"ECC_GOVERNANCE_CAPTURE": "1"},
        )
        assert result["code"] == 0, "Should process output without blocking"

    if t("PostToolUse governance hook processes tool output", test_post_tool_output):
        passed += 1
    else:
        failed += 1

    def test_large_input():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        large_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/test.py", "content": "x" * 100000},
        }
        start_time = time.time()
        result = run_hook_command(command, large_input)
        elapsed = time.time() - start_time

        assert result["code"] == 0, "Should complete successfully"
        assert elapsed < 10, f"Should complete in <10s, took {elapsed:.1f}s"

    if t("governance hook handles very large input without hanging", test_large_input):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # Error Handling
    # ==========================================
    print("\nError Handling:")

    def test_unexpected_structure():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {
            "unexpected": {"nested": {"deeply": "value"}},
        })
        assert result["code"] == 0, "Should handle unexpected input structure"

    if t("hooks do not crash on unexpected input structure", test_unexpected_structure):
        passed += 1
    else:
        failed += 1

    def test_null_values():
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        result = run_hook_command(command, {
            "tool_name": None,
            "tool_input": None,
        })
        assert result["code"] == 0, "Should handle null values gracefully"

    if t("hooks handle null values in input", test_null_values):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # Timeout Enforcement
    # ==========================================
    print("\nTimeout Enforcement:")

    def test_timeout():
        test_dir = tempfile.mkdtemp(prefix="hook-integration-test-")
        hanging_hook_path = os.path.join(test_dir, "hanging_hook.py")
        Path(hanging_hook_path).write_text(
            "import time\nwhile True:\n    time.sleep(0.1)\n"
        )

        try:
            start_time = time.time()
            error = None
            try:
                run_hook_with_input(hanging_hook_path, {}, {}, timeout=0.5)
            except TimeoutError as e:
                error = e

            elapsed = time.time() - start_time
            assert error is not None, "Should raise TimeoutError"
            assert "timed out" in str(error).lower(), "Error should mention timeout"
            assert elapsed >= 0.45, f"Should wait at least ~0.5s, waited {elapsed:.2f}s"
            assert elapsed < 3, f"Should not wait much longer than 0.5s, waited {elapsed:.2f}s"
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if t("run_hook_with_input kills hanging hooks after timeout", test_timeout):
        passed += 1
    else:
        failed += 1

    # ==========================================
    # Summary
    # ==========================================
    print("\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}\n")

    sys.exit(1 if failed > 0 else 0)


run_tests()
