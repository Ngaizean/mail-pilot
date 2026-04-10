"""Email provider presets for common Chinese and international providers."""

from __future__ import annotations

PROVIDERS: dict[str, dict[str, object]] = {
    "163.com": {
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "smtp_ssl": True,
        "imap_host": "imap.163.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需授权码（非登录密码），在网页版邮箱设置中获取",
    },
    "vip.163.com": {
        "smtp_host": "smtp.vip.163.com",
        "smtp_port": 465,
        "smtp_ssl": True,
        "imap_host": "imap.vip.163.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需授权码",
    },
    "126.com": {
        "smtp_host": "smtp.126.com",
        "smtp_port": 465,
        "smtp_ssl": True,
        "imap_host": "imap.126.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需授权码",
    },
    "yeah.net": {
        "smtp_host": "smtp.yeah.net",
        "smtp_port": 465,
        "smtp_ssl": True,
        "imap_host": "imap.yeah.net",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需授权码",
    },
    "qq.com": {
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "smtp_ssl": True,
        "imap_host": "imap.qq.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需授权码",
    },
    "gmail.com": {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_ssl": False,  # STARTTLS
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需 App Password（非登录密码），在 Google 账号安全设置中生成",
    },
    "outlook.com": {
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "smtp_ssl": False,  # STARTTLS
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需 App Password 或 OAuth2",
    },
    "hotmail.com": {
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "同 Outlook",
    },
    "yahoo.com": {
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 465,
        "smtp_ssl": True,
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "imap_ssl": True,
        "note": "需 App Password",
    },
}


def detect_provider(email: str) -> dict[str, object] | None:
    """Detect email provider from email address domain.

    Args:
        email: Full email address (e.g. "user@163.com")

    Returns:
        Provider preset dict or None if unknown.
    """
    if "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].lower()
    return PROVIDERS.get(domain)


def list_providers() -> list[dict[str, str]]:
    """Return all known providers with display info."""
    results = []
    for domain, preset in PROVIDERS.items():
        results.append({
            "domain": domain,
            "smtp": f"{preset['smtp_host']}:{preset['smtp_port']}",
            "imap": f"{preset['imap_host']}:{preset['imap_port']}",
            "note": preset.get("note", ""),
        })
    return results
