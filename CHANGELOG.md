# Changelog

## [0.1.0] - 2026-04-10

### Added

**M1 - Core Sending**
- Interactive setup wizard (`python -m mail_pilot setup`) with auto-detection of 9 email providers
- SMTP sending with SSL/STARTTLS, CC/BCC, HTML, attachments
- Three credential backends: macOS Keychain, Linux keyring, Fernet encrypted fallback
- Exponential backoff retry (3 attempts) on transient SMTP errors
- Date-locked deduplication via SHA256 sentinel files
- Dry-run mode for email preview
- `--verbose` / `--quiet` output control

**M2 - IMAP Receiving**
- `check` — list recent emails with UID, from, subject, date
- `fetch` — retrieve full email (headers + body + attachment list)
- `search` — filter by from/subject/since/before/unseen
- `download` — save attachments to disk
- `mark-read` / `mark-unread` — toggle email flags
- `list-mailboxes` — list all IMAP folders
- `reply` — reply with In-Reply-To / References threading headers
- `forward` — forward with quoted original content

**M3 - Templates & Testing**
- Jinja2 template engine with built-in variables (date, recipient, sender, etc.)
- Example templates (daily_reminder.md, weekly_report.md)
- RFC 2047 Chinese subject encoding, RFC 2231 attachment filename encoding
- 95 unit tests (presets, security, encoding, dedup, template, config, smtp, cli)

**M4 - Packaging & CI**
- pyproject.toml with optional dependency groups
- GitHub Actions CI workflow (multi-OS, multi-Python matrix)
- SKILL.md for OpenClaw / Claude Code AI agent integration
- Complete README with data flow diagrams, FAQ, architecture

### Security
- Passwords never stored in config files — Keychain / keyring / Fernet only
- macOS Keychain: password passed via stdin pipe, not CLI arguments
- Fernet: per-user random salt, PBKDF2 with 200k iterations
- Attachment path whitelist validation
- Body file path validation
