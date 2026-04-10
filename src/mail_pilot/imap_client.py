"""IMAP client for reading, searching, and managing emails."""

from __future__ import annotations

import email
import imaplib
import logging
import os
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

from mail_pilot.config import resolve_account
from mail_pilot.credentials import retrieve_password

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_MAILBOX = "INBOX"
DEFAULT_LIMIT = 20


def _connect_imap(
    host: str, port: int, use_ssl: bool, timeout: int,
) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
    """Connect to IMAP server."""
    logger.debug("连接 IMAP: %s:%d (SSL=%s)", host, port, use_ssl)
    if use_ssl:
        return imaplib.IMAP4_SSL(host, port, timeout=timeout)
    else:
        return imaplib.IMAP4(host, port, timeout=timeout)


def _decode_header_value(raw: str) -> str:
    """Decode RFC 2047 encoded header value."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return "".join(decoded)


def _parse_date(date_str: str) -> str:
    """Parse email date to ISO format."""
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return date_str


def _parse_email_headers(msg: email.message.Message) -> dict[str, Any]:
    """Extract key headers from an email message."""
    return {
        "from": _decode_header_value(msg.get("From", "")),
        "to": _decode_header_value(msg.get("To", "")),
        "cc": _decode_header_value(msg.get("Cc", "")),
        "subject": _decode_header_value(msg.get("Subject", "")),
        "date": _parse_date(msg.get("Date", "")),
        "message_id": msg.get("Message-ID", ""),
        "references": msg.get("References", ""),
        "in_reply_to": msg.get("In-Reply-To", ""),
    }


def _extract_body(msg: email.message.Message) -> dict[str, str]:
    """Extract text/plain and text/html bodies from a message."""
    text_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain" and not text_body:
                charset = part.get_content_charset() or "utf-8"
                try:
                    text_body = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    text_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
            elif content_type == "text/html" and not html_body:
                charset = part.get_content_charset() or "utf-8"
                try:
                    html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
    else:
        content_type = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    return {"text": text_body, "html": html_body}


def _extract_attachments(msg: email.message.Message) -> list[dict[str, str]]:
    """List attachments in a message (without downloading)."""
    attachments = []
    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in disposition:
            continue
        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)
            size = len(part.get_payload(decode=True) or b"")
            attachments.append({"filename": filename, "size": size})
    return attachments


def _parse_recent_period(period: str) -> datetime:
    """Parse a period string like '2h', '30m', '1d' to a datetime."""
    period = period.strip().lower()
    now = datetime.now(timezone.utc)

    if period.endswith("h"):
        hours = int(period[:-1])
        return now - timedelta(hours=hours)
    elif period.endswith("m"):
        minutes = int(period[:-1])
        return now - timedelta(minutes=minutes)
    elif period.endswith("d"):
        days = int(period[:-1])
        return now - timedelta(days=days)
    else:
        raise ValueError(f"无法解析时间范围: {period}（支持 h/m/d 后缀，如 2h, 30m, 7d）")


def _open_mailbox(
    config: dict,
    alias_or_email: Optional[str],
    mailbox: str,
    timeout: int,
    readonly: bool = True,
) -> tuple[imaplib.IMAP4 | imaplib.IMAP4_SSL, dict[str, Any]]:
    """Connect, login, and select a mailbox. Returns (mail_conn, account)."""
    account = resolve_account(config, alias_or_email)
    password = retrieve_password(
        account["alias"], account["email"], account["credential_backend"]
    )

    mail = _connect_imap(
        account["imap_host"], account["imap_port"],
        account["imap_ssl"], timeout,
    )
    mail.login(account["email"], password)
    mail.select(mailbox, readonly=readonly)

    return mail, account


# ── Public API ───────────────────────────────────────────────────────────────

def check(
    config: dict,
    alias_or_email: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    recent: Optional[str] = None,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Check inbox for recent emails.

    Returns:
        Dict with list of email summaries.
    """
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout)

    try:
        # Build search criteria
        criteria = []
        if recent:
            since_date = _parse_recent_period(recent)
            # IMAP SINCE uses date-only format DD-Mon-YYYY (no quotes, no parens)
            criteria.append(f'SINCE {since_date.strftime("%d-%b-%Y")}')

        search_query = " ".join(criteria) if criteria else "ALL"

        status, data = mail.search(None, search_query)
        if status != "OK":
            return {"status": "error", "error": "search_failed", "detail": status}

        uids = data[0].split() if data[0] else []
        # Get the most recent 'limit' emails
        uids = uids[-limit:]
        uids.reverse()

        emails_list = []
        for uid in uids:
            status, msg_data = mail.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID)])")
            if status != "OK":
                continue
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    headers = _parse_email_headers(msg)
                    headers["uid"] = uid.decode()
                    emails_list.append(headers)

        return {
            "status": "ok",
            "account": account["alias"],
            "mailbox": mailbox,
            "count": len(emails_list),
            "emails": emails_list,
        }
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def fetch(
    config: dict,
    uid: str,
    alias_or_email: Optional[str] = None,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch a full email by UID.

    Returns:
        Dict with full email content including headers, body, and attachment list.
    """
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout)

    try:
        status, msg_data = mail.fetch(uid.encode(), "(RFC822)")
        if status != "OK":
            return {"status": "error", "error": "fetch_failed", "uid": uid}

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                headers = _parse_email_headers(msg)
                body = _extract_body(msg)
                attachments = _extract_attachments(msg)

                return {
                    "status": "ok",
                    "uid": uid,
                    "headers": headers,
                    "body": body,
                    "attachments": attachments,
                }

        return {"status": "error", "error": "not_found", "uid": uid}
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def search(
    config: dict,
    alias_or_email: Optional[str] = None,
    from_filter: Optional[str] = None,
    subject_filter: Optional[str] = None,
    since: Optional[str] = None,
    before: Optional[str] = None,
    unseen: bool = False,
    limit: int = DEFAULT_LIMIT,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Search emails by various criteria.

    Returns:
        Dict with matching email summaries.
    """
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout)

    try:
        criteria = []

        if from_filter:
            criteria.append(f'FROM "{from_filter}"')
        if subject_filter:
            criteria.append(f'SUBJECT "{subject_filter}"')
        if since:
            since_date = _parse_recent_period(since)
            criteria.append(f'SINCE {since_date.strftime("%d-%b-%Y")}')
        if before:
            before_date = _parse_recent_period(before)
            criteria.append(f'BEFORE {before_date.strftime("%d-%b-%Y")}')
        if unseen:
            criteria.append("UNSEEN")

        search_query = " ".join(criteria) if criteria else "ALL"
        logger.debug("IMAP SEARCH: %s", search_query)

        status, data = mail.search(None, search_query)
        if status != "OK":
            return {"status": "error", "error": "search_failed"}

        uids = data[0].split() if data[0] else []
        uids = uids[-limit:]
        uids.reverse()

        emails_list = []
        for uid in uids:
            status, msg_data = mail.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE)])")
            if status != "OK":
                continue
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    headers = _parse_email_headers(msg)
                    headers["uid"] = uid.decode()
                    emails_list.append(headers)

        return {
            "status": "ok",
            "account": account["alias"],
            "mailbox": mailbox,
            "count": len(emails_list),
            "emails": emails_list,
        }
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def download(
    config: dict,
    uid: str,
    alias_or_email: Optional[str] = None,
    filename: Optional[str] = None,
    output_dir: Optional[str] = None,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Download attachments from an email.

    Returns:
        Dict with downloaded file paths.
    """
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout)

    try:
        status, msg_data = mail.fetch(uid.encode(), "(RFC822)")
        if status != "OK":
            return {"status": "error", "error": "fetch_failed", "uid": uid}

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                attachments = _extract_attachments(msg)

                if not attachments:
                    return {
                        "status": "ok",
                        "uid": uid,
                        "downloaded": [],
                        "message": "邮件没有附件",
                    }

                # Set output directory
                out_dir = Path(output_dir) if output_dir else Path.cwd()
                out_dir.mkdir(parents=True, exist_ok=True)

                downloaded = []
                for part in msg.walk():
                    disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" not in disposition:
                        continue

                    att_filename = part.get_filename()
                    if not att_filename:
                        continue
                    att_filename = _decode_header_value(att_filename)

                    # Override filename if specified and only one attachment
                    if filename and len(attachments) == 1:
                        att_filename = filename

                    # Sanitize filename
                    att_filename = att_filename.replace("/", "_").replace("\\", "_")
                    filepath = out_dir / att_filename

                    payload = part.get_payload(decode=True)
                    if payload:
                        filepath.write_bytes(payload)
                        downloaded.append(str(filepath))
                        logger.info("已下载: %s (%d bytes)", filepath, len(payload))

                return {
                    "status": "ok",
                    "uid": uid,
                    "downloaded": downloaded,
                }

        return {"status": "error", "error": "not_found", "uid": uid}
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def mark_read(
    config: dict,
    uids: list[str],
    alias_or_email: Optional[str] = None,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Mark emails as read (add \\Seen flag)."""
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout, readonly=False)

    try:
        marked = []
        for uid in uids:
            status, _ = mail.store(uid.encode(), "+FLAGS", "\\Seen")
            if status == "OK":
                marked.append(uid)
            else:
                logger.warning("标记已读失败: UID %s", uid)

        return {
            "status": "ok",
            "marked_read": marked,
            "count": len(marked),
        }
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def mark_unread(
    config: dict,
    uids: list[str],
    alias_or_email: Optional[str] = None,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Mark emails as unread (remove \\Seen flag)."""
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout, readonly=False)

    try:
        marked = []
        for uid in uids:
            status, _ = mail.store(uid.encode(), "-FLAGS", "\\Seen")
            if status == "OK":
                marked.append(uid)
            else:
                logger.warning("标记未读失败: UID %s", uid)

        return {
            "status": "ok",
            "marked_unread": marked,
            "count": len(marked),
        }
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def list_mailboxes(
    config: dict,
    alias_or_email: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """List all available mailboxes/folders."""
    account = resolve_account(config, alias_or_email)
    password = retrieve_password(
        account["alias"], account["email"], account["credential_backend"]
    )

    mail = _connect_imap(
        account["imap_host"], account["imap_port"],
        account["imap_ssl"], timeout,
    )
    mail.login(account["email"], password)

    try:
        status, folders = mail.list()
        if status != "OK":
            return {"status": "error", "error": "list_failed"}

        mailbox_list = []
        for folder in folders:
            if isinstance(folder, bytes):
                folder = folder.decode()
            # Parse: (\\HasNoChildren) "/" "INBOX"
            parts = folder.split(' "/" ')
            if len(parts) >= 2:
                name = parts[-1].strip('"')
                flags = parts[0].strip()
                mailbox_list.append({"name": name, "flags": flags})
            else:
                mailbox_list.append({"name": folder, "flags": ""})

        return {
            "status": "ok",
            "account": account["alias"],
            "mailboxes": mailbox_list,
        }
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def get_message_headers_for_reply(
    config: dict,
    uid: str,
    alias_or_email: Optional[str] = None,
    mailbox: str = DEFAULT_MAILBOX,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[dict[str, str]]:
    """Fetch message-id and references for reply threading.

    Returns:
        Dict with message_id, references, from, subject or None.
    """
    mail, account = _open_mailbox(config, alias_or_email, mailbox, timeout)

    try:
        status, msg_data = mail.fetch(
            uid.encode(),
            "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES IN-REPLY-TO FROM SUBJECT)])"
        )
        if status != "OK":
            return None

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                return {
                    "message_id": msg.get("Message-ID", ""),
                    "references": msg.get("References", ""),
                    "in_reply_to": msg.get("In-Reply-To", ""),
                    "from": _decode_header_value(msg.get("From", "")),
                    "subject": _decode_header_value(msg.get("Subject", "")),
                }

        return None
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass
