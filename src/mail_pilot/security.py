"""Security utilities: path validation and input sanitization."""

from __future__ import annotations

import os
from pathlib import Path

# Default allowed directories for attachments
DEFAULT_ALLOWED_DIRS: list[str] = [
    os.getcwd(),
    str(Path.home()),
    str(Path.home() / "Downloads"),
    str(Path.home() / "Desktop"),
    str(Path.home() / "Documents"),
    "/tmp",
]


def validate_attachment_path(
    filepath: str,
    allowed_dirs: list[str] | None = None,
) -> Path:
    """Validate that an attachment path is within allowed directories.

    Args:
        filepath: Path to the attachment file.
        allowed_dirs: List of allowed base directories. Defaults to DEFAULT_ALLOWED_DIRS.

    Returns:
        Resolved absolute Path.

    Raises:
        ValueError: Path is outside allowed directories or does not exist.
    """
    if allowed_dirs is None:
        allowed_dirs = DEFAULT_ALLOWED_DIRS

    path = Path(filepath).resolve()

    # Check existence
    if not path.exists():
        raise ValueError(f"附件文件不存在: {filepath}")
    if not path.is_file():
        raise ValueError(f"路径不是文件: {filepath}")

    # Check allowed directories
    allowed_resolved = [Path(d).resolve() for d in allowed_dirs]
    if not any(str(path).startswith(str(d)) for d in allowed_resolved):
        raise ValueError(
            f"附件路径不在白名单内: {filepath}\n"
            f"允许的目录: {[str(d) for d in allowed_resolved]}"
        )

    return path


def sanitize_email(email: str) -> str:
    """Basic email address sanitization.

    Strips whitespace and lowercases the domain portion.
    """
    email = email.strip()
    if "@" not in email:
        raise ValueError(f"无效的邮箱地址: {email}")
    local, domain = email.rsplit("@", 1)
    return f"{local}@{domain.lower()}"


def sanitize_alias(alias: str) -> str:
    """Sanitize an account alias.

    Only allows alphanumeric, underscore, hyphen, and dot characters.
    """
    alias = alias.strip()
    if not alias:
        raise ValueError("别名不能为空")
    if not all(c.isalnum() or c in "_-." for c in alias):
        raise ValueError(f"别名包含非法字符: {alias}（仅允许字母、数字、_、-、.）")
    return alias


def validate_subject(subject: str) -> str:
    """Validate email subject line."""
    subject = subject.strip()
    if not subject:
        raise ValueError("邮件主题不能为空")
    if len(subject.encode("utf-8")) > 998:
        raise ValueError("邮件主题过长（RFC 5322 限制 998 字节）")
    return subject


def check_attachment_size(filepath: str, max_bytes: int = 25 * 1024 * 1024) -> None:
    """Check that a single attachment does not exceed size limit.

    Args:
        filepath: Path to the file.
        max_bytes: Maximum allowed size in bytes (default 25 MB).
    """
    size = os.path.getsize(filepath)
    if size > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        raise ValueError(
            f"附件超过大小限制: {actual_mb:.1f} MB > {max_mb:.0f} MB\n"
            f"文件: {filepath}"
        )


def check_total_size(filepaths: list[str], max_bytes: int = 50 * 1024 * 1024) -> None:
    """Check that total size of all attachments does not exceed limit.

    Args:
        filepaths: List of file paths.
        max_bytes: Maximum total size in bytes (default 50 MB).
    """
    total = sum(os.path.getsize(f) for f in filepaths)
    if total > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = total / (1024 * 1024)
        raise ValueError(
            f"附件总大小超过限制: {actual_mb:.1f} MB > {max_mb:.0f} MB"
        )
