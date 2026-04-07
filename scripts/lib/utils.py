# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Cross-platform utility functions for Claude Code hooks and scripts.
Works on Windows, macOS, and Linux.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

# Platform detection
is_windows = sys.platform == "win32"
is_macos = sys.platform == "darwin"
is_linux = sys.platform == "linux"

SESSION_DATA_DIR_NAME = "session-data"
LEGACY_SESSIONS_DIR_NAME = "sessions"
WINDOWS_RESERVED_SESSION_IDS = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def get_home_dir() -> str:
    """Get the user's home directory (cross-platform)."""
    return str(Path.home())


def get_claude_dir() -> str:
    """Get the Claude config directory."""
    return str(Path.home() / ".claude")


def get_sessions_dir() -> str:
    """Get the sessions directory."""
    return str(Path(get_claude_dir()) / SESSION_DATA_DIR_NAME)


def get_legacy_sessions_dir() -> str:
    """Get the legacy sessions directory used by older ECC installs."""
    return str(Path(get_claude_dir()) / LEGACY_SESSIONS_DIR_NAME)


def get_session_search_dirs() -> list:
    """Get all session directories to search, in canonical-first order."""
    return list(dict.fromkeys([get_sessions_dir(), get_legacy_sessions_dir()]))


def get_learned_skills_dir() -> str:
    """Get the learned skills directory."""
    return str(Path(get_claude_dir()) / "skills" / "learned")


def get_temp_dir() -> str:
    """Get the temp directory (cross-platform)."""
    return tempfile.gettempdir()


def ensure_dir(dir_path: str) -> str:
    """Ensure a directory exists (create if not).

    Args:
        dir_path: Directory path to create
    Returns:
        The directory path
    Raises:
        RuntimeError: If directory cannot be created
    """
    try:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno != 17:  # EEXIST
            raise RuntimeError(f"Failed to create directory '{dir_path}': {e}") from e
    return dir_path


def get_date_string() -> str:
    """Get current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def get_time_string() -> str:
    """Get current time in HH:MM format."""
    return datetime.now().strftime("%H:%M")


def get_date_time_string() -> str:
    """Get current datetime in YYYY-MM-DD HH:MM:SS format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_git_repo_name() -> str | None:
    """Get the git repository name."""
    result = run_command("git rev-parse --show-toplevel")
    if not result["success"]:
        return None
    return Path(result["output"]).name


def get_project_name() -> str | None:
    """Get project name from git repo or current directory."""
    repo_name = get_git_repo_name()
    if repo_name:
        return repo_name
    return Path.cwd().name or None


def sanitize_session_id(raw: str) -> str | None:
    """Sanitize a string for use as a session filename segment.

    Replaces invalid characters with hyphens, collapses runs, strips
    leading/trailing hyphens, and removes leading dots so hidden-dir names
    like ".claude" map cleanly to "claude".

    Pure non-ASCII inputs get a stable 8-char hash so distinct names do not
    collapse to the same fallback session id. Mixed-script inputs retain their
    ASCII part and gain a short hash suffix for disambiguation.
    """
    if not raw or not isinstance(raw, str):
        return None

    has_non_ascii = any(ord(c) > 0x7F for c in raw)
    normalized = re.sub(r"^\.+", "", raw)
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", normalized)
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = re.sub(r"^-+|-+$", "", sanitized)

    if sanitized:
        suffix = hashlib.sha256(normalized.encode()).hexdigest()[:6]
        if sanitized.upper() in WINDOWS_RESERVED_SESSION_IDS:
            return f"{sanitized}-{suffix}"
        if not has_non_ascii:
            return sanitized
        return f"{sanitized}-{suffix}"

    # Remove whitespace and Unicode punctuation
    meaningful = "".join(
        c for c in normalized
        if not c.isspace() and not unicodedata.category(c).startswith("P")
    )
    if not meaningful:
        return None

    return hashlib.sha256(normalized.encode()).hexdigest()[:8]


def get_session_id_short(fallback: str = "default") -> str:
    """Get short session ID from CLAUDE_SESSION_ID environment variable.

    Returns last 8 characters, falls back to a sanitized project name then 'default'.
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if session_id:
        sanitized = sanitize_session_id(session_id[-8:])
        if sanitized:
            return sanitized
    return sanitize_session_id(get_project_name()) or sanitize_session_id(fallback) or "default"


def find_files(dir_path: str, pattern: str, options: dict | None = None) -> list:
    """Find files matching a pattern in a directory (cross-platform).

    Args:
        dir_path: Directory to search
        pattern: File pattern (e.g., "*.tmp", "*.md")
        options: Options dict with keys: maxAge (days), recursive (bool)
    Returns:
        List of dicts with 'path' and 'mtime' keys, sorted newest first
    """
    if not dir_path or not isinstance(dir_path, str):
        return []
    if not pattern or not isinstance(pattern, str):
        return []

    opts = options or {}
    max_age = opts.get("maxAge", None)
    recursive = opts.get("recursive", False)
    results = []

    if not Path(dir_path).exists():
        return results

    # Escape regex special characters then convert glob wildcards
    regex_pattern = re.escape(pattern)
    regex_pattern = regex_pattern.replace(r"\*", ".*").replace(r"\?", ".")
    regex = re.compile(f"^{regex_pattern}$")

    def search_dir(current_dir: str) -> None:
        try:
            for entry in Path(current_dir).iterdir():
                if entry.is_file() and regex.match(entry.name):
                    try:
                        stat = entry.stat()
                        mtime_ms = stat.st_mtime * 1000
                        if max_age is not None:
                            now_ms = datetime.now().timestamp() * 1000
                            age_days = (now_ms - mtime_ms) / (1000 * 60 * 60 * 24)
                            if age_days <= max_age:
                                results.append({"path": str(entry), "mtime": mtime_ms})
                        else:
                            results.append({"path": str(entry), "mtime": mtime_ms})
                    except OSError:
                        continue
                elif entry.is_dir() and recursive:
                    search_dir(str(entry))
        except PermissionError:
            pass

    search_dir(dir_path)
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results


def read_stdin_json(options: dict | None = None) -> dict:
    """Read JSON from stdin (for hook input).

    Args:
        options: Options dict with keys: maxSize (bytes), timeoutS (seconds, non-Windows only)
    Returns:
        Parsed JSON object, or empty dict if stdin is empty or invalid
    """
    opts = options or {}
    max_size = opts.get("maxSize", 1024 * 1024)
    timeout_s = opts.get("timeoutS", 5)

    prev_handler = None

    def _timeout_handler(signum: int, frame) -> None:
        raise TimeoutError("stdin read timed out")

    try:
        if not is_windows and timeout_s:
            prev_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_s)
        data = sys.stdin.read(max_size)
        if not is_windows and timeout_s:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)
        return json.loads(data) if data.strip() else {}
    except (json.JSONDecodeError, OSError, TimeoutError):
        if not is_windows and timeout_s and prev_handler is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)
        return {}


def log(message: str) -> None:
    """Log to stderr (visible to user in Claude Code)."""
    print(message, file=sys.stderr)


def output(data) -> None:
    """Output to stdout (returned to Claude)."""
    if isinstance(data, (dict, list)):
        print(json.dumps(data))
    else:
        print(data)


def read_file(file_path: str) -> str | None:
    """Read a text file safely."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def write_file(file_path: str, content: str) -> None:
    """Write a text file."""
    ensure_dir(str(Path(file_path).parent))
    Path(file_path).write_text(content, encoding="utf-8")


def append_file(file_path: str, content: str) -> None:
    """Append to a text file."""
    ensure_dir(str(Path(file_path).parent))
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(content)


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    if not re.match(r"^[a-zA-Z0-9_.-]+$", cmd):
        return False
    return shutil.which(cmd) is not None


def run_command(cmd: str, options: dict | None = None) -> dict:
    """Run a command and return output.

    SECURITY NOTE: Only use with trusted, hardcoded commands. Never pass
    user-controlled input directly.

    Args:
        cmd: Command to execute (should be trusted/hardcoded)
        options: Additional options passed to subprocess.run (unused, kept for API compatibility)
    Returns:
        Dict with 'success' (bool) and 'output' (str) keys
    """
    allowed_prefixes = ["git ", "node ", "npx ", "which ", "where ", "python ", "uv "]
    if not any(cmd.startswith(prefix) for prefix in allowed_prefixes):
        return {"success": False, "output": "run_command blocked: unrecognized command prefix"}

    # Reject shell metacharacters
    unquoted = re.sub(r'"[^"]*"', "", cmd)
    unquoted = re.sub(r"'[^']*'", "", unquoted)
    if re.search(r"[;|&\n]", unquoted) or re.search(r"[`$]", cmd):
        return {"success": False, "output": "run_command blocked: shell metacharacters not allowed"}

    try:
        argv = shlex.split(cmd)
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
        )
        return {"success": result.returncode == 0, "output": result.stdout.strip()}
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        return {"success": False, "output": str(e)}


def is_git_repo() -> bool:
    """Check if current directory is a git repository."""
    return run_command("git rev-parse --git-dir")["success"]


def get_git_modified_files(patterns: list | None = None) -> list:
    """Get git modified files, optionally filtered by regex patterns.

    Args:
        patterns: List of regex pattern strings to filter files.
                  Invalid patterns are silently skipped.
    Returns:
        List of modified file paths
    """
    if not is_git_repo():
        return []

    result = run_command("git diff --name-only HEAD")
    if not result["success"]:
        return []

    files = [f for f in result["output"].split("\n") if f]

    if patterns:
        compiled = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            try:
                compiled.append(re.compile(pattern))
            except re.error:
                pass
        if compiled:
            files = [f for f in files if any(r.search(f) for r in compiled)]

    return files


def replace_in_file(file_path: str, search, replace: str, options: dict | None = None) -> bool:
    """Replace text in a file (cross-platform sed alternative).

    Args:
        file_path: Path to the file
        search: Pattern to search for (str or compiled regex)
        replace: Replacement string
        options: Options dict; 'all' (bool) replaces all occurrences for string search
    Returns:
        True if file was written, False on error
    """
    content = read_file(file_path)
    if content is None:
        return False

    opts = options or {}
    try:
        if opts.get("all") and isinstance(search, str):
            new_content = content.replace(search, replace)
        elif isinstance(search, str):
            new_content = content.replace(search, replace, 1)
        else:
            new_content = re.sub(search, replace, content)
        write_file(file_path, new_content)
        return True
    except Exception as e:  # noqa: BLE001
        log(f"[Utils] replace_in_file failed for {file_path}: {e}")
        return False


def count_in_file(file_path: str, pattern) -> int:
    """Count occurrences of a pattern in a file.

    Args:
        file_path: Path to the file
        pattern: Pattern to count (str or compiled regex)
    Returns:
        Number of matches found
    """
    content = read_file(file_path)
    if content is None:
        return 0

    try:
        return len(re.findall(pattern, content))
    except re.error:
        return 0


def strip_ansi(s: str) -> str:
    """Strip all ANSI escape sequences from a string.

    Handles:
    - CSI sequences: ESC[ ... <letter>
    - OSC sequences: ESC] ... BEL/ST
    - Charset selection: ESC(B
    - Bare ESC + single letter

    Args:
        s: Input string possibly containing ANSI codes
    Returns:
        Cleaned string with all escape sequences removed
    """
    if not isinstance(s, str):
        return ""
    return re.sub(
        r"\x1b(?:\[[0-9;?]*[A-Za-z]|\][^\x07\x1b]*(?:\x07|\x1b\\)|\([A-Z]|[A-Z])",
        "",
        s,
    )


def grep_file(file_path: str, pattern) -> list:
    """Search for pattern in file and return matching lines with line numbers.

    Args:
        file_path: Path to the file
        pattern: Pattern to search for (str or compiled regex)
    Returns:
        List of dicts with 'lineNumber' and 'content' keys
    """
    content = read_file(file_path)
    if content is None:
        return []

    try:
        if isinstance(pattern, str):
            regex = re.compile(pattern)
        else:
            # Create a new regex without global flag (Python doesn't use lastIndex)
            flags = pattern.flags
            regex = re.compile(pattern.pattern, flags)
    except re.error:
        return []

    results = []
    for i, line in enumerate(content.split("\n"), 1):
        if regex.search(line):
            results.append({"lineNumber": i, "content": line})

    return results
