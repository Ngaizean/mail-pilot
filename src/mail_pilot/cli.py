"""CLI entry point: argparse-based command routing."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from getpass import getpass
from typing import Any

from mail_pilot import __version__
from mail_pilot.config import (
    add_account,
    list_accounts,
    load_config,
    remove_account,
    resolve_account,
)
from mail_pilot.credentials import get_backend
from mail_pilot.presets import detect_provider, list_providers
from mail_pilot.security import sanitize_alias, sanitize_email
from mail_pilot.smtp_client import send_email, test_connection


logger = logging.getLogger("mail_pilot")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _json_output(data: dict[str, Any]) -> None:
    """Print structured JSON to stdout."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging based on flags."""
    if quiet:
        level = logging.CRITICAL
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
        stream=sys.stderr,
    )


def _get_account_flag(args: argparse.Namespace) -> dict:
    """Common: load config and extract account flag."""
    return load_config(), getattr(args, "from_account", None) or getattr(args, "account", None)


# ── M1 Commands ──────────────────────────────────────────────────────────────

def cmd_setup(args: argparse.Namespace) -> int:
    """Interactive account setup wizard."""
    print("\n=== Mail Pilot 账号配置向导 ===\n")

    # Email address
    addr = input("邮箱地址: ").strip()
    try:
        addr = sanitize_email(addr)
    except ValueError as e:
        print(f"错误: {e}")
        return 1

    # Auto-detect provider
    preset = detect_provider(addr)
    if preset:
        domain = addr.rsplit("@", 1)[1].lower()
        print(f"已识别邮箱服务商: {domain}")
        if preset.get("note"):
            print(f"  提示: {preset['note']}")
    else:
        print("未识别的邮箱服务商，请手动配置")
        domain = "custom"

    # Alias
    default_alias = domain.replace(".", "-")
    alias = input(f"账号别名 [{default_alias}]: ").strip() or default_alias
    try:
        alias = sanitize_alias(alias)
    except ValueError as e:
        print(f"错误: {e}")
        return 1

    # Password
    password = getpass("密码/授权码: ")
    if not password:
        print("错误: 密码不能为空")
        return 1

    # Fernet passphrase if needed
    passphrase = None
    backend = get_backend()
    if backend == "fernet":
        print("\n检测到系统不支持 Keychain，将使用加密文件存储。")
        passphrase = getpass("设置加密口令（请妥善保管）: ")
        if not passphrase:
            print("错误: 加密口令不能为空")
            return 1

    # Add account
    try:
        config = add_account(
            alias=alias,
            email=addr,
            password=password,
            set_default=True,
            passphrase=passphrase,
        )
    except Exception as e:
        print(f"配置失败: {e}")
        return 1

    # Test connection
    print("\n正在测试 SMTP 连接...")
    result = test_connection(config, alias)
    if result["status"] == "ok":
        print(f"连接成功! ({result['smtp']})")
    else:
        print(f"连接失败: {result.get('detail', '未知错误')}")
        print("账号已保存，可稍后使用 test-connection 重新测试。")

    if len(config["accounts"]) == 1:
        print(f"\n已设置 '{alias}' 为默认账号。")
    else:
        set_default = input("\n是否设为默认账号? [y/N]: ").strip().lower()
        if set_default == "y":
            config["default_account"] = alias
            from mail_pilot.config import save_config
            save_config(config)
            print(f"已设置 '{alias}' 为默认账号。")

    print(f"\n配置完成! 现在可以发送邮件:")
    print(f"  python -m mail_pilot send --to someone@example.com --subject 'Hello' --body 'World'\n")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    """Send an email."""
    config = load_config()

    to = [e.strip() for e in args.to.split(",") if e.strip()]
    cc = [e.strip() for e in args.cc.split(",") if e.strip()] if args.cc else None
    bcc = [e.strip() for e in args.bcc.split(",") if e.strip()] if args.bcc else None
    attachments = [p.strip() for p in args.attach.split(",") if p.strip()] if args.attach else None

    # Template support
    body = args.body or ""
    template_path = getattr(args, "template", None)
    if template_path:
        from mail_pilot.template import (
            build_template_context,
            parse_var_args,
            render_template,
        )
        from mail_pilot.config import resolve_account
        account = resolve_account(config, args.from_account)
        extra_vars = parse_var_args(getattr(args, "var", None))
        context = build_template_context(
            recipient=to[0] if to else "",
            sender=account["email"],
            subject=args.subject,
            account_alias=account["alias"],
            extra_vars=extra_vars,
        )
        body = render_template(template_path, context)

    result = send_email(
        config=config,
        alias_or_email=args.from_account,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=args.subject,
        body=body,
        body_file=getattr(args, "body_file", None) if not template_path else None,
        html=args.html,
        attachments=attachments,
        reply_to=args.reply_to,
        dry_run=args.dry_run,
        dedup=args.dedup,
        timeout=args.timeout,
        max_retries=args.retry,
    )

    _json_output(result)
    return 0 if result["status"] in ("sent", "deduplicated", "dry_run") else 1


def cmd_list_accounts(args: argparse.Namespace) -> int:
    """List all configured accounts."""
    config = load_config()
    accounts = list_accounts(config)
    if not accounts:
        _json_output({"accounts": [], "message": "没有配置任何账号"})
        return 0
    _json_output({"accounts": accounts})
    return 0


def cmd_remove_account(args: argparse.Namespace) -> int:
    """Remove an account."""
    config = load_config()
    from mail_pilot.config import get_account
    account = get_account(config, args.alias)
    if account is None:
        _json_output({"status": "error", "error": "not_found", "detail": f"账号不存在: {args.alias}"})
        return 1

    if not args.yes:
        confirm = input(f"确认删除账号 '{account['alias']}' ({account['email']})? [y/N]: ").strip().lower()
        if confirm != "y":
            print("已取消")
            return 0

    try:
        remove_account(args.alias)
        _json_output({"status": "removed", "alias": args.alias})
        return 0
    except Exception as e:
        _json_output({"status": "error", "error": str(e)})
        return 1


def cmd_test_connection(args: argparse.Namespace) -> int:
    """Test SMTP connection."""
    config = load_config()
    result = test_connection(config, args.account)
    _json_output(result)
    return 0 if result["status"] == "ok" else 1


# ── M2 Commands ──────────────────────────────────────────────────────────────

def cmd_check(args: argparse.Namespace) -> int:
    """Check inbox for recent emails."""
    from mail_pilot.imap_client import check as imap_check

    config = load_config()
    result = imap_check(
        config=config,
        alias_or_email=args.account,
        limit=args.limit,
        recent=args.recent,
        mailbox=args.mailbox,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch a full email by UID."""
    from mail_pilot.imap_client import fetch as imap_fetch

    config = load_config()
    result = imap_fetch(
        config=config,
        uid=args.uid,
        alias_or_email=args.account,
        mailbox=args.mailbox,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_search(args: argparse.Namespace) -> int:
    """Search emails by criteria."""
    from mail_pilot.imap_client import search as imap_search

    config = load_config()
    result = imap_search(
        config=config,
        alias_or_email=args.account,
        from_filter=args.from_filter,
        subject_filter=args.subject_filter,
        since=args.since,
        before=args.before,
        unseen=args.unseen,
        limit=args.limit,
        mailbox=args.mailbox,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_download(args: argparse.Namespace) -> int:
    """Download attachments from an email."""
    from mail_pilot.imap_client import download as imap_download

    config = load_config()
    result = imap_download(
        config=config,
        uid=args.uid,
        alias_or_email=args.account,
        filename=args.file,
        output_dir=args.dir,
        mailbox=args.mailbox,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_mark_read(args: argparse.Namespace) -> int:
    """Mark emails as read."""
    from mail_pilot.imap_client import mark_read as imap_mark_read

    config = load_config()
    result = imap_mark_read(
        config=config,
        uids=args.uids,
        alias_or_email=args.account,
        mailbox=args.mailbox,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_mark_unread(args: argparse.Namespace) -> int:
    """Mark emails as unread."""
    from mail_pilot.imap_client import mark_unread as imap_mark_unread

    config = load_config()
    result = imap_mark_unread(
        config=config,
        uids=args.uids,
        alias_or_email=args.account,
        mailbox=args.mailbox,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_list_mailboxes(args: argparse.Namespace) -> int:
    """List all mailboxes/folders."""
    from mail_pilot.imap_client import list_mailboxes as imap_list_mailboxes

    config = load_config()
    result = imap_list_mailboxes(
        config=config,
        alias_or_email=args.account,
        timeout=args.timeout,
    )
    _json_output(result)
    return 0 if result.get("status") == "ok" else 1


def cmd_reply(args: argparse.Namespace) -> int:
    """Reply to an email."""
    from email.utils import parseaddr
    from mail_pilot.imap_client import get_message_headers_for_reply

    config = load_config()
    account = args.account

    # Fetch original message headers for threading
    original = get_message_headers_for_reply(
        config=config, uid=args.uid, alias_or_email=account,
        mailbox=args.mailbox, timeout=args.timeout,
    )
    if not original:
        _json_output({"status": "error", "error": "not_found", "detail": f"未找到邮件 UID: {args.uid}"})
        return 1

    # Extract reply-to email address using proper parser
    from_header = original.get("from", "")
    _, reply_email = parseaddr(from_header)
    if not reply_email:
        reply_email = from_header.strip()

    # Build reply subject
    subject = original.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Build References header
    references = original.get("references", "")
    message_id = original.get("message_id", "")
    if references:
        references = f"{references} {message_id}"
    else:
        references = message_id

    result = send_email(
        config=config,
        alias_or_email=account,
        to=[reply_email],
        subject=subject,
        body=args.body or "",
        html=args.html,
        in_reply_to=message_id,
        references=references,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )

    _json_output(result)
    return 0 if result["status"] in ("sent", "dry_run") else 1


def cmd_forward(args: argparse.Namespace) -> int:
    """Forward an email."""
    from mail_pilot.imap_client import fetch as imap_fetch

    config = load_config()
    account = args.account

    # Fetch original email
    original = imap_fetch(
        config=config, uid=args.uid, alias_or_email=account,
        mailbox=args.mailbox, timeout=args.timeout,
    )
    if original.get("status") != "ok":
        _json_output({"status": "error", "error": "not_found", "detail": f"未找到邮件 UID: {args.uid}"})
        return 1

    headers = original["headers"]
    body_text = original["body"].get("text") or original["body"].get("html", "")

    # Build forward body
    fwd_body = args.body + "\n\n" if args.body else ""
    fwd_body += f"---------- 转发的邮件 ----------\n"
    fwd_body += f"From: {headers['from']}\n"
    fwd_body += f"Date: {headers['date']}\n"
    fwd_body += f"Subject: {headers['subject']}\n\n"
    fwd_body += body_text

    subject = headers.get("subject", "")
    if not subject.lower().startswith("fwd:"):
        subject = f"Fwd: {subject}"

    to = [e.strip() for e in args.to.split(",") if e.strip()]

    result = send_email(
        config=config,
        alias_or_email=account,
        to=to,
        subject=subject,
        body=fwd_body,
        html=args.html,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )

    _json_output(result)
    return 0 if result["status"] in ("sent", "dry_run") else 1


# ── Argument Parser ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="mail_pilot",
        description="Mail Pilot — 面向 AI Agent 的安全邮件 CLI 工具",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ── setup ──
    p_setup = subparsers.add_parser("setup", help="交互式配置向导")
    p_setup.set_defaults(func=cmd_setup)

    # ── send ──
    p_send = subparsers.add_parser("send", help="发送邮件")
    p_send.add_argument("--to", required=True, help="收件人（逗号分隔多个）")
    p_send.add_argument("--subject", "-s", required=True, help="邮件主题")
    p_send.add_argument("--body", "-b", default="", help="邮件正文")
    p_send.add_argument("--body-file", help="从文件读取正文")
    p_send.add_argument("--from", dest="from_account", help="发件账号（别名或邮箱）")
    p_send.add_argument("--cc", help="抄送（逗号分隔）")
    p_send.add_argument("--bcc", help="密送（逗号分隔）")
    p_send.add_argument("--html", action="store_true", help="HTML 格式邮件")
    p_send.add_argument("--attach", help="附件路径（逗号分隔多个）")
    p_send.add_argument("--template", help="Jinja2 模板文件路径")
    p_send.add_argument("--var", action="append", help="模板变量 key=value（可多次指定）")
    p_send.add_argument("--reply-to", help="回复地址")
    p_send.add_argument("--dry-run", action="store_true", help="模拟发送（不实际投递）")
    p_send.add_argument("--dedup", action="store_true", help="启用日期去重")
    p_send.add_argument("--timeout", type=int, default=30, help="连接超时（秒，默认 30）")
    p_send.add_argument("--retry", type=int, default=3, help="最大重试次数（默认 3）")
    p_send.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_send.add_argument("--quiet", "-q", action="store_true", help="仅输出 JSON")
    p_send.set_defaults(func=cmd_send)

    # ── list-accounts ──
    p_list = subparsers.add_parser("list-accounts", help="列出所有账号")
    p_list.set_defaults(func=cmd_list_accounts)

    # ── remove-account ──
    p_remove = subparsers.add_parser("remove-account", help="删除账号")
    p_remove.add_argument("alias", help="账号别名")
    p_remove.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    p_remove.set_defaults(func=cmd_remove_account)

    # ── test-connection ──
    p_test = subparsers.add_parser("test-connection", help="测试 SMTP 连接")
    p_test.add_argument("--account", "-a", help="账号别名（默认使用默认账号）")
    p_test.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_test.set_defaults(func=cmd_test_connection)

    # ── M2: check ──
    p_check = subparsers.add_parser("check", help="查看收件箱")
    p_check.add_argument("--account", "-a", help="账号别名")
    p_check.add_argument("--limit", type=int, default=20, help="返回数量（默认 20）")
    p_check.add_argument("--recent", help="时间范围（如 2h, 30m, 7d）")
    p_check.add_argument("--mailbox", default="INBOX", help="邮箱目录（默认 INBOX）")
    p_check.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_check.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_check.add_argument("--quiet", "-q", action="store_true", help="仅输出 JSON")
    p_check.set_defaults(func=cmd_check)

    # ── M2: fetch ──
    p_fetch = subparsers.add_parser("fetch", help="获取邮件全文")
    p_fetch.add_argument("uid", help="邮件 UID")
    p_fetch.add_argument("--account", "-a", help="账号别名")
    p_fetch.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_fetch.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_fetch.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_fetch.set_defaults(func=cmd_fetch)

    # ── M2: search ──
    p_search = subparsers.add_parser("search", help="搜索邮件")
    p_search.add_argument("--from", dest="from_filter", help="发件人筛选")
    p_search.add_argument("--subject", dest="subject_filter", help="主题筛选")
    p_search.add_argument("--since", help="时间范围（如 2h, 7d）")
    p_search.add_argument("--before", help="截止时间（如 2h, 7d）")
    p_search.add_argument("--unseen", action="store_true", help="仅未读邮件")
    p_search.add_argument("--limit", type=int, default=20, help="返回数量")
    p_search.add_argument("--account", "-a", help="账号别名")
    p_search.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_search.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_search.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_search.set_defaults(func=cmd_search)

    # ── M2: download ──
    p_download = subparsers.add_parser("download", help="下载附件")
    p_download.add_argument("uid", help="邮件 UID")
    p_download.add_argument("--file", help="指定文件名（单附件时生效）")
    p_download.add_argument("--dir", help="保存目录（默认当前目录）")
    p_download.add_argument("--account", "-a", help="账号别名")
    p_download.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_download.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_download.set_defaults(func=cmd_download)

    # ── M2: mark-read ──
    p_mark_read = subparsers.add_parser("mark-read", help="标记为已读")
    p_mark_read.add_argument("uids", nargs="+", help="邮件 UID（多个用空格分隔）")
    p_mark_read.add_argument("--account", "-a", help="账号别名")
    p_mark_read.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_mark_read.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_mark_read.set_defaults(func=cmd_mark_read)

    # ── M2: mark-unread ──
    p_mark_unread = subparsers.add_parser("mark-unread", help="标记为未读")
    p_mark_unread.add_argument("uids", nargs="+", help="邮件 UID（多个用空格分隔）")
    p_mark_unread.add_argument("--account", "-a", help="账号别名")
    p_mark_unread.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_mark_unread.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_mark_unread.set_defaults(func=cmd_mark_unread)

    # ── M2: list-mailboxes ──
    p_mailboxes = subparsers.add_parser("list-mailboxes", help="列出邮箱目录")
    p_mailboxes.add_argument("--account", "-a", help="账号别名")
    p_mailboxes.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_mailboxes.set_defaults(func=cmd_list_mailboxes)

    # ── M2: reply ──
    p_reply = subparsers.add_parser("reply", help="回复邮件")
    p_reply.add_argument("uid", help="邮件 UID")
    p_reply.add_argument("--body", "-b", default="", help="回复正文")
    p_reply.add_argument("--html", action="store_true", help="HTML 格式")
    p_reply.add_argument("--account", "-a", help="账号别名")
    p_reply.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_reply.add_argument("--dry-run", action="store_true", help="模拟发送")
    p_reply.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_reply.set_defaults(func=cmd_reply)

    # ── M2: forward ──
    p_forward = subparsers.add_parser("forward", help="转发邮件")
    p_forward.add_argument("uid", help="邮件 UID")
    p_forward.add_argument("--to", required=True, help="转发收件人（逗号分隔）")
    p_forward.add_argument("--body", "-b", default="", help="转发说明")
    p_forward.add_argument("--html", action="store_true", help="HTML 格式")
    p_forward.add_argument("--account", "-a", help="账号别名")
    p_forward.add_argument("--mailbox", default="INBOX", help="邮箱目录")
    p_forward.add_argument("--dry-run", action="store_true", help="模拟发送")
    p_forward.add_argument("--timeout", type=int, default=30, help="连接超时（秒）")
    p_forward.set_defaults(func=cmd_forward)

    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    verbose = getattr(args, "verbose", False)
    quiet = getattr(args, "quiet", False)
    _setup_logging(verbose=verbose, quiet=quiet)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130
    except Exception as e:
        logger.debug("异常详情", exc_info=True)
        _json_output({"status": "error", "error": type(e).__name__, "detail": str(e)})
        return 1
