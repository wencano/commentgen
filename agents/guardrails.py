"""
Guardrails for social-comment agents.

Policy text (blocked phrases, regexes, refusal copy) lives under `agents/policy/`
so you can edit lists without touching Python. Optional override:

    export COMMENTGEN_GUARDRAILS_POLICY_DIR=/path/to/custom-policy

Logic (clipping, normalization, when to apply which check) stays here.
"""
from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Final, Tuple

# --- Limits (chars); keep in code — change here if you need different caps ---

MAX_SOURCE_TEXT_CHARS: Final[int] = 32_000
MAX_IMAGE_EXTRACT_CHARS: Final[int] = 50_000
MAX_COMMENT_CHARS: Final[int] = 4_000
MAX_SESSION_TITLE_CHARS: Final[int] = 80
MAX_SESSION_TITLE_SEED: Final[int] = 2_000


def _policy_dir() -> Path:
    override = (os.getenv("COMMENTGEN_GUARDRAILS_POLICY_DIR") or "").strip()
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent / "policy"


def _read_nonempty_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


@lru_cache
def _compiled_blocked_regexes() -> Tuple[re.Pattern[str], ...]:
    out: list[re.Pattern[str]] = []
    d = _policy_dir()
    for name in ("blocked_regex.txt",):
        p = d / name
        for i, line in enumerate(_read_nonempty_lines(p), 1):
            try:
                out.append(re.compile(line, re.IGNORECASE | re.DOTALL))
            except re.error as e:
                raise ValueError(
                    f"Invalid regex in {p.name} (line {i}): {line!r} — {e}"
                ) from e
    return tuple(out)


@lru_cache
def _injection_regexes() -> Tuple[re.Pattern[str], ...]:
    out: list[re.Pattern[str]] = []
    p = _policy_dir() / "injection_regex.txt"
    for i, line in enumerate(_read_nonempty_lines(p), 1):
        try:
            out.append(re.compile(line, re.IGNORECASE | re.DOTALL))
        except re.error as e:
            raise ValueError(
                f"Invalid regex in injection_regex.txt (line {i}): {line!r} — {e}"
            ) from e
    return tuple(out)


@lru_cache
def _blocked_substrings() -> Tuple[str, ...]:
    p = _policy_dir() / "blocked_substrings.txt"
    return tuple(s.lower() for s in _read_nonempty_lines(p))


@lru_cache
def _refusal_message() -> str:
    p = _policy_dir() / "refusal_message.txt"
    if p.is_file():
        t = p.read_text().strip()
        if t:
            return t
    return (
        "I can’t help with that request. Please share a public post to comment on, "
        "and I’ll draft a thoughtful reply that fits the conversation."
    )


# Public alias (lazy-loaded on first use — same string for a given process)
def get_refusal_comment() -> str:
    return _refusal_message()


# Backwards compatibility: most callers use REFUSAL_COMMENT as a constant
REFUSAL_COMMENT: str = ""  # set at end of module after loaders exist


def normalize_for_match(text: str) -> str:
    t = (text or "").replace("\x00", "")
    t = unicodedata.normalize("NFKC", t)
    return t.strip()


def contains_strict_disallowed(text: str) -> bool:
    n = normalize_for_match(text)
    low = n.lower()
    for s in _blocked_substrings():
        if s in low:
            return True
    for pat in _compiled_blocked_regexes():
        if pat.search(n):
            return True
    return False


def looks_like_injection_attack(message: str) -> bool:
    m = normalize_for_match(message)
    if not m or len(m) > 500:
        return False
    for pat in _injection_regexes():
        if pat.search(m):
            return True
    return False


def clip_source_for_comment(source_post_text: str) -> str:
    s = (source_post_text or "").replace("\x00", "")
    if len(s) <= MAX_SOURCE_TEXT_CHARS:
        return s
    return s[:MAX_SOURCE_TEXT_CHARS] + "\n[…trimmed: content exceeded length limit]"


def clip_for_session_title_seed(message: str) -> str:
    s = (message or "").replace("\x00", "")
    if len(s) <= MAX_SESSION_TITLE_SEED:
        return s
    return s[:MAX_SESSION_TITLE_SEED]


def clip_extracted_image_text(text: str) -> str:
    t = (text or "").replace("\x00", "")
    if len(t) <= MAX_IMAGE_EXTRACT_CHARS:
        return t
    return t[:MAX_IMAGE_EXTRACT_CHARS] + " [trimmed]"


def sanitize_comment_text(comment: str) -> str:
    t = (comment or "").replace("\x00", "").strip()
    if len(t) > MAX_COMMENT_CHARS:
        t = t[:MAX_COMMENT_CHARS].rstrip() + "…"
    if contains_strict_disallowed(t):
        return get_refusal_comment()
    return t


def sanitize_title_text(title: str) -> str:
    t = " ".join((title or "").replace("\x00", "").split())
    if not t:
        return "New chat"
    t = t[:MAX_SESSION_TITLE_CHARS]
    if contains_strict_disallowed(t) or looks_like_injection_attack(t):
        return "New chat"
    return t


REFUSAL_COMMENT = get_refusal_comment()
