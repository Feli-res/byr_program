# scripts · 正式工程运行命令

在项目根目录执行。Windows 使用 PowerShell 脚本；Python 入口供 Linux、macOS、WSL 和自动检查使用。

| 脚本 | 用途 |
| --- | --- |
| `verify_final412.py`、`final412-browser.cjs` | 4.12 真实 HTTPS/WSS 流程、管理、暂停整周期、重启/恢复读取及浏览器页面检查；专用密码留在 `.local` |
| `server412.py`、`restore412.py`、`test_restore412.py` | 校验既有 SSH 指纹的更新/备份/下载、完整独立恢复及备份安全检查；步骤见 [4.12 交付](../docs/final/README.md) |
| `package_final412.py` | 打包当前源码与验收说明，排除私密设置和构建缓存，生成逐文件及整包 SHA256 |
| `Prepare-Dev.ps1` | 生成随机本机配置，启动独立数据库，构建后端、执行迁移及构建前端 |
| `Start-Dev.ps1` | 启动数据库、后端与网页，记录自己启动的进程；默认支持前端热更新 |
| `Stop-Dev.ps1` | 只停止记录的进程及其子进程、开发专用容器，保留数据 |
| `Init-Admin.ps1` | 交互创建首位管理员，不回显密码；已存在管理员时拒绝再次初始化 |
| `Verify-Acceptance.ps1` | 构建一次，执行工程/账户/论坛/商品/聊天回归及4.6跨模块验收 |
| `verify_acceptance.py` | 同批数据全流程、管理联动、旧登录跨业务拒绝、重启和原账号保护；`--regressions`加跑旧验收 |
| `verify_ai48.py`、`ai48-browser.cjs` | 4.8 独立数据库、真实本机向量检索和浏览器验收；需预先构建前后端并启动本机向量服务 |
| `Verify-Reminders.ps1` | 4.9 完整验收：格式、Clippy、单元测试、前后端构建、独立临时库与浏览器提醒流程 |
| `verify_reminders.py`、`reminders-browser.cjs` | 订阅创建、全量/增量检查、去重、暂停恢复、封禁、重试、重启和浏览器保存提醒 |
| `seed_411.py`、`load_411.py`、`guard_411.py`、`check_411.py` | 4.11 服务器 411 隔离栈造数、20 HTTP + 10 WebSocket + 提醒混合负载、保护监控和只读计数；只连 411，不连 trial |
| `Verify-Admin.ps1` | 4.10 完整验收：格式、Clippy、单元测试、前后端构建、独立临时库与浏览器管理流程 |
| `verify_admin.py`、`admin-browser.cjs` | 四类举报、公告、板块、任务、审计、联动和重启检查 |
| `Verify-Pagination.ps1` | 论坛分页验收：构建、页码窗口、独立临时库和真实浏览器翻页 |
| `verify_pagination.py`、`pagination-browser.cjs` | 45 条帖子的 20/20/5 分页、页码、跳页校验、边界和窄屏 |
| `test_pagination.mjs` | 页码窗口的纯函数检查：首页/末页、省略号、越界夹取 |
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
