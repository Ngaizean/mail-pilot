"""SMTP client with SSL/STARTTLS, retry, timeout, attachments, and dry-run."""

from __future__ import annotations

import logging
import os
import smtplib
import time
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders as email_encoders
from pathlib import Path
from typing import Any

from mail_pilot.config import resolve_account
from mail_pilot.credentials import retrieve_password
from mail_pilot.dedup import is_duplicate, mark_sent
from mail_pilot.encoding import (
    encode_attachment_filename,
    encode_subject,
    make_email_message,
)
from mail_pilot.security import (
    check_attachment_size,
    check_total_size,
    validate_attachment_path,
    validate_subject,
)

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds, exponential backoff base


def _connect_smtp(
    host: str,
    port: int,
    use_ssl: bool,
    timeout: int,
) -> smtplib.SMTP | smtplib.SMTP_SSL:
    """Establish SMTP connection with SSL or STARTTLS.

    Args:
        host: SMTP server hostname.
        port: SMTP server port.
        use_ssl: Use direct SSL (True) or STARTTLS (False).
        timeout: Connection timeout in seconds.

    Returns:
        Connected SMTP instance.
    """
    logger.debug("连接 SMTP: %s:%d (SSL=%s)", host, port, use_ssl)

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()

    return server


def _add_attachments(msg: MIMEMultipart, attachments: list[str]) -> None:
    """Add file attachments to a message.

    Args:
        msg: MIMEMultipart message.
        attachments: List of file paths.
    """
    paths = []
    for filepath in attachments:
        path = validate_attachment_path(filepath)
        check_attachment_size(str(path))
        paths.append(str(path))

    check_total_size(paths)

    for path_str in paths:
        path = Path(path_str)
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        email_encoders.encode_base64(part)
        filename_param = encode_attachment_filename(path.name)
        part.add_header("Content-Disposition", f"attachment; {filename_param}")
        msg.attach(part)
        logger.debug("附件已添加: %s (%d bytes)", path.name, path.stat().st_size)


def _send_with_retry(
    server: smtplib.SMTP | smtplib.SMTP_SSL,
    from_addr: str,
    to_addrs: list[str],
    msg: MIMEMultipart | MIMEText,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_RETRY_DELAY,
) -> dict[str, Any]:
    """Send email with exponential backoff retry.

    Returns:
        Result dict with status and details.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            server.send_message(msg, from_addr=from_addr, to_addrs=to_addrs)
            return {"status": "sent", "attempts": attempt}
        except smtplib.SMTPAuthenticationError as e:
            return {
                "status": "error",
                "error": "auth_failed",
                "detail": str(e),
                "attempts": attempt,
            }
        except (smtplib.SMTPHeloError, smtplib.SMTPNotSupportedError) as e:
            # Server refused our HELO/EHLO or unsupported command — don't retry
            return {
                "status": "error",
                "error": type(e).__name__,
                "detail": str(e),
                "attempts": attempt,
            }
        except smtplib.SMTPResponseException as e:
            if 400 <= e.smtp_code < 500:
                # Transient error — retry
                last_error = e
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "SMTP %d 临时错误，第 %d/%d 次重试，等待 %.1fs",
                    e.smtp_code, attempt, max_retries, delay,
                )
                time.sleep(delay)
            else:
                # Permanent error — don't retry
                return {
                    "status": "error",
                    "error": "permanent",
                    "smtp_code": e.smtp_code,
                    "detail": str(e),
                    "attempts": attempt,
                }
        except (TimeoutError, ConnectionError, OSError) as e:
            last_error = e
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "网络错误，第 %d/%d 次重试，等待 %.1fs",
                attempt, max_retries, delay,
            )
            time.sleep(delay)

    return {
        "status": "error",
        "error": "max_retries_exceeded",
        "detail": str(last_error),
        "attempts": max_retries,
    }


def send_email(
    config: dict,
    alias_or_email: str | None = None,
    to: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str = "",
    body: str = "",
    body_file: str | None = None,
    html: bool = False,
    attachments: list[str] | None = None,
    reply_to: str | None = None,
    dry_run: bool = False,
    dedup: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict[str, Any]:
    """Send an email.

    Args:
        config: Loaded config dict.
        alias_or_email: Sender account alias or email. Uses default if None.
        to: List of To recipients.
        cc: List of CC recipients.
        bcc: List of BCC recipients.
        subject: Email subject.
        body: Email body text.
        body_file: Read body from file (overrides body).
        html: Whether body is HTML.
        attachments: List of attachment file paths.
        reply_to: Reply-To address.
        dry_run: Preview without sending.
        dedup: Enable date-locked dedup.
        timeout: SMTP connection timeout.
        max_retries: Maximum retry count.
        in_reply_to: Message-ID for threading.
        references: References header for threading.

    Returns:
        Result dict with status and details.
    """
    if not to:
        return {"status": "error", "error": "missing_recipients", "detail": "未指定收件人"}

    # Resolve account
    account = resolve_account(config, alias_or_email)
    from_addr = account["email"]

    # Read body from file if specified
    if body_file:
        with open(body_file, "r", encoding="utf-8") as f:
            body = f.read()

    # Validate
    subject = validate_subject(subject)

    # Check dedup
    if dedup:
        primary_recipient = to[0]
        if is_duplicate(from_addr, primary_recipient, subject):
            logger.info("邮件已去重跳过: %s → %s / %s", from_addr, primary_recipient, subject)
            return {
                "status": "deduplicated",
                "from": from_addr,
                "to": primary_recipient,
                "subject": subject,
            }

    # Build message
    has_attachments = attachments and len(attachments) > 0

    if has_attachments:
        msg = MIMEMultipart()
        text_part = MIMEText(body, _subtype="html" if html else "plain", _charset="utf-8")
        msg.attach(text_part)
        _add_attachments(msg, attachments)
        # Set headers
        msg["Subject"] = encode_subject(subject)
        msg["From"] = from_addr
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references
    else:
        msg = make_email_message(
            subject=subject,
            body=body,
            from_addr=from_addr,
            to_addrs=to,
            cc_addrs=cc,
            bcc_addrs=bcc,
            reply_to=reply_to,
            html=html,
            in_reply_to=in_reply_to,
            references=references,
        )

    # Collect all recipients for SMTP envelope
    all_recipients = list(to)
    if cc:
        all_recipients.extend(cc)
    if bcc:
        all_recipients.extend(bcc)

    # Dry-run: return constructed message without sending
    if dry_run:
        return {
            "status": "dry_run",
            "from": from_addr,
            "to": to,
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body_length": len(body),
            "attachments": [Path(a).name for a in (attachments or [])],
            "html": html,
            "message_preview": body[:200] + ("..." if len(body) > 200 else ""),
        }

    # Connect and send
    password = retrieve_password(
        account["alias"], account["email"], account["credential_backend"]
    )

    try:
        server = _connect_smtp(
            account["smtp_host"],
            account["smtp_port"],
            account["smtp_ssl"],
            timeout,
        )
        server.login(account["email"], password)

        result = _send_with_retry(server, from_addr, all_recipients, msg, max_retries)

        try:
            server.quit()
        except Exception:
            pass

    except smtplib.SMTPAuthenticationError as e:
        return {
            "status": "error",
            "error": "auth_failed",
            "detail": f"SMTP 认证失败: {e}",
            "account": account["alias"],
        }
    except (TimeoutError, ConnectionError, OSError) as e:
        return {
            "status": "error",
            "error": "connection_failed",
            "detail": f"连接 SMTP 服务器失败: {e}",
        }

    # Mark as sent for dedup
    if dedup and result["status"] == "sent":
        mark_sent(from_addr, to[0], subject)

    # Enrich result
    result["from"] = from_addr
    result["to"] = to
    result["subject"] = subject

    return result


def test_connection(
    config: dict,
    alias_or_email: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Test SMTP connection for an account.

    Returns:
        Result dict with connection status.
    """
    account = resolve_account(config, alias_or_email)
    password = retrieve_password(
        account["alias"], account["email"], account["credential_backend"]
    )

    try:
        server = _connect_smtp(
            account["smtp_host"],
            account["smtp_port"],
            account["smtp_ssl"],
            timeout,
        )
        server.login(account["email"], password)
        server.quit()

        return {
            "status": "ok",
            "account": account["alias"],
            "email": account["email"],
            "smtp": f"{account['smtp_host']}:{account['smtp_port']}",
        }
    except smtplib.SMTPAuthenticationError as e:
        return {
            "status": "error",
            "error": "auth_failed",
            "account": account["alias"],
            "detail": f"认证失败: {e}",
        }
    except (TimeoutError, ConnectionError, OSError) as e:
        return {
            "status": "error",
            "error": "connection_failed",
            "account": account["alias"],
            "detail": f"连接失败: {e}",
        }
