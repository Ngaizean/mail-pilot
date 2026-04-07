# Mail Pilot — 需求文档 (PRD)

## 1. 项目概述

**名称：** Mail Pilot 🛩️
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

- [ ] `python setup.py` 命令行交互引导
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
- [ ] 所有输出为 JSON 格式，便于 AI Agent 解析

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

### Phase 2: 收件与搜索

#### 2.5 IMAP 收件检查

- [ ] `python -m mail_pilot check [--limit N] [--recent 2h] [--mailbox INBOX]`
- [ ] `python -m mail_pilot fetch <uid> [--mailbox INBOX]`
- [ ] `python -m mail_pilot search [--from] [--subject] [--since] [--before] [--unseen] [--limit]`
- [ ] `python -m mail_pilot download <uid> [--file <name>] [--dir <path>]`
- [ ] `python -m mail_pilot mark-read <uid> [uid2 ...]`
- [ ] `python -m mail_pilot mark-unread <uid> [uid2 ...]`
- [ ] `python -m mail_pilot list-mailboxes`

### Phase 3: 模板与高级功能

#### 2.6 Jinja2 模板引擎（可选依赖）

- [ ] `--template <path>` 参数加载 Jinja2 模板
- [ ] 模板上下文自动注入：`date`, `datetime`, `recipient`
- [ ] 支持 `--var key=value` 传入自定义变量
- [ ] 内置示例模板（维生素提醒、新闻摘要等）

#### 2.7 配置管理

- [ ] 配置文件路径：`~/.config/mail-pilot/accounts.json`
- [ ] 仅存储非敏感信息（邮箱地址、服务器参数、别名）
- [ ] JSON schema 校验
- [ ] `python -m mail_pilot test-connection [--account <alias>]` 测试连通性

---

## 3. 非功能需求

### 3.1 安全

- 密码**永不**以明文写入磁盘（Keychain 优先）
- 降级方案使用 Fernet 加密，密钥由用户 `passphrase` 派生
- 附件路径白名单校验（`ALLOWED_DIRS`）
- SKILL.md metadata 正确声明所有环境变量和凭据路径
- 不调用任何外部 API，纯本地 SMTP/IMAP

### 3.2 兼容性

- Python 3.10+
- macOS 12+（Keychain）, Ubuntu 20.04+（libsecret）, Debian 11+
- OpenClaw Skill 格式兼容（SKILL.md + scripts/）
- Claude Code MCP Skill 格式兼容

### 3.3 依赖策略

| 层级 | 依赖 | 必要性 |
|---|---|---|
| Core | smtplib, imaplib, email, json, subprocess, pathlib | Python stdlib |
| macOS Keychain | `security` CLI (macOS 内置) | 系统自带 |
| Linux Keychain | `keyring` (pip) | 可选，无则降级 |
| 模板 | `jinja2` (pip) | 可选，`--template` 时才需要 |
| 加密降级 | `cryptography` (pip) | 可选，Keychain 不可用时 |

### 3.4 用户体验

- 所有命令输出 JSON，便于 AI Agent 解析
- 错误信息结构化（JSON error + stderr 人类可读信息）
- `--quiet` 模式：仅输出 JSON，无 stderr
- 彩色终端提示（setup 向导），`--no-color` 可关闭

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
│       ├── config.py           # account management (accounts.json)
│       ├── credentials.py      # Keychain / keyring / fernet backend
│       ├── smtp_client.py      # SMTP send logic
│       ├── imap_client.py      # IMAP read/search logic
│       ├── dedup.py            # date-locked dedup
│       ├── presets.py          # email provider presets
│       ├── template.py         # Jinja2 template engine (optional)
│       └── security.py         # path whitelist, input validation
├── templates/                  # example Jinja2 templates
│   └── vitamin_reminder.md
└── tests/
    ├── test_smtp.py
    ├── test_imap.py
    ├── test_credentials.py
    ├── test_dedup.py
    └── test_presets.py
```

---

## 5. 技术方案

### 5.1 凭据存储 — macOS Keychain

```python
import subprocess

def keychain_set(service: str, account: str, password: str):
    subprocess.run([
        "security", "add-generic-password",
        "-a", account,        # account name (email)
        "-s", service,        # service name
        "-w", password,       # password from stdin
    ], input=password.encode(), check=True)

def keychain_get(service: str, account: str) -> str:
    result = subprocess.run([
        "security", "find-generic-password",
        "-a", account, "-s", service, "-w",
    ], capture_output=True, text=True, check=True)
    return result.stdout.strip()
```

### 5.2 凭据存储 — 降级 Fernet 加密

```python
from cryptography.fernet import Fernet
import hashlib, base64

def derive_key(passphrase: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.pbkdf2_hmac(
        'sha256', passphrase.encode(), b'mail-pilot-salt', 100000
    )[:32])
```

### 5.3 发件去重 — 哨兵文件

```python
import hashlib, pathlib

def dedup_key(sender, recipient, subject, date_str) -> str:
    raw = f"{sender}|{recipient}|{subject}|{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def is_duplicate(sender, recipient, subject):
    key = dedup_key(sender, recipient, subject, date.today().isoformat())
    lock = pathlib.Path(f"~/.cache/mail-pilot/sent/{key}.lock").expanduser()
    return lock.exists()
```

---

## 6. 里程碑

| Phase | 内容 | 预计时间 |
|---|---|---|
| **M1** | setup.py 向导 + Keychain 存储 + SMTP 发件 + 去重 + SKILL.md | 1-2 天 |
| **M2** | IMAP 收件（check/fetch/search/download/mark） | 1 天 |
| **M3** | Jinja2 模板 + 示例模板 + 测试 + 文档完善 | 1 天 |
| **M4** | ClawHub 发布 + GitHub Actions CI + pyproject.toml 打包 | 0.5 天 |

---

## 7. 竞品对比

详见 README 或项目 Wiki。核心差异：Keychain 原生存密码、零依赖核心、国内邮箱优先、发件去重。

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `security` CLI 在某些 macOS 版本行为不同 | Keychain 存取失败 | 降级到 Fernet 加密 |
| 国内邮箱 SMTP 端口被封 | 发件失败 | 提示用户检查网络；预设 465(SSL) 和 587(STARTTLS) 双端口 |
| Keyring 在 headless Linux 不可用 | 凭据无法存储 | 自动检测并降级 |
| IMAP 搜索性能差（大量邮件） | 搜索慢 | 默认 `--limit 20`，引导用户用 `--since` 缩小范围 |
