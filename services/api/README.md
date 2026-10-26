# api · Rust / Salvo 后端

使用根目录 `Cargo.toml` 工作区和 `Cargo.lock`，Rust 版本见 `rust-toolchain.toml`。

| 文件 | 内容 |
| --- | --- |
| `src/main.rs` | 启动、JSON 日志、显式 `--migrate` 命令 |
| `src/lib.rs` | 配置、MySQL / Redis、请求编号、统一响应、健康检查及开发读写示例 |
| `src/accounts/` | 注册登录、会话/CSRF、资料头像、角色封禁、重置与审计 |
| `src/lib.rs` 内的 tests | 中文长度边界、公开监听限制、独立存活检查和开发接口开关/来源检查 |

`/health/live` 不依赖数据库；`/health/ready` 检查 MySQL、Redis 和迁移版本。`/api/dev/records` 是开发验证接口，不属于 4.3 的正式业务接口；默认关闭，打开时后端只允许监听回环地址，并校验浏览器 Origin。真实账户和账户权限已在 `src/accounts/` 实现，见 [4.5 说明](../../docs/accounts/README.md)；其余业务后续实现。

输入与返回遵循 4.3 的 JSON、字符串 ID、UTC 时间、错误码和请求编号约定。启动步骤见 [工程说明](../../docs/engineering/README.md)。
