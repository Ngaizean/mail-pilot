"""Tests for dedup module."""

import pytest
from datetime import date
from mail_pilot.dedup import is_duplicate, mark_sent, clean_expired


class TestDedup:
    def test_not_duplicate_initially(self):
        assert is_duplicate("a@x.com", "b@y.com", "Test") is False

    def test_mark_then_check(self):
        sender = "dedup_test@x.com"
        recipient = "dedup_test@y.com"
        subject = "Dedup Test Subject"
        test_date = date(2026, 1, 1)

        mark_sent(sender, recipient, subject, test_date)
        assert is_duplicate(sender, recipient, subject, test_date) is True

    def test_different_subject_not_duplicate(self):
        sender = "dedup_test2@x.com"
        recipient = "dedup_test2@y.com"
        test_date = date(2026, 1, 2)

        mark_sent(sender, recipient, "Subject A", test_date)
        assert is_duplicate(sender, recipient, "Subject B", test_date) is False

    def test_different_date_not_duplicate(self):
        sender = "dedup_test3@x.com"
        recipient = "dedup_test3@y.com"
        subject = "Same Subject"

        mark_sent(sender, recipient, subject, date(2026, 1, 3))
        assert is_duplicate(sender, recipient, subject, date(2026, 1, 4)) is False

    def test_clean_expired(self):
        # Just verify it runs without error
        removed = clean_expired(ttl_days=0)
        assert isinstance(removed, int)
