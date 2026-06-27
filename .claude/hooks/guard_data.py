#!/usr/bin/env python3
"""
PreToolUse hook: block git from staging/committing data, DB, cache, or .env files.

Runs before Bash tool calls. If the command is a `git add` / `git commit` that
would include the gitignored runtime artifacts (data/, *.db, *.parquet, .env),
it DENIES the action. This is a belt-and-suspenders complement to .gitignore:
it catches `git add -f`, `git add .` after a stray un-ignored file, etc.

This file contains NO secrets and is safe to commit.
"""

from __future__ import annotations

import json
import re
import sys
from typing import List

# Substrings that must never enter a commit. Matched against the git command.
FORBIDDEN_PATTERNS: List["re.Pattern[str]"] = [
    re.compile(r"\bdata/"),          # the runtime data directory
    re.compile(r"\.env(?:\b|$)"),    # any .env (but NOT .env.example, handled below)
    re.compile(r"\.db\b"),
    re.compile(r"\.sqlite3?\b"),
    re.compile(r"\.parquet\b"),
    re.compile(r"\.key\b"),
    re.compile(r"\.pem\b"),
    re.compile(r"dontshow\.py"),
    re.compile(r"config_secret\.py"),
    re.compile(r"secrets\.py"),
]

# Git subcommands that write to the index / history.
GIT_WRITE_RE = re.compile(r"\bgit\s+(add|commit|stage)\b")


def _is_git_write(command: str) -> bool:
    """True if the command stages or commits to git."""
    return bool(GIT_WRITE_RE.search(command))


def _find_violations(command: str) -> List[str]:
    """Return forbidden tokens referenced by a git-write command."""
    # Allow the committed template explicitly.
    sanitized = command.replace(".env.example", "")
    hits: List[str] = []
    for pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(sanitized)
        if match:
            hits.append(match.group(0))
    return hits


def main() -> int:
    """Read the hook payload and deny git writes that touch protected files."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # fail open

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input", {}) or {}).get("command", "")
    if not isinstance(command, str) or not _is_git_write(command):
        return 0

    violations = _find_violations(command)
    if not violations:
        return 0

    reason = (
        "🔒 Blocked by guard_data hook: this git command references protected "
        f"runtime/secret files ({', '.join(sorted(set(violations)))}). These are "
        "gitignored on purpose and must never be committed. Remove them from the "
        "command (and never use `git add -f` on them)."
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
