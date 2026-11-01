# 邮智汇 · 程序设计实验

邮智汇是以校园讨论为主体的综合论坛，提供论坛交流、二手商品信息、站内消息、AI 商品匹配与持续提醒，并计划探索论坛侧的相似帖子提示。使用自主账号，不接校园 CAS，也不代表用户已通过校园身份认证。

**更新日期：2026 年 10 月 31 日。4.10 管理页面与功能联动已在本机验收并更新试用站；4.8 AI 功能和 4.9 商品提醒也已在试用站运行。**

## 服务器试用

网站：**<https://youzhihui.85-121-122-124.sslip.io>**。同学可直接注册使用，不需要安装开发工具。服务器使用独立新数据库，本机三个账号与资料没有迁移或覆盖。

已通过公网双会话发帖、上传、商品搜索和实时私聊检查，完成可信来源限流、权限、更新备份与容器重启后的资料核对。4.8 AI 功能和 4.9 商品提醒已更新到试用站；4.10 已更新至 `trial-20261031-02`，四类举报、公告、板块和任务管理页已可用，线上完成公告首页可见、管理页加载和窄屏检查。每日备份已启用，已下载一份到本机；尚未设置自动异地同步，也未做正式负载测试或完整独立恢复演练。

入口：[服务器使用说明](邮智汇_服务器使用说明.md) · [部署与更新记录](docs/deployment/README.md)。

## 4.6 已完成什么

| 板块 | 网页上能做什么 | 后台已经处理什么 |
| --- | --- | --- |
| 4.6.1 论坛和上传 | 发帖编辑、回复、点赞收藏、我的内容；选择图片和PDF | 真实保存、分页、文件归属与大小数量检查、版面授权、隐藏删除后的文件访问 |
| 4.6.2 商品和普通搜索 | 发布编辑商品、图片排序、预留已售下架；关键词和价格校区筛选 | 整数分、商品状态、版本冲突、管理员限制、帖子商品统一搜索及当前权限过滤 |
| 4.6.3 聊天和通知 | 联系卖家、双方实时文字聊天、历史未读、通知列表与已读 | 会话复用、先存后确认、重试去重、离线补读、私聊成员权限、旧登录连接失效 |
| 4.6.4 全流程验收 | 同一批数据完成“登录→发帖回复→发布商品→搜索→联系卖家→聊天→通知” | 管理联动、改密封禁、故障恢复、重启后数据一致，以及原有功能回归 |

本轮新增8组跨模块检查、3个真实浏览器测试通过；工程、账户、论坛、商品、聊天回归全部通过，14项Rust单元测试和3项金额测试通过，前后端构建通过。详情见 [4.6整体验收](docs/acceptance/README.md) 与 [逐项验收范围](docs/acceptance/验收范围.md)。

4.8 已接入关键词与语义搜索、AI 商品需求解析与条件筛选、帖子举报及 AI 辅助建议，并完成独立环境与服务器基本流程验证，见 [4.8 使用与验收](docs/ai48/README.md)。4.9 商品订阅与持续提醒也已在本机完成并验收，并更新到试用站：保存条件后按周期检查、首轮逐件提醒当前符合商品、同一商品不重复通知，并处理暂停、删除、售出、封禁、失败重试和重启恢复；说明见 [4.9 使用与验收](docs/reminders/README.md)。论坛侧已选定“相似帖子提示”为 AI 选做；社区首页和校园求助是推荐增加的方向，组队招募及板块自主管理有余力再做，均需另行开发和验收。4.6本轮记录不代表AI效果或完整性能通过；4.7基础功能服务器部署的独立结果见上方入口。

## 4.10 已完成什么

| 内容 | 实际结果 |
| --- | --- |
| 统一管理入口 | `/admin` 概览和按角色菜单；管理员、版主只看到自己有权使用的页面 |
| 四类举报 | 帖子、评论、商品、私信均可提交、去重、查看和裁定；版主只处理授权板块，商品和私信仅管理员 |
| 管理联动 | 隐藏帖子后搜索和旧地址失效；隐藏评论后正文不再返回；商品下架后搜索、AI 匹配和提醒不再接受 |
| 公告 | 草稿、发布、撤回；草稿和撤回内容公开接口 404；首页和 `/announcements` 只显示已发布内容 |
| 板块与任务 | 新建、改名、启停板块；停用后不能新发帖但历史帖可读；任务列表脱敏并支持暂停 |
| 审计 | 记录操作者、动作、对象、原因、时间和安全变化，不记录私信正文或私人条件 |
| 验收 | 11 组后端检查、1 个浏览器场景、23 项 Rust 单元测试通过；论坛、商品、聊天回归通过 |

说明见 [4.10 使用与验收](docs/admin/README.md)，逐项结果见 [验收记录](docs/admin/verification.json)。本阶段不新增数据库迁移，旧 `post-reports` 入口保留兼容；论坛体验扩展仍为选做，未实现。

目录整理已完成：旧示例和草图归档，测试辅助方法共用，前端按用途拆分。重新构建后的文件体积约从20.29 GB降至7.41 GB，详见 [整理结果](docs/maintenance/README.md)。

## 从哪里开始看

| 想了解什么 | 阅读入口 |
| --- | --- |
| 服务器网址与日常操作 | [服务器使用说明](邮智汇_服务器使用说明.md) |
| 当前有哪些成果、哪些还没做 | [当前成果汇报](邮智汇_当前成果汇报.md) |
| 4.8 功能怎么用、做过哪些检查 | [4.8 使用与验收](docs/ai48/README.md) · [帖子举报设计](docs/design/06_帖子举报与AI辅助处理.md) · [共用 AI 接口设计](docs/design/07_共用AI调用接口.md) |
| 4.9 商品提醒怎么用、验证了什么 | [4.9 使用与验收](docs/reminders/README.md) · [实施计划](docs/reminders/PLAN.md) |
| 4.10 管理页面怎么用、验证了什么 | [4.10 使用与验收](docs/admin/README.md) · [验收记录](docs/admin/verification.json) |
| 项目是什么、全过程怎么完成 | [项目计划书](邮智汇_程设项目计划书.md) |
| 综合论坛定位及创新方向 | [综合论坛创新方向](demand/邮智汇_综合论坛创新方向.md)，包含已选择的相似帖子提示 |
| 第一版必须做什么、怎样检查 | [T01 需求与验收清单](demand/T01_首版需求基线与验收清单.md) |
| 怎样启动、停止和检查程序 | [工程运行说明](docs/engineering/README.md) · [账户功能说明](docs/accounts/README.md) · [论坛与上传说明](docs/forum/README.md) · [商品与搜索说明](docs/goods/README.md) · [聊天与通知说明](docs/chat/README.md) |
| 4.6全流程怎样验收、哪些项目仍待做 | [整体验收说明](docs/acceptance/README.md) · [范围表](docs/acceptance/验收范围.md) |
| 文件夹怎样精简 | [整理结果与目录盘点](docs/maintenance/README.md)，已归档旧资料、清理缓存并合并重复辅助代码 |
| 页面计划做成什么样 | [HTML 页面草图](archive/early-docs/page-drafts/index.html) · [打开说明](archive/early-docs/page-drafts/README.md) |
| 前后端按什么字段和规则配合 | [4.3 设计包](docs/design/README.md) |
| 三个参考仓库怎么使用 | [参考代码说明](.upstream/README.md) |

## 本机怎样使用

项目位置：`D:\program_design_experiment`。先打开 Docker Desktop，再在 PowerShell 中进入项目目录：

```powershell
Set-Location D:\program_design_experiment
```

首次准备、升级已有工程或依赖改变后执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Prepare-Dev.ps1
```

已有程序在运行时先停止；正常启动使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Start-Dev.ps1
```

| 页面 | 地址与用途 |
| --- | --- |
| 论坛首页 | <http://localhost:3000/> · <http://localhost:3000/posts> |
| 发布帖子 | <http://localhost:3000/posts/new>，登录后使用 |
| 我的内容 | <http://localhost:3000/me/posts> · <http://localhost:3000/me/favorites> |
| 帖子管理 | <http://localhost:3000/admin/posts>，管理员或授权版主使用 |
| 商品与搜索 | <http://localhost:3000/goods> · <http://localhost:3000/search> |
| 公告 | <http://localhost:3000/announcements>；首页同时显示最新公告 |
| 管理概览 | <http://localhost:3000/admin>，管理员或版主登录后使用 |
| 举报、公告、板块与任务管理 | `/admin/reports` · `/admin/announcements` · `/admin/boards` · `/admin/subscriptions` · `/admin/audit-logs` |
| 发布与我的商品 | <http://localhost:3000/goods/new> · <http://localhost:3000/me/goods> |
| 消息：私聊与通知 | <http://localhost:3000/messages> · <http://localhost:3000/notifications>；顶部从“消息”进入，商品详情可联系卖家 |
| 商品管理 | <http://localhost:3000/admin/goods>，管理员使用 |
| 注册、登录 | <http://localhost:3000/register> · <http://localhost:3000/login> |
| 个人资料 | <http://localhost:3000/profile>，登录后使用 |
| 账户管理 | <http://localhost:3000/admin/users>，管理员登录后使用 |
| 开发读写检查 | <http://localhost:3000/dev-check>，保存并刷新检查测试记录 |

本机开发库中已按要求创建以下账号，登录验证通过。账号区分大小写，登录时必须按清单中的大小写输入，昵称与下列账号写法相同；密码由项目负责人掌握，文档不保存。

| 账号 | 权限 |
| --- | --- |
| Administrator001 | 管理员 |
| TestUser001 | 普通用户 |
| TestUser002 | 普通用户 |

当前开发库已有管理员，无需再次执行初始化。以后准备一个全新数据库、且没有管理员时，才使用 `scripts/Init-Admin.ps1` 交互创建第一位管理员；其他管理员由已有管理员授权。

停止程序和开发数据库，保留已保存数据：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Stop-Dev.ps1
```

需要重跑完整4.6验收时，先停止正在运行的开发程序，再执行下列命令。它会构建一次，顺序执行原有回归和新的跨模块检查，并停止、重启开发专用数据库：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Verify-Acceptance.ps1
```

只检查某个功能时，使用 [脚本目录](scripts/README.md) 中对应的单项验收命令，不必每次全部重跑。

详细配置、准备步骤和故障处理见 [工程说明](docs/engineering/README.md) 与 [账户说明](docs/accounts/README.md)。真实配置位于被 Git 忽略的 `deploy/.env`；本机工具、缓存和日志位于 `.local/`。

## 目录

```text
.
├─ README.md                         总入口、4.6成果和本机命令
├─ 邮智汇_当前成果汇报.md              实际完成与后续安排
├─ 邮智汇_程设项目计划书.md             4.1—4.12任务
├─ apps/web/                         正式前端，组件按forum/goods/chat拆分
├─ services/api/                     正式Rust后端
├─ migrations/                       7个不可改写的数据库版本
├─ deploy/                           本地与服务器容器、更新和备份设置
├─ scripts/                          正式准备、启动、停止和验收命令
│  └─ test_support/                 共用验收方法
├─ demand/                           当前需求、原Word及课程模板
├─ docs/                             设计、运行、功能、验收和整理记录
├─ archive/                          早期示例、旧讨论和HTML草图
│  └─ reference-code/               原始参考代码的阅读入口
├─ .upstream/                        原始参考源码与许可，保持原位
├─ checks/                           仅一个历史链接兼容README
├─ .github/workflows/                自动检查配置
└─ .local/                           工具、缓存、真实上传、私有备份与日志
```

各目录说明：[前端](apps/web/README.md) · [后端](services/api/README.md) · [数据库版本](migrations/README.md) · [部署设置](deploy/README.md) · [脚本](scripts/README.md) · [需求](demand/README.md) · [设计与记录](docs/README.md) · [准备检查](archive/preparation-checks/README.md) · [参考代码](.upstream/README.md) · [旧资料](archive/early-docs/discussions/README.md) · [整理记录](docs/maintenance/README.md)。

## 下一步与最终交付

原4.6.1—4.6.4四个业务板块已完成本机验收，4.7基础功能、4.8 AI搜索与商品匹配、4.9 商品提醒和 4.10 管理与举报联动已完成并部署试用。下一步进入 4.11：逐项完成剩余业务验收、比较普通搜索与 AI 效果、检查多人同时使用的速度；之后 4.12 在试用站完成最终核验、独立备份恢复和课程演示。社区首页、校园求助和相似帖子提示等是后续推荐或选做方向，不改变原定必做项。目录清理和代码整理已完成，见 [实际结果](docs/maintenance/README.md)；旧资料归档、正式工具独立、测试方法共用及前端文件拆分均已复验。

最终目标是在 **4 核 16 GB、IP 为 `85.121.122.124` 的服务器**运行网站，用户输入网址即可使用。基础功能已在该服务器运行，HTTPS、外网基础流程、备份及重启更新保留已检查；多人负载和完整独立恢复仍待后续实测。第二台电脑独立安装为选做，GitHub 自动检查已配置但尚未远端运行。