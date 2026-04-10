"""Jinja2 template engine for email body generation (optional dependency)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _check_jinja2() -> None:
    """Verify Jinja2 is installed."""
    try:
        import jinja2  # noqa: F401
    except ImportError:
        raise ImportError(
            "Jinja2 未安装。请运行: pip install jinja2\n"
            "或在 pyproject.toml 中添加: mail-pilot[template]"
        )


def build_template_context(
    recipient: str = "",
    sender: str = "",
    subject: str = "",
    account_alias: str = "",
    extra_vars: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the template context with built-in and user variables.

    Args:
        recipient: Recipient email address.
        sender: Sender email address.
        subject: Email subject.
        account_alias: Current account alias.
        extra_vars: User-provided variables via --var.

    Returns:
        Context dict for template rendering.
    """
    context = {
        "date": date.today().isoformat(),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": recipient,
        "sender": sender,
        "subject": subject,
        "account_alias": account_alias,
    }

    if extra_vars:
        # User vars override built-in vars
        context.update(extra_vars)

    return context


def parse_var_args(var_list: list[str] | None) -> dict[str, str]:
    """Parse --var key=value arguments into a dict.

    Args:
        var_list: List of "key=value" strings.

    Returns:
        Dict of parsed variables.

    Raises:
        ValueError: If a var is not in key=value format.
    """
    if not var_list:
        return {}

    result = {}
    for item in var_list:
        if "=" not in item:
            raise ValueError(f"变量格式错误: {item}（应为 key=value）")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"变量名不能为空: {item}")
        result[key] = value

    return result


def render_template(
    template_path: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template with the given context.

    Args:
        template_path: Path to the Jinja2 template file.
        context: Template context dict.

    Returns:
        Rendered string.
    """
    _check_jinja2()

    from jinja2 import Environment, FileSystemLoader, TemplateNotFound

    path = Path(template_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    env = Environment(
        loader=FileSystemLoader(str(path.parent)),
        keep_trailing_newline=True,
    )

    try:
        template = env.get_template(path.name)
    except TemplateNotFound:
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    rendered = template.render(**context)
    logger.debug("模板渲染完成: %s (%d bytes)", template_path, len(rendered))
    return rendered


def render_from_string(
    template_str: str,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template from a string.

    Args:
        template_str: Jinja2 template string.
        context: Template context dict.

    Returns:
        Rendered string.
    """
    _check_jinja2()

    from jinja2 import Environment

    env = Environment(keep_trailing_newline=True)
    template = env.from_string(template_str)
    return template.render(**context)
