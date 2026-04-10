# Mail Pilot

A secure, zero-dependency email CLI for AI agents. Send and receive email via IMAP/SMTP with native Keychain credential storage, multi-account switching, deduplication, and first-class Chinese email provider support.

## Features

- **Native Keychain storage** -- macOS Keychain / Linux libsecret, passwords never touch disk
- **Zero-dependency core** -- Python stdlib `smtplib` + `imaplib`, optional Jinja2 for templates
- **One-command setup** -- `python -m mail_pilot setup` interactive wizard, auto-detects provider
- **Multi-account** -- `--from <alias>` switches sender without editing config
- **Built-in dedup** -- `--dedup` date-locked sending prevents duplicate emails from cron catch-up
- **Chinese providers first** -- 163.com / QQ.com / 126.com / yeah.net built-in presets
- **Dry-run mode** -- `--dry-run` previews email without sending
- **Reply & Forward** -- `reply <uid>` and `forward <uid>` with proper headers

## Prerequisites

- Python 3.10+
- macOS 12+ (Keychain) or Ubuntu 20.04+ / Debian 11+ (libsecret)
- For Chinese email providers: SMTP authorization code (not login password)

## Installation

```bash
git clone https://github.com/Ngaizean/mail-pilot.git
cd mail-pilot
pip install -e .
```

## Quick Start

```bash
# 1. Add an account (interactive wizard)
python -m mail_pilot setup

# 2. Send an email
python -m mail_pilot send --to someone@example.com --subject "Hello" --body "World"

# 3. Check inbox
python -m mail_pilot check --limit 5

# 4. Search emails
python -m mail_pilot search --from boss@company.com --since 2h
```

## Usage

### Account Management

```bash
# Interactive setup wizard (auto-detects provider)
python -m mail_pilot setup

# List all configured accounts
python -m mail_pilot list-accounts

# Test connection for an account
python -m mail_pilot test-connection --account 163

# Remove an account
python -m mail_pilot remove-account 163
```

### Sending

```bash
# Basic send
python -m mail_pilot send --to user@example.com --subject "Test" --body "Hello"

# Multi-recipient, CC, BCC
python -m mail_pilot send --to a@x.com,b@x.com --cc c@x.com --bcc d@x.com \
  --subject "Meeting" --body "Tomorrow 3pm"

# HTML email
python -m mail_pilot send --to user@example.com --subject "Report" \
  --body "<h1>Report</h1><p>Done.</p>" --html

# With attachments
python -m mail_pilot send --to user@example.com --subject "Files" \
  --body "See attached" --attach ./report.pdf,./data.csv

# Body from file
python -m mail_pilot send --to user@example.com --subject "Long text" \
  --body-file ./email.txt

# Specify sender account
python -m mail_pilot send --from qq --to user@example.com --subject "Hi" --body "From QQ"

# Dedup (skip if already sent today with same from/to/subject)
python -m mail_pilot send --to user@example.com --subject "Daily" --body "Report" --dedup

# Dry-run (preview without sending)
python -m mail_pilot send --to user@example.com --subject "Test" --body "Preview" --dry-run
```

### Inbox

```bash
# Check recent emails
python -m mail_pilot check --limit 10
python -m mail_pilot check --recent 2h --mailbox INBOX

# Fetch a specific email by UID
python -m mail_pilot fetch 12345

# Search emails
python -m mail_pilot search --from sender@example.com
python -m mail_pilot search --subject "invoice" --since 7d --unseen
python -m mail_pilot search --before 2026-03-01 --limit 50

# Download attachment
python -m mail_pilot download 12345 --file report.pdf --dir ~/Downloads/

# Mark emails
python -m mail_pilot mark-read 12345 12346
python -m mail_pilot mark-unread 12345

# List mailboxes
python -m mail_pilot list-mailboxes
```

### Reply & Forward

```bash
# Reply to an email (sets In-Reply-To and References headers)
python -m mail_pilot reply 12345 --body "Thanks, received."

# Forward an email
python -m mail_pilot forward 12345 --to colleague@example.com --body "FYI"
```

### Templates (optional, requires Jinja2)

```bash
# Use a Jinja2 template
python -m mail_pilot send --to user@example.com --subject "Daily Report" \
  --template templates/daily_report.md --var name="Alice" --var count=42

# Install Jinja2 if not present
pip install jinja2
```

Built-in template variables: `date`, `datetime`, `recipient`, `sender`, `subject`, `account_alias`, plus any `--var` overrides.

### Debug Mode

```bash
# Verbose output (connection details, SMTP/IMAP interaction)
python -m mail_pilot send --to user@example.com --subject "Test" --body "Hi" --verbose

# Quiet mode (JSON only, no stderr)
python -m mail_pilot check --quiet
```

## Configuration

### accounts.json

Location: `~/.config/mail-pilot/accounts.json`

```json
{
  "version": 1,
  "default_account": "163",
  "accounts": [
    {
      "alias": "163",
      "email": "user@163.com",
      "provider": "163.com",
      "smtp_host": "smtp.163.com",
      "smtp_port": 465,
      "smtp_ssl": true,
      "imap_host": "imap.163.com",
      "imap_port": 993,
      "imap_ssl": true,
      "credential_backend": "keychain"
    }
  ]
}
```

The `version` field enables automatic migration when the config format changes in future releases.

### Credential Storage

| Platform | Backend | Notes |
|---|---|---|
| macOS | Keychain (`security` CLI) | Default, uses Security.framework |
| Linux | `keyring` (libsecret/gnome-keyring) | `pip install keyring` |
| Fallback | Fernet encrypted file | Auto-activated when Keychain unavailable |

Keychain service name: `com.mail-pilot.<alias>`

### Cache

Dedup sentinel files: `~/.cache/mail-pilot/sent/`

## Architecture

```
mail-pilot/
├── src/mail_pilot/
│   ├── cli.py              # argparse CLI commands
│   ├── config.py           # accounts.json management + migration
│   ├── credentials.py      # Keychain / keyring / Fernet backends
│   ├── smtp_client.py      # SMTP send with retry & timeout
│   ├── imap_client.py      # IMAP read/search/mark
│   ├── dedup.py            # Date-locked dedup sentinel files
│   ├── presets.py          # Email provider presets
│   ├── template.py         # Jinja2 template engine (optional)
│   ├── security.py         # Path whitelist, input validation
│   └── encoding.py         # Chinese email encoding (RFC 2047)
├── templates/              # Example Jinja2 templates
├── tests/                  # Test suite
├── SKILL.md                # OpenClaw skill descriptor
└── docs/PRD.md             # Product requirements document
```

## Built-in Provider Presets

| Provider | SMTP | IMAP | Auth |
|---|---|---|---|
| 163.com | smtp.163.com:465 SSL | imap.163.com:993 SSL | Authorization code |
| vip.163.com | smtp.vip.163.com:465 SSL | imap.vip.163.com:993 SSL | Authorization code |
| 126.com | smtp.126.com:465 SSL | imap.126.com:993 SSL | Authorization code |
| yeah.net | smtp.yeah.net:465 SSL | imap.yeah.net:993 SSL | Authorization code |
| QQ Mail | smtp.qq.com:465 SSL | imap.qq.com:993 SSL | Authorization code |
| Gmail | smtp.gmail.com:587 STARTTLS | imap.gmail.com:993 SSL | App Password |
| Outlook | smtp.office365.com:587 STARTTLS | outlook.office365.com:993 SSL | OAuth2 / App Password |

## FAQ

**Q: Setup wizard says "Keychain not available"**
A: On macOS, ensure Keychain Access is working. On Linux, install `libsecret` (`sudo apt install libsecret-1-dev`) and `pip install keyring`. The tool will auto-fallback to encrypted file storage.

**Q: Chinese emails show garbled text**
A: Mail Pilot enforces UTF-8 encoding and RFC 2047 subject encoding. If the recipient sees garbled text, their email client may be misconfigured. Use `--html` for better compatibility.

**Q: SMTP connection timeout**
A: Default timeout is 30 seconds. Increase with `--timeout 60`. Check firewall/proxy settings if connecting to Chinese providers from overseas.

**Q: Authorization code vs login password**
A: Chinese email providers (163, QQ, 126) require an "authorization code" (授权码) generated in the webmail settings, not your login password. The setup wizard will guide you.

**Q: How to use with AI agents (Claude Code / OpenClaw)?**
A: All output is JSON-formatted. Use `--quiet` to suppress stderr. See `SKILL.md` for OpenClaw integration.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xxx`)
3. Commit with clear messages
4. Run tests: `pytest tests/`
5. Open a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for details.
