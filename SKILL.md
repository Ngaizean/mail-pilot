# Mail Pilot

Send and receive email via SMTP/IMAP with native Keychain credential storage.

## When to Use

- User asks to send an email
- User asks to check inbox or search emails
- User needs to manage email accounts
- User wants to send recurring/templated emails

## Prerequisites

- Python 3.10+
- At least one email account configured via `python -m mail_pilot setup`
- For Chinese email providers (163, QQ, 126): SMTP authorization code required

## Commands

### Account Setup

```bash
python -m mail_pilot setup
```

Interactive wizard that guides through adding an email account. Auto-detects provider from email address.

### Send Email

```bash
python -m mail_pilot send --to <email> --subject <text> --body <text>
```

Options:
- `--from <alias>` — Sender account (default: first configured account)
- `--cc <emails>` — CC recipients (comma-separated)
- `--bcc <emails>` — BCC recipients (comma-separated)
- `--html` — Send as HTML email
- `--attach <paths>` — Attachments (comma-separated)
- `--body-file <path>` — Read body from file
- `--reply-to <email>` — Set Reply-To address
- `--dry-run` — Preview email without sending
- `--dedup` — Skip if already sent today (same from/to/subject)
- `--timeout <seconds>` — Connection timeout (default: 30)
- `--retry <count>` — Max retries on transient failure (default: 3)
- `--verbose` — Show SMTP/IMAP debug output
- `--quiet` — JSON output only

### Check Inbox

```bash
python -m mail_pilot check [--limit 10] [--recent 2h]
```

### Search Emails

```bash
python -m mail_pilot search --from <email> --subject <text> --since 1d --unseen
```

### Reply / Forward

```bash
python -m mail_pilot reply <uid> --body <text>
python -m mail_pilot forward <uid> --to <email>
```

### Account Management

```bash
python -m mail_pilot list-accounts
python -m mail_pilot test-connection --account <alias>
python -m mail_pilot remove-account <alias>
```

## Output Format

All output is JSON to stdout. Example:

```json
{
  "status": "sent",
  "from": "user@163.com",
  "to": ["someone@example.com"],
  "subject": "Hello",
  "attempts": 1
}
```

Error output:
```json
{
  "status": "error",
  "error": "auth_failed",
  "detail": "SMTP 认证失败: ..."
}
```

## Credential Storage

Credentials are stored securely using:

1. **macOS**: System Keychain (`security` CLI) — service name `com.mail-pilot.<alias>`
2. **Linux**: System keyring (`keyring` + libsecret/gnome-keyring)
3. **Fallback**: Fernet-encrypted file with per-user random salt

Passwords are **never** stored in plain text or config files.

Config file (non-sensitive data only): `~/.config/mail-pilot/accounts.json`

## Security Notes

- No passwords in config files or environment variables
- Attachment paths validated against whitelist (cwd, home, Downloads, Desktop, Documents, /tmp)
- No external API calls — direct SMTP/IMAP connections only
- All email encoding uses UTF-8 with proper RFC 2047 subject encoding

## Supported Providers

Built-in presets for: 163.com, vip.163.com, 126.com, yeah.net, QQ Mail, Gmail, Outlook, Yahoo.

## Error Handling for AI Agents

| Error | Meaning | Agent Action |
|---|---|---|
| `auth_failed` | SMTP authentication error | Ask user to check password/authorization code |
| `connection_failed` | Cannot reach SMTP server | Check network/firewall, suggest `--timeout` increase |
| `max_retries_exceeded` | Transient errors exhausted retries | Wait and retry later |
| `not_found` | Account not found | Run `setup` first |
| `deduplicated` | Already sent today | Skip, no action needed |
| `missing_recipients` | No `--to` provided | Ask user for recipient |
