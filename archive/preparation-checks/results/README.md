# results · 已保存的检查结果

这里保存 2026 年 10 月 20 日准备阶段的结果。重新执行对应脚本会覆盖相关 JSON；这些文件记录运行当时的情况，不代表当前服务状态或正式业务验收结果。

## 文件目录

| 文件 | 对应内容 | 更新方式 |
| --- | --- | --- |
| [requirements-result.json](requirements-result.json) | 9 类功能、20 项用例编号、约定条目及链接核对 | `Check-Requirements.ps1` |
| [reference-check.json](reference-check.json) | 原候选 Rust 后端的锁文件构建检查 | `Build-Reference.ps1` |
| [reference-unit-result.json](reference-unit-result.json) | 指定的纯计算测试，未执行其他测试 | `Test-Reference.ps1` |
| [frontend-result.json](frontend-result.json) | 参考 Vue 前端构建、入口和脚本访问 | `Check-Frontend.ps1` |
| [web-tools-result.json](web-tools-result.json) | Next.js / React 最小页面构建和访问 | `Check-WebTools.ps1` |
| [rust-smoke-result.json](rust-smoke-result.json) | 配置、Salvo 内部请求、MySQL 和 Redis 读写 | `Run-Smoke.ps1` |
| [rust-restart-result.json](rust-restart-result.json) | 检查容器重启后的只读验证 | `Restart-And-Verify.ps1` |
| [environment.json](environment.json) | 本机工具、镜像版本及检查范围 | `Record-Environment.ps1`，需先启动检查容器 |
| [services-final-state.json](services-final-state.json) | 当次检查结束时两个容器已停止、数据卷保留 | 当次收尾命令保存；停止或启动后不会自动更新 |

大体积构建日志在项目根目录的 `.local/logs/`，不提交。结果解释见 [检查报告](../../../demand/4.1与4.2_检查结果与使用说明.md)，复现步骤见 [checks 说明](../README.md)。
