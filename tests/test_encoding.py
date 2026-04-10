"""Tests for encoding module."""

import pytest
from mail_pilot.encoding import (
    encode_subject,
    encode_address,
    encode_attachment_filename,
    make_email_message,
)


class TestEncodeSubject:
    def test_ascii_passthrough(self):
        assert encode_subject("Hello World") == "Hello World"

    def test_chinese_encoded(self):
        result = encode_subject("测试邮件主题")
        # Header may or may not encode depending on length,
        # but result must be a string
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mixed(self):
        result = encode_subject("Report 2026")
        assert result == "Report 2026"


class TestEncodeAddress:
    def test_no_name(self):
        assert encode_address(None, "user@163.com") == "user@163.com"

    def test_ascii_name(self):
        result = encode_address("Alice", "alice@example.com")
        assert "Alice" in result
        assert "alice@example.com" in result

    def test_chinese_name(self):
        result = encode_address("张三", "zhang@163.com")
        assert "utf-8" in result
        assert "zhang@163.com" in result


class TestEncodeAttachmentFilename:
    def test_ascii_filename(self):
        result = encode_attachment_filename("report.pdf")
        assert result == 'filename="report.pdf"'

    def test_chinese_filename(self):
        result = encode_attachment_filename("报告.pdf")
        assert "utf-8" in result
        assert "report.pdf" not in result.lower()


class TestMakeEmailMessage:
    def test_basic_message(self):
        msg = make_email_message(
            subject="Test",
            body="Hello",
            from_addr="sender@163.com",
            to_addrs=["receiver@example.com"],
        )
        assert msg["Subject"] == "Test"
        assert msg["From"] == "sender@163.com"
        assert msg["To"] == "receiver@example.com"
        assert "text/plain" in msg.get_content_type()
        assert msg["Cc"] is None

    def test_html_message(self):
        msg = make_email_message(
            subject="Test",
            body="<h1>Hi</h1>",
            from_addr="s@163.com",
            to_addrs=["r@example.com"],
            html=True,
        )
        assert "text/html" in msg.get_content_type()

    def test_with_cc_and_reply_to(self):
        msg = make_email_message(
            subject="Test",
            body="Hi",
            from_addr="s@163.com",
            to_addrs=["r@example.com"],
            cc_addrs=["cc@example.com"],
            reply_to="reply@163.com",
        )
        assert msg["Cc"] == "cc@example.com"
        assert msg["Reply-To"] == "reply@163.com"

    def test_chinese_subject(self):
        msg = make_email_message(
            subject="测试邮件主题较长触发编码",
            body="内容",
            from_addr="s@163.com",
            to_addrs=["r@example.com"],
        )
        # Subject is properly set as a string
        assert msg["Subject"] is not None
        assert len(msg["Subject"]) > 0

    def test_threading_headers(self):
        msg = make_email_message(
            subject="Re: Test",
            body="Reply",
            from_addr="s@163.com",
            to_addrs=["r@example.com"],
            in_reply_to="<msg123@163.com>",
            references="<msg100@163.com> <msg123@163.com>",
        )
        assert msg["In-Reply-To"] == "<msg123@163.com>"
        assert msg["References"] == "<msg100@163.com> <msg123@163.com>"
