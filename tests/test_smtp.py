"""Tests for smtp_client module (dry-run and error paths only, no real SMTP)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from mail_pilot.smtp_client import send_email, _connect_smtp


class TestSendEmailValidation:
    def test_missing_recipients(self):
        result = send_email({"accounts": []}, to=[], subject="Test", body="Hi")
        assert result["status"] == "error"
        assert result["error"] == "missing_recipients"

    def test_no_accounts(self):
        with pytest.raises(ValueError, match="没有配置任何账号"):
            send_email(
                {"accounts": [], "default_account": ""},
                to=["a@x.com"], subject="Test", body="Hi",
            )

    @patch("mail_pilot.smtp_client.resolve_account")
    def test_dry_run(self, mock_resolve):
        mock_resolve.return_value = {
            "alias": "163", "email": "user@163.com",
            "credential_backend": "keychain",
        }
        result = send_email(
            {"accounts": [{"alias": "163"}]},
            to=["a@x.com"], subject="Test", body="Hello World",
            dry_run=True,
        )
        assert result["status"] == "dry_run"
        assert result["from"] == "user@163.com"
        assert result["to"] == ["a@x.com"]
        assert result["body_length"] == 11
        assert "Hello World" in result["message_preview"]

    @patch("mail_pilot.smtp_client.resolve_account")
    def test_dry_run_with_attachments_list(self, mock_resolve, tmp_path):
        """Dry-run with real attachment shows filenames in result."""
        mock_resolve.return_value = {
            "alias": "163", "email": "user@163.com",
            "credential_backend": "keychain",
        }
        # Create a real temp file in a whitelisted dir
        att = Path("/tmp") / "mail_pilot_test_file.pdf"
        att.write_bytes(b"%PDF-fake")
        try:
            result = send_email(
                {"accounts": [{"alias": "163"}]},
                to=["a@x.com"], subject="Test", body="Hi",
                dry_run=True, attachments=[str(att)],
            )
            assert result["status"] == "dry_run"
            assert result["attachments"] == ["mail_pilot_test_file.pdf"]
        finally:
            att.unlink(missing_ok=True)

    @patch("mail_pilot.smtp_client.resolve_account")
    def test_dedup_skips(self, mock_resolve):
        mock_resolve.return_value = {
            "alias": "163", "email": "user@163.com",
            "credential_backend": "keychain",
        }
        with patch("mail_pilot.smtp_client.is_duplicate", return_value=True):
            result = send_email(
                {"accounts": [{"alias": "163"}]},
                to=["a@x.com"], subject="Daily", body="Report",
                dedup=True,
            )
            assert result["status"] == "deduplicated"

    @patch("mail_pilot.smtp_client.resolve_account")
    def test_dedup_marks_sent(self, mock_resolve):
        mock_resolve.return_value = {
            "alias": "163", "email": "user@163.com",
            "smtp_host": "smtp.163.com", "smtp_port": 465,
            "smtp_ssl": True, "credential_backend": "keychain",
        }
        with patch("mail_pilot.smtp_client.is_duplicate", return_value=False), \
             patch("mail_pilot.smtp_client.retrieve_password", return_value="pass"), \
             patch("mail_pilot.smtp_client._connect_smtp") as mock_conn, \
             patch("mail_pilot.smtp_client.mark_sent") as mock_mark:
            mock_server = MagicMock()
            mock_conn.return_value = mock_server
            mock_server.send_message = MagicMock()
            result = send_email(
                {"accounts": [{"alias": "163"}]},
                to=["a@x.com"], subject="Daily", body="Report",
                dedup=True,
            )
            assert result["status"] == "sent"
            mock_mark.assert_called_once()


class TestConnectSmtp:
    @patch("mail_pilot.smtp_client.smtplib.SMTP_SSL")
    def test_ssl_connection(self, mock_ssl):
        mock_ssl.return_value = MagicMock()
        server = _connect_smtp("smtp.163.com", 465, True, 30)
        mock_ssl.assert_called_once_with("smtp.163.com", 465, timeout=30)

    @patch("mail_pilot.smtp_client.smtplib.SMTP")
    def test_starttls_connection(self, mock_smtp):
        mock_instance = MagicMock()
        mock_smtp.return_value = mock_instance
        server = _connect_smtp("smtp.gmail.com", 587, False, 30)
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        assert mock_instance.ehlo.call_count == 2
        mock_instance.starttls.assert_called_once()
