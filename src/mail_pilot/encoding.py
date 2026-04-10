"""Chinese email encoding utilities (RFC 2047, RFC 2231)."""

from __future__ import annotations

from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
import urllib.parse


def encode_subject(subject: str) -> str:
    """Encode email subject with RFC 2047 for non-ASCII characters.

    Args:
        subject: Raw subject string (may contain Chinese characters).

    Returns:
        Encoded subject string safe for email headers.
    """
    # If pure ASCII, no encoding needed
    try:
        subject.encode("ascii")
        return subject
    except UnicodeEncodeError:
        return str(Header(subject, "utf-8"))


def encode_address(name: str | None, email: str) -> str:
    """Encode a From/To/Cc address with RFC 2047 for non-ASCII names.

    Args:
        name: Display name (may be None or contain Chinese).
        email: Email address.

    Returns:
        Formatted address string like "Name <email@x.com>".
    """
    if not name:
        return email
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        name = str(Header(name, "utf-8"))
    return formataddr((name, email))


def encode_attachment_filename(filename: str) -> str:
    """Encode attachment filename with RFC 2231 for non-ASCII characters.

    Args:
        filename: Original filename (may contain Chinese).

    Returns:
        Encoded filename parameter string for Content-Disposition header.
    """
    try:
        filename.encode("ascii")
        return f'filename="{filename}"'
    except UnicodeEncodeError:
        encoded = urllib.parse.quote(filename, safe="")
        return f"filename*=utf-8''{encoded}"


def make_email_message(
    subject: str,
    body: str,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    reply_to: str | None = None,
    html: bool = False,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> MIMEText:
    """Construct a properly encoded email message.

    Args:
        subject: Email subject (may contain Chinese).
        body: Email body text.
        from_addr: Sender email address.
        to_addrs: List of To recipients.
        cc_addrs: List of CC recipients.
        bcc_addrs: List of BCC recipients (not included in headers).
        reply_to: Reply-To address.
        html: Whether body is HTML.
        in_reply_to: Message-ID being replied to (for threading).
        references: References header (for threading).

    Returns:
        MIMEText message ready to send.
    """
    subtype = "html" if html else "plain"
    msg = MIMEText(body, _subtype=subtype, _charset="utf-8")

    msg["Subject"] = encode_subject(subject)
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)

    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)

    if reply_to:
        msg["Reply-To"] = reply_to

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to

    if references:
        msg["References"] = references

    return msg
