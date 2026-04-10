# Mail Pilot v0.2.0 — 迭代计划 (PRD)

基于 v0.1.0（95 个测试通过，14 个 CLI 命令），v0.2.0 聚焦三大方向：**OAuth2 现代认证**、**收件体验增强**、**开发者体验**。

## 1. OAuth2 认证支持

### 1.1 问题

Gmail 和 Outlook 逐步淘汰 App Password，强制要求 OAuth2。当前 v0.1.0 仅支持明文密码/授权码，无法适应这一趋势。

### 1.2 方案

采用本地 HTTP 回调方式实现 OAuth2 Authorization Code Flow：

```
用户执行 setup → 打开浏览器授权 → 回调到 localhost:<port> → 获取 token → 存入 Keychain
```

#### 支持的服务商

| Provider | OAuth2 类型 | Scopes |
|---|---|---|
| Gmail | Google OAuth2 | `https://mail.google.com/` |
| Outlook | Microsoft Identity Platform | `https://outlook.office365.com/IMAP.AccessAsUser.All` + `SMTP.Send` |

#### 新增文件

```
src/mail_pilot/
├── oauth2.py              # OAuth2 流程：授权URL生成、token交换、刷新
├── token_store.py         # access_token / refresh_token 安全存储
```

#### CLI 变更

```bash
# setup 向导自动识别 OAuth2 服务商并引导浏览器授权
python -m mail_pilot setup
# 输入 gmail 地址 → 自动打开浏览器 → 授权 → token 存入 Keychain

# 手动刷新 token（通常自动完成）
python -m mail_pilot refresh-token --account gmail
```

#### accounts.json 变更（v1 → v2 迁移）

```json
{
  "version": 2,
  "accounts": [
    {
      "alias": "gmail",
      "email": "user@gmail.com",
      "provider": "gmail.com",
      "auth_type": "oauth2",
      "oauth2_client_id": "...",
      "token_expiry": "2026-04-11T12:00:00Z",
      "...": "其余字段不变"
    }
  ]
}
```

- `auth_type`: 新增字段，`"password"` | `"oauth2"`，默认 `"password"`（向后兼容）
- 迁移逻辑：v1 账号自动添加 `"auth_type": "password"`，不影响现有配置

#### 技术实现

- **Google**: 使用 `google-auth-library`（可选依赖），或纯 HTTP 请求 `accounts.google.com`
- **Outlook**: 使用 Microsoft Identity Platform v2.0 端点 `login.microsoftonline.com`
- **Token 存储**: `access_token` 和 `refresh_token` 存入 Keychain（service: `com.mail-pilot.<alias>.oauth2`）
- **Token 刷新**: SMTP/IMAP 连接前检查过期，自动刷新（Google access_token 约 1 小时有效期）
- **XOAUTH2**: SMTP/IMAP 使用 `auth=XOAUTH2` SASL 机制，非明文密码

### 1.3 依赖

```
[project.optional-dependencies]
oauth2 = ["requests>=2.28"]    # 仅用于 OAuth2 token 交换
```

核心仍为零依赖。仅当 setup 检测到 OAuth2 服务商时提示安装。

---

## 2. 收件体验增强

### 2.1 Reply-All（回复所有人）

```bash
python -m mail_pilot reply <uid> --body "Thanks" --reply-all
```

- 从原始邮件的 `From` + `To` + `Cc` 中提取所有收件人
- 排除自己的邮箱地址（避免回复给自己）
- 生成 `To` 和 `Cc` 列表

### 2.2 邮件移动/删除

```bash
# 移动邮件到指定文件夹
python -m mail_pilot move <uid> --to "Archive"

# 删除邮件（移到 Trash 或永久删除）
python -m mail_pilot delete <uid> [--permanent]
```

### 2.3 邮件统计

```bash
# 查看邮箱统计信息
python -m mail_pilot stats [--account <alias>] [--since 30d]
```

输出：
```json
{
  "status": "ok",
  "total_emails": 1234,
  "unread": 56,
  "by_sender": [
    {"sender": "boss@company.com", "count": 45},
    {"sender": "newsletter@x.com", "count": 30}
  ],
  "by_day": {"Mon": 23, "Tue": 18, "Wed": 15, "..."}
}
```

---

## 3. 开发者体验

### 3.1 Shell 自动补全

```bash
# 生成 bash 补全脚本
python -m mail_pilot completion bash > ~/.mail-pilot-completion.bash
source ~/.mail-pilot-completion.bash

# 生成 zsh 补全脚本
python -m mail_pilot completion zsh > ~/.zfunc/_mail_pilot

# 生成 fish 补全脚本
python -m mail_pilot completion fish > ~/.config/fish/completions/mail_pilot.fish
```

补全内容：
- 所有 14+ 个命令
- `--from` / `--account` 自动补全已配置账号别名
- `--mailbox` 自动补全 IMAP 文件夹名（需联网）

### 3.2 集成测试框架

新增 `tests/integration/` 目录，使用本地 mock SMTP/IMAP 服务器：

```
tests/
├── integration/
│   ├── conftest.py          # pytest fixtures: mock SMTP/IMAP server
│   ├── test_smtp_integration.py   # 真实 SMTP 协议交互测试
│   └── test_imap_integration.py   # 真实 IMAP 协议交互测试
```

- 使用 `aiosmtpd` 作为 mock SMTP 服务器
- 使用 `imap_tools` 或自定义 mock 作为 IMAP 服务器
- 测试真实邮件发送/接收/搜索/标记的完整流程

### 3.3 错误码标准化

所有错误统一为枚举值，便于 AI Agent 编程处理：

```python
# src/mail_pilot/errors.py
class ErrorCode:
    AUTH_FAILED = "auth_failed"
    CONNECTION_FAILED = "connection_failed"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    NOT_FOUND = "not_found"
    DUPLICATED = "deduplicated"
    MISSING_RECIPIENTS = "missing_recipients"
    PERMANENT = "permanent"
    TOKEN_EXPIRED = "token_expired"          # 新增
    OAUTH2_REQUIRED = "oauth2_required"      # 新增
    PROVIDER_UNSUPPORTED = "provider_unsupported"  # 新增
```

---

## 4. 里程碑

| Phase | 内容 | 预计时间 |
|---|---|---|
| **M1** | OAuth2 框架 + Gmail OAuth2 支持 + accounts.json v2 迁移 | 2-3 天 |
| **M2** | Outlook OAuth2 + token 自动刷新 + XOAUTH2 SASL | 1-2 天 |
| **M3** | Reply-All + 邮件移动/删除 + 邮件统计 | 1 天 |
| **M4** | Shell 补全 + 集成测试框架 + 错误码标准化 + CHANGELOG | 1 天 |

总计约 **5-7 天**。

---

## 5. 不在 v0.2.0 范围内（后续版本）

- IMAP IDLE 实时推送通知
- PGP/S/MIME 邮件加密
- 邮件规则/过滤器（自动分类）
- 多语言 UI（当前仅中文提示）
- PyPI 发布 + Homebrew formula
- 配置导入/导出（跨设备迁移）
