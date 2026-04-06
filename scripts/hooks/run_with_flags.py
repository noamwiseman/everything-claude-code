#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Executes a hook script only when enabled by ECC hook profile flags.

Usage:
  uv run run_with_flags.py <hookId> <scriptRelativePath> [profilesCsv]
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

MAX_STDIN = 1024 * 1024
STDIN_CHUNK_SIZE = 65536

# Insert lib directory into path for hook_flags import
_SCRIPT_DIR = Path(__file__).parent
_LIB_DIR = _SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(_LIB_DIR))

from hook_flags import is_hook_enabled  # noqa: E402


def _read_stdin_raw() -> tuple:
    """Read all stdin up to MAX_STDIN bytes.

    Returns:
        Tuple of (raw_str, truncated_bool)
    """
    chunks = []
    total_size = 0
    truncated = False

    while True:
        chunk = sys.stdin.read(STDIN_CHUNK_SIZE)
        if not chunk:
            break
        if total_size < MAX_STDIN:
            remaining = MAX_STDIN - total_size
            chunks.append(chunk[:remaining])
            total_size += len(chunk)
            if len(chunk) > remaining:
                truncated = True
        else:
            truncated = True

    return "".join(chunks), truncated


def _write_stderr(stderr: str) -> None:
    if not stderr:
        return
    if not stderr.endswith("\n"):
        stderr += "\n"
    sys.stderr.write(stderr)


def _emit_hook_result(raw: str, output) -> int:
    """Write hook output and return exit code."""
    if isinstance(output, (str, bytes)):
        sys.stdout.write(str(output))
        return 0

    if isinstance(output, dict):
        stderr_val = output.get("stderr")
        if stderr_val:
            _write_stderr(str(stderr_val))

        if "stdout" in output:
            sys.stdout.write(str(output.get("stdout") or ""))
        elif not isinstance(output.get("exitCode"), int) or output.get("exitCode") == 0:
            sys.stdout.write(raw)

        exit_code = output.get("exitCode")
        return exit_code if isinstance(exit_code, int) else 0

    sys.stdout.write(raw)
    return 0


def _get_plugin_root() -> str:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if plugin_root:
        return plugin_root
    # __file__ is scripts/hooks/run_with_flags.py → go up two levels to repo root
    return str(Path(__file__).parent.parent.parent)


def main() -> None:
    args = sys.argv[1:]
    hook_id = args[0] if len(args) > 0 else None
    rel_script_path = args[1] if len(args) > 1 else None
    profiles_csv = args[2] if len(args) > 2 else None

    raw, truncated = _read_stdin_raw()

    if not hook_id or not rel_script_path:
        sys.stdout.write(raw)
        sys.exit(0)

    if not is_hook_enabled(hook_id, {"profiles": profiles_csv}):
        sys.stdout.write(raw)
        sys.exit(0)

    plugin_root = _get_plugin_root()
    resolved_root = str(Path(plugin_root).resolve())
    script_path = str(Path(plugin_root, rel_script_path).resolve())

    # Prevent path traversal outside the plugin root (Python 3.9+ is_relative_to)
    try:
        Path(script_path).relative_to(resolved_root)
    except ValueError:
        sys.stderr.write(f"[Hook] Path traversal rejected for {hook_id}: {script_path}\n")
        sys.stdout.write(raw)
        sys.exit(0)

    if not Path(script_path).exists():
        sys.stderr.write(f"[Hook] Script not found for {hook_id}: {script_path}\n")
        sys.stdout.write(raw)
        sys.exit(0)

    # Prefer direct import when the hook exports a run() function.
    # This eliminates one Python process spawn per hook.
    #
    # SAFETY: Only import hooks that define run(). Legacy hooks may execute
    # side effects at module scope which would interfere with the parent process.
    hook_module = None
    try:
        src = Path(script_path).read_text(encoding="utf-8")
        has_run_export = "def run(" in src

        if has_run_export:
            spec = importlib.util.spec_from_file_location("_hook_module", script_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                hook_module = mod
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[Hook] import failed for {hook_id}: {e}\n")

    if hook_module and hasattr(hook_module, "run") and callable(hook_module.run):
        try:
            output = hook_module.run(raw, {"truncated": truncated, "maxStdin": MAX_STDIN})
            sys.exit(_emit_hook_result(raw, output))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[Hook] run() error for {hook_id}: {e}\n")
            sys.stdout.write(raw)
        sys.exit(0)

    # Legacy path: spawn a child Python process for hooks without run() export
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            input=raw,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **os.environ,
                "ECC_HOOK_INPUT_TRUNCATED": "1" if truncated else "0",
                "ECC_HOOK_INPUT_MAX_BYTES": str(MAX_STDIN),
            },
            cwd=os.getcwd(),
        )
    except subprocess.TimeoutExpired:
        _write_stderr(f"[Hook] legacy hook timed out for {hook_id}")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        _write_stderr(f"[Hook] legacy hook execution failed for {hook_id}: {e}")
        sys.exit(1)

    if result.stdout:
        sys.stdout.write(result.stdout)
    elif result.returncode == 0:
        sys.stdout.write(raw)

    if result.stderr:
        sys.stderr.write(result.stderr)

    if result.returncode not in (0, None):
        _write_stderr(f"[Hook] legacy hook exited {result.returncode} for {hook_id}")

    sys.exit(result.returncode if result.returncode is not None else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[Hook] run_with_flags error: {e}\n")
        sys.exit(0)
