# Mail Pilot — Email Skill for OpenClaw

Send and receive email via SMTP/IMAP with native macOS Keychain credential storage. All output is JSON for easy parsing.

## When to Use

- User asks to send, reply to, or forward an email
- User asks to check inbox, fetch, or search emails
- User needs email attachments downloaded
- User wants to send templated or recurring emails with deduplication

## Quick Reference

The binary is `python3.12 -m mail_pilot` (installed via pip). All commands output JSON to stdout.

**Currently configured accounts:**
- `qq` — 1595344775@qq.com (default)
- `163` — 13622563776@163.com
- `ouc` — yuyizhen@stu.ouc.edu.cn

**Config file:** `~/.config/mail-pilot/accounts.json`
**Credentials:** macOS Keychain (service `com.mail-pilot.<alias>`)

## Common Commands

### Send Email

```bash
python3.12 -m mail_pilot send --to <email> --subject <text> --body <text> [--from <alias>] [--cc <emails>] [--bcc <emails>] [--html] [--attach <paths>] [--body-file <path>] [--reply-to <email>] [--dry-run] [--dedup] [--quiet]
```

- `--from`: alias or email, defaults to first configured account
- `--dedup`: skip if same from/to/subject already sent today
- `--quiet`: JSON only, suppress stderr (recommended for scripting)

### Check Inbox

```bash
python3.12 -m mail_pilot check [--account <alias>] [--limit 20] [--recent 2h] [--mailbox INBOX]
```

### Fetch Full Email

```bash
python3.12 -m mail_pilot fetch <uid> [--account <alias>]
```

Returns headers, body (text + html), and attachment list.

### Search Emails

```bash
python3.12 -m mail_pilot search [--from <sender>] [--subject <text>] [--since 7d] [--unseen] [--limit 20] [--account <alias>]
```

Period format: `30m`, `2h`, `7d`.

### Reply / Forward

```bash
python3.12 -m mail_pilot reply <uid> --body <text> [--account <alias>]
python3.12 -m mail_pilot forward <uid> --to <email> [--body <note>] [--account <alias>]
```

Automatically sets In-Reply-To, References, and threading headers.

### Download Attachments

```bash
python3.12 -m mail_pilot download <uid> [--dir <path>] [--account <alias>]
```

### Account Management

```bash
python3.12 -m mail_pilot list-accounts
python3.12 -m mail_pilot test-connection --account <alias>
```

### Add New Account (requires TTY — ask user to run manually)

```bash
python3.12 -m mail_pilot setup
```

For non-TTY environments, use Python API directly:

```python
from mail_pilot.config import add_account

add_account(alias='gmail', email='user@gmail.com', password='app-password-here')

# For providers not in presets (e.g. university email):
add_account(
    alias='uni',
    email='user@uni.edu.cn',
    password='auth-code',
    provider_override={
        'provider': 'uni.edu.cn',
        'smtp_host': 'smtp.uni.edu.cn',
        'smtp_port': 465,
        'smtp_ssl': True,
        'imap_host': 'imap.uni.edu.cn',
        'imap_port': 993,
        'imap_ssl': True,
    }
)
```

## Output Format

All commands output JSON. Key `status` values:

| Status | Meaning |
|---|---|
| `sent` | Email delivered |
| `ok` | Operation succeeded (check, fetch, search) |
| `deduplicated` | Skipped (already sent today) |
| `dry_run` | Preview only |
| `error` | Failed — check `error` field for details |

## Error Handling

| Error | Action |
|---|---|
| `auth_failed` | Ask user to verify password or regenerate authorization code |
| `connection_failed` | Check network, increase `--timeout` |
| `max_retries_exceeded` | Wait and retry later |
| `not_found` | Account or email UID doesn't exist |
| `missing_recipients` | Ask user for recipient |

## Important Notes

- **Credentials are in macOS Keychain**, never in config files
- **163/126/yeah.net** requires IMAP ID (RFC 2971) before SELECT — this is handled automatically
- **Gmail** requires App Password (not account password) — user must generate one from Google Account → Security → 2-Step Verification → App Passwords
- **QQ Mail** requires authorization code from QQ Mail settings → Account → POP3/SMTP/IMAP
- For long email bodies, use `--body-file <path>` instead of `--body` to avoid shell escaping issues
- Use `--quiet` when calling from exec to keep output clean
