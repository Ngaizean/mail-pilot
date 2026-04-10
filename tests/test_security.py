"""Tests for security module."""

import os
import tempfile
import pytest
from mail_pilot.security import (
    sanitize_email,
    sanitize_alias,
    validate_subject,
    check_attachment_size,
    check_total_size,
    validate_attachment_path,
)


class TestSanitizeEmail:
    def test_normal(self):
        assert sanitize_email("user@163.com") == "user@163.com"

    def test_strips_whitespace(self):
        assert sanitize_email("  user@163.com  ") == "user@163.com"

    def test_lowercases_domain(self):
        assert sanitize_email("User@163.COM") == "User@163.com"

    def test_no_at(self):
        with pytest.raises(ValueError, match="无效的邮箱"):
            sanitize_email("noemail")

    def test_empty(self):
        with pytest.raises(ValueError):
            sanitize_email("")


class TestSanitizeAlias:
    def test_normal(self):
        assert sanitize_alias("my-163") == "my-163"

    def test_underscore_dot(self):
        assert sanitize_alias("my_account.v2") == "my_account.v2"

    def test_empty(self):
        with pytest.raises(ValueError, match="不能为空"):
            sanitize_alias("")

    def test_spaces_only(self):
        with pytest.raises(ValueError):
            sanitize_alias("   ")

    def test_special_chars(self):
        with pytest.raises(ValueError, match="非法字符"):
            sanitize_alias("bad alias!")

    def test_strips(self):
        assert sanitize_alias("  hello  ") == "hello"


class TestValidateSubject:
    def test_normal(self):
        assert validate_subject("Hello") == "Hello"

    def test_chinese(self):
        assert validate_subject("测试邮件") == "测试邮件"

    def test_strips(self):
        assert validate_subject("  Hello  ") == "Hello"

    def test_empty(self):
        with pytest.raises(ValueError, match="不能为空"):
            validate_subject("")

    def test_spaces_only(self):
        with pytest.raises(ValueError):
            validate_subject("   ")


class TestAttachmentSize:
    def test_small_file_ok(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100)
            f.flush()
            check_attachment_size(f.name, max_bytes=1000)
            os.unlink(f.name)

    def test_file_too_large(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 2000)
            f.flush()
            with pytest.raises(ValueError, match="超过大小限制"):
                check_attachment_size(f.name, max_bytes=1000)
            os.unlink(f.name)

    def test_total_size_ok(self):
        files = []
        for _ in range(3):
            f = tempfile.NamedTemporaryFile(delete=False)
            f.write(b"x" * 100)
            f.flush()
            files.append(f.name)
            f.close()
        check_total_size(files, max_bytes=1000)
        for p in files:
            os.unlink(p)

    def test_total_size_exceeded(self):
        files = []
        for _ in range(3):
            f = tempfile.NamedTemporaryFile(delete=False)
            f.write(b"x" * 500)
            f.flush()
            files.append(f.name)
            f.close()
        with pytest.raises(ValueError, match="总大小超过限制"):
            check_total_size(files, max_bytes=1000)
        for p in files:
            os.unlink(p)
