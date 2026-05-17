"""Hex string validation helpers."""

from __future__ import annotations


def is_depot_key(s: str) -> bool:
    """Depot key: exactly 64 hex characters."""
    return len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s)


def is_hex(s: str) -> bool:
    if not s:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


def is_decimal(s: str) -> bool:
    return bool(s) and s.isdigit()
