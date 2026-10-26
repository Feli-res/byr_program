# web · 邮智汇前端

- `app/`：共用页面布局、论坛、账户、个人内容及管理页面，以及 `/dev-check` 联通检查页。
- `lib/api.js`：统一请求、超时和错误提示。
- `lib/upload.js`、`components/files.js`：共用文件上传、进度与附件展示。
- `components/forum.js`：论坛列表、编辑、详情、评论和管理。
- `public/fonts/`：已下载的思源黑体中文字体、来源及 OFL 许可。
- `tests/`、`playwright.config.mjs`：真实浏览器保存、刷新、故障和窄屏检查。
- `next.config.mjs`：将同源 `/api/`、`/health/` 请求转给 Rust 后端；后端地址由 `API_INTERNAL_URL` 设置。

使用 Node.js 24.14.0，依赖版本由 `package-lock.json` 固定。先按 [工程说明](../../docs/engineering/README.md) 准备数据库和后端，再启动前端。注册、登录、资料头像、改密及管理员账户管理已接入，见 [4.5 账户说明](../../docs/accounts/README.md)。4.6.1 论坛和通用上传已实现并通过本机检查，见 [论坛说明](../../docs/forum/README.md)；商品、搜索、聊天和 AI 后续实现。
