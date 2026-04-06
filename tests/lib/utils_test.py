#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Tests for scripts/lib/utils.py

Run with: python tests/lib/utils_test.py
      or: uv run tests/lib/utils_test.py
"""

import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "lib"))

import utils


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
    print("\n=== Testing utils.py ===\n")
    passed = 0
    failed = 0

    rocket_party = "\U0001F680\U0001F389"

    # Platform Detection tests
    print("Platform Detection:")

    def t_platform_bools():
        assert isinstance(utils.is_windows, bool)
        assert isinstance(utils.is_macos, bool)
        assert isinstance(utils.is_linux, bool)

    if test("is_windows/is_macos/is_linux are booleans", t_platform_bools):
        passed += 1
    else:
        failed += 1

    def t_platform_exclusive():
        platforms = [utils.is_windows, utils.is_macos, utils.is_linux]
        assert sum(platforms) <= 1, "More than one platform is True"

    if test("at most one platform should be True", t_platform_exclusive):
        passed += 1
    else:
        failed += 1

    # Directory Functions tests
    print("\nDirectory Functions:")

    def t_home_dir():
        home = utils.get_home_dir()
        assert isinstance(home, str)
        assert len(home) > 0
        assert Path(home).exists()

    if test("get_home_dir returns valid path", t_home_dir):
        passed += 1
    else:
        failed += 1

    def t_claude_dir():
        claude_dir = utils.get_claude_dir()
        home_dir = utils.get_home_dir()
        assert claude_dir.startswith(home_dir)
        assert ".claude" in claude_dir

    if test("get_claude_dir returns path under home", t_claude_dir):
        passed += 1
    else:
        failed += 1

    def t_sessions_dir():
        sessions_dir = utils.get_sessions_dir()
        claude_dir = utils.get_claude_dir()
        assert sessions_dir.startswith(claude_dir)
        assert sessions_dir.endswith(os.path.join(".claude", "session-data")) or sessions_dir.endswith("/.claude/session-data")

    if test("get_sessions_dir returns path under Claude dir", t_sessions_dir):
        passed += 1
    else:
        failed += 1

    def t_session_search_dirs():
        search_dirs = utils.get_session_search_dirs()
        assert search_dirs[0] == utils.get_sessions_dir()
        assert search_dirs[1] == utils.get_legacy_sessions_dir()

    if test("get_session_search_dirs includes canonical and legacy paths", t_session_search_dirs):
        passed += 1
    else:
        failed += 1

    def t_temp_dir():
        temp_dir = utils.get_temp_dir()
        assert isinstance(temp_dir, str)
        assert len(temp_dir) > 0

    if test("get_temp_dir returns valid temp directory", t_temp_dir):
        passed += 1
    else:
        failed += 1

    def t_ensure_dir():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}")
        try:
            utils.ensure_dir(test_dir)
            assert Path(test_dir).exists()
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("ensure_dir creates directory", t_ensure_dir):
        passed += 1
    else:
        failed += 1

    # Date/Time Functions tests
    print("\nDate/Time Functions:")

    def t_date_string():
        date = utils.get_date_string()
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", date), f"Expected YYYY-MM-DD, got {date}"

    if test("get_date_string returns YYYY-MM-DD format", t_date_string):
        passed += 1
    else:
        failed += 1

    def t_time_string():
        time_str = utils.get_time_string()
        assert re.match(r"^\d{2}:\d{2}$", time_str), f"Expected HH:MM, got {time_str}"

    if test("get_time_string returns HH:MM format", t_time_string):
        passed += 1
    else:
        failed += 1

    def t_datetime_string():
        dt = utils.get_date_time_string()
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", dt), f"Expected YYYY-MM-DD HH:MM:SS, got {dt}"

    if test("get_date_time_string returns full datetime format", t_datetime_string):
        passed += 1
    else:
        failed += 1

    # Project Name Functions tests
    print("\nProject Name Functions:")

    def t_git_repo_name():
        repo_name = utils.get_git_repo_name()
        assert repo_name is None or isinstance(repo_name, str)

    if test("get_git_repo_name returns string or None", t_git_repo_name):
        passed += 1
    else:
        failed += 1

    def t_project_name():
        name = utils.get_project_name()
        assert name and len(name) > 0

    if test("get_project_name returns non-empty string", t_project_name):
        passed += 1
    else:
        failed += 1

    # sanitize_session_id tests
    print("\nsanitize_session_id:")

    def t_strip_leading_dots():
        assert utils.sanitize_session_id(".claude") == "claude"

    if test("sanitize_session_id strips leading dots", t_strip_leading_dots):
        passed += 1
    else:
        failed += 1

    def t_replace_dots_spaces():
        assert utils.sanitize_session_id("my.project") == "my-project"
        assert utils.sanitize_session_id("my project") == "my-project"

    if test("sanitize_session_id replaces dots and spaces", t_replace_dots_spaces):
        passed += 1
    else:
        failed += 1

    def t_special_chars():
        assert utils.sanitize_session_id("project@v2") == "project-v2"
        assert utils.sanitize_session_id("a...b") == "a-b"

    if test("sanitize_session_id replaces special chars and collapses runs", t_special_chars):
        passed += 1
    else:
        failed += 1

    def t_valid_chars():
        assert utils.sanitize_session_id("my-project_123") == "my-project_123"

    if test("sanitize_session_id preserves valid chars", t_valid_chars):
        passed += 1
    else:
        failed += 1

    def t_windows_reserved():
        for reserved in ["CON", "prn", "Aux", "nul", "COM1", "lpt9"]:
            sanitized = utils.sanitize_session_id(reserved)
            assert sanitized, f"Expected sanitized output for {reserved}"
            assert sanitized.upper() != reserved.upper()
            assert re.search(r"-[a-f0-9]{6}$", sanitized, re.IGNORECASE), \
                f"Expected hash suffix for {reserved}, got {sanitized}"

    if test("sanitize_session_id appends hash suffix for Windows reserved device names", t_windows_reserved):
        passed += 1
    else:
        failed += 1

    def t_null_empty():
        assert utils.sanitize_session_id("") is None
        assert utils.sanitize_session_id(None) is None  # type: ignore[arg-type]
        assert utils.sanitize_session_id("...") is None
        assert utils.sanitize_session_id("\u2026") is None  # ellipsis

    if test("sanitize_session_id returns None for empty or punctuation-only values", t_null_empty):
        passed += 1
    else:
        failed += 1

    def t_non_ascii_hash():
        chinese = utils.sanitize_session_id("\u6211\u7684\u9879\u76ee")
        cyrillic = utils.sanitize_session_id("\u043f\u0440\u043e\u0435\u043a\u0442")
        emoji = utils.sanitize_session_id(rocket_party)
        assert re.match(r"^[a-f0-9]{8}$", chinese), f"Expected 8-char hash, got: {chinese}"
        assert re.match(r"^[a-f0-9]{8}$", cyrillic), f"Expected 8-char hash, got: {cyrillic}"
        assert re.match(r"^[a-f0-9]{8}$", emoji), f"Expected 8-char hash, got: {emoji}"
        assert chinese != cyrillic
        assert chinese != emoji
        assert utils.sanitize_session_id("\u65e5\u672c\u8a9e\u30d7\u30ed\u30b8\u30a7\u30af\u30c8") == \
               utils.sanitize_session_id("\u65e5\u672c\u8a9e\u30d7\u30ed\u30b8\u30a7\u30af\u30c8")

    if test("sanitize_session_id returns stable hashes for non-ASCII values", t_non_ascii_hash):
        passed += 1
    else:
        failed += 1

    def t_mixed_script():
        mixed = utils.sanitize_session_id("\u6211\u7684app")
        mixed_two = utils.sanitize_session_id("\u4ed6\u7684app")
        pure = utils.sanitize_session_id("app")
        assert pure == "app"
        assert mixed.startswith("app-"), f"Expected mixed-script prefix, got: {mixed}"
        assert mixed != pure
        assert mixed != mixed_two

    if test("sanitize_session_id disambiguates mixed-script names from pure ASCII", t_mixed_script):
        passed += 1
    else:
        failed += 1

    def t_idempotent():
        for inp in [".claude", "my.project", "project@v2", "a...b", "my-project_123"]:
            once = utils.sanitize_session_id(inp)
            twice = utils.sanitize_session_id(once)
            assert once == twice, f"Expected idempotent result for {inp}"

    if test("sanitize_session_id is idempotent", t_idempotent):
        passed += 1
    else:
        failed += 1

    def t_windows_reserved_prefix():
        con = utils.sanitize_session_id("CON")
        aux = utils.sanitize_session_id("aux")
        assert con.startswith("CON-"), f"Expected CON to get a suffix, got: {con}"
        assert aux.startswith("aux-"), f"Expected aux to get a suffix, got: {aux}"
        assert utils.sanitize_session_id("COM1") != "COM1"

    if test("sanitize_session_id preserves readable prefixes for Windows reserved device names", t_windows_reserved_prefix):
        passed += 1
    else:
        failed += 1

    # Session ID Functions tests
    print("\nSession ID Functions:")

    def t_fallback_project():
        with with_env({"CLAUDE_SESSION_ID": None}):
            short_id = utils.get_session_id_short()
            assert short_id == utils.sanitize_session_id(utils.get_project_name())

    if test("get_session_id_short falls back to sanitized project name", t_fallback_project):
        passed += 1
    else:
        failed += 1

    def t_last_8():
        with with_env({"CLAUDE_SESSION_ID": "test-session-abc12345"}):
            assert utils.get_session_id_short() == "abc12345"

    if test("get_session_id_short returns last 8 characters", t_last_8):
        passed += 1
    else:
        failed += 1

    def t_short_session():
        with with_env({"CLAUDE_SESSION_ID": "short"}):
            assert utils.get_session_id_short() == "short"

    if test("get_session_id_short handles short session IDs", t_short_session):
        passed += 1
    else:
        failed += 1

    def t_explicit_fallback():
        # Test that when CLAUDE_SESSION_ID is empty and project name is unavailable,
        # the explicit fallback is sanitized and used.
        from unittest import mock
        with with_env({"CLAUDE_SESSION_ID": ""}):
            with mock.patch.object(utils, "get_project_name", return_value=None):
                result = utils.get_session_id_short("my.fallback")
                assert result == "my-fallback"

    if test("get_session_id_short sanitizes explicit fallback parameter", t_explicit_fallback):
        passed += 1
    else:
        failed += 1

    # File Operations tests
    print("\nFile Operations:")

    def t_read_nonexistent():
        assert utils.read_file("/non/existent/file/path.txt") is None

    if test("read_file returns None for non-existent file", t_read_nonexistent):
        passed += 1
    else:
        failed += 1

    def t_write_read():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        content = "Hello, World!"
        try:
            utils.write_file(test_file, content)
            assert utils.read_file(test_file) == content
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("write_file and read_file work together", t_write_read):
        passed += 1
    else:
        failed += 1

    def t_append():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "Line 1\n")
            utils.append_file(test_file, "Line 2\n")
            assert utils.read_file(test_file) == "Line 1\nLine 2\n"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("append_file adds content to file", t_append):
        passed += 1
    else:
        failed += 1

    def t_replace_regex():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "Hello, World!")
            utils.replace_in_file(test_file, re.compile(r"World"), "Universe")
            assert utils.read_file(test_file) == "Hello, Universe!"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("replace_in_file replaces text", t_replace_regex):
        passed += 1
    else:
        failed += 1

    def t_count():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "foo bar foo baz foo")
            assert utils.count_in_file(test_file, r"foo") == 3
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("count_in_file counts occurrences", t_count):
        passed += 1
    else:
        failed += 1

    def t_grep():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "line 1 foo\nline 2 bar\nline 3 foo")
            matches = utils.grep_file(test_file, re.compile(r"foo"))
            assert len(matches) == 2
            assert matches[0]["lineNumber"] == 1
            assert matches[1]["lineNumber"] == 3
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("grep_file finds matching lines", t_grep):
        passed += 1
    else:
        failed += 1

    # findFiles tests
    print("\nfindFiles:")

    def t_find_nonexistent():
        results = utils.find_files("/non/existent/dir", "*.txt")
        assert results == []

    if test("find_files returns empty for non-existent directory", t_find_nonexistent):
        passed += 1
    else:
        failed += 1

    def t_find_matching():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}")
        try:
            Path(test_dir).mkdir()
            Path(os.path.join(test_dir, "test1.txt")).write_text("content")
            Path(os.path.join(test_dir, "test2.txt")).write_text("content")
            Path(os.path.join(test_dir, "test.md")).write_text("content")

            txt_files = utils.find_files(test_dir, "*.txt")
            assert len(txt_files) == 2

            md_files = utils.find_files(test_dir, "*.md")
            assert len(md_files) == 1
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files finds matching files", t_find_matching):
        passed += 1
    else:
        failed += 1

    # Edge Cases tests
    print("\nEdge Cases:")

    def t_find_null_dir():
        assert utils.find_files(None, "*.txt") == []  # type: ignore[arg-type]
        assert utils.find_files("", "*.txt") == []

    if test("find_files returns empty for None/empty dir", t_find_null_dir):
        passed += 1
    else:
        failed += 1

    def t_find_null_pattern():
        assert utils.find_files("/tmp", None) == []  # type: ignore[arg-type]
        assert utils.find_files("/tmp", "") == []

    if test("find_files returns empty for None/empty pattern", t_find_null_pattern):
        passed += 1
    else:
        failed += 1

    def t_find_max_age():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-maxage-{os.getpid()}")
        try:
            Path(test_dir).mkdir()
            Path(os.path.join(test_dir, "recent.txt")).write_text("content")
            results = utils.find_files(test_dir, "*.txt", {"maxAge": 1})
            assert len(results) == 1
            assert results[0]["path"].endswith("recent.txt")
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files supports maxAge filter", t_find_max_age):
        passed += 1
    else:
        failed += 1

    def t_find_recursive():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-recursive-{os.getpid()}")
        sub_dir = os.path.join(test_dir, "sub")
        try:
            Path(sub_dir).mkdir(parents=True)
            Path(os.path.join(test_dir, "top.txt")).write_text("content")
            Path(os.path.join(sub_dir, "nested.txt")).write_text("content")
            shallow = utils.find_files(test_dir, "*.txt", {"recursive": False})
            assert len(shallow) == 1
            deep = utils.find_files(test_dir, "*.txt", {"recursive": True})
            assert len(deep) == 2
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files supports recursive option", t_find_recursive):
        passed += 1
    else:
        failed += 1

    def t_count_invalid_regex():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "test content")
            assert utils.count_in_file(test_file, "(unclosed") == 0
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("count_in_file handles invalid regex pattern", t_count_invalid_regex):
        passed += 1
    else:
        failed += 1

    def t_grep_invalid_regex():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "test content")
            assert utils.grep_file(test_file, "[invalid") == []
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("grep_file handles invalid regex pattern", t_grep_invalid_regex):
        passed += 1
    else:
        failed += 1

    def t_replace_nonexistent():
        assert utils.replace_in_file("/non/existent/file.txt", "foo", "bar") is False

    if test("replace_in_file returns False for non-existent file", t_replace_nonexistent):
        passed += 1
    else:
        failed += 1

    def t_count_nonexistent():
        assert utils.count_in_file("/non/existent/file.txt", r"foo") == 0

    if test("count_in_file returns 0 for non-existent file", t_count_nonexistent):
        passed += 1
    else:
        failed += 1

    def t_grep_nonexistent():
        assert utils.grep_file("/non/existent/file.txt", r"foo") == []

    if test("grep_file returns empty for non-existent file", t_grep_nonexistent):
        passed += 1
    else:
        failed += 1

    def t_command_unsafe():
        assert utils.command_exists("cmd; rm -rf") is False
        assert utils.command_exists("$(whoami)") is False
        assert utils.command_exists("cmd && echo hi") is False

    if test("command_exists rejects unsafe command names", t_command_unsafe):
        passed += 1
    else:
        failed += 1

    def t_ensure_idempotent():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-idem-{os.getpid()}")
        try:
            r1 = utils.ensure_dir(test_dir)
            r2 = utils.ensure_dir(test_dir)
            assert r1 == test_dir
            assert r2 == test_dir
            assert Path(test_dir).exists()
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("ensure_dir is idempotent", t_ensure_idempotent):
        passed += 1
    else:
        failed += 1

    # System Functions tests
    print("\nSystem Functions:")

    def t_command_exists_python():
        assert utils.command_exists("python3") or utils.command_exists("python") or utils.command_exists("uv")

    if test("command_exists finds python or uv", t_command_exists_python):
        passed += 1
    else:
        failed += 1

    def t_command_not_exist():
        assert utils.command_exists("nonexistent_command_12345") is False

    if test("command_exists returns False for fake command", t_command_not_exist):
        passed += 1
    else:
        failed += 1

    def t_run_command():
        result = utils.run_command("git --version")
        assert result["success"] is True
        assert "git" in result["output"].lower()

    if test("run_command executes simple command", t_run_command):
        passed += 1
    else:
        failed += 1

    def t_run_blocked():
        result = utils.run_command("echo hello")
        assert result["success"] is False
        assert "blocked" in result["output"]

    if test("run_command blocks unrecognized command prefixes", t_run_blocked):
        passed += 1
    else:
        failed += 1

    # output() and log() tests
    print("\noutput() and log():")

    def t_output_str():
        captured = []
        orig_print = __builtins__["print"] if isinstance(__builtins__, dict) else print
        import builtins
        original = builtins.print
        builtins.print = lambda *args, **kwargs: captured.append(args[0] if args else "")
        try:
            utils.output("hello")
        finally:
            builtins.print = original
        assert captured[0] == "hello"

    if test("output() writes string to stdout", t_output_str):
        passed += 1
    else:
        failed += 1

    def t_output_dict():
        captured = []
        import builtins
        original = builtins.print
        builtins.print = lambda *args, **kwargs: captured.append(args[0] if args else "")
        try:
            utils.output({"key": "value", "num": 42})
        finally:
            builtins.print = original
        import json
        assert json.loads(captured[0]) == {"key": "value", "num": 42}

    if test("output() JSON-stringifies dicts", t_output_dict):
        passed += 1
    else:
        failed += 1

    def t_output_list():
        captured = []
        import builtins
        original = builtins.print
        builtins.print = lambda *args, **kwargs: captured.append(args[0] if args else "")
        try:
            utils.output([1, 2, 3])
        finally:
            builtins.print = original
        assert captured[0] == "[1, 2, 3]"

    if test("output() JSON-stringifies lists", t_output_list):
        passed += 1
    else:
        failed += 1

    def t_log_stderr():
        captured = []
        orig_write = sys.stderr.write
        sys.stderr.write = lambda s: captured.append(s)
        try:
            utils.log("test message")
        finally:
            sys.stderr.write = orig_write
        combined = "".join(captured)
        assert "test message" in combined

    if test("log() writes to stderr", t_log_stderr):
        passed += 1
    else:
        failed += 1

    # isGitRepo() tests
    print("\nis_git_repo():")

    def t_is_git_repo():
        assert utils.is_git_repo() is True

    if test("is_git_repo returns True in a git repo", t_is_git_repo):
        passed += 1
    else:
        failed += 1

    # getGitModifiedFiles() tests
    print("\nget_git_modified_files():")

    def t_git_files_array():
        files = utils.get_git_modified_files()
        assert isinstance(files, list)

    if test("get_git_modified_files returns a list", t_git_files_array):
        passed += 1
    else:
        failed += 1

    def t_git_files_filter():
        files = utils.get_git_modified_files([r"\.NONEXISTENT_EXTENSION$"])
        assert isinstance(files, list)
        assert len(files) == 0

    if test("get_git_modified_files filters by regex patterns", t_git_files_filter):
        passed += 1
    else:
        failed += 1

    def t_git_files_invalid_patterns():
        files = utils.get_git_modified_files(["(unclosed", r"\.py$", "[invalid"])
        assert isinstance(files, list)

    if test("get_git_modified_files skips invalid patterns", t_git_files_invalid_patterns):
        passed += 1
    else:
        failed += 1

    # getLearnedSkillsDir() test
    print("\nget_learned_skills_dir():")

    def t_learned_skills():
        d = utils.get_learned_skills_dir()
        assert ".claude" in d
        assert "skills" in d
        assert "learned" in d

    if test("get_learned_skills_dir returns path under Claude dir", t_learned_skills):
        passed += 1
    else:
        failed += 1

    # replaceInFile behavior tests
    print("\nreplace_in_file (behavior):")

    def t_replace_first_only():
        # Python's re.sub replaces ALL occurrences by default (no /g flag distinction).
        # Unlike JS where /foo/ (no g) replaces first only; in Python re.sub is always global.
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "foo bar foo baz foo")
            utils.replace_in_file(test_file, re.compile(r"foo"), "qux")
            content = utils.read_file(test_file)
            # Python re.sub replaces all matches
            assert content == "qux bar qux baz qux"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("replace_in_file with regex replaces all occurrences (Python re.sub default)", t_replace_first_only):
        passed += 1
    else:
        failed += 1

    def t_replace_all_regex():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "foo bar foo baz foo")
            utils.replace_in_file(test_file, re.compile(r"foo"), "qux")
            content = utils.read_file(test_file)
            assert content == "qux bar qux baz qux"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("replace_in_file with regex works correctly", t_replace_all_regex):
        passed += 1
    else:
        failed += 1

    def t_replace_str_first():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "hello world hello")
            utils.replace_in_file(test_file, "hello", "goodbye")
            content = utils.read_file(test_file)
            assert content == "goodbye world hello"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("replaces with string search (first occurrence)", t_replace_str_first):
        passed += 1
    else:
        failed += 1

    def t_replace_all_option():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "hello world hello again hello")
            utils.replace_in_file(test_file, "hello", "goodbye", {"all": True})
            content = utils.read_file(test_file)
            assert content == "goodbye world goodbye again goodbye"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("replaces all occurrences with string when options.all is True", t_replace_all_option):
        passed += 1
    else:
        failed += 1

    def t_replace_unicode():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-{os.getpid()}.txt")
        try:
            unicode_content = "日本語テスト \U0001F680 émojis"
            utils.write_file(test_file, unicode_content)
            content = utils.read_file(test_file)
            assert content == unicode_content
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("write_file handles unicode content", t_replace_unicode):
        passed += 1
    else:
        failed += 1

    # findFiles with regex special characters
    print("\nfindFiles (regex chars):")

    def t_find_regex_special():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-regex-{os.getpid()}")
        try:
            Path(test_dir).mkdir()
            Path(os.path.join(test_dir, "file(1).txt")).write_text("content")
            Path(os.path.join(test_dir, "file+2.txt")).write_text("content")
            Path(os.path.join(test_dir, "file[3].txt")).write_text("content")

            parens = utils.find_files(test_dir, "file(1).txt")
            assert len(parens) == 1, "Should match file(1).txt literally"

            plus = utils.find_files(test_dir, "file+2.txt")
            assert len(plus) == 1, "Should match file+2.txt literally"

            brackets = utils.find_files(test_dir, "file[3].txt")
            assert len(brackets) == 1, "Should match file[3].txt literally"
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files handles regex special chars in pattern", t_find_regex_special):
        passed += 1
    else:
        failed += 1

    def t_find_wildcard():
        test_dir = os.path.join(utils.get_temp_dir(), f"utils-test-glob-{os.getpid()}")
        try:
            Path(test_dir).mkdir()
            Path(os.path.join(test_dir, "app(v2).js")).write_text("content")
            Path(os.path.join(test_dir, "app(v3).ts")).write_text("content")

            js_files = utils.find_files(test_dir, "*.js")
            assert len(js_files) == 1
            assert js_files[0]["path"].endswith("app(v2).js")
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files wildcard still works with special chars", t_find_wildcard):
        passed += 1
    else:
        failed += 1

    # read_stdin_json tests
    print("\nread_stdin_json():")

    def t_stdin_json():
        import json, subprocess
        script = (
            "import sys, json\n"
            "sys.path.insert(0, 'scripts/lib')\n"
            "import utils\n"
            "result = utils.read_stdin_json()\n"
            "sys.stdout.write(json.dumps(result))"
        )
        repo_root = str(Path(__file__).parent.parent.parent)
        result = subprocess.run(
            [sys.executable, "-c", script],
            input='{"tool_input":{"command":"ls"}}',
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=5,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed == {"tool_input": {"command": "ls"}}

    if test("read_stdin_json parses valid JSON from stdin", t_stdin_json):
        passed += 1
    else:
        failed += 1

    def t_stdin_invalid():
        import json, subprocess
        script = (
            "import sys, json\n"
            "sys.path.insert(0, 'scripts/lib')\n"
            "import utils\n"
            "result = utils.read_stdin_json()\n"
            "sys.stdout.write(json.dumps(result))"
        )
        repo_root = str(Path(__file__).parent.parent.parent)
        result = subprocess.run(
            [sys.executable, "-c", script],
            input="not json",
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=5,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}

    if test("read_stdin_json returns {} for invalid JSON", t_stdin_invalid):
        passed += 1
    else:
        failed += 1

    def t_stdin_empty():
        import json, subprocess
        script = (
            "import sys, json\n"
            "sys.path.insert(0, 'scripts/lib')\n"
            "import utils\n"
            "result = utils.read_stdin_json()\n"
            "sys.stdout.write(json.dumps(result))"
        )
        repo_root = str(Path(__file__).parent.parent.parent)
        result = subprocess.run(
            [sys.executable, "-c", script],
            input="",
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=5,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}

    if test("read_stdin_json returns {} for empty stdin", t_stdin_empty):
        passed += 1
    else:
        failed += 1

    # grep_file global regex fix
    print("\ngrep_file (global regex fix):")

    def t_grep_all_lines():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-grep-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "match-line\nmatch-line\nmatch-line\nmatch-line")
            matches = utils.grep_file(test_file, re.compile(r"match", re.IGNORECASE))
            assert len(matches) == 4, f"Should find all 4 lines, found {len(matches)}"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("grep_file finds ALL matching lines", t_grep_all_lines):
        passed += 1
    else:
        failed += 1

    def t_grep_case_insensitive():
        test_file = os.path.join(utils.get_temp_dir(), f"utils-test-grep-ci-{os.getpid()}.txt")
        try:
            utils.write_file(test_file, "FOO\nfoo\nFoO\nbar")
            matches = utils.grep_file(test_file, re.compile(r"foo", re.IGNORECASE))
            assert len(matches) == 3, f"Should find 3 case-insensitive matches, found {len(matches)}"
        finally:
            Path(test_file).unlink(missing_ok=True)

    if test("grep_file preserves regex flags (case-insensitive)", t_grep_case_insensitive):
        passed += 1
    else:
        failed += 1

    # command_exists edge cases
    print("\ncommand_exists Edge Cases:")

    def t_cmd_empty():
        assert utils.command_exists("") is False

    if test("command_exists rejects empty string", t_cmd_empty):
        passed += 1
    else:
        failed += 1

    def t_cmd_spaces():
        assert utils.command_exists("my command") is False

    if test("command_exists rejects command with spaces", t_cmd_spaces):
        passed += 1
    else:
        failed += 1

    def t_cmd_slashes():
        assert utils.command_exists("/usr/bin/python") is False
        # backslash
        assert utils.command_exists("..\\cmd") is False

    if test("command_exists rejects command with path separators", t_cmd_slashes):
        passed += 1
    else:
        failed += 1

    # findFiles ? wildcard
    print("\nfindFiles Edge Cases:")

    def t_find_question_mark():
        test_dir = os.path.join(utils.get_temp_dir(), f"ff-qmark-{os.getpid()}")
        utils.ensure_dir(test_dir)
        try:
            Path(os.path.join(test_dir, "a1.txt")).write_text("")
            Path(os.path.join(test_dir, "b2.txt")).write_text("")
            Path(os.path.join(test_dir, "abc.txt")).write_text("")

            results = utils.find_files(test_dir, "??.txt")
            names = sorted(Path(r["path"]).name for r in results)
            assert names == ["a1.txt", "b2.txt"], f"Should match exactly 2-char basenames, got {names}"
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files with ? wildcard matches single character", t_find_question_mark):
        passed += 1
    else:
        failed += 1

    def t_find_sort_by_mtime():
        test_dir = os.path.join(utils.get_temp_dir(), f"ff-sort-{os.getpid()}")
        utils.ensure_dir(test_dir)
        try:
            import time
            f1 = os.path.join(test_dir, "old.txt")
            f2 = os.path.join(test_dir, "new.txt")
            Path(f1).write_text("old")
            past = (time.time() - 60, time.time() - 60)
            os.utime(f1, past)
            Path(f2).write_text("new")

            results = utils.find_files(test_dir, "*.txt")
            assert len(results) == 2
            assert Path(results[0]["path"]).name == "new.txt", \
                f"Newest file should be first, got {Path(results[0]['path']).name}"
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files sorts by mtime (newest first)", t_find_sort_by_mtime):
        passed += 1
    else:
        failed += 1

    def t_find_max_age_filter():
        test_dir = os.path.join(utils.get_temp_dir(), f"ff-age-{os.getpid()}")
        utils.ensure_dir(test_dir)
        try:
            import time
            recent = os.path.join(test_dir, "recent.txt")
            old = os.path.join(test_dir, "old.txt")
            Path(recent).write_text("new")
            Path(old).write_text("old")
            past = time.time() - 30 * 24 * 60 * 60
            os.utime(old, (past, past))

            results = utils.find_files(test_dir, "*.txt", {"maxAge": 7})
            assert len(results) == 1, "Should only return recent file"
            assert results[0]["path"].endswith("recent.txt")
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    if test("find_files with maxAge filters old files", t_find_max_age_filter):
        passed += 1
    else:
        failed += 1

    # strip_ansi tests
    print("\nstrip_ansi():")

    def t_strip_ansi():
        assert utils.strip_ansi("\x1b[31mhello\x1b[0m") == "hello"
        assert utils.strip_ansi("no escape codes") == "no escape codes"
        assert utils.strip_ansi("") == ""
        assert utils.strip_ansi(None) == ""  # type: ignore[arg-type]

    if test("strip_ansi removes ANSI escape codes", t_strip_ansi):
        passed += 1
    else:
        failed += 1

    print(f"\nResults: Passed: {passed}, Failed: {failed}")
    sys.exit(1 if failed > 0 else 0)


run_tests()
