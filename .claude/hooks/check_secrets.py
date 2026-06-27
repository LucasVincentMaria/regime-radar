#!/usr/bin/env python3
"""
PreToolUse hook: block writing or committing anything that looks like a secret.

Runs before Edit / Write / Bash tool calls. It scans the content being written
(or the command being run) for API-key-shaped strings and DENIES the action if
it finds one — so secrets never reach disk in a tracked file, let alone GitHub.

Claude Code hook protocol:
  - Input  : a JSON object on stdin describing the tool call.
  - Output : exit code 0 = allow. To BLOCK, print a JSON decision to stdout
             and exit 0, OR exit with code 2 (stderr shown to the user).
  We use the JSON-decision form for a clear, user-visible reason.

This file contains NO secrets and is safe to commit.
"""

from __future__ import annotations

import json
import re
import sys
from typing import List, Tuple

# Patterns that strongly indicate a real secret. Kept deliberately specific to
# avoid false positives on ordinary code. (description, compiled regex)
SECRET_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic API key assignment", re.compile(
        r"""(?ix)
        (?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|
           auth[_-]?token|client[_-]?secret|private[_-]?key)
        \s*[:=]\s*
        ['"]?
        ([A-Za-z0-9_\-]{20,})        # an actual long value, not a placeholder
        ['"]?
        """)),
    ("Alpaca key", re.compile(r"(?i)(PK|AK)[A-Z0-9]{16,}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Bearer token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
]

# Values that are obviously placeholders — never treat these as real secrets.
PLACEHOLDER_HINTS = (
    "your", "example", "placeholder", "xxxx", "changeme", "todo",
    "<", ">", "redacted", "dummy", "test_key", "fake",
)


def _is_placeholder(value: str) -> bool:
    """Return True if a matched value looks like a template placeholder."""
    low = value.lower()
    return any(hint in low for hint in PLACEHOLDER_HINTS)


def _scan(text: str) -> List[str]:
    """Return a list of human-readable findings for any secrets in `text`."""
    findings: List[str] = []
    for description, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            # If the pattern captured a value group, check it for placeholders.
            value = match.group(match.lastindex) if match.lastindex else match.group(0)
            if _is_placeholder(value):
                continue
            findings.append(description)
    return findings


def _extract_text(tool_name: str, tool_input: dict) -> str:
    """Pull the text we should scan out of the tool input."""
    parts: List[str] = []
    # Write / Edit content
    for key in ("content", "new_string", "old_string"):
        val = tool_input.get(key)
        if isinstance(val, str):
            parts.append(val)
    # Bash command (catches `echo "API_KEY=..." >> file` and `git commit -m`)
    if tool_name == "Bash":
        cmd = tool_input.get("command")
        if isinstance(cmd, str):
            parts.append(cmd)
    return "\n".join(parts)


def main() -> int:
    """Read the hook payload, scan it, and allow or deny the tool call."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # If we can't parse input, fail open (don't block normal work).
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    text = _extract_text(tool_name, tool_input)
    if not text:
        return 0

    findings = _scan(text)
    if not findings:
        return 0

    unique = sorted(set(findings))
    reason = (
        "🔒 Blocked by check_secrets hook: the content looks like it contains a "
        f"secret ({', '.join(unique)}). Secrets must live in .env (gitignored), "
        "never in tracked files. If this is a false positive, use a placeholder "
        "value or put the real value in .env."
    )

    decision = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
