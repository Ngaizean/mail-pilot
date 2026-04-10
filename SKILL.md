# Mail Pilot — AI Agent Skill

Send and receive email via SMTP/IMAP with native Keychain credential storage. All output is JSON for easy parsing.

## When to Use

- User asks to send, reply to, or forward an email
- User asks to check inbox, fetch, or search emails
- User needs to manage email accounts (add, remove, test)
- User wants to send recurring/templated emails with deduplication

## Prerequisites

- Python 3.9+
- At least one email account configured via `python -m mail_pilot setup`
- For Chinese email providers (163, QQ, 126): SMTP authorization code (not login password)

## Installation

```bash
cd /path/to/mail-pilot
pip install -e .
```

Verify: `python -m mail_pilot --version`

## Commands Reference

### Account Setup

```bash
python -m mail_pilot setup
```

Interactive wizard: enter email address (auto-detects provider), alias, password. Tests SMTP connection automatically. If no account exists, run this first before any other command.

**Output (on success):**
- Human-readable terminal output (not JSON)
- Account saved to `~/.config/mail-pilot/accounts.json`

### Send Email

```bash
python -m mail_pilot send \
  --to <email1,email2> \
  --subject <text> \
  --body <text> \
  [--from <alias>] \
  [--cc <emails>] [--bcc <emails>] \
  [--html] [--attach <paths>] \
  [--body-file <path>] \
  [--reply-to <email>] \
  [--template <path>] [--var key=value] \
  [--dry-run] [--dedup] \
  [--timeout <seconds>] [--retry <count>] \
  [--verbose] [--quiet]
```

**Parameters:**

| Parameter | Required | Description |
|---|---|---|
| `--to` | Yes | Recipients, comma-separated |
| `--subject` / `-s` | Yes | Email subject |
| `--body` / `-b` | No | Email body text (or use `--body-file` / `--template`) |
| `--from` | No | Sender account alias or email (default: first configured account) |
| `--cc` | No | CC recipients, comma-separated |
| `--bcc` | No | BCC recipients, comma-separated |
| `--html` | No | Send as HTML email |
| `--attach` | No | Attachment file paths, comma-separated (25 MB per file, 50 MB total) |
| `--body-file` | No | Read body from file (overrides `--body`) |
| `--reply-to` | No | Reply-To address |
| `--template` | No | Jinja2 template file path (requires `pip install jinja2`) |
| `--var` | No | Template variable `key=value` (can be repeated) |
| `--dry-run` | No | Preview without sending |
| `--dedup` | No | Skip if already sent today |
| `--timeout` | No | Connection timeout in seconds (default: 30) |
| `--retry` | No | Max retry attempts (default: 3) |
| `--verbose` / `-v` | No | Debug output to stderr |
| `--quiet` / `-q` | No | JSON only, suppress stderr |

**JSON Output:**

```json
{"status": "sent", "from": "user@163.com", "to": ["a@x.com"], "subject": "Hello", "attempts": 1}
```

```json
{"status": "deduplicated", "from": "user@163.com", "to": "a@x.com", "subject": "Daily Report"}
```

```json
{"status": "dry_run", "from": "user@163.com", "to": ["a@x.com"], "subject": "Test", "body_length": 15, "attachments": ["report.pdf"], "message_preview": "..."}
```

### Check Inbox

```bash
python -m mail_pilot check [--limit 20] [--recent 2h] [--mailbox INBOX] [--account <alias>]
```

Returns list of recent emails with uid, from, to, subject, date.

**JSON Output:**
```json
{
  "status": "ok",
  "account": "163",
  "mailbox": "INBOX",
  "count": 3,
  "emails": [
    {"uid": "123", "from": "Alice <alice@x.com>", "subject": "Hello", "date": "2026-04-10T10:00:00+08:00"},
    ...
  ]
}
```

### Fetch Email

```bash
python -m mail_pilot fetch <uid> [--account <alias>] [--mailbox INBOX]
```

Returns full email content: headers, body (text + html), attachment list.

**JSON Output:**
```json
{
  "status": "ok",
  "uid": "123",
  "headers": {"from": "...", "to": "...", "subject": "...", "date": "...", "message_id": "..."},
  "body": {"text": "plain text content", "html": "<p>html content</p>"},
  "attachments": [{"filename": "report.pdf", "size": 12345}]
}
```

### Search Emails

```bash
python -m mail_pilot search \
  [--from <sender>] [--subject <text>] \
  [--since <period>] [--before <period>] \
  [--unseen] [--limit 20] \
  [--account <alias>] [--mailbox INBOX]
```

Period format: `30m` (minutes), `2h` (hours), `7d` (days).

**JSON Output:** Same format as `check`.

### Download Attachments

```bash
python -m mail_pilot download <uid> [--file <name>] [--dir <path>] [--account <alias>]
```

Downloads all attachments from the specified email. `--file` renames single attachments.

**JSON Output:**
```json
{"status": "ok", "uid": "123", "downloaded": ["/path/to/report.pdf", "/path/to/data.csv"]}
```

### Mark Read / Unread

```bash
python -m mail_pilot mark-read <uid1> <uid2> ... [--account <alias>]
python -m mail_pilot mark-unread <uid1> <uid2> ... [--account <alias>]
```

**JSON Output:**
```json
{"status": "ok", "marked_read": ["123", "124"], "count": 2}
```

### List Mailboxes

```bash
python -m mail_pilot list-mailboxes [--account <alias>]
```

**JSON Output:**
```json
{"status": "ok", "account": "163", "mailboxes": [{"name": "INBOX", "flags": "(\\HasNoChildren)"}, ...]}
```

### Reply to Email

```bash
python -m mail_pilot reply <uid> --body <text> [--html] [--account <alias>] [--dry-run]
```

Automatically fetches original email's `Message-ID` and `References`, sets `In-Reply-To` and threading headers. Extracts sender via `email.utils.parseaddr`. Prepends `Re:` to subject.

**JSON Output:** Same as `send`.

### Forward Email

```bash
python -m mail_pilot forward <uid> --to <email> [--body <note>] [--html] [--account <alias>] [--dry-run]
```

Fetches original email, quotes it below the forward note, prepends `Fwd:` to subject.

**JSON Output:** Same as `send`.

### Account Management

```bash
# List accounts
python -m mail_pilot list-accounts
# {"accounts": [{"alias": "163", "email": "user@163.com", "provider": "163.com", "is_default": true}]}

# Test connection
python -m mail_pilot test-connection --account 163
# {"status": "ok", "account": "163", "email": "user@163.com", "smtp": "smtp.163.com:465"}

# Remove account
python -m mail_pilot remove-account <alias> [-y]
# {"status": "removed", "alias": "163"}
```

## Template Variables

When using `--template`, these variables are available:

| Variable | Type | Description |
|---|---|---|
| `date` | str | Current date `YYYY-MM-DD` |
| `datetime` | str | Current datetime `YYYY-MM-DD HH:MM:SS` |
| `recipient` | str | First recipient email |
| `sender` | str | Sender email |
| `subject` | str | Email subject |
| `account_alias` | str | Current account alias |

Pass custom variables with `--var key=value`. User vars override built-ins.

## Credential Storage

| Platform | Backend | Storage Location |
|---|---|---|
| macOS | Keychain (`security` CLI) | Service: `com.mail-pilot.<alias>`, Account: `<email>` |
| Linux | `keyring` (libsecret) | System keyring |
| Fallback | Fernet encrypted file | `~/.config/mail-pilot/credentials/<alias>.{salt,enc}` |

**Security:**
- Passwords never stored in config files or environment variables
- Keychain access requires user authentication on macOS
- Fernet uses per-user random salt + PBKDF2 (200k iterations)
- No external API calls -- direct SMTP/IMAP only

## File Paths

| Path | Purpose |
|---|---|
| `~/.config/mail-pilot/accounts.json` | Account config (non-sensitive) |
| `~/.config/mail-pilot/credentials/` | Fernet encrypted passwords (fallback only) |
| `~/.cache/mail-pilot/sent/` | Dedup sentinel files |

## Error Handling for AI Agents

| Error Code | Meaning | Recommended Action |
|---|---|---|
| `auth_failed` | SMTP/IMAP authentication failed | Ask user to verify password or regenerate authorization code |
| `connection_failed` | Cannot reach server | Check network, suggest `--timeout` increase, check firewall |
| `max_retries_exceeded` | Transient errors exhausted all retries | Wait and retry later, check server status |
| `not_found` | Account or email UID not found | Run `setup` first, or verify UID exists |
| `deduplicated` | Already sent today (same from/to/subject) | Skip, no action needed |
| `missing_recipients` | `--to` not provided | Ask user for recipient |
| `permanent` | SMTP 5xx permanent error | Check email address validity, review server response |

## Supported Providers

Built-in presets: 163.com, vip.163.com, 126.com, yeah.net, QQ Mail, Gmail, Outlook, Hotmail, Yahoo.

Setup wizard auto-detects provider from email domain and displays provider-specific instructions (e.g., "需授权码" for 163.com, "需 App Password" for Gmail).
