"""Credential storage backends: macOS Keychain, Linux keyring, Fernet fallback."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

CREDENTIALS_DIR = Path.home() / ".config" / "mail-pilot" / "credentials"


class CredentialError(Exception):
    """Raised when credential operations fail."""


def get_backend() -> str:
    """Detect the best available credential backend.

    Returns:
        One of: "keychain", "keyring", "fernet".
    """
    if sys.platform == "darwin":
        # Check if `security` CLI is available
        try:
            subprocess.run(
                ["security", "authorizationdb", "read", "system.keychain.modify"],
                capture_output=True, timeout=5,
            )
            return "keychain"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("macOS Keychain 不可用，降级到 Fernet")

    if sys.platform.startswith("linux"):
        try:
            import keyring  # noqa: F401
            # Try to access the backend to verify it's functional
            kr_backend = __import__("keyring").get_keyring()
            if kr_backend and kr_backend.name != "fail.Keyring":
                return "keyring"
        except ImportError:
            logger.warning("keyring 库未安装，降级到 Fernet")
        except Exception:
            logger.warning("keyring 后端不可用，降级到 Fernet")

    return "fernet"


# ── macOS Keychain ──────────────────────────────────────────────────────────

def keychain_set(service: str, account: str, password: str) -> None:
    """Store password in macOS Keychain.

    Args:
        service: Keychain service name (e.g. "com.mail-pilot.163").
        account: Account name (email address).
        password: Password to store.
    """
    # Delete existing entry first (avoid duplicate key error)
    subprocess.run(
        ["security", "delete-generic-password", "-a", account, "-s", service],
        capture_output=True,
    )

    # Store via stdin (not CLI args, to avoid exposing in `ps`)
    subprocess.run(
        ["security", "add-generic-password",
         "-a", account, "-s", service, "-w"],
        input=password.encode(),
        check=True,
    )
    logger.info("密码已存入 Keychain: %s / %s", service, account)


def keychain_get(service: str, account: str) -> str:
    """Retrieve password from macOS Keychain.

    Args:
        service: Keychain service name.
        account: Account name (email address).

    Returns:
        Stored password string.
    """
    result = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def keychain_delete(service: str, account: str) -> None:
    """Delete password from macOS Keychain."""
    subprocess.run(
        ["security", "delete-generic-password", "-a", account, "-s", service],
        capture_output=True, check=True,
    )
    logger.info("密码已从 Keychain 删除: %s / %s", service, account)


# ── Fernet Encrypted File (Fallback) ────────────────────────────────────────

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a Fernet key from passphrase and salt."""
    import base64
    import hashlib
    return base64.urlsafe_b64encode(
        hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 200000)[:32]
    )


def fernet_set(alias: str, passphrase: str, password: str) -> None:
    """Store password using Fernet encryption with per-user random salt.

    Args:
        alias: Account alias (used for filename).
        passphrase: User-provided passphrase for key derivation.
        password: Password to encrypt and store.
    """
    from cryptography.fernet import Fernet

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate per-user random salt
    salt = os.urandom(32)
    (CREDENTIALS_DIR / f"{alias}.salt").write_bytes(salt)

    key = _derive_key(passphrase, salt)
    encrypted = Fernet(key).encrypt(password.encode())
    (CREDENTIALS_DIR / f"{alias}.enc").write_bytes(encrypted)
    logger.info("密码已加密存储: %s", alias)


def fernet_get(alias: str, passphrase: str) -> str:
    """Retrieve password from Fernet encrypted file.

    Args:
        alias: Account alias.
        passphrase: User-provided passphrase for key derivation.

    Returns:
        Decrypted password string.
    """
    from cryptography.fernet import Fernet, InvalidToken

    salt_path = CREDENTIALS_DIR / f"{alias}.salt"
    enc_path = CREDENTIALS_DIR / f"{alias}.enc"

    if not salt_path.exists() or not enc_path.exists():
        raise CredentialError(f"找不到加密凭据文件: {alias}")

    salt = salt_path.read_bytes()
    key = _derive_key(passphrase, salt)

    try:
        encrypted = enc_path.read_bytes()
        return Fernet(key).decrypt(encrypted).decode()
    except InvalidToken:
        raise CredentialError("解密失败：passphrase 不正确")


def fernet_delete(alias: str) -> None:
    """Delete Fernet encrypted credential files."""
    salt_path = CREDENTIALS_DIR / f"{alias}.salt"
    enc_path = CREDENTIALS_DIR / f"{alias}.enc"
    for p in (salt_path, enc_path):
        if p.exists():
            p.unlink()
    logger.info("加密凭据已删除: %s", alias)


# ── Linux keyring ────────────────────────────────────────────────────────────

def keyring_set(service: str, account: str, password: str) -> None:
    """Store password in system keyring (Linux)."""
    import keyring as kr
    kr.set_password(service, account, password)
    logger.info("密码已存入 keyring: %s / %s", service, account)


def keyring_get(service: str, account: str) -> str:
    """Retrieve password from system keyring."""
    import keyring as kr
    password = kr.get_password(service, account)
    if password is None:
        raise CredentialError(f"keyring 中未找到凭据: {service} / {account}")
    return password


def keyring_delete(service: str, account: str) -> None:
    """Delete password from system keyring."""
    import keyring as kr
    kr.delete_password(service, account)
    logger.info("密码已从 keyring 删除: %s / %s", service, account)


# ── Unified API ─────────────────────────────────────────────────────────────

def store_password(alias: str, email: str, password: str, backend: str | None = None, passphrase: str | None = None) -> str:
    """Store password using the specified or auto-detected backend.

    Args:
        alias: Account alias.
        email: Email address.
        password: Password to store.
        backend: Force specific backend ("keychain", "keyring", "fernet"). Auto-detected if None.
        passphrase: Required for Fernet backend.

    Returns:
        The backend name that was used.
    """
    if backend is None:
        backend = get_backend()

    service = f"com.mail-pilot.{alias}"

    if backend == "keychain":
        keychain_set(service, email, password)
    elif backend == "keyring":
        keyring_set(service, email, password)
    elif backend == "fernet":
        if not passphrase:
            raise CredentialError("Fernet 后端需要提供 passphrase")
        fernet_set(alias, passphrase, password)
    else:
        raise CredentialError(f"未知后端: {backend}")

    return backend


def retrieve_password(alias: str, email: str, backend: str, passphrase: str | None = None) -> str:
    """Retrieve password from the specified backend.

    Args:
        alias: Account alias.
        email: Email address.
        backend: Backend to use ("keychain", "keyring", "fernet").
        passphrase: Required for Fernet backend.

    Returns:
        The stored password.
    """
    service = f"com.mail-pilot.{alias}"

    if backend == "keychain":
        return keychain_get(service, email)
    elif backend == "keyring":
        return keyring_get(service, email)
    elif backend == "fernet":
        if not passphrase:
            raise CredentialError("Fernet 后端需要提供 passphrase")
        return fernet_get(alias, passphrase)
    else:
        raise CredentialError(f"未知后端: {backend}")


def delete_password(alias: str, email: str, backend: str) -> None:
    """Delete stored password.

    Args:
        alias: Account alias.
        email: Email address.
        backend: Backend to use.
    """
    service = f"com.mail-pilot.{alias}"

    if backend == "keychain":
        keychain_delete(service, email)
    elif backend == "keyring":
        keyring_delete(service, email)
    elif backend == "fernet":
        fernet_delete(alias)
    else:
        raise CredentialError(f"未知后端: {backend}")
