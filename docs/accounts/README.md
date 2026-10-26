# 4.5 · 自主账户和身份限制

日期：2026 年 10 月 26 日。开发依据：[T01](../../demand/T01_首版需求基线与验收清单.md) 与 [4.3 接口设计](../design/03_接口与消息约定.md)。使用平台自主账号，不接校园 CAS。

## 页面和使用顺序

启动方法沿用 [4.4 工程说明](../engineering/README.md)。升级已有环境先停止项目程序，再执行 `scripts/Prepare-Dev.ps1`；脚本保留原数据库密码和数据，补充本机认证密钥并执行新迁移。

| 页面 | 可以做什么 |
| --- | --- |
| `/register` | 注册普通用户；成功后进入登录，不自动登录 |
| `/login` | 登录；错误、封禁、需重置和频率限制均有明确提示 |
| `/profile` | 查看账号、角色和会话期限；修改昵称、简介和头像 |
| `/change-password` | 验证原密码并修改；成功后全部旧会话失效，重新登录 |
| `/reset-password` | 使用管理员核实后签发的一次性凭据设置新密码 |
| `/admin/users` | 管理员按原因授权角色/板块、封禁或解封、签发重置凭据 |

只需要浏览器操作这些页面。前端显示权限仅用于界面体验，后端每次请求都会重新检查会话、账号状态、角色及资源归属。

## 创建第一位管理员

不提供公开“注册管理员”入口。先启动 Docker 并完成准备，再在项目根目录的 PowerShell 中执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Init-Admin.ps1
```

按提示输入账号、昵称和两次密码。密码输入不会回显；没有示例密码或通用管理员账号。已存在任何管理员时，该初始化命令会拒绝再次创建。后续管理员由已授权管理员分配，不能通过注册字段指定。

Linux / WSL 可以执行 `python3 scripts/dev.py init-admin`。命令也支持从标准输入读取注册格式 JSON，仅供隔离测试使用；不要将真实密码写入脚本、命令参数、仓库或终端历史。

## 后端实现入口

| 文件 | 内容 |
| --- | --- |
| [accounts/mod.rs](../../services/api/src/accounts/mod.rs) | 账户接口、会话与请求保护、资料、权限、管理员初始化和审计 |
| [accounts/security.rs](../../services/api/src/accounts/security.rs) | Argon2id、随机令牌、摘要及带签名且绑定会话的 CSRF 凭据 |
| [accounts/files.rs](../../services/api/src/accounts/files.rs) | 头像解码、大小/归属/配额、绑定与清理 |
| [0004_account_security.sql](../../migrations/0004_account_security.sql) | 登录失败计数和限制期限；保存在 MySQL 中，Redis 重启不会清空限制 |
| [verify_accounts.py](../../scripts/verify_accounts.py) | 独立临时数据库中的真实接口、故障、并发及浏览器检查 |
| [accounts.spec.mjs](../../apps/web/tests/accounts.spec.mjs) | 账户与管理员页面、头像、改密、重置及数据库故障检查 |

接口使用 `/api/v1` 设计中的字段，返回字符串 ID、UTC 时间、请求编号及统一错误。当前只实现账户相关操作和头像文件能力；帖子/商品文件类型在对应业务阶段实现。

## 已固定的账户规则

- 账号按 ASCII 规则校验、去首尾空白并转小写后判断唯一。注册只得到 `user`。
- 密码 8～64 个 Unicode 码点，不截断、不去空白。Argon2id v19：内存 19 MiB、迭代 2、并行度 1；使用独立随机盐。同时最多执行两项密码计算，避免占满开发机资源。
- 会话令牌使用 32 字节随机数，数据库只存 SHA-256 摘要。浏览器 Cookie 为 host-only、HttpOnly、SameSite=Lax；正式 HTTPS 配置 `COOKIE_SECURE=true`。
- 会话绝对有效 7 天，不静默续期；退出只撤销当前会话，改密、重置、封禁撤销全部会话。每个受保护请求重新检查数据库状态。
- 写请求必须携带签名且绑定当前会话/匿名身份的 CSRF Cookie 和请求头，并匹配配置的完整 Origin。前端统一请求方法负责获取，密码和令牌不放在 URL。
- 同一账号或后端识别的源 IP 在 15 分钟累计 5 次登录失败后限制 15 分钟，返回 `Retry-After`。当前本机代理请求共享回环 IP 桶，且不信任任意转发头；服务器试部署时需要按真实代理链配置可信客户端 IP 识别。
- 管理员重置凭据最长 30 分钟，一次使用，仅允许改密；签发时撤销旧凭据和会话，成功后重新登录。
- 管理角色变动、封禁和重置按统一锁顺序执行，保护最后一个可用管理员；普通用户和版主不能调用账户管理接口。封禁暂停有效监控任务，解封不自动恢复。
- 管理操作保存原因及安全变化字段；访问日志和审计不保存密码、Cookie、重置凭据或私人资料正文。

密码与请求保护的实现参考 [OWASP 密码存储建议](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) 和 [CSRF 建议](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)。这不是对外部署后的完整安全审计。

## 头像与数据保存

只接受真实解码通过、类型和扩展名一致的 JPEG、PNG、WebP，最多 2 MiB；最长边 4096 像素，解码预算 64 MiB。用户总文件配额仍为 200 MiB。文件以服务器生成的随机文件名保存在 `UPLOAD_ROOT`，不暴露磁盘路径。

未绑定文件只能上传者读取；绑定为头像后公开读取。替换或移除后旧文件立即不可读取，进入清理；实际删除后才返还配额。未绑定文件 24 小时到期，每小时分批清理；也可在已载入运行设置后执行 API 的 `--cleanup-files` 命令。读取总会先检查当前绑定状态，不把目录作为静态资源直接开放。

`AUTH_SECRET`、`COOKIE_SECURE`、`UPLOAD_ROOT` 在 `deploy/.env.example` 中有示例。真实密钥首次随机生成后保存在被忽略的 `deploy/.env`，重启沿用同一份；不要每次启动重新生成。已有三个迁移版本保持原样，新能力由第四个迁移补充。

## 本机验收

先停止开发程序，再执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Verify-Accounts.ps1
```

实际结果见 [verification.json](verification.json)。测试使用随机账号、仅由本次创建的 `byr_accounts_…` 临时库及合成图片，结束后撤销该临时库的授权并删除该库，不修改开发库里的真实用户。截图和日志在 `.local/logs/accounts/`；不会对显示重置凭据的页面截图。

验证会把已实现接口的 JSON 响应与 4.3 OpenAPI 契约逐项比较。Windows 脚本会优先使用已有检查依赖，缺少时安装到被忽略的 `.local/accounts-qa/python`；Linux 可先执行 `python3 -m pip install --target .local/accounts-qa/python -r docs/accounts/requirements-tests.txt`，再运行 `python3 scripts/verify_accounts.py`。

本机验收覆盖注册、会话、请求保护、头像、权限、重置、并发保护和故障恢复。第二台电脑独立安装为选做；最终交付目标是在服务器运行，用户通过网址访问。

**仍待后续验证：**AC02 中撤销后实时连接 5 秒内关闭，需等 4.6 接入 WebSocket；服务器部署、HTTPS、真实代理链、性能和备份恢复在后续阶段验证。当前不能把这些项标为通过。

下一步 **4.6：论坛、商品和聊天**。返回 [项目首页](../../README.md)。
