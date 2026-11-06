# 参考仓库

以下固定版本仅用于了解本项目的参考来源；正式应用不依赖下载或运行这些参考仓库。为避免重复保存第三方源码及其中的默认凭据，本仓库只保留来源链接。

| 参考项目 | 固定版本 | 本项目参考范围 |
| --- | --- | --- |
| hnu-doc | [d71b997](https://github.com/gygy-hh/hnu-doc/tree/d71b9976bcd6606b0e74855fda092338687218af) | Rust 服务配置、日志和通用处理思路；账户和业务按本项目重写 |
| jhserver | [8fb142e](https://github.com/gygy-hh/jhserver/tree/8fb142e049f0eac1a53abf522cb861ccd944685a) | 调度和通知思路；本项目使用自己的 Rust 实现 |
| FRAS-lab-website | [892e0b1](https://github.com/gygy-hh/FRAS-lab-website/tree/892e0b14d2a784c833597ecb9fc91f2a41b996d2) | 页面、表单和管理体验；按本项目技术栈自行实现 |

hnu-doc 和 jhserver 原版本包含 MIT 许可；第三个仓库的本地检查未发现许可文件，直接采用代码前应确认允许范围。来源与检查结论见 [复用规划](../demand/已有hub复用规划.md) 和 [准备检查](../demand/4.1与4.2_检查结果与使用说明.md)。

原本地参考快照已保存在被 Git 忽略的 `.local/public-cleanup-20261106/upstream-original/`，供本机查阅；新克隆的仓库可使用上方固定版本链接。不要把原快照、其默认凭据或私密配置重新加入公开仓库。
