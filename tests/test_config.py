"""Tests for config module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from mail_pilot.config import (
    _default_config,
    load_config,
    save_config,
    get_account,
    get_default_account,
    resolve_account,
    list_accounts,
    add_account,
    remove_account,
    CURRENT_VERSION,
)


class TestDefaultConfig:
    def test_structure(self):
        cfg = _default_config()
        assert cfg["version"] == CURRENT_VERSION
        assert cfg["default_account"] == ""
        assert cfg["accounts"] == []


class TestLoadConfig:
    def test_creates_config_if_missing(self, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            cfg = load_config()
            assert cfg["version"] == CURRENT_VERSION
            assert cfg_path.exists()

    def test_loads_existing(self, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        data = {"version": 1, "default_account": "test", "accounts": [
            {"alias": "test", "email": "test@163.com", "provider": "163.com",
             "smtp_host": "smtp.163.com", "smtp_port": 465, "smtp_ssl": True,
             "imap_host": "imap.163.com", "imap_port": 993, "imap_ssl": True,
             "credential_backend": "keychain", "created_at": ""}
        ]}
        cfg_path.write_text(json.dumps(data))
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            cfg = load_config()
            assert cfg["default_account"] == "test"
            assert len(cfg["accounts"]) == 1

    def test_corrupted_json(self, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        cfg_path.write_text("{invalid json")
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            with pytest.raises(ValueError, match="配置文件损坏"):
                load_config()


class TestSaveConfig:
    def test_write_and_read(self, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            cfg = _default_config()
            cfg["default_account"] = "x"
            save_config(cfg)
            content = cfg_path.read_text()
            assert '"default_account": "x"' in content


class TestGetAccount:
    def test_find_by_alias(self):
        cfg = {"accounts": [{"alias": "163", "email": "a@163.com"}]}
        assert get_account(cfg, "163") is not None

    def test_find_by_email(self):
        cfg = {"accounts": [{"alias": "163", "email": "a@163.com"}]}
        assert get_account(cfg, "a@163.com") is not None

    def test_not_found(self):
        cfg = {"accounts": []}
        assert get_account(cfg, "x") is None


class TestGetDefaultAccount:
    def test_returns_default(self):
        cfg = {"default_account": "163", "accounts": [
            {"alias": "163", "email": "a@163.com"},
            {"alias": "qq", "email": "b@qq.com"},
        ]}
        acc = get_default_account(cfg)
        assert acc["alias"] == "163"

    def test_fallback_to_first(self):
        cfg = {"default_account": "", "accounts": [
            {"alias": "qq", "email": "b@qq.com"},
        ]}
        acc = get_default_account(cfg)
        assert acc["alias"] == "qq"

    def test_no_accounts(self):
        cfg = {"default_account": "", "accounts": []}
        assert get_default_account(cfg) is None


class TestResolveAccount:
    def test_by_alias(self):
        cfg = {"default_account": "163", "accounts": [
            {"alias": "163", "email": "a@163.com"},
        ]}
        assert resolve_account(cfg, "163")["alias"] == "163"

    def test_fallback_to_default(self):
        cfg = {"default_account": "163", "accounts": [
            {"alias": "163", "email": "a@163.com"},
        ]}
        assert resolve_account(cfg)["alias"] == "163"

    def test_not_found_raises(self):
        with pytest.raises(ValueError, match="账号不存在"):
            resolve_account({"default_account": "", "accounts": []}, "none")

    def test_no_accounts_raises(self):
        with pytest.raises(ValueError, match="没有配置任何账号"):
            resolve_account({"default_account": "", "accounts": []})


class TestListAccounts:
    def test_empty(self):
        assert list_accounts({"accounts": [], "default_account": ""}) == []

    def test_with_default(self):
        cfg = {"accounts": [
            {"alias": "163", "email": "a@163.com", "provider": "163.com", "credential_backend": "keychain"},
        ], "default_account": "163"}
        result = list_accounts(cfg)
        assert len(result) == 1
        assert result[0]["is_default"] is True

    def test_non_default(self):
        cfg = {"accounts": [
            {"alias": "qq", "email": "b@qq.com", "provider": "qq.com", "credential_backend": "keychain"},
        ], "default_account": "163"}
        result = list_accounts(cfg)
        assert result[0]["is_default"] is False


class TestAddAccount:
    @patch("mail_pilot.credentials.store_password")
    @patch("mail_pilot.config.get_backend", return_value="keychain")
    def test_add_success(self, mock_backend, mock_store, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            cfg = add_account("163", "user@163.com", "pass123", set_default=True)
            assert len(cfg["accounts"]) == 1
            assert cfg["accounts"][0]["alias"] == "163"
            assert cfg["default_account"] == "163"
            mock_store.assert_called_once()

    @patch("mail_pilot.credentials.store_password")
    @patch("mail_pilot.config.get_backend", return_value="keychain")
    def test_duplicate_alias_raises(self, mock_backend, mock_store, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            add_account("163", "user@163.com", "pass")
            with pytest.raises(ValueError, match="别名已存在"):
                add_account("163", "other@163.com", "pass2")

    @patch("mail_pilot.credentials.store_password")
    @patch("mail_pilot.config.get_backend", return_value="keychain")
    def test_unknown_provider_raises(self, mock_backend, mock_store, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            with pytest.raises(ValueError, match="无法识别邮箱服务商"):
                add_account("x", "user@unknown.xyz", "pass")


class TestRemoveAccount:
    @patch("mail_pilot.config.delete_password")
    @patch("mail_pilot.credentials.store_password")
    @patch("mail_pilot.config.get_backend", return_value="keychain")
    def test_remove_success(self, mock_backend, mock_store, mock_del, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            add_account("163", "user@163.com", "pass")
            cfg = remove_account("163")
            assert len(cfg["accounts"]) == 0
            assert cfg["default_account"] == ""
            mock_del.assert_called_once()

    def test_remove_nonexistent_raises(self, tmp_path):
        cfg_path = tmp_path / "accounts.json"
        with patch("mail_pilot.config.CONFIG_PATH", cfg_path), \
             patch("mail_pilot.config.CONFIG_DIR", tmp_path):
            load_config()  # create empty config
            with pytest.raises(ValueError, match="账号不存在"):
                remove_account("none")
