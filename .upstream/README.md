# 参考源码目录

这里保存固定版本的原始参考源码和 ZIP，供阅读、比较及后续迁移使用。源码已保存不表示已完成构建、迁移或功能验收。

## hnu doc

`hnu-doc-d71b9976bcd6606b0e74855fda092338687218af/` 是 Rust 试卷资料库后端。主要参考配置、日志、中间件、数据库和缓存连接等通用组件；平台账户、论坛业务和搜索需要重写。来源为 [hnu-doc 固定版本](https://github.com/gygy-hh/hnu-doc/tree/d71b9976bcd6606b0e74855fda092338687218af)。

## jhserver

`jhserver-8fb142e049f0eac1a53abf522cb861ccd944685a/` 是 C++ 游戏服务器。主要参考到期任务调度、游戏邮件、会话撤销及后台管理设计，相关能力按论坛需求用 Rust 实现，不运行第二套游戏业务服务。来源为 [jhserver 固定版本](https://github.com/gygy-hh/jhserver/tree/8fb142e049f0eac1a53abf522cb861ccd944685a)。

## FRAS lab website

`FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2/` 是 Java/Vue 实验室官网。`frontend/` 提供公开页面及管理界面，`backend/` 提供认证、内容 CRUD、上传及迁移，`docs/` 保存过程说明，`deploy.ps1` 是原站部署脚本。主要借鉴页面、内容管理和分层设计；原始源码保持不变，示例配置及部署脚本不直接用于本项目。来源为 [FRAS-lab-website 固定版本](https://github.com/gygy-hh/FRAS-lab-website/tree/892e0b14d2a784c833597ecb9fc91f2a41b996d2)，归档和校验信息见 [来源记录](E:/program_design_experiment/.upstream/FRAS-lab-website.source.json)。

具体复用动作见 [三个仓库复用规划](E:/program_design_experiment/demand/已有hub复用规划.md)，项目缺口和开发顺序见 [代码评估与后续计划](E:/program_design_experiment/demand/现有代码评估与后续开发计划.md)。
