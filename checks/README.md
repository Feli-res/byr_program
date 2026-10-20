# 4.1 与 4.2 的运行检查

这里是准备阶段的检查代码，不是正式论坛。用来确认电脑上的工具、参考代码、资料保存及重启读取能够工作。检查完成不会表示论坛、账户或 AI 已经实现。

本次实际结果和三个仓库的取舍见 [4.1 与 4.2 检查报告](../demand/4.1与4.2_检查结果与使用说明.md)。

## 目录与文件用途

| 目录或文件 | 用途 |
| --- | --- |
| [results/](results/README.md) | 已保存的版本、构建、读写及重启检查结果 |
| [rust-smoke/](rust-smoke/README.md) | 独立编写的 Rust、Salvo、MySQL 和 Redis 最小示例 |
| [web-smoke/](web-smoke/README.md) | 独立编写的 Next.js / React 最小页面 |
| [compose.yaml](compose.yaml) | 检查专用的 MySQL、Redis 容器和数据卷 |
| [Bootstrap-Rust.ps1](Bootstrap-Rust.ps1) | 将 Rust 工具安装到项目本机目录 |
| [Use-ProjectTools.ps1](Use-ProjectTools.ps1) | 为当前脚本设置工具路径和缓存位置，由其他脚本调用 |
| [Check-Requirements.ps1](Check-Requirements.ps1) | 核对需求编号、约定条目及相关文档链接 |
| [Prepare-Checks.ps1](Prepare-Checks.ps1) | 首次生成随机数据库密码，启动检查容器并等待就绪 |
| [Check-WebTools.ps1](Check-WebTools.ps1) | 构建 Next.js 示例，短暂启动并检查页面访问 |
| [Check-Frontend.ps1](Check-Frontend.ps1) | 在副本中构建参考 Vue 前端，检查页面和脚本访问 |
| [Build-Reference.ps1](Build-Reference.ps1) | 按原锁文件对候选 Rust 后端执行构建检查 |
| [Test-Reference.ps1](Test-Reference.ps1) | 只执行参考后端中指定的纯计算测试 |
| [Build-Smoke.ps1](Build-Smoke.ps1) | 构建独立 Rust 示例 |
| [Run-Smoke.ps1](Run-Smoke.ps1) | 执行配置、内部请求、MySQL 和 Redis 读写检查 |
| [Restart-And-Verify.ps1](Restart-And-Verify.ps1) | 重启检查容器，再只读确认先前数据仍在 |
| [Record-Environment.ps1](Record-Environment.ps1) | 记录实际工具与容器版本 |

## 本机检查使用的工具

- Node.js 24.14.0、npm 11.9.0。
- 项目内 Rust 1.99.1，Windows GNU 版本；本机使用已有的 `D:/mingw64/bin` GCC 8.1.0。其他电脑可将 `BYR_MINGW_BIN` 设置为自己的 MinGW `bin` 目录。
- Docker Desktop 的服务已启动，Docker 29.2.0、Compose 5.0.2。
- 检查用 MySQL 8.4.11、Redis 7.4.11；镜像已按实际下载标识固定。
- 独立网页使用 Next.js 16.4.2、React/React DOM 19.3.1；参考网页仍使用原锁文件中的 Vue/Vite。

工具和下载保存在忽略目录 `.local/`，不修改系统 PATH。数据库随机密码也在这个目录，不提交到仓库。检查用 MySQL、Redis 仅绑定本机 `23306`、`26379`，不会代替正式网站的数据。

## 在项目根目录按顺序运行

下列命令的 `ExecutionPolicy Bypass` 只用于这一条 PowerShell 进程，不修改系统的脚本设置。第一次需要网络下载依赖，先手动打开已安装的 Docker Desktop。

1. 初次准备 Rust，当前电脑已经装好时可跳过：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Bootstrap-Rust.ps1
   ```

2. 核对需求并启动独立资料服务：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Check-Requirements.ps1
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Prepare-Checks.ps1
   ```

3. 验证选用的前端工具及参考前端：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Check-WebTools.ps1
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Check-Frontend.ps1
   ```

   脚本会构建并短暂打开只供本机访问的检查页面，检查后关闭自己启动的进程。Vue 参考页面没有连接原 Java 后端，不将其显示内容当作完整业务验证。

4. 检查候选后端、运行不涉及学校账号的指定测试：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Build-Reference.ps1
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Test-Reference.ps1
   ```

   `Build-Reference` 按原锁文件执行 `cargo check`；指定测试会编译测试程序，只运行 `pow_correct`。没有启动原业务服务或运行学校登录及爬虫测试。

5. 构建并运行我们单独编写的小示例：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Build-Smoke.ps1
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Run-Smoke.ps1
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Restart-And-Verify.ps1
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File checks/Record-Environment.ps1
   ```

   小示例检查配置读取、Salvo 程序内部的一次模拟请求、MySQL 和 Redis 的写入读取；最后重启检查容器，再只读验证先前数据。它不启动正式论坛，也不创建论坛用户和业务表。

## 查看结果和停止服务

结果保存在 `checks/results/`，较大的构建日志保存在 `.local/logs/`。正式功能的 20 项验收用例仍待实现后执行。

只停止本次检查服务，保留数据供下次验证：

```powershell
docker compose --env-file .local/checks.env -f checks/compose.yaml stop
```

再次需要时运行 `Prepare-Checks.ps1`。不要用删除数据卷的方式代替重启验证。

2026 年 10 月 20 日的检查结束时已停止两个检查容器，保留数据卷；这是当时的记录，当前运行状态请在 Docker 中查看。返回 [项目总目录](../README.md)。
