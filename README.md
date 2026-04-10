# Mail Pilot

A secure, zero-dependency email CLI for AI agents. Send and receive email via IMAP/SMTP with native Keychain credential storage, multi-account switching, deduplication, and first-class Chinese email provider support.

**[Documentation (PRD)](docs/PRD.md)** | **[AI Agent Integration (SKILL.md)](SKILL.md)**

## Features

- **Native Keychain storage** -- macOS Keychain / Linux libsecret, passwords never touch disk
- **Zero-dependency core** -- Python stdlib `smtplib` + `imaplib`, optional Jinja2 for templates
- **One-command setup** -- `python -m mail_pilot setup` interactive wizard, auto-detects provider
- **Multi-account** -- `--from <alias>` switches sender without editing config
- **Built-in dedup** -- `--dedup` date-locked sending prevents duplicate emails from cron catch-up
- **Chinese providers first** -- 163.com / QQ.com / 126.com / yeah.net built-in presets
- **Dry-run mode** -- `--dry-run` previews email without sending
- **Reply & Forward** -- `reply <uid>` and `forward <uid>` with proper threading headers
- **Full IMAP** -- check, fetch, search, download attachments, mark read/unread
- **Retry with backoff** -- exponential backoff on transient SMTP errors (4xx, timeout)

## Prerequisites

- Python 3.9+
- macOS 12+ (Keychain) or Ubuntu 20.04+ / Debian 11+ (libsecret)
- For Chinese email providers: SMTP authorization code (not login password)

## Installation

```bash
git clone https://github.com/Ngaizean/mail-pilot.git
cd mail-pilot
pip install -e .
```

Optional dependencies:
```bash
pip install -e ".[template]"  # Jinja2 template engine
pip install -e ".[keyring]"   # Linux keyring support
pip install -e ".[crypto]"    # Fernet encrypted fallback
pip install -e ".[dev]"       # pytest for development
```

## Quick Start

```bash
# 1. Add an account (interactive wizard, auto-detects provider)
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
# Interactive setup wizard (auto-detects provider from email address)
python -m mail_pilot setup

# List all configured accounts (JSON output)
python -m mail_pilot list-accounts

# Test SMTP connection for a specific account
python -m mail_pilot test-connection --account 163

# Remove an account (with confirmation prompt)
python -m mail_pilot remove-account 163
# Skip confirmation
python -m mail_pilot remove-account 163 -y
```

**Setup wizard flow:**
1. Enter email address -- auto-detects provider and shows preset info
2. Choose an alias (default: domain name with dots replaced by hyphens)
3. Enter password/authorization code (hidden input via `getpass`)
4. Auto-tests SMTP connection
5. Saves account to `~/.config/mail-pilot/accounts.json`
6. Stores password in system Keychain (or encrypted file as fallback)

### Sending Emails

```bash
# Basic send
python -m mail_pilot send --to user@example.com --subject "Test" --body "Hello"

# Multi-recipient with CC and BCC
python -m mail_pilot send --to a@x.com,b@x.com --cc c@x.com --bcc d@x.com \
  --subject "Meeting" --body "Tomorrow 3pm"

# HTML email
python -m mail_pilot send --to user@example.com --subject "Report" \
  --body "<h1>Report</h1><p>Done.</p>" --html

# With attachments (comma-separated, size limit: 25 MB per file, 50 MB total)
python -m mail_pilot send --to user@example.com --subject "Files" \
  --body "See attached" --attach ./report.pdf,./data.csv

# Read body from file (supports long email content)
python -m mail_pilot send --to user@example.com --subject "Long text" \
  --body-file ./email.txt

# Specify sender account (by alias or email)
python -m mail_pilot send --from qq --to user@example.com --subject "Hi" --body "From QQ"

# Dedup: skip if already sent today with same from/to/subject combination
# Useful for cron/scheduled tasks that might re-run
python -m mail_pilot send --to user@example.com --subject "Daily" --body "Report" --dedup

# Dry-run: construct email and preview without actually sending
python -m mail_pilot send --to user@example.com --subject "Test" --body "Preview" --dry-run

# Adjust timeout and retries
python -m mail_pilot send --to user@example.com --subject "Test" --body "Hi" \
  --timeout 60 --retry 5

# Set Reply-To address
python -m mail_pilot send --to user@example.com --subject "Question" \
  --body "Please reply to support" --reply-to support@example.com
```

### Inbox (IMAP)

```bash
# Check recent emails (returns subject, from, date, uid for each)
python -m mail_pilot check --limit 10
python -m mail_pilot check --recent 2h          # last 2 hours
python -m mail_pilot check --recent 7d          # last 7 days
python -m mail_pilot check --mailbox INBOX      # specific mailbox
python -m mail_pilot check --account 163        # specific account

# Fetch full email by UID (headers + body + attachment list)
python -m mail_pilot fetch 12345

# Search emails with various filters
python -m mail_pilot search --from sender@example.com
python -m mail_pilot search --subject "invoice" --since 7d --unseen
python -m mail_pilot search --since 1h --limit 50
python -m mail_pilot search --unseen --mailbox INBOX

# Download attachments from an email
python -m mail_pilot download 12345                          # to current directory
python -m mail_pilot download 12345 --dir ~/Downloads/       # to specific directory
python -m mail_pilot download 12345 --file report.pdf        # rename single attachment

# Mark emails as read/unread
python -m mail_pilot mark-read 12345 12346 12347
python -m mail_pilot mark-unread 12345

# List all mailboxes/folders in the account
python -m mail_pilot list-mailboxes
```

### Reply & Forward

```bash
# Reply to an email (auto-sets In-Reply-To, References, and "Re:" prefix)
python -m mail_pilot reply 12345 --body "Thanks, received."
python -m mail_pilot reply 12345 --body "<p>Got it</p>" --html

# Forward an email (includes original as quoted text)
python -m mail_pilot forward 12345 --to colleague@example.com
python -m mail_pilot forward 12345 --to a@x.com,b@x.com --body "Please review"
```

**Threading behavior:**
- `reply` fetches the original email's `Message-ID` and `References` headers
- Sets `In-Reply-To: <original-message-id>` on the new email
- Appends original `Message-ID` to `References` header chain
- Auto-prepends `Re:` to subject if not already present
- `forward` auto-prepends `Fwd:` and includes original sender/date/subject in body

### Templates (optional, requires Jinja2)

```bash
# Install Jinja2
pip install jinja2

# Use a template file
python -m mail_pilot send --to user@example.com --subject "Daily Report" \
  --template templates/daily_reminder.md \
  --var items="Task A" --var items="Task B"

# Use weekly report template
python -m mail_pilot send --to boss@company.com --subject "Week Report" \
  --template templates/weekly_report.md \
  --var summary="Completed 5 tasks" --var plan="Start new sprint"
```

**Built-in template variables:**

| Variable | Description | Example |
|---|---|---|
| `{{ date }}` | Current date | `2026-04-10` |
| `{{ datetime }}` | Current datetime | `2026-04-10 14:30:00` |
| `{{ recipient }}` | Recipient email | `user@163.com` |
| `{{ sender }}` | Sender email | `me@163.com` |
| `{{ subject }}` | Email subject | `Daily Report` |
| `{{ account_alias }}` | Account alias | `163` |

User-provided `--var` values override built-in variables.

### Debug Mode

```bash
# Verbose: shows SMTP/IMAP connection details, authentication, data transfer
python -m mail_pilot send --to user@example.com --subject "Test" --body "Hi" --verbose

# Quiet: only JSON output to stdout, no stderr messages
python -m mail_pilot check --quiet
```

## Output Format

All output is structured JSON to stdout, designed for AI agent parsing.

**Successful send:**
```json
{
  "status": "sent",
  "from": "user@163.com",
  "to": ["someone@example.com"],
  "subject": "Hello",
  "attempts": 1
}
```

**Deduplicated:**
```json
{
  "status": "deduplicated",
  "from": "user@163.com",
  "to": "someone@example.com",
  "subject": "Daily Report"
}
```

**Dry-run preview:**
```json
{
  "status": "dry_run",
  "from": "user@163.com",
  "to": ["someone@example.com"],
  "subject": "Test",
  "body_length": 15,
  "attachments": ["report.pdf"],
  "html": false,
  "message_preview": "This is a test..."
}
```

**Error:**
```json
{
  "status": "error",
  "error": "auth_failed",
  "detail": "SMTP 认证失败: (535, b'Error: authentication failed')"
}
```

## Configuration

### accounts.json

**Location:** `~/.config/mail-pilot/accounts.json`

Contains only non-sensitive account metadata (email, server settings, alias). Passwords are stored separately in the system credential backend.

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
      "credential_backend": "keychain",
      "created_at": "2026-04-10T12:00:00Z"
    },
    {
      "alias": "gmail",
      "email": "user@gmail.com",
      "provider": "gmail.com",
      "smtp_host": "smtp.gmail.com",
      "smtp_port": 587,
      "smtp_ssl": false,
      "imap_host": "imap.gmail.com",
      "imap_port": 993,
      "imap_ssl": true,
      "credential_backend": "keychain",
      "created_at": "2026-04-10T12:05:00Z"
    }
  ]
}
```

The `version` field enables automatic migration when the config format changes. Backups are created before each migration (`accounts.json.bak.<timestamp>`).

### Credential Storage

| Platform | Backend | How It Works |
|---|---|---|
| macOS | Keychain via `security` CLI | Password passed through stdin pipe (not CLI args). Service: `com.mail-pilot.<alias>` |
| Linux | `keyring` (libsecret/gnome-keyring/kwallet) | Requires `pip install keyring`. Falls back if unavailable. |
| Fallback | Fernet-encrypted file | Per-user random salt (`os.urandom(32)`), PBKDF2 key derivation (200k iterations). Stored in `~/.config/mail-pilot/credentials/` |

**Security guarantees:**
- Passwords are **never** stored in `accounts.json`, `.env`, or any config file
- On macOS, passwords are only accessible to the logged-in user via Keychain Access
- Fernet fallback requires a user-provided passphrase

### Cache

- Dedup sentinel files: `~/.cache/mail-pilot/sent/<hash>.lock`
- Auto-cleanup of files older than 7 days via `dedup.clean_expired()`

## Architecture

```
mail-pilot/
├── src/mail_pilot/
│   ├── __init__.py          # Package version
│   ├── __main__.py          # Entry point (python -m mail_pilot)
│   ├── cli.py               # 14 CLI commands via argparse
│   ├── config.py            # accounts.json CRUD + version migration
│   ├── credentials.py       # 3 backends: Keychain / keyring / Fernet
│   ├── smtp_client.py       # SMTP connect, send with retry, dry-run
│   ├── imap_client.py       # IMAP check/fetch/search/download/mark
│   ├── dedup.py             # SHA256 sentinel file deduplication
│   ├── presets.py           # 9 provider presets (163, QQ, Gmail...)
│   ├── template.py          # Jinja2 template rendering (optional)
│   ├── encoding.py          # RFC 2047/2231 Chinese email encoding
│   └── security.py          # Path whitelist, size limits, input validation
├── templates/               # Example Jinja2 templates
│   ├── daily_reminder.md
│   └── weekly_report.md
├── tests/                   # 57 test cases
│   ├── test_presets.py
│   ├── test_security.py
│   ├── test_encoding.py
│   ├── test_dedup.py
│   └── test_template.py
├── SKILL.md                 # AI agent integration guide
├── docs/PRD.md              # Product requirements document
└── pyproject.toml           # Package configuration
```

**Data flow (sending):**
```
CLI args → cli.py → config.py (resolve account)
                   → credentials.py (retrieve password)
                   → encoding.py (build MIME message)
                   → dedup.py (check/mark sentinel)
                   → smtp_client.py (connect + send with retry)
```

**Data flow (receiving):**
```
CLI args → cli.py → config.py (resolve account)
                   → credentials.py (retrieve password)
                   → imap_client.py (connect + search/fetch)
                   → JSON output
```

## Built-in Provider Presets

| Provider | SMTP | IMAP | SSL Mode | Auth Type |
|---|---|---|---|---|
| 163.com | smtp.163.com:465 | imap.163.com:993 | Direct SSL | Authorization code |
| vip.163.com | smtp.vip.163.com:465 | imap.vip.163.com:993 | Direct SSL | Authorization code |
| 126.com | smtp.126.com:465 | imap.126.com:993 | Direct SSL | Authorization code |
| yeah.net | smtp.yeah.net:465 | imap.yeah.net:993 | Direct SSL | Authorization code |
| QQ Mail | smtp.qq.com:465 | imap.qq.com:993 | Direct SSL | Authorization code |
| Gmail | smtp.gmail.com:587 | imap.gmail.com:993 | STARTTLS | App Password |
| Outlook | smtp.office365.com:587 | outlook.office365.com:993 | STARTTLS | OAuth2 / App Password |
| Hotmail | smtp.office365.com:587 | outlook.office365.com:993 | STARTTLS | Same as Outlook |
| Yahoo | smtp.mail.yahoo.com:465 | imap.mail.yahoo.com:993 | Direct SSL | App Password |

## FAQ

**Q: Setup wizard says "Keychain not available"**
A: On macOS, ensure Keychain Access is working. On Linux, install `libsecret` (`sudo apt install libsecret-1-dev`) and `pip install keyring`. The tool auto-falls back to encrypted file storage.

**Q: Chinese emails show garbled text**
A: Mail Pilot enforces UTF-8 encoding and RFC 2047 subject encoding. If recipients see garbled text, their email client may be misconfigured. Use `--html` for better cross-client compatibility.

**Q: SMTP connection timeout**
A: Default timeout is 30 seconds. Increase with `--timeout 60`. Check firewall/proxy settings if connecting to Chinese providers from overseas.

**Q: Authorization code vs login password**
A: Chinese email providers (163, QQ, 126) require an "authorization code" generated in webmail settings, not your login password. The setup wizard displays provider-specific instructions.

**Q: How to use with AI agents (Claude Code / OpenClaw)?**
A: All output is JSON to stdout. Use `--quiet` to suppress stderr. See `SKILL.md` for full integration guide including error handling strategies.

**Q: How does dedup work?**
A: `--dedup` generates a SHA256 hash from `(sender, recipient, subject, date)`. A sentinel file is created at `~/.cache/mail-pilot/sent/<hash>.lock`. If the same email (same from/to/subject) was already sent today, it's skipped. TTL is configurable.

**Q: What happens on network errors?**
A: SMTP sends are retried up to 3 times with exponential backoff (1s, 2s, 4s). Transient errors (4xx, timeout, connection refused) trigger retry. Permanent errors (5xx, auth failure) fail immediately.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xxx`)
3. Make changes and add tests
4. Run tests: `PYTHONPATH=src pytest tests/ -v`
5. Open a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for details.
