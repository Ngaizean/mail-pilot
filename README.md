# 🛩️ Mail Pilot

A secure, zero-dependency email skill for AI agents (OpenClaw / Claude Code). Send and receive email via IMAP/SMTP with native Keychain credential storage, multi-account switching, deduplication, and first-class Chinese email provider support.

## Features

- 🔐 **Native Keychain storage** — macOS Security.framework / Linux secret-storage, passwords never touch disk
- 🪶 **Zero-dependency core** — Python stdlib `smtplib` + `imaplib`, optional Jinja2 for templates
- 🎯 **One-command setup** — `python setup.py` interactive wizard, auto-detects email provider
- 🔄 **Multi-account `--from`** — Switch sender freely without editing config files
- 🛡️ **Built-in dedup** — `--dedup` date-locked sending prevents duplicate emails from cron catch-up
- 🇨🇳 **Chinese providers first** — 163.com / QQ.com / 126.com / yeah.net built-in presets
- 📋 **Jinja2 templates** — Optional template engine for recurring emails
- ✅ **Transparent metadata** — All credentials and config paths properly declared

## Quick Start

```bash
git clone https://github.com/Ngaizean/mail-pilot.git
cd mail-pilot
pip install -e .
python setup.py          # interactive account setup
python -m mail_pilot send --to someone@example.com --subject "Hello" --body "World"
```

## License

MIT
