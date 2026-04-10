"""Date-locked deduplication via sentinel files."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "mail-pilot" / "sent"


def _dedup_key(sender: str, recipient: str, subject: str, date_str: str) -> str:
    """Generate a deterministic hash key for dedup."""
    raw = f"{sender}|{recipient}|{subject}|{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _sentinel_path(key: str) -> Path:
    """Return the sentinel file path for a given key."""
    return CACHE_DIR / f"{key}.lock"


def is_duplicate(
    sender: str,
    recipient: str,
    subject: str,
    target_date: date | None = None,
) -> bool:
    """Check if this email was already sent today.

    Args:
        sender: Sender email address.
        recipient: Primary recipient email address.
        subject: Email subject.
        target_date: Date to check (defaults to today UTC).

    Returns:
        True if a sentinel file exists (already sent).
    """
    if target_date is None:
        target_date = date.today()
    key = _dedup_key(sender, recipient, subject, target_date.isoformat())
    return _sentinel_path(key).exists()


def mark_sent(
    sender: str,
    recipient: str,
    subject: str,
    target_date: date | None = None,
) -> Path:
    """Create a sentinel file to mark email as sent.

    Args:
        sender: Sender email address.
        recipient: Primary recipient email address.
        subject: Email subject.
        target_date: Date for the sentinel (defaults to today UTC).

    Returns:
        Path to the created sentinel file.
    """
    if target_date is None:
        target_date = date.today()
    key = _dedup_key(sender, recipient, subject, target_date.isoformat())
    path = _sentinel_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def clean_expired(ttl_days: int = 7) -> int:
    """Remove sentinel files older than ttl_days.

    Args:
        ttl_days: Maximum age in days. Files older than this are removed.

    Returns:
        Number of files removed.
    """
    if not CACHE_DIR.exists():
        return 0

    import time

    cutoff = time.time() - (ttl_days * 86400)
    removed = 0
    for f in CACHE_DIR.iterdir():
        if f.is_file() and f.suffix == ".lock" and f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    return removed
