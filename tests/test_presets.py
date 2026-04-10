"""Tests for presets module."""

import pytest
from mail_pilot.presets import detect_provider, list_providers, PROVIDERS


class TestDetectProvider:
    def test_163(self):
        p = detect_provider("user@163.com")
        assert p is not None
        assert p["smtp_host"] == "smtp.163.com"
        assert p["smtp_port"] == 465
        assert p["smtp_ssl"] is True

    def test_qq(self):
        p = detect_provider("test@qq.com")
        assert p is not None
        assert p["smtp_host"] == "smtp.qq.com"

    def test_gmail(self):
        p = detect_provider("user@gmail.com")
        assert p is not None
        assert p["smtp_port"] == 587
        assert p["smtp_ssl"] is False  # STARTTLS

    def test_outlook(self):
        p = detect_provider("user@outlook.com")
        assert p is not None

    def test_unknown(self):
        assert detect_provider("user@unknown.xyz") is None

    def test_no_at(self):
        assert detect_provider("notanemail") is None

    def test_case_insensitive(self):
        p = detect_provider("User@163.COM")
        assert p is not None
        assert p["smtp_host"] == "smtp.163.com"

    def test_all_providers_have_required_fields(self):
        for domain, preset in PROVIDERS.items():
            assert "smtp_host" in preset, f"{domain} missing smtp_host"
            assert "smtp_port" in preset, f"{domain} missing smtp_port"
            assert "imap_host" in preset, f"{domain} missing imap_host"
            assert "imap_port" in preset, f"{domain} missing imap_port"


class TestListProviders:
    def test_returns_list(self):
        providers = list_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 7

    def test_each_has_required_fields(self):
        for p in list_providers():
            assert "domain" in p
            assert "smtp" in p
            assert "imap" in p
