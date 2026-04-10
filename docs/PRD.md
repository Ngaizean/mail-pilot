# Mail Pilot — 需求文档 (PRD)

## 1. 项目概述

**名称：** Mail Pilot
**定位：** 面向 AI Agent 的安全邮件收发工具（OpenClaw / Claude Code Skill）
**开源协议：** MIT
**仓库：** https://github.com/Ngaizean/mail-pilot
**技术栈：** Python 3.10+（核心零外部依赖）

### 1.1 解决的问题

现有 OpenClaw/Agent 邮件 Skill 存在以下共性痛点：

1. **密码明文存储** — 凭据存于 .env / config.toml / credentials.json，易泄露
2. **依赖笨重** — Node 系 skill 需要 npm install 拉取大量包
3. **配置繁琐** — 手动填写 20+ 环境变量，无交互引导
4. **多账号切换困难** — 需改配置文件或使用前缀变量
5. **无发件去重** — Agent 定时任务重启后易重复发送
6. **国内邮箱支持差** — 仅个别 skill 预设 163/QQ，无引导
7. **安全元数据缺失** — 注册表 metadata 与实际凭据需求不匹配

### 1.2 目标用户

- OpenClaw / Claude Code / Amp 等 AI Agent 用户
- 需要通过 SMTP 发送自动化邮件的开发者
- 使用国内邮箱（163 / QQ / 126）的中文用户
- 关注凭据安全的隐私敏感用户

---

## 2. 功能需求

### Phase 1: 核心发件（MVP）

#### 2.1 交互式配置向导

- [ ] `python -m mail_pilot setup` 命令行交互引导
- [ ] 自动检测邮箱类型（输入邮箱地址自动推断 SMTP/IMAP 参数）
- [ ] 密码/授权码输入时隐藏回显（`getpass`）
- [ ] 配置完成后自动测试 SMTP 连接
- [ ] 支持添加多个账号，每个账号有别名（如 `--account 163`）

**内置邮箱预设：**

| Provider | IMAP Host | IMAP Port | SMTP Host | SMTP Port | 备注 |
|---|---|---|---|---|---|
| 163.com | imap.163.com | 993 | smtp.163.com | 465 | SSL, 需授权码 |
| vip.163.com | imap.vip.163.com | 993 | smtp.vip.163.com | 465 | SSL, 需授权码 |
| 126.com | imap.126.com | 993 | smtp.126.com | 465 | SSL, 需授权码 |
| yeah.net | imap.yeah.net | 993 | smtp.yeah.net | 465 | SSL, 需授权码 |
| QQ Mail | imap.qq.com | 993 | smtp.qq.com | 465 | SSL, 需授权码 |
| Gmail | imap.gmail.com | 993 | smtp.gmail.com | 587 | STARTTLS, 需 App Password |
| Outlook | outlook.office365.com | 993 | smtp.office365.com | 587 | STARTTLS |

#### 2.2 SMTP 发件

- [ ] `python -m mail_pilot send --to <email> --subject <text> --body <text>`
- [ ] 支持 `--from <alias|email>` 指定发件人（从已配置账号中选）
- [ ] 支持 `--cc` / `--bcc`
- [ ] 支持 `--html` 发送 HTML 邮件
- [ ] 支持 `--attach <path>` 附件（逗号分隔多个）
- [ ] 支持 `--body-file` 从文件读取正文
- [ ] 支持 `--reply-to <email>` 设置回复地址
- [ ] 所有输出为 JSON 格式，便于 AI Agent 解析

**调试与安全选项：**

- [ ] `--dry-run` 模拟发送，构造邮件但不实际投递，输出完整邮件内容（headers + body）供预览
- [ ] `--verbose` 输出 SMTP/IMAP 底层交互详情（连接、认证、DATA 阶段）
- [ ] `--timeout <seconds>` 设置连接与读写超时（默认 30 秒）
- [ ] `--quiet` 仅输出 JSON，无 stderr

**附件限制：**

- [ ] 单个附件默认上限 25 MB，超过时发出警告
- [ ] 单封邮件总大小（含所有附件）上限 50 MB，超过时拒绝发送
- [ ] 可通过 `--max-attachment-size` 覆盖默认限制

**中文编码规范：**

- [ ] 邮件正文统一使用 UTF-8（`Content-Type: text/plain; charset=utf-8`）
- [ ] HTML 邮件使用 UTF-8（`Content-Type: text/html; charset=utf-8`）
- [ ] 邮件主题使用 RFC 2047 编码（`=?utf-8?B?...?=`）
- [ ] 附件文件名使用 RFC 2231 编码（非 ASCII 文件名）
- [ ] `Content-Transfer-Encoding` 对中文内容使用 base64 或 quoted-printable

#### 2.3 Keychain 凭据存储

- [ ] macOS：使用 `security` CLI（Security.framework）存取密码
  - Service name: `com.mail-pilot.<account_alias>`
  - Account name: `<email_address>`
- [ ] Linux：使用 `keyring` 库（libsecret / gnome-keyring / kwallet）
- [ ] 降级方案：若 Keychain 不可用，提示用户并支持加密文件存储（Fernet 对称加密）
- [ ] `python -m mail_pilot list-accounts` 列出所有已配置账号（不含密码）
- [ ] `python -m mail_pilot remove-account <alias>` 删除账号及凭据

#### 2.4 发件去重

- [ ] `--dedup` 参数：基于 `(<from>, <to>, <subject>, <date>)` 生成哨兵文件
- [ ] 哨兵文件路径：`~/.cache/mail-pilot/sent/<hash>.lock`
- [ ] 当天（UTC）重复发送自动跳过并返回 `{"deduplicated": true}`
- [ ] 默认过期时间 24h，可通过 `--dedup-ttl` 调整

#### 2.5 SMTP 重试机制

- [ ] 发送失败时自动重试，默认最多 3 次（`--retry <count>` 可配置）
- [ ] 重试间隔指数退避：1s, 2s, 4s...
- [ ] 以下情况触发重试：
  - 网络超时（socket.timeout）
  - 连接被拒（ConnectionRefusedError）
  - SMTP 临时错误码（4xx）
- [ ] 以下情况不重试，直接报错：
  - 认证失败（SMTPAuthenticationError）
  - 收件人不存在（5xx 永久错误）
- [ ] 重试耗尽后输出结构化错误信息，包含最后一次错误详情

### Phase 2: 收件与搜索

#### 2.6 IMAP 收件检查

- [ ] `python -m mail_pilot check [--limit N] [--recent 2h] [--mailbox INBOX]`
- [ ] `python -m mail_pilot fetch <uid> [--mailbox INBOX]`
- [ ] `python -m mail_pilot search [--from] [--subject] [--since] [--before] [--unseen] [--limit]`
- [ ] `python -m mail_pilot download <uid> [--file <name>] [--dir <path>]`
- [ ] `python -m mail_pilot mark-read <uid> [uid2 ...]`
- [ ] `python -m mail_pilot mark-unread <uid> [uid2 ...]`
- [ ] `python -m mail_pilot list-mailboxes`

#### 2.7 回复与转发

- [ ] `python -m mail_pilot reply <uid> --body <text>` — 回复邮件
  - 自动设置 `In-Reply-To` 和 `References` 头（保持邮件线程）
  - 默认 `Reply-To` 为原始发件人
  - 可选 `--reply-all` 回复所有收件人（To + CC）
  - 可选 `--html` 回复 HTML 格式
- [ ] `python -m mail_pilot forward <uid> --to <email>` — 转发邮件
  - 原始邮件作为附件或内嵌引用
  - 可选 `--body` 添加转发说明

### Phase 3: 模板与高级功能

#### 2.8 Jinja2 模板引擎（可选依赖）

- [ ] `--template <path>` 参数加载 Jinja2 模板
- [ ] 模板上下文自动注入：
  - `date` — 当前日期（YYYY-MM-DD）
  - `datetime` — 当前日期时间（YYYY-MM-DD HH:MM:SS）
  - `recipient` — 收件人邮箱
  - `sender` — 发件人邮箱
  - `subject` — 邮件主题
  - `account_alias` — 当前账号别名
- [ ] 支持 `--var key=value` 传入自定义变量（覆盖内置变量）
- [ ] 内置示例模板（每日提醒、周报摘要等）

#### 2.9 配置管理

- [ ] 配置文件路径：`~/.config/mail-pilot/accounts.json`
- [ ] 仅存储非敏感信息（邮箱地址、服务器参数、别名）
- [ ] JSON schema 校验（见第 5 节数据结构定义）
- [ ] `python -m mail_pilot test-connection [--account <alias>]` 测试连通性

### Phase 4: 打包与发布

#### 2.10 OpenClaw Skill 描述

- [ ] 项目根目录创建 `SKILL.md`，内容包含：
  - **名称与描述**：技能名称、一句话功能描述
  - **触发条件**：用户发送/检查/搜索邮件时自动激活
  - **前置条件**：Python 3.10+、已运行 `mail_pilot setup`
  - **命令映射**：自然语言到 CLI 命令的映射规则
  - **输出格式**：JSON schema 声明
  - **凭据声明**：明确声明需要 Keychain 访问权限，说明存储路径和 service name
  - **安全声明**：密码不写入磁盘、附件路径白名单
  - **错误处理**：常见错误码及 AI Agent 处理建议
- [ ] 兼容 Claude Code MCP Skill 格式

---

## 3. 非功能需求

### 3.1 安全

- 密码**永不**以明文写入磁盘（Keychain 优先）
- 降级方案使用 Fernet 加密，密钥由用户 passphrase + per-user 随机 salt 派生
- 附件路径白名单校验（`ALLOWED_DIRS`）
- SKILL.md metadata 正确声明所有环境变量和凭据路径
- 不调用任何外部 API，纯本地 SMTP/IMAP
- `security` CLI 调用时密码通过 stdin 管道传入，不暴露在命令行参数中

### 3.2 兼容性

- Python 3.10+
- macOS 12+（Keychain）, Ubuntu 20.04+（libsecret）, Debian 11+
- OpenClaw Skill 格式兼容（SKILL.md + scripts/）
- Claude Code MCP Skill 格式兼容

### 3.3 依赖策略

| 层级 | 依赖 | 必要性 |
|---|---|---|
| Core | smtplib, imaplib, email, json, subprocess, pathlib, logging | Python stdlib |
| macOS Keychain | `security` CLI (macOS 内置) | 系统自带 |
| Linux Keychain | `keyring` (pip) | 可选，无则降级 |
| 模板 | `jinja2` (pip) | 可选，`--template` 时才需要 |
| 加密降级 | `cryptography` (pip) | 可选，Keychain 不可用时 |

### 3.4 用户体验

- 所有命令输出 JSON，便于 AI Agent 解析
- 错误信息结构化（JSON error + stderr 人类可读信息）
- `--quiet` 模式：仅输出 JSON，无 stderr
- `--verbose` 模式：输出 SMTP/IMAP 交互详情，用于调试
- 彩色终端提示（setup 向导），`--no-color` 可关闭

### 3.5 日志规格

- 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR`
- 默认级别：`WARNING`
- `--verbose` 时级别降为 `DEBUG`
- 日志输出到 stderr（不干扰 stdout 的 JSON 输出）
- 日志格式：`[%(levelname)s] %(message)s`
- 不写入日志文件（CLI 工具，每次调用独立运行）
- SMTP/IMAP 连接、认证、断开等关键操作记录 INFO 级别日志
- 重试、超时、降级等异常情况记录 WARNING 级别日志

### 3.6 连接复用

- 单次 `mail_pilot` 调用内的多次 SMTP/IMAP 操作复用同一连接
- 连接建立后缓存至进程生命周期结束
- 发送完毕后主动发送 `QUIT` 命令优雅断开
- 连接超时或断开后自动重建

---

## 4. 项目结构

```
mail-pilot/
├── README.md
├── LICENSE
├── pyproject.toml
├── SKILL.md                    # OpenClaw skill 描述
├── docs/
│   └── PRD.md                  # 本文档
├── src/
│   └── mail_pilot/
│       ├── __init__.py
│       ├── __main__.py         # CLI entry point
│       ├── cli.py              # argparse commands
│       ├── config.py           # account management + version migration
│       ├── credentials.py      # Keychain / keyring / fernet backend
│       ├── smtp_client.py      # SMTP send logic (with retry & timeout)
│       ├── imap_client.py      # IMAP read/search logic
│       ├── dedup.py            # date-locked dedup
│       ├── presets.py          # email provider presets
│       ├── template.py         # Jinja2 template engine (optional)
│       ├── encoding.py         # Chinese email encoding (RFC 2047 / RFC 2231)
│       └── security.py         # path whitelist, input validation
├── templates/                  # example Jinja2 templates
│   └── daily_reminder.md
└── tests/
    ├── test_smtp.py
    ├── test_imap.py
    ├── test_credentials.py
    ├── test_dedup.py
    ├── test_presets.py
    └── test_encoding.py
```

---

## 5. 数据结构定义

### 5.1 accounts.json Schema

路径：`~/.config/mail-pilot/accounts.json`

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
    }
  ]
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `version` | int | 是 | 配置格式版本号，用于自动迁移 |
| `default_account` | string | 否 | 默认账号别名，未指定 `--from` 时使用 |
| `accounts[].alias` | string | 是 | 账号别名，用于 `--from` 引用，唯一标识 |
| `accounts[].email` | string | 是 | 邮箱地址 |
| `accounts[].provider` | string | 是 | 邮箱服务商（对应 presets.py 中的预设） |
| `accounts[].smtp_host` | string | 是 | SMTP 服务器地址 |
| `accounts[].smtp_port` | int | 是 | SMTP 端口 |
| `accounts[].smtp_ssl` | bool | 是 | 是否使用 SSL（true）或 STARTTLS（false） |
| `accounts[].imap_host` | string | 是 | IMAP 服务器地址 |
| `accounts[].imap_port` | int | 是 | IMAP 端口 |
| `accounts[].imap_ssl` | bool | 是 | 是否使用 SSL |
| `accounts[].credential_backend` | string | 是 | 凭据后端：`keychain` / `keyring` / `fernet` |
| `accounts[].created_at` | string | 否 | ISO 8601 创建时间 |

**版本迁移：**

- `config.py` 启动时检查 `version` 字段
- 若版本低于当前版本，自动执行迁移函数链（v1→v2→v3...）
- 迁移前备份原文件至 `accounts.json.bak.<timestamp>`
- 迁移完成后写入新版本号

### 5.2 Fernet 加密存储结构

路径：`~/.config/mail-pilot/credentials/`

```
credentials/
├── <alias>.salt          # per-user 随机 salt（base64 编码，32 字节）
└── <alias>.enc           # Fernet 加密后的密码
```

每个账号独立的随机 salt，密钥派生公式：

```
key = PBKDF2(passphrase, random_salt_32bytes, iterations=200000, hash=SHA256)
fernet_key = base64.urlsafe_b64encode(key[:32])
```

---

## 6. 技术方案

### 6.1 凭据存储 — macOS Keychain

**安全修正：** 密码通过 stdin 管道传入，不作为命令行参数（避免 `ps aux` 泄露）。

```python
import subprocess

def keychain_set(service: str, account: str, password: str):
    # 先删除旧条目（避免 duplicate key 报错）
    subprocess.run([
        "security", "delete-generic-password",
        "-a", account, "-s", service,
    ], capture_output=True)  # 忽略不存在时的错误

    # 通过 stdin 安全写入密码
    subprocess.run([
        "security", "add-generic-password",
        "-a", account,
        "-s", service,
        "-w",  # 从 stdin 读取密码
    ], input=password.encode(), check=True)

def keychain_get(service: str, account: str) -> str:
    result = subprocess.run([
        "security", "find-generic-password",
        "-a", account, "-s", service, "-w",
    ], capture_output=True, text=True, check=True)
    return result.stdout.strip()
```

### 6.2 凭据存储 — 降级 Fernet 加密

**安全修正：** 使用 per-user 随机 salt 替代硬编码 salt。

```python
import os, hashlib, base64
from cryptography.fernet import Fernet
from pathlib import Path

CREDENTIALS_DIR = Path("~/.config/mail-pilot/credentials").expanduser()

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return base64.urlsafe_b64encode(
        hashlib.pbkdf2_hmac('sha256', passphrase.encode(), salt, 200000)[:32]
    )

def fernet_set(alias: str, passphrase: str, password: str):
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # 生成 per-user 随机 salt
    salt = os.urandom(32)
    (CREDENTIALS_DIR / f"{alias}.salt").write_bytes(salt)

    # 派生密钥并加密
    key = _derive_key(passphrase, salt)
    encrypted = Fernet(key).encrypt(password.encode())
    (CREDENTIALS_DIR / f"{alias}.enc").write_bytes(encrypted)

def fernet_get(alias: str, passphrase: str) -> str:
    salt = (CREDENTIALS_DIR / f"{alias}.salt").read_bytes()
    key = _derive_key(passphrase, salt)
    encrypted = (CREDENTIALS_DIR / f"{alias}.enc").read_bytes()
    return Fernet(key).decrypt(encrypted).decode()
```

### 6.3 发件去重 — 哨兵文件

```python
import hashlib, pathlib
from datetime import date

def dedup_key(sender, recipient, subject, date_str) -> str:
    raw = f"{sender}|{recipient}|{subject}|{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def is_duplicate(sender, recipient, subject) -> bool:
    key = dedup_key(sender, recipient, subject, date.today().isoformat())
    lock = pathlib.Path(f"~/.cache/mail-pilot/sent/{key}.lock").expanduser()
    return lock.exists()

def mark_sent(sender, recipient, subject):
    key = dedup_key(sender, recipient, subject, date.today().isoformat())
    lock = pathlib.Path(f"~/.cache/mail-pilot/sent/{key}.lock").expanduser()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch()
```

### 6.4 SMTP 重试机制

```python
import time, logging, smtplib

def smtp_send_with_retry(
    smtp_client, message, max_retries=3, base_delay=1.0
) -> dict:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            smtp_client.send_message(message)
            return {"status": "sent", "attempts": attempt}
        except smtplib.SMTPAuthenticationError as e:
            return {"status": "error", "error": "auth_failed", "detail": str(e)}
        except smtplib.SMTPResponseException as e:
            if 400 <= e.smtp_code < 500:
                last_error = e
                delay = base_delay * (2 ** (attempt - 1))
                logging.warning("SMTP %d 错误，%d/%d 次重试，等待 %.1fs",
                                e.smtp_code, attempt, max_retries, delay)
                time.sleep(delay)
            else:
                return {"status": "error", "error": "permanent", "detail": str(e)}
        except (TimeoutError, ConnectionError, OSError) as e:
            last_error = e
            delay = base_delay * (2 ** (attempt - 1))
            logging.warning("网络错误，%d/%d 次重试，等待 %.1fs",
                            attempt, max_retries, delay)
            time.sleep(delay)
    return {"status": "error", "error": "max_retries_exceeded", "detail": str(last_error)}
```

### 6.5 中文邮件编码

```python
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

def make_chinese_email(
    subject: str, body: str, from_email: str, from_name: str | None = None,
    to: list[str] = None, html: bool = False
) -> MIMEText:
    content_type = "text/html" if html else "text/plain"
    msg = MIMEText(body, _subtype=content_type.split("/")[1], _charset="utf-8")

    # RFC 2047 编码中文主题
    msg["Subject"] = Header(subject, "utf-8")

    # RFC 2047 编码中文发件人名
    if from_name:
        msg["From"] = formataddr((str(Header(from_name, "utf-8")), from_email))
    else:
        msg["From"] = from_email

    if to:
        msg["To"] = ", ".join(to)

    return msg
```

---

## 7. 里程碑

| Phase | 内容 | 预计时间 |
|---|---|---|
| **M1** | setup 向导 + Keychain 存储 + SMTP 发件 + 重试 + 去重 + SKILL.md | 1-2 天 |
| **M2** | IMAP 收件（check/fetch/search/download/mark）+ 回复/转发 | 1 天 |
| **M3** | Jinja2 模板 + 示例模板 + 中文编码 + 测试 + 文档完善 | 1 天 |
| **M4** | ClawHub 发布 + GitHub Actions CI + pyproject.toml 打包 | 0.5 天 |

---

## 8. 竞品对比

| 特性 | Mail Pilot | open-email-skill (Node) | python-smtp-skill | imap-mcp-server |
|---|---|---|---|---|
| **语言** | Python 3.10+ | Node.js | Python | Python |
| **核心依赖** | 零（stdlib） | npm (nodemailer 等) | 零 | imapclient |
| **凭据存储** | 系统原生 Keychain | .env 文件 | config.toml | .env 文件 |
| **多账号** | 原生支持，别名切换 | 手动改配置 | 前缀变量 | 单账号 |
| **发件去重** | 内置 `--dedup` | 无 | 无 | 无 |
| **国内邮箱** | 163/QQ/126/yeah 预设 | 需手动配置 | 部分预设 | 需手动配置 |
| **收件功能** | IMAP 全功能 | 无 | 无 | IMAP 只读 |
| **回复/转发** | 原生支持线程头 | 无 | 无 | 无 |
| **Dry-run** | `--dry-run` | 无 | 无 | 无 |
| **模板** | Jinja2 可选 | 无 | 无 | 无 |
| **输出格式** | 结构化 JSON | 文本 | 文本 | JSON |
| **重试机制** | 指数退避，3 次 | 无 | 无 | 无 |
| **AI Agent 适配** | OpenClaw + Claude Code | OpenClaw | OpenClaw | MCP |

**核心差异：**
1. **Keychain 原生存储** — 唯一使用系统级凭据管理的方案
2. **零依赖核心** — Python stdlib 覆盖全部核心功能
3. **发件去重** — 唯一内置去重机制，解决 Agent 定时任务痛点
4. **国内邮箱优先** — 开箱即用的中文邮箱预设与编码支持
5. **全功能收发** — 唯一同时覆盖 SMTP 发送 + IMAP 收取 + 回复/转发的方案

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `security` CLI 在某些 macOS 版本行为不同 | Keychain 存取失败 | 降级到 Fernet 加密；启动时检测 `security` 可用性 |
| 国内邮箱 SMTP 端口被封 | 发件失败 | 提示用户检查网络；预设 465(SSL) 和 587(STARTTLS) 双端口 |
| Keyring 在 headless Linux 不可用 | 凭据无法存储 | 自动检测并降级到 Fernet；文档说明 headless 环境配置方法 |
| IMAP 搜索性能差（大量邮件） | 搜索慢 | 默认 `--limit 20`，引导用户用 `--since` 缩小范围 |
| SMTP 服务商发送频率限制 | 批量发送被拒 | 内置发送间隔控制；文档说明各服务商限制 |
| accounts.json 格式变更 | 升级后配置失效 | `version` 字段 + 自动迁移 + 迁移前备份 |
| 附件路径穿越攻击 | 安全漏洞 | `security.py` 白名单校验 + 路径规范化 |
