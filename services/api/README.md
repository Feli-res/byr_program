# api · Rust / Salvo 后端

使用根目录 `Cargo.toml` 工作区和 `Cargo.lock`，Rust 版本见 `rust-toolchain.toml`。

| 文件 | 内容 |
| --- | --- |
| `src/main.rs` | 启动、JSON 日志、显式 `--migrate` 命令 |
| `src/lib.rs` | 配置、MySQL / Redis、请求编号、统一响应、健康检查及开发读写示例 |
| `src/access.rs` | 各业务共用原账户的身份、请求保护及错误处理规则 |
| `src/goods.rs`、`src/search.rs` | 商品、字典、图片、状态、管理及统一关键词搜索 |
| `src/chat/` | 私聊持久化、通知、单次票据、WebSocket、登录失效和有限推送重试 |
| `src/content.rs` | 帖子与商品共用的持久变更计数和搜索更新记录 |
| `src/forum.rs` | 帖子评论、点赞收藏、个人列表、版面管理及内容变更记录 |
| `src/accounts/` | 注册登录、会话/CSRF、资料头像、角色封禁、重置与审计 |
| `src/lib.rs` 内的 tests | 中文长度边界、公开监听限制、独立存活检查和开发接口开关/来源检查 |

`/health/live` 不依赖数据库；`/health/ready` 检查 MySQL、Redis 和迁移版本。`/api/dev/records` 是开发验证接口，不属于 4.3 的正式业务接口；默认关闭，打开时后端只允许监听回环地址，并校验浏览器 Origin。真实账户和账户权限已在 `src/accounts/` 实现，见 [4.5 说明](../../docs/accounts/README.md)；4.6.1 论坛及通用上传也已实现，见 [论坛说明](../../docs/forum/README.md)。4.6.2 商品与关键词搜索已实现，见 [商品说明](../../docs/goods/README.md)；4.6.3 聊天通知也已实现，见 [聊天说明](../../docs/chat/README.md)；4.6.4已验证跨业务权限、管理联动与重启，见 [整体验收](../../docs/acceptance/README.md)；AI与持续提醒后续实现。

输入与返回遵循 4.3 的 JSON、字符串 ID、UTC 时间、错误码和请求编号约定。启动步骤见 [工程说明](../../docs/engineering/README.md)。

4.7增加可选的`TRUSTED_PROXY_KEY`。只有密钥正确且访客IP合法时，登录限流才采用网关覆盖后的来源；未配置时仍按直接连接地址处理。正式API使用普通用户与独立上传卷，见 [部署说明](../../docs/deployment/README.md)。
