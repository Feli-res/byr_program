# web · 邮智汇前端

- `app/`：共用页面布局、论坛、商品、搜索、账户、个人内容及管理页面，以及 `/messages`、`/notifications`、`/dev-check` 页面。
- `lib/api.js`：统一请求、超时和错误提示。
- `lib/upload.js`、`components/files.js`：共用文件上传、进度与附件展示。
- `components/forum.js`：论坛列表、编辑、详情、评论和管理。
- `components/goods.js`、`lib/money.mjs`：商品、搜索、状态和严格金额转换。
- `components/chat.js`、`components/chat-contact.js`、`components/realtime.js`：私聊通知、联系卖家、实时连接与断线补读。
- `public/fonts/`：已下载的思源黑体中文字体、来源及 OFL 许可。
- `tests/`、`playwright.config.mjs`：真实浏览器保存、刷新、故障和窄屏检查，`acceptance.spec.mjs`把论坛、商品、搜索、聊天与通知串成同一条流程。
- `next.config.mjs`：将同源 `/api/`、`/health/` 请求转给 Rust 后端；后端地址由 `API_INTERNAL_URL` 设置。

使用 Node.js 24.14.0，依赖版本由 `package-lock.json` 固定。先按 [工程说明](../../docs/engineering/README.md) 准备数据库和后端，再启动前端。注册、登录、资料头像、改密及管理员账户管理已接入，见 [4.5 账户说明](../../docs/accounts/README.md)。4.6.1 论坛和通用上传已实现并通过本机检查，见 [论坛说明](../../docs/forum/README.md)；4.6.2 商品和关键词搜索也已实现，见 [商品说明](../../docs/goods/README.md)；4.6.3 聊天通知也已实现，见 [聊天说明](../../docs/chat/README.md)；4.6.4全流程检查也已完成，下一步4.7，AI后续接入。
