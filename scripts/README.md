# scripts · 正式工程运行命令

在项目根目录执行。Windows 使用 PowerShell 脚本；Python 入口供 Linux、macOS、WSL 和自动检查使用。

| 脚本 | 用途 |
| --- | --- |
| `Prepare-Dev.ps1` | 生成随机本机配置，启动独立数据库，构建后端、执行迁移及构建前端 |
| `Start-Dev.ps1` | 启动数据库、后端与网页，记录自己启动的进程；默认支持前端热更新 |
| `Stop-Dev.ps1` | 只停止记录的进程及其子进程、开发专用容器，保留数据 |
| `Init-Admin.ps1` | 交互创建首位管理员，不回显密码；已存在管理员时拒绝再次初始化 |
| `Verify-Acceptance.ps1` | 构建一次，执行工程/账户/论坛/商品/聊天回归及4.6跨模块验收 |
| `verify_acceptance.py` | 同批数据全流程、管理联动、旧登录跨业务拒绝、重启和原账号保护；`--regressions`加跑旧验收 |
| `Verify-Chat.ps1` | 4.6.3 完整验收：构建、独立临时库、真实WebSocket、聊天通知及浏览器 |
| `verify_chat.py` | 聊天去重补读、票据、登录撤销、通知权限、推送故障及重启检查 |
| `Verify-Goods.ps1` | 4.6.2 完整验收：构建、金额、独立临时库、商品/搜索/文件及浏览器 |
| `verify_goods.py` | 商品、价格状态、搜索、权限、并发、故障与重启的隔离验收 |
| `Verify-Forum.ps1` | 4.6.1 完整验收：构建、独立临时库、论坛上传、权限、故障与浏览器 |
| `verify_forum.py` | 论坛接口、并发编辑、文件、版面管理及重启的隔离验收 |
| `Verify-Accounts.ps1` | 完整4.5验收：单元、构建、隔离临时库、真实接口与浏览器 |
| `verify_accounts.py` | 隔离临时库的账户、安全、头像、并发、故障和重启验收 |
| `Verify-Dev.ps1` | 格式检查、Rust 测试、构建及完整运行验证；检查时需要开发端口空闲 |
| `Use-ProjectTools.ps1` | 正式工具路径设置，不依赖归档检查目录 |
| `test_support/` | 共用进程、临时数据库、客户端和样例，见 [说明](test_support/README.md) |
| `Use-DevEnvironment.ps1` | 读取设置；已有项目内 Rust 工具时自动使用，否则使用系统 Rust |
| `dev.py` | 跨平台配置生成、数据库启动、迁移及前后端前台启动 |
| `verify_runtime.py` | 真实 HTTP、SQL 迁移、浏览器、数据库故障与重启读取；结束停止本次程序和开发容器，保留数据卷 |

Windows 的完整命令、跨平台步骤和第二台电脑清单见 [工程说明](../docs/engineering/README.md)。较大日志与截图保存在 `.local/logs/dev/`，结果摘要保存在 `docs/engineering/runtime-verification.json`。

4.5 的页面与操作顺序见 [账户说明](../docs/accounts/README.md)。4.6.1 见 [论坛和上传说明](../docs/forum/README.md)，其日志与截图在 `.local/logs/forum/`。4.6.2 见 [商品和搜索说明](../docs/goods/README.md)，日志与截图在 `.local/logs/goods/`。4.6.3 见 [聊天和通知说明](../docs/chat/README.md)，日志与截图在 `.local/logs/chat/`。4.6整体见 [验收说明](../docs/acceptance/README.md)，新日志与截图在`.local/logs/acceptance/`。
