# deploy · 本地运行配置

- `compose.dev.yaml`：独立的 `youzhihui-dev` MySQL、Redis 和持久数据卷，不使用 `youzhihui-checks` 的数据。
- `.env.example`：无真实密码的设置示例。
- `.env`：准备脚本首次生成的随机密码和本机设置，已被 Git 忽略。

默认网页 `http://localhost:3000`、API `127.0.0.1:8080`、MySQL `127.0.0.1:23307`、Redis `127.0.0.1:26380`。全部绑定本机，未部署云服务器。停止命令保留数据卷，之后启动仍能读取原记录。不要将删卷当作日常停止方法。

完整命令见 [4.4 使用说明](../docs/engineering/README.md)。

4.5 增加 `AUTH_SECRET`、`COOKIE_SECURE`、`UPLOAD_ROOT`。准备脚本会为旧本机配置补随机密钥，保留已有数据库密码。真实密钥只保存在被忽略的 `.env`，跨重启保持稳定。
