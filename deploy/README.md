# deploy · 本地与服务器运行配置

| 文件 | 用途 |
| --- | --- |
| `compose.dev.yaml`、`.env.example` | 本机 MySQL、Redis 配置，继续使用独立开发数据 |
| `compose.prod.yaml` | 服务器前端、API、MySQL、Redis与持久数据卷 |
| `Dockerfile.api`、`Dockerfile.web` | Linux 正式镜像构建；API以普通用户运行 |
| `production.env.example` | 无真实密码的正式设置示例 |
| `nginx.prod.conf.example` | 本次试用站入口规则示例，网关密钥须替换 |
| `manage.sh` | 服务器启动、停止、重启、日志和手动备份 |
| `update.sh` | 构建新版本、备份、迁移、启动和检查 |
| `youzhihui-backup.service`、`youzhihui-backup.timer` | 每日配套备份的定时任务模板 |
| `backup.sh` | 数据库、上传、设置和版本配套备份，保留最近14份 |

本机 `.env` 与服务器 `.env.prod` 各自保存，禁止互相覆盖或提交。正式脚本当前按 `/home/sunxiang/youzhihui` 配置，不能直接用于其他目录或项目。

本机步骤见 [工程说明](../docs/engineering/README.md)；公网地址与服务器命令见 [服务器使用说明](../邮智汇_服务器使用说明.md)，检查结果见 [4.7记录](../docs/deployment/README.md)。

停止容器会保留数据；不要使用删卷命令代替停止。
