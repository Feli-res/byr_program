# web · 邮智汇前端

- `app/`：正式论坛、商品、搜索、消息、通知、账户和管理页面。
- `components/forum/`、`goods/`、`chat/`：按列表、编辑、详情等用途拆分，见 [组件目录](components/README.md)。同名JS保留页面导入入口。
- `components/shared/content.js`、`lib/use-data.js`：共用显示与列表读取，切换账号清除旧内容，聊天后台刷新保留当前视图。
- `lib/api.js`、`lib/upload.js`、`components/files.js`：统一请求、超时、上传和附件。
- `lib/money.mjs`、`tests/unit/money.test.mjs`：严格金额转换和单元测试。
- `tests/*.spec.mjs`、`playwright.config.mjs`：真实浏览器流程、权限、故障、窄屏及换号缓存检查；不扫描unit目录。
- `public/fonts/`：正式网页本地中文字体、来源和OFL许可。
- `next.config.mjs`：本机同源API转发；服务器按需生成standalone镜像，由Nginx直接转发API与WebSocket，关闭开发入口。

按 [工程说明](../../docs/engineering/README.md)准备与启动。4.6已完成并通过 [整体验收](../../docs/acceptance/README.md)，4.7已提供HTTPS试用站，见 [服务器说明](../../邮智汇_服务器使用说明.md)；下一步进入4.8接入AI搜索与匹配。HTML草图在 [归档目录](../../archive/early-docs/page-drafts/README.md)。
