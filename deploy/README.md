# deploy · 本地与服务器运行配置

> 隐私说明（2026-11-06）：服务器地址、站点域名和登录用户名已替换为示例标记；实际目标保存在本机私有配置中。历史验收数字保持原样。

| 文件 | 用途 |
| --- | --- |
| `compose.dev.yaml`、`.env.example` | 本机 MySQL、Redis 配置，继续使用独立开发数据 |
| `compose.prod.yaml` | 服务器前端、API、MySQL、Redis与持久数据卷 |
| `Dockerfile.api`、`Dockerfile.web` | Linux 正式镜像构建；API以普通用户运行 |
| `production.env.example` | 无真实密码的正式设置示例 |
| `server-target.example.json` | 服务器目标配置示例；复制到被忽略的 `.local/server-target.json` 后私下填写 |
| `nginx.prod.conf.example` | 本次试用站入口规则示例，网关密钥须替换 |
| `manage.sh` | 服务器启动、停止、重启、日志和手动备份 |
| `update.sh` | 构建新版本、备份、迁移、启动和检查 |
| `youzhihui-backup.service`、`youzhihui-backup.timer` | 每日配套备份的定时任务模板 |
| `backup.sh` | 数据库、上传、设置和版本配套备份，保留最近14份 |
| `backup_inventory.py` | 网站停止写入时记录所有表精确行数和上传文件 SHA256；与新版 `backup.sh` 成对安装 |
| `compose.restore412.yaml` | 4.12 全新独立恢复容器及卷，仅 loopback 18103 入口；不与 trial 共用数据库或上传卷 |

本机 `.env` 与服务器 `.env.prod` 各自保存，禁止互相覆盖或提交。将 `manage.sh`、`update.sh`、`backup.sh` 放在服务器项目的 `shared/` 下时，它们自动以 `shared/` 的父目录作为项目根；也可通过 `YOUZHIHUI_BASE` 指定。安装 `youzhihui-backup.service` 前需将示例 `/srv/youzhihui` 改成实际路径。

本机服务器工具读取 `.local/server-target.json` 中的 `host`、`ssh_user`、`base_dir`、`origin`，也可分别使用 `YOUZHIHUI_SERVER_HOST`、`YOUZHIHUI_SSH_USER`、`YOUZHIHUI_BASE`、`YOUZHIHUI_ORIGIN` 环境变量。密码继续单独保存在 `.local/ssh-password.txt` 或 `YOUSHIZHUI_SSH_PASSWORD`，SSH 主机指纹保存在 `.local/server-known-hosts`。这些文件均不得提交。

本机步骤见 [工程说明](../docs/engineering/README.md)；公网地址与服务器命令见 [服务器使用说明](../邮智汇_服务器使用说明.md)，检查结果见 [4.7记录](../docs/deployment/README.md)。

停止容器会保留数据；不要使用删卷命令代替停止。

完整独立恢复方法见 [4.12 恢复演练](../docs/final/恢复演练.md)。工具已准备；是否实际恢复通过，以该目录真实记录为准。
