#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Tests for scripts/hooks/governance_capture.py

Run with: python tests/hooks/governance_capture_test.py
      or: uv run tests/hooks/governance_capture_test.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "hooks"))

from governance_capture import (
    APPROVAL_COMMANDS,
    SECRET_PATTERNS,
    SECURITY_RELEVANT_TOOLS,
    SENSITIVE_PATHS,
    analyze_for_governance_events,
    detect_approval_required,
    detect_secrets,
    detect_sensitive_path,
    generate_event_id,
    run,
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


def run_tests() -> None:
    print("\n=== Testing governance_capture ===\n")
    passed = 0
    failed = 0

    # ── detect_secrets ──────────────────────────────────────────

    def t_aws():
        findings = detect_secrets("my key is AKIAIOSFODNN7EXAMPLE")
        assert len(findings) > 0
        assert any(f["name"] == "aws_key" for f in findings)

    if test("detectSecrets finds AWS access keys", t_aws):
        passed += 1
    else:
        failed += 1

    def t_generic():
        findings = detect_secrets('api_key = "sk-proj-abcdefghij1234567890"')
        assert len(findings) > 0
        assert any(f["name"] == "generic_secret" for f in findings)

    if test("detectSecrets finds generic secrets", t_generic):
        passed += 1
    else:
        failed += 1

    def t_private_key():
        findings = detect_secrets("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
        assert len(findings) > 0
        assert any(f["name"] == "private_key" for f in findings)

    if test("detectSecrets finds private keys", t_private_key):
        passed += 1
    else:
        failed += 1

    def t_github():
        findings = detect_secrets("token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij")
        assert len(findings) > 0
        assert any(f["name"] == "github_token" for f in findings)

    if test("detectSecrets finds GitHub tokens", t_github):
        passed += 1
    else:
        failed += 1

    def t_clean():
        findings = detect_secrets("This is a normal log message with no secrets.")
        assert len(findings) == 0

    if test("detectSecrets returns empty list for clean text", t_clean):
        passed += 1
    else:
        failed += 1

    def t_null():
        assert detect_secrets(None) == []
        assert detect_secrets("") == []  # type: ignore[arg-type]

    if test("detectSecrets handles None and empty string", t_null):
        passed += 1
    else:
        failed += 1

    # ── detect_approval_required ─────────────────────────────────

    def t_force_push():
        findings = detect_approval_required("git push origin main --force")
        assert len(findings) > 0

    if test("detectApprovalRequired flags force push", t_force_push):
        passed += 1
    else:
        failed += 1

    def t_hard_reset():
        findings = detect_approval_required("git reset --hard HEAD~3")
        assert len(findings) > 0

    if test("detectApprovalRequired flags hard reset", t_hard_reset):
        passed += 1
    else:
        failed += 1

    def t_rm_rf():
        findings = detect_approval_required("rm -rf /tmp/important")
        assert len(findings) > 0

    if test("detectApprovalRequired flags rm -rf", t_rm_rf):
        passed += 1
    else:
        failed += 1

    def t_drop_table():
        findings = detect_approval_required("DROP TABLE users")
        assert len(findings) > 0

    if test("detectApprovalRequired flags DROP TABLE", t_drop_table):
        passed += 1
    else:
        failed += 1

    def t_safe():
        findings = detect_approval_required("git status")
        assert len(findings) == 0

    if test("detectApprovalRequired allows safe commands", t_safe):
        passed += 1
    else:
        failed += 1

    def t_null_approval():
        assert detect_approval_required(None) == []  # type: ignore[arg-type]
        assert detect_approval_required("") == []

    if test("detectApprovalRequired handles None", t_null_approval):
        passed += 1
    else:
        failed += 1

    # ── detect_sensitive_path ────────────────────────────────────

    def t_env_files():
        assert detect_sensitive_path(".env")
        assert detect_sensitive_path(".env.local")
        assert detect_sensitive_path("/project/.env.production")

    if test("detectSensitivePath identifies .env files", t_env_files):
        passed += 1
    else:
        failed += 1

    def t_cred_files():
        assert detect_sensitive_path("credentials.json")
        assert detect_sensitive_path("/home/user/.ssh/id_rsa")
        assert detect_sensitive_path("server.key")
        assert detect_sensitive_path("cert.pem")

    if test("detectSensitivePath identifies credential files", t_cred_files):
        passed += 1
    else:
        failed += 1

    def t_normal_files():
        assert not detect_sensitive_path("index.js")
        assert not detect_sensitive_path("README.md")
        assert not detect_sensitive_path("package.json")

    if test("detectSensitivePath returns False for normal files", t_normal_files):
        passed += 1
    else:
        failed += 1

    def t_null_path():
        assert not detect_sensitive_path(None)  # type: ignore[arg-type]
        assert not detect_sensitive_path("")

    if test("detectSensitivePath handles None", t_null_path):
        passed += 1
    else:
        failed += 1

    # ── analyze_for_governance_events ─────────────────────────────

    def t_secrets_in_input():
        events = analyze_for_governance_events({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/config.js",
                "content": 'const key = "AKIAIOSFODNN7EXAMPLE";',
            },
        })
        assert len(events) > 0
        secret_event = next((e for e in events if e["eventType"] == "secret_detected"), None)
        assert secret_event is not None
        assert secret_event["payload"]["severity"] == "critical"

    if test("analyzeForGovernanceEvents detects secrets in tool input", t_secrets_in_input):
        passed += 1
    else:
        failed += 1

    def t_approval_commands():
        events = analyze_for_governance_events({
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main --force"},
        })
        assert len(events) > 0
        approval_event = next((e for e in events if e["eventType"] == "approval_requested"), None)
        assert approval_event is not None
        assert approval_event["payload"]["severity"] == "high"

    if test("analyzeForGovernanceEvents detects approval-required commands", t_approval_commands):
        passed += 1
    else:
        failed += 1

    def t_command_fingerprint():
        command = "git push origin main --force"
        events = analyze_for_governance_events({
            "tool_name": "Bash",
            "tool_input": {"command": command},
        })
        approval_event = next((e for e in events if e["eventType"] == "approval_requested"), None)
        assert approval_event is not None
        assert approval_event["payload"]["commandName"] == "git"
        fp = approval_event["payload"]["commandFingerprint"]
        assert isinstance(fp, str) and len(fp) == 12 and all(c in "0123456789abcdef" for c in fp)
        assert "command" not in approval_event["payload"]

    if test("approval events fingerprint commands instead of storing raw command text", t_command_fingerprint):
        passed += 1
    else:
        failed += 1

    def t_security_fingerprint():
        command = "sudo chmod 600 ~/.ssh/id_rsa"
        events = analyze_for_governance_events(
            {"tool_name": "Bash", "tool_input": {"command": command}},
            {"hookPhase": "post"},
        )
        security_event = next((e for e in events if e["eventType"] == "security_finding"), None)
        assert security_event is not None
        assert security_event["payload"]["commandName"] == "sudo"
        fp = security_event["payload"]["commandFingerprint"]
        assert isinstance(fp, str) and len(fp) == 12 and all(c in "0123456789abcdef" for c in fp)
        assert "command" not in security_event["payload"]

    if test("security findings fingerprint elevated commands instead of storing raw command text", t_security_fingerprint):
        passed += 1
    else:
        failed += 1

    def t_sensitive_path():
        events = analyze_for_governance_events({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/project/.env.production",
                "old_string": "DB_URL=old",
                "new_string": "DB_URL=new",
            },
        })
        assert len(events) > 0
        policy_event = next((e for e in events if e["eventType"] == "policy_violation"), None)
        assert policy_event is not None
        assert policy_event["payload"]["reason"] == "sensitive_file_access"

    if test("analyzeForGovernanceEvents detects sensitive file access", t_sensitive_path):
        passed += 1
    else:
        failed += 1

    def t_elevated_priv():
        events = analyze_for_governance_events(
            {"tool_name": "Bash", "tool_input": {"command": "sudo rm -rf /etc/something"}},
            {"hookPhase": "post"},
        )
        security_event = next((e for e in events if e["eventType"] == "security_finding"), None)
        assert security_event is not None
        assert security_event["payload"]["reason"] == "elevated_privilege_command"

    if test("analyzeForGovernanceEvents detects elevated privilege commands", t_elevated_priv):
        passed += 1
    else:
        failed += 1

    def t_clean_input():
        events = analyze_for_governance_events({
            "tool_name": "Read",
            "tool_input": {"file_path": "/project/src/index.js"},
        })
        assert len(events) == 0

    if test("analyzeForGovernanceEvents returns empty for clean inputs", t_clean_input):
        passed += 1
    else:
        failed += 1

    def t_session_id():
        events = analyze_for_governance_events(
            {"tool_name": "Write", "tool_input": {"file_path": "/project/.env", "content": "DB_URL=test"}},
            {"sessionId": "test-session-123"},
        )
        assert len(events) > 0
        assert events[0]["sessionId"] == "test-session-123"

    if test("analyzeForGovernanceEvents populates session ID from context", t_session_id):
        passed += 1
    else:
        failed += 1

    def t_unique_ids():
        events1 = analyze_for_governance_events(
            {"tool_name": "Write", "tool_input": {"file_path": ".env", "content": ""}}
        )
        events2 = analyze_for_governance_events(
            {"tool_name": "Write", "tool_input": {"file_path": ".env.local", "content": ""}}
        )
        if events1 and events2:
            assert events1[0]["id"] != events2[0]["id"]

    if test("analyzeForGovernanceEvents generates unique event IDs", t_unique_ids):
        passed += 1
    else:
        failed += 1

    # ── run() function ─────────────────────────────────────────

    def t_flag_off():
        original = os.environ.get("ECC_GOVERNANCE_CAPTURE")
        os.environ.pop("ECC_GOVERNANCE_CAPTURE", None)
        try:
            inp = '{"tool_name":"Bash","tool_input":{"command":"git push --force"}}'
            result = run(inp)
            assert result == inp
        finally:
            if original is not None:
                os.environ["ECC_GOVERNANCE_CAPTURE"] = original

    if test("run() passes through input when feature flag is off", t_flag_off):
        passed += 1
    else:
        failed += 1

    def t_flag_on():
        original = os.environ.get("ECC_GOVERNANCE_CAPTURE")
        os.environ["ECC_GOVERNANCE_CAPTURE"] = "1"
        try:
            inp = '{"tool_name":"Read","tool_input":{"file_path":"index.js"}}'
            result = run(inp)
            assert result == inp
        finally:
            if original is not None:
                os.environ["ECC_GOVERNANCE_CAPTURE"] = original
            else:
                os.environ.pop("ECC_GOVERNANCE_CAPTURE", None)

    if test("run() passes through input when feature flag is on", t_flag_on):
        passed += 1
    else:
        failed += 1

    def t_invalid_json():
        original = os.environ.get("ECC_GOVERNANCE_CAPTURE")
        os.environ["ECC_GOVERNANCE_CAPTURE"] = "1"
        try:
            result = run("not valid json")
            assert result == "not valid json"
        finally:
            if original is not None:
                os.environ["ECC_GOVERNANCE_CAPTURE"] = original
            else:
                os.environ.pop("ECC_GOVERNANCE_CAPTURE", None)

    if test("run() handles invalid JSON gracefully", t_invalid_json):
        passed += 1
    else:
        failed += 1

    def t_truncated_event():
        orig_cap = os.environ.get("ECC_GOVERNANCE_CAPTURE")
        orig_hook = os.environ.get("CLAUDE_HOOK_EVENT_NAME")
        os.environ["ECC_GOVERNANCE_CAPTURE"] = "1"
        os.environ["CLAUDE_HOOK_EVENT_NAME"] = "PreToolUse"

        stderr_output = []
        orig_stderr_write = sys.stderr.write

        def capture_stderr(chunk):
            stderr_output.append(str(chunk))

        sys.stderr.write = capture_stderr
        try:
            inp = '{"tool_name":"Bash","tool_input":{"command":"rm -rf /tmp/important"}}'
            result = run(inp, {"truncated": True, "maxStdin": 1024})
            assert result == inp
        finally:
            sys.stderr.write = orig_stderr_write
            if orig_cap is not None:
                os.environ["ECC_GOVERNANCE_CAPTURE"] = orig_cap
            else:
                os.environ.pop("ECC_GOVERNANCE_CAPTURE", None)
            if orig_hook is not None:
                os.environ["CLAUDE_HOOK_EVENT_NAME"] = orig_hook
            else:
                os.environ.pop("CLAUDE_HOOK_EVENT_NAME", None)

        combined = "".join(stderr_output)
        assert "hook_input_truncated" in combined, "Should emit truncation event"
        assert "1024" in combined, "Should record the truncation limit"
        assert "rm -rf /tmp/important" not in combined, "Should not leak raw command text"

    if test("run() emits hook_input_truncated event without logging raw command text", t_truncated_event):
        passed += 1
    else:
        failed += 1

    def t_multiple_events():
        events = analyze_for_governance_events({
            "tool_name": "Bash",
            "tool_input": {"command": 'API_KEY="AKIAIOSFODNN7EXAMPLE" git push --force'},
        })
        event_types = [e["eventType"] for e in events]
        assert "secret_detected" in event_types
        assert "approval_requested" in event_types

    if test("run() can detect multiple event types in one input", t_multiple_events):
        passed += 1
    else:
        failed += 1

    print(f"\nResults: Passed: {passed}, Failed: {failed}")
    sys.exit(1 if failed > 0 else 0)


run_tests()
