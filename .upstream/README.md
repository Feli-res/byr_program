# .upstream · 参考源码

这里保存三个参考仓库的固定版本源码和 ZIP，供阅读、比较及后续采用。仓库内部的文件保持原样，项目自身的改写和验证放在其他目录。

## 目录

| 源码目录 | 原用途及本项目参考范围 |
| --- | --- |
| [hnu-doc-d71b9976bcd6606b0e74855fda092338687218af/](hnu-doc-d71b9976bcd6606b0e74855fda092338687218af/) | Rust 试卷资料库后端。参考配置、日志、中间件、数据库及缓存连接；自主账户和论坛业务重写。 |
| [jhserver-8fb142e049f0eac1a53abf522cb861ccd944685a/](jhserver-8fb142e049f0eac1a53abf522cb861ccd944685a/) | C++ 游戏服务器。参考到期任务和通知思路，用 Rust 实现论坛周期监控，不接入整套游戏服务。 |
| [FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2/](FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2/) | Java/Vue 实验室官网。参考页面、表单、上传和内容管理，按 React/Rust 重写。 |

| 归档与记录 | 说明 |
| --- | --- |
| [hnu-doc.zip](hnu-doc.zip) | hnu-doc 的本地源码归档 |
| [jhserver.zip](jhserver.zip) | jhserver 的本地源码归档 |
| [FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2.zip](FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2.zip) | 第三个仓库的固定版本归档 |
| [FRAS-lab-website.source.json](FRAS-lab-website.source.json) | 第三个仓库的来源与校验记录 |

第三个仓库内，`frontend/` 是公开及管理页面，`backend/` 是认证、内容管理、上传和数据库调整代码，`docs/` 是过程说明，`deploy.ps1` 是原站部署脚本。

## 原仓库及检查结果

| 仓库 | 固定版本来源 | 2026 年 10 月 20 日的检查结果 |
| --- | --- | --- |
| hnu-doc | [原始版本](https://github.com/gygy-hh/hnu-doc/tree/d71b9976bcd6606b0e74855fda092338687218af) | 按锁文件检查及一项纯计算测试通过；未运行学校登录或原业务服务 |
| jhserver | [原始版本](https://github.com/gygy-hh/jhserver/tree/8fb142e049f0eac1a53abf522cb861ccd944685a) | 已阅读调度代码；未编译、运行游戏服务器 |
| FRAS-lab-website | [原始版本](https://github.com/gygy-hh/FRAS-lab-website/tree/892e0b14d2a784c833597ecb9fc91f2a41b996d2) | 前端副本构建和 HTTP 检查通过；未运行 Java 后端 |

## 使用说明

hnu-doc 工作区声明 MIT，jhserver 包含 MIT 许可；实际采用代码时核实并保留相应版权与许可。第三个仓库快照未发现许可文件，确认允许范围前参考设计、自行编写。原站账号、密码、密钥、图片及部署脚本不直接用于本项目。

详细取舍见 [仓库复用规划](../demand/已有hub复用规划.md)，真实检查结果见 [4.1 与 4.2 报告](../demand/4.1与4.2_检查结果与使用说明.md)，复现命令见 [检查代码说明](../checks/README.md)。返回 [项目总目录](../README.md)。
