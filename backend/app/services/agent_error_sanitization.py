from __future__ import annotations

import re
from typing import Any

_URL_USERINFO_PATTERN = re.compile(
    r"(?P<scheme>\b[a-z][a-z0-9+.-]*://)[^/\s?#@]+@",
    re.IGNORECASE,
)
_AUTHORIZATION_PATTERN = re.compile(
    r"\b(?P<scheme>bearer|basic)\s+[^\s,;]+",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<prefix>\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|secret)"
    r"\b\s*[:=]\s*)[^&\s,;]+",
    re.IGNORECASE,
)


def scrub_agent_runtime_error(value: Any, *, limit: int = 2000) -> str:
    """Return bounded diagnostic text with common credential forms removed."""

    text = str(value or "").strip()
    if not text:
        if isinstance(value, BaseException):
            text = value.__class__.__name__
        else:
            return ""
    text = _URL_USERINFO_PATTERN.sub(r"\g<scheme>[REDACTED]@", text)
    text = _AUTHORIZATION_PATTERN.sub(r"\g<scheme> [REDACTED]", text)
    text = _SENSITIVE_ASSIGNMENT_PATTERN.sub(r"\g<prefix>[REDACTED]", text)
    bounded_limit = max(int(limit), 1)
    if len(text) <= bounded_limit:
        return text
    if bounded_limit <= 3:
        return text[:bounded_limit]
    return text[: bounded_limit - 3] + "..."
