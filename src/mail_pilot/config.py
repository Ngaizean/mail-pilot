"""Account configuration management: accounts.json with version migration."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mail_pilot.credentials import delete_password, get_backend
from mail_pilot.presets import detect_provider

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "mail-pilot"
CONFIG_PATH = CONFIG_DIR / "accounts.json"

CURRENT_VERSION = 1


def _default_config() -> dict[str, Any]:
    """Return a blank config structure."""
    return {
        "version": CURRENT_VERSION,
        "default_account": "",
        "accounts": [],
    }


def load_config() -> dict[str, Any]:
    """Load accounts.json, creating it if missing.

    Returns:
        Parsed config dict.
    """
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = _default_config()
        save_config(config)
        return config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Run migrations if needed
    version = config.get("version", 0)
    if version < CURRENT_VERSION:
        config = _migrate(config, version)
        save_config(config)

    return config


def save_config(config: dict[str, Any]) -> None:
    """Write config to accounts.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config["version"] = CURRENT_VERSION
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _migrate(config: dict[str, Any], from_version: int) -> dict[str, Any]:
    """Run migration chain from from_version to CURRENT_VERSION."""
    # Backup before migrating
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = CONFIG_PATH.with_name(f"accounts.json.bak.{timestamp}")
    shutil.copy2(CONFIG_PATH, backup_path)
    logger.info("配置已备份到: %s", backup_path)

    # Migration chain: v0 → v1
    if from_version < 1:
        config = _migrate_v0_to_v1(config)

    config["version"] = CURRENT_VERSION
    return config


def _migrate_v0_to_v1(config: dict[str, Any]) -> dict[str, Any]:
    """Migrate from unversioned config to v1."""
    if "version" not in config:
        config["version"] = 1
    if "default_account" not in config:
        config["default_account"] = ""
    if "accounts" not in config:
        config["accounts"] = []
    return config


def add_account(
    alias: str,
    email: str,
    password: str,
    provider_override: dict[str, Any] | None = None,
    set_default: bool = False,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """Add a new email account.

    Args:
        alias: Account alias.
        email: Email address.
        password: Password or authorization code.
        provider_override: Override provider settings. Auto-detects if None.
        set_default: Set as default account.
        passphrase: Required when Fernet backend is used.

    Returns:
        Updated config dict.
    """
    from mail_pilot.security import sanitize_alias, sanitize_email
    from mail_pilot.credentials import store_password

    alias = sanitize_alias(alias)
    email = sanitize_email(email)

    config = load_config()

    # Check for duplicate alias
    for acc in config["accounts"]:
        if acc["alias"] == alias:
            raise ValueError(f"别名已存在: {alias}")
        if acc["email"] == email:
            raise ValueError(f"邮箱已配置: {email}（别名: {acc['alias']}）")

    # Detect provider
    if provider_override:
        provider = provider_override
        provider_name = provider_override.get("provider", "custom")
    else:
        preset = detect_provider(email)
        if preset is None:
            raise ValueError(
                f"无法识别邮箱服务商: {email}\n"
                f"请使用 --provider 手动指定"
            )
        provider = preset
        provider_name = email.rsplit("@", 1)[1].lower()

    # Detect and store credentials
    backend = get_backend()
    store_password(alias, email, password, backend=backend, passphrase=passphrase)

    # Build account entry
    account = {
        "alias": alias,
        "email": email,
        "provider": provider_name,
        "smtp_host": provider["smtp_host"],
        "smtp_port": provider["smtp_port"],
        "smtp_ssl": provider.get("smtp_ssl", True),
        "imap_host": provider["imap_host"],
        "imap_port": provider["imap_port"],
        "imap_ssl": provider.get("imap_ssl", True),
        "credential_backend": backend,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    config["accounts"].append(account)

    if set_default or not config["default_account"]:
        config["default_account"] = alias

    save_config(config)
    logger.info("账号已添加: %s (%s)", alias, email)
    return config


def remove_account(alias: str) -> dict[str, Any]:
    """Remove an account and its stored credentials.

    Args:
        alias: Account alias to remove.

    Returns:
        Updated config dict.
    """
    config = load_config()

    account = get_account(config, alias)
    if account is None:
        raise ValueError(f"账号不存在: {alias}")

    # Delete stored credentials
    delete_password(account["alias"], account["email"], account["credential_backend"])

    # Remove from config
    config["accounts"] = [a for a in config["accounts"] if a["alias"] != alias]

    # Update default if needed
    if config["default_account"] == alias:
        config["default_account"] = config["accounts"][0]["alias"] if config["accounts"] else ""

    save_config(config)
    logger.info("账号已删除: %s", alias)
    return config


def get_account(config: dict[str, Any], alias_or_email: str) -> dict[str, Any] | None:
    """Look up an account by alias or email address.

    Args:
        config: Loaded config dict.
        alias_or_email: Account alias or email address.

    Returns:
        Account dict or None.
    """
    for acc in config["accounts"]:
        if acc["alias"] == alias_or_email or acc["email"] == alias_or_email:
            return acc
    return None


def get_default_account(config: dict[str, Any]) -> dict[str, Any] | None:
    """Get the default account."""
    default = config.get("default_account", "")
    if default:
        return get_account(config, default)
    # Fallback to first account
    if config["accounts"]:
        return config["accounts"][0]
    return None


def resolve_account(config: dict[str, Any], alias_or_email: str | None = None) -> dict[str, Any]:
    """Resolve account from alias/email or fall back to default.

    Args:
        config: Loaded config dict.
        alias_or_email: Optional account alias or email.

    Returns:
        Account dict.

    Raises:
        ValueError: No account found.
    """
    if alias_or_email:
        acc = get_account(config, alias_or_email)
        if acc is None:
            raise ValueError(f"账号不存在: {alias_or_email}")
        return acc

    acc = get_default_account(config)
    if acc is None:
        raise ValueError("没有配置任何账号，请先运行: python -m mail_pilot setup")
    return acc


def list_accounts(config: dict[str, Any]) -> list[dict[str, str]]:
    """List all accounts (without credentials).

    Returns:
        List of account summary dicts.
    """
    result = []
    for acc in config["accounts"]:
        result.append({
            "alias": acc["alias"],
            "email": acc["email"],
            "provider": acc["provider"],
            "backend": acc["credential_backend"],
            "is_default": acc["alias"] == config.get("default_account"),
        })
    return result
