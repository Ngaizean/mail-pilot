"""Tests for CLI module (parser and command routing)."""

import pytest
from mail_pilot.cli import build_parser, main


class TestBuildParser:
    def test_all_commands_registered(self):
        parser = build_parser()
        # Parse each command with minimal args
        test_cases = [
            "setup",
            ["send", "--to", "a@x.com", "-s", "Test", "-b", "Hi"],
            "list-accounts",
            ["remove-account", "test", "-y"],
            ["test-connection"],
            ["check"],
            ["fetch", "123"],
            ["search"],
            ["download", "123"],
            ["mark-read", "123"],
            ["mark-unread", "123"],
            "list-mailboxes",
            ["reply", "123", "-b", "ok"],
            ["forward", "123", "--to", "a@x.com"],
        ]
        for args in test_cases:
            if isinstance(args, str):
                result = parser.parse_args([args])
                assert result.command == args
            else:
                result = parser.parse_args(args)
                assert result.command is not None

    def test_send_default_values(self):
        parser = build_parser()
        args = parser.parse_args(["send", "--to", "a@x.com", "-s", "Test"])
        assert args.to == "a@x.com"
        assert args.subject == "Test"
        assert args.body == ""
        assert args.html is False
        assert args.dry_run is False
        assert args.dedup is False
        assert args.timeout == 30
        assert args.retry == 3

    def test_send_all_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "--to", "a@x.com,b@x.com", "-s", "Test", "-b", "Hi",
            "--html", "--dry-run", "--dedup", "--timeout", "60", "--retry", "5",
            "--cc", "c@x.com", "--bcc", "d@x.com", "--verbose",
        ])
        assert args.html is True
        assert args.dry_run is True
        assert args.dedup is True
        assert args.timeout == 60
        assert args.retry == 5
        assert args.cc == "c@x.com"
        assert args.bcc == "d@x.com"
        assert args.verbose is True

    def test_send_template_vars(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "--to", "a@x.com", "-s", "Test",
            "--template", "tpl.md", "--var", "name=Alice", "--var", "count=5",
        ])
        assert args.template == "tpl.md"
        assert args.var == ["name=Alice", "count=5"]

    def test_search_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "search", "--from", "a@x.com", "--subject", "test",
            "--since", "2h", "--unseen", "--limit", "50",
        ])
        assert args.from_filter == "a@x.com"
        assert args.subject_filter == "test"
        assert args.since == "2h"
        assert args.unseen is True
        assert args.limit == 50


class TestMainNoCommand:
    def test_no_args_shows_help(self, capsys):
        """Calling main() with sys.argv having no command should work."""
        import sys
        old_argv = sys.argv
        sys.argv = ["mail_pilot"]
        try:
            result = main()
            assert result == 0
        finally:
            sys.argv = old_argv


class TestListAccountsCommand:
    def test_empty_accounts(self, capsys):
        from mail_pilot.cli import cmd_list_accounts
        import argparse
        args = argparse.Namespace()
        with patch("mail_pilot.cli.load_config", return_value={"accounts": []}):
            ret = cmd_list_accounts(args)
            assert ret == 0
            captured = capsys.readouterr()
            assert "没有配置任何账号" in captured.out


from unittest.mock import patch
