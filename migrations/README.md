# migrations · 正式数据库版本

1. `0001_accounts_and_shared.sql`：账户、会话、板块、字典及文件基础表。
2. `0002_forum_goods_messages_monitoring.sql`：论坛、商品、私聊、监控、通知、治理和索引等表及初始字典。
3. `0003_development_records.sql`：与真实业务分开的 `dev_records` 测试表。
4. `0004_account_security.sql`：账户/IP登录失败限制，跨 Redis 和服务重启保留。
5. `0005_chat_session_reasons.sql`：增加登录撤销原因，供实时连接区分退出、改密、重置和封禁；不新建表。

前两个文件承接 [4.3 建表草案](../docs/design/schema.sql) 的 32 张表，账户、论坛、商品搜索和私聊通知接口已按 4.5—4.6.3 实现，AI、监控等后续实现。加开发测试表、账户安全表共 34 张应用表；SQLx 另建 `_sqlx_migrations` 记录已执行版本。

通过 API 的 `--migrate` 命令执行，不要求额外安装 SQLx CLI。执行过的文件保持不变，后续调整另加新版本；`.gitattributes` 禁止 Git 改写迁移换行符，避免跨平台校验和变化。MySQL 建表会隐式提交，失败时需要排查已执行的 DDL，不能认为全部自动回滚。先在开发空库验证，正式服务器部署属于后续阶段。
