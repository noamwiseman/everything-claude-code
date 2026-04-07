#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
Governance Event Capture Hook

PreToolUse/PostToolUse hook that detects governance-relevant events
and writes them to stderr for session correlation.

Captured event types:
  - secret_detected: Hardcoded secrets in tool input/output
  - policy_violation: Actions that violate configured policies
  - security_finding: Security-relevant tool invocations
  - approval_requested: Operations requiring explicit approval
  - hook_input_truncated: Hook input exceeded the safe inspection limit

Enable: Set ECC_GOVERNANCE_CAPTURE=1
Configure session: Set ECC_SESSION_ID for session correlation
"""

import hashlib
import json
import os
import re
import sys
import time

MAX_STDIN = 1024 * 1024
STDIN_CHUNK_SIZE = 65536

# Patterns that indicate potential hardcoded secrets
SECRET_PATTERNS = [
    {"name": "aws_key", "pattern": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}", re.IGNORECASE)},
    {
        "name": "generic_secret",
        "pattern": re.compile(
            r"(?:secret|password|token|api[_-]?key)\s*[:=]\s*[\"'][^\"']{8,}", re.IGNORECASE
        ),
    },
    {
        "name": "private_key",
        "pattern": re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    },
    {
        "name": "jwt",
        "pattern": re.compile(
            r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
        ),
    },
    {"name": "github_token", "pattern": re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")},
]

# Tool names that represent security-relevant operations
SECURITY_RELEVANT_TOOLS = {"Bash"}

# Commands that require governance approval
APPROVAL_COMMANDS = [
    re.compile(r"git\s+push\s+.*--force"),
    re.compile(r"git\s+reset\s+--hard"),
    re.compile(r"rm\s+-rf?\s"),
    re.compile(r"DROP\s+(?:TABLE|DATABASE)", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM\s+\w+\s*(?:;|$)", re.IGNORECASE),
]

# File patterns that indicate policy-sensitive paths
SENSITIVE_PATHS = [
    re.compile(r"\.env(?:\.|$)"),
    re.compile(r"credentials", re.IGNORECASE),
    re.compile(r"secrets?\.", re.IGNORECASE),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"id_rsa"),
]


def generate_event_id() -> str:
    """Generate a unique event ID."""
    ts = time.time_ns() // 1_000_000
    rand = os.urandom(4).hex()
    return f"gov-{ts}-{rand}"


def detect_secrets(text: str) -> list:
    """Scan text content for hardcoded secrets.

    Returns list of dicts with 'name' key for each detected secret.
    """
    if not text or not isinstance(text, str):
        return []
    return [{"name": p["name"]} for p in SECRET_PATTERNS if p["pattern"].search(text)]


def detect_approval_required(command: str) -> list:
    """Check if a command requires governance approval.

    Returns list of dicts with 'pattern' key for each matched rule.
    """
    if not command or not isinstance(command, str):
        return []
    return [{"pattern": p.pattern} for p in APPROVAL_COMMANDS if p.search(command)]


def detect_sensitive_path(file_path: str) -> bool:
    """Check if a file path is policy-sensitive."""
    if not file_path or not isinstance(file_path, str):
        return False
    return any(p.search(file_path) for p in SENSITIVE_PATHS)


def _fingerprint_command(command: str):
    """Return a short SHA-256 fingerprint of a command string."""
    if not command or not isinstance(command, str):
        return None
    return hashlib.sha256(command.encode()).hexdigest()[:12]


def _summarize_command(command: str) -> dict:
    """Return commandName and commandFingerprint without storing the raw command."""
    if not command or not isinstance(command, str):
        return {"commandName": None, "commandFingerprint": None}

    trimmed = command.strip()
    if not trimmed:
        return {"commandName": None, "commandFingerprint": None}

    parts = trimmed.split()
    return {
        "commandName": parts[0] if parts else None,
        "commandFingerprint": _fingerprint_command(trimmed),
    }


def _emit_governance_event(event: dict) -> None:
    sys.stderr.write(f"[governance] {json.dumps(event)}\n")


def analyze_for_governance_events(input_data: dict, context: dict = None) -> list:
    """Analyze a hook input payload and return governance events to capture.

    Args:
        input_data: Parsed hook input (tool_name, tool_input, tool_output)
        context: Additional context (sessionId, hookPhase)
    Returns:
        List of governance event dicts
    """
    context = context or {}
    events = []

    tool_name = input_data.get("tool_name", "") or ""
    tool_input = input_data.get("tool_input") or {}
    tool_output = input_data.get("tool_output", "")
    if not isinstance(tool_output, str):
        tool_output = ""
    session_id = context.get("sessionId", None)
    hook_phase = context.get("hookPhase", "unknown")

    # 1. Secret detection in tool input content
    if isinstance(tool_input, dict):
        input_text = json.dumps(tool_input)
    else:
        input_text = str(tool_input)

    input_secrets = detect_secrets(input_text)
    output_secrets = detect_secrets(tool_output)
    all_secrets = input_secrets + output_secrets

    if all_secrets:
        events.append({
            "id": generate_event_id(),
            "sessionId": session_id,
            "eventType": "secret_detected",
            "payload": {
                "toolName": tool_name,
                "hookPhase": hook_phase,
                "secretTypes": [s["name"] for s in all_secrets],
                "location": "input" if input_secrets else "output",
                "severity": "critical",
            },
            "resolvedAt": None,
            "resolution": None,
        })

    # 2. Approval-required commands (Bash only)
    if tool_name == "Bash":
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        approval_findings = detect_approval_required(command)
        command_summary = _summarize_command(command)

        if approval_findings:
            events.append({
                "id": generate_event_id(),
                "sessionId": session_id,
                "eventType": "approval_requested",
                "payload": {
                    "toolName": tool_name,
                    "hookPhase": hook_phase,
                    **command_summary,
                    "matchedPatterns": [f["pattern"] for f in approval_findings],
                    "severity": "high",
                },
                "resolvedAt": None,
                "resolution": None,
            })

    # 3. Policy violation: writing to sensitive paths
    file_path = ""
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    if file_path and detect_sensitive_path(file_path):
        events.append({
            "id": generate_event_id(),
            "sessionId": session_id,
            "eventType": "policy_violation",
            "payload": {
                "toolName": tool_name,
                "hookPhase": hook_phase,
                "filePath": file_path[:200],
                "reason": "sensitive_file_access",
                "severity": "warning",
            },
            "resolvedAt": None,
            "resolution": None,
        })

    # 4. Security-relevant tool usage tracking
    if tool_name in SECURITY_RELEVANT_TOOLS and hook_phase == "post":
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        has_elevated = bool(
            re.search(r"sudo\s", command)
            or re.search(r"chmod\s", command)
            or re.search(r"chown\s", command)
        )
        command_summary = _summarize_command(command)

        if has_elevated:
            events.append({
                "id": generate_event_id(),
                "sessionId": session_id,
                "eventType": "security_finding",
                "payload": {
                    "toolName": tool_name,
                    "hookPhase": hook_phase,
                    **command_summary,
                    "reason": "elevated_privilege_command",
                    "severity": "medium",
                },
                "resolvedAt": None,
                "resolution": None,
            })

    return events


def run(raw_input: str, options: dict = None) -> str:
    """Core hook logic.

    Args:
        raw_input: Raw JSON string from stdin
        options: Dict with optional 'truncated' and 'maxStdin' keys
    Returns:
        The original input (pass-through)
    """
    options = options or {}

    # Gate on feature flag
    if os.environ.get("ECC_GOVERNANCE_CAPTURE", "").lower() != "1":
        return raw_input

    session_id = os.environ.get("ECC_SESSION_ID", None)
    hook_event = os.environ.get("CLAUDE_HOOK_EVENT_NAME", "unknown")
    hook_phase = "pre" if hook_event.startswith("Pre") else "post"

    if options.get("truncated"):
        _emit_governance_event({
            "id": generate_event_id(),
            "sessionId": session_id,
            "eventType": "hook_input_truncated",
            "payload": {
                "hookPhase": hook_phase,
                "sizeLimitBytes": options.get("maxStdin", MAX_STDIN),
                "severity": "warning",
            },
            "resolvedAt": None,
            "resolution": None,
        })

    try:
        input_data = json.loads(raw_input)
        events = analyze_for_governance_events(input_data, {
            "sessionId": session_id,
            "hookPhase": hook_phase,
        })
        for event in events:
            _emit_governance_event(event)
    except (json.JSONDecodeError, ValueError):
        # Silently ignore parse errors — never block the tool pipeline.
        pass

    return raw_input


# ── stdin entry point ────────────────────────────────
if __name__ == "__main__":
    _raw_chunks = []
    _total_size = 0
    _truncated = os.environ.get("ECC_HOOK_INPUT_TRUNCATED", "").lower() in ("1", "true", "yes")

    while True:
        _chunk = sys.stdin.read(STDIN_CHUNK_SIZE)
        if not _chunk:
            break
        if _total_size < MAX_STDIN:
            _remaining = MAX_STDIN - _total_size
            _raw_chunks.append(_chunk[:_remaining])
            _total_size += len(_chunk)
            if len(_chunk) > _remaining:
                _truncated = True
        else:
            _truncated = True

    _raw = "".join(_raw_chunks)
    _max_stdin = int(os.environ.get("ECC_HOOK_INPUT_MAX_BYTES", str(MAX_STDIN)))
    _result = run(_raw, {"truncated": _truncated, "maxStdin": _max_stdin})
    sys.stdout.write(_result)
