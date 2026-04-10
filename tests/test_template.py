"""Tests for template module."""

import pytest
from mail_pilot.template import build_template_context, parse_var_args


class TestBuildContext:
    def test_default_context(self):
        ctx = build_template_context()
        assert "date" in ctx
        assert "datetime" in ctx
        assert "recipient" in ctx
        assert "sender" in ctx

    def test_with_params(self):
        ctx = build_template_context(
            recipient="user@163.com",
            sender="me@163.com",
            subject="Hello",
            account_alias="163",
        )
        assert ctx["recipient"] == "user@163.com"
        assert ctx["sender"] == "me@163.com"
        assert ctx["subject"] == "Hello"
        assert ctx["account_alias"] == "163"

    def test_extra_vars_override(self):
        ctx = build_template_context(
            recipient="old@x.com",
            extra_vars={"recipient": "new@x.com", "custom": "value"},
        )
        assert ctx["recipient"] == "new@x.com"
        assert ctx["custom"] == "value"


class TestParseVarArgs:
    def test_single(self):
        result = parse_var_args(["name=Alice"])
        assert result == {"name": "Alice"}

    def test_multiple(self):
        result = parse_var_args(["name=Alice", "count=42"])
        assert result == {"name": "Alice", "count": "42"}

    def test_value_with_equals(self):
        result = parse_var_args(["equation=a=b"])
        assert result == {"equation": "a=b"}

    def test_empty(self):
        assert parse_var_args(None) == {}
        assert parse_var_args([]) == {}

    def test_no_equals(self):
        with pytest.raises(ValueError, match="格式错误"):
            parse_var_args(["noequals"])

    def test_empty_key(self):
        with pytest.raises(ValueError, match="不能为空"):
            parse_var_args(["=value"])
