# 邮智汇 · 程序设计实验

邮智汇是以校园讨论为主体的综合论坛，提供论坛交流、二手商品、关键词与语义搜索、AI 商品需求理解、持续商品提醒、站内私聊和社区管理。使用自主账号，不接校园 CAS，也不代表用户已通过校园身份认证。

**文档更新：2026 年 11 月 6 日。按当前确认的首版范围，计划书 4.1—4.12 已完成。最近一次部署与最终验收日期为 2026 年 11 月 5 日，版本为 `final-20261105-01`。**

最终交付已覆盖完整业务流程、项目重启、独立备份恢复、演示与运维说明，证据见 [4.12 交付记录](docs/final/README.md) 与 [机器可读汇总](docs/final/production-verification.json)。2026-11-05 按负责人要求取消另一成员维护和 AI 标注双人复核两项要求；AI 标注方法仍如实记录为规则生成与抽样核对。

## 服务器试用

网站：**<https://youzhihui.85-121-122-124.sslip.io>**。同学可直接注册使用，不需要安装开发工具。服务器使用独立新数据库，本机三个账号与资料没有迁移或覆盖。

最近一次部署记录为 `final-20261105-01`，包含完整首版功能及 4.11 修复。已通过公网双会话发帖、上传、AI 与普通搜索、商品提醒、举报公告和实时私聊检查；上一版与更新前配套备份保留，每日备份启用，完整独立恢复及本机副本 SHA256 校验通过。4.11 的规定负载在隔离栈完成，4.12 的生产入口检查属于业务复验。

入口：[服务器使用说明](邮智汇_服务器使用说明.md) · [最新运行状态记录](docs/final/server-runtime.json) · [早期部署记录](docs/deployment/README.md)。

## 已完成功能与阶段

| 阶段 | 已完成内容 | 说明与证据 |
| --- | --- | --- |
| 4.1—4.3 需求与设计 | 首版范围、页面、数据结构、HTTP/实时接口、权限与共同匹配规则 | [需求基线](demand/T01_首版需求基线与验收清单.md) · [设计包](docs/design/README.md) |
| 4.4—4.5 工程与账户 | 正式前后端、迁移、注册登录退出、资料头像、改密重置、角色权限与封禁 | [工程说明](docs/engineering/README.md) · [账户说明](docs/accounts/README.md) |
| 4.6.1 论坛与上传 | 发帖编辑、评论回复、点赞收藏、图片/PDF、我的内容、固定分页与跳页 | [论坛说明](docs/forum/README.md) · [分页验收](docs/forum/pagination-verification.json) |
| 4.6.2 商品与普通搜索 | 带图发布编辑、整数分金额、预留/已售/下架、关键词与价格校区筛选 | [商品说明](docs/goods/README.md) |
| 4.6.3—4.6.4 聊天与全流程 | 联系卖家、实时文字私聊、去重重试、离线补读、未读与通知、跨模块验收 | [聊天说明](docs/chat/README.md) · [整体验收](docs/acceptance/README.md) |
| 4.7 试用部署 | HTTPS、来源限流、生产配置、持久卷、日志、更新、定时备份 | [服务器说明](邮智汇_服务器使用说明.md) |
| 4.8 AI 搜索与匹配 | 语义搜索、商品需求理解、条件确认修改、硬条件过滤、帖子举报与 AI 辅助建议 | [AI 功能说明](docs/ai48/README.md) |
| 4.9 持续商品提醒 | 保存条件、首轮全量与后续增量检查、通知去重、暂停恢复删除、失败重试与重启继续 | [提醒说明](docs/reminders/README.md) |
| 4.10 管理与联动 | 用户角色、板块、帖子商品、四类举报、公告、脱敏任务、审计；处理结果联动搜索和提醒 | [管理说明](docs/admin/README.md) · [验收记录](docs/admin/verification.json) |
| 4.11—4.12 评测与交付 | 功能矩阵、AI 对比、隔离负载、生产复验、完整独立恢复、演示与运维材料 | [4.11 总结](docs/acceptance/4.11_验收总结.md) · [4.12 交付](docs/final/README.md) |

普通用户管理自己的内容；版主仅处理授权板块；管理员处理全站管理事务，但不能默认读取所有私聊或私人需求。隐藏、删除、商品下架等状态会在详情、文件访问、搜索、匹配和提醒中生效。

技术栈：前端 Next.js / React，后端 Rust / Salvo / Tokio，MySQL 保存业务资料与向量，Redis 保存临时连接信息，磁盘保存上传文件。文本 AI 由后端调用，中文向量服务在内部运行；真实密钥不进入浏览器。

## 评测与最终验收

| 子项 | 实际结果 |
| --- | --- |
| 4.11.1 全站检查 | AC01—AC20 矩阵齐全；AC12/13/14/19/20 在该阶段实测，其余引用 4.4—4.10 独立库结果；4.12 另补生产浏览器复验 |
| 4.11.2 AI 对比 | 500 商品、40 需求；字段准确率 95%～100%，硬约束违规 0；提醒 20+20，精确率 1.0、重复 0 |
| 4.11.3 负载 | 修复后 20 HTTP + 10 WS 运行 5 分钟；HTTP P95 全达标；索引满载 2 秒、0 pending；WebSocket 0 次 1013；语义降级 3.7% |
| 4.12 生产流程 | 10 项完整流程、6 项浏览器检查通过；修改预算/校区、已售排除、私聊及举报公告均有实际结果 |
| 4.12 提醒与重启 | 项目 API/web 重启后旧资料保留；暂停任务观察 320 秒无新通知；一个新商品样本约 297.515 秒后通知一次 |
| 4.12 独立恢复 | 快照 `20261105T085058Z` 恢复到全新独立数据库及卷；36 张表行数、17 个上传文件大小和 SHA256 全部一致；恢复任务跨重启与后续真实周期去重通过 |
| 4.12 备份与材料 | 完整备份已下载到本机并校验，演示、运维、源码包和文件哈希清单齐备；恢复测试容器已停止，数据卷保留 |

原始结果见 [功能检查](docs/acceptance/4.11_功能检查.md)、[AI 评测](docs/acceptance/4.11_AI评测.md)、[修复后负载测试](docs/acceptance/4.11_负载测试_修复后.md) 与 [最终验收汇总](docs/final/production-verification.json)。

性能结果来自服务器 411 隔离栈的 1.5 CPU 配额环境，生产 HTTPS 入口的本轮检查为业务复验，不据此承诺并发容量。AI 金标采用结构化规则生成与抽样核对；完整自然句的关键词基线命中率较低，评测结果不能外推到所有查询。297.515 秒仅为一个生产提醒样本，不是 P95。

## 从哪里开始看

| 想了解什么 | 阅读入口 |
| --- | --- |
| 服务器网址与日常操作 | [服务器使用说明](邮智汇_服务器使用说明.md) |
| 最终验收、恢复与课程演示 | [4.12 交付记录](docs/final/README.md) · [恢复演练](docs/final/恢复演练.md) · [演示脚本](docs/final/课程演示.md) · [运维操作](docs/final/运维交接.md) |
| 当前有哪些成果、哪些还没做 | [当前成果汇报](邮智汇_当前成果汇报.md) |
| 4.8 功能怎么用、做过哪些检查 | [4.8 使用与验收](docs/ai48/README.md) · [帖子举报设计](docs/design/06_帖子举报与AI辅助处理.md) · [共用 AI 接口设计](docs/design/07_共用AI调用接口.md) |
| 4.9 商品提醒怎么用、验证了什么 | [4.9 使用与验收](docs/reminders/README.md) · [实施计划](docs/reminders/PLAN.md) |
| 4.10 管理页面怎么用、验证了什么 | [4.10 使用与验收](docs/admin/README.md) · [验收记录](docs/admin/verification.json) |
| 论坛列表分页怎么用、验证了什么 | [论坛说明](docs/forum/README.md) · [分页验收记录](docs/forum/pagination-verification.json) |
| 项目是什么、全过程怎么完成 | [项目计划书](邮智汇_程设项目计划书.md) |
| 综合论坛定位及选做方向 | [综合论坛创新方向](demand/邮智汇_综合论坛创新方向.md)，该文件保留早期规划，实际完成范围以本 README 与 4.12 为准 |
| 第一版必须做什么、怎样检查 | [T01 需求与验收清单](demand/T01_首版需求基线与验收清单.md) |
| 怎样启动、停止和检查程序 | [工程运行说明](docs/engineering/README.md) · [账户功能说明](docs/accounts/README.md) · [论坛与上传说明](docs/forum/README.md) · [商品与搜索说明](docs/goods/README.md) · [聊天与通知说明](docs/chat/README.md) |
| 历史阶段的全流程检查 | [4.6 整体验收](docs/acceptance/README.md) · [阶段范围表](docs/acceptance/验收范围.md)，最新完成状态以 4.12 为准 |
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
| 论坛首页 | <http://localhost:3000/> |
| 论坛帖子列表 | <http://localhost:3000/posts>；每页 20 条，可用页码、上一页/下一页和跳页 |
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
├─ README.md                         全项目进度、验收、运行和交付入口
├─ 邮智汇_当前成果汇报.md              实际完成与后续安排
├─ 邮智汇_程设项目计划书.md             4.1—4.12任务
├─ apps/web/                         正式前端，含论坛、商品、聊天、提醒和管理页面
├─ services/api/                     正式Rust后端
├─ migrations/                       7个不可改写的数据库版本
├─ deploy/                           开发、生产及独立恢复配置，更新与备份工具
├─ scripts/                          正式准备、启动、停止和验收命令
│  └─ test_support/                 共用验收方法
├─ demand/                           当前需求、原Word及课程模板
├─ docs/                             设计、运行、功能、验收和整理记录
│  └─ final/                        4.12最终证据、演示与运维说明
├─ archive/                          早期示例、旧讨论和HTML草图
│  └─ reference-code/               原始参考代码的阅读入口
├─ .upstream/                        原始参考源码与许可，保持原位
├─ checks/                           仅一个历史链接兼容README
├─ .github/workflows/                自动检查配置
└─ .local/                           工具、缓存、真实上传、私有备份与日志
```

各目录说明：[前端](apps/web/README.md) · [后端](services/api/README.md) · [数据库版本](migrations/README.md) · [部署设置](deploy/README.md) · [脚本](scripts/README.md) · [需求](demand/README.md) · [设计与记录](docs/README.md) · [准备检查](archive/preparation-checks/README.md) · [参考代码](.upstream/README.md) · [旧资料](archive/early-docs/discussions/README.md) · [整理记录](docs/maintenance/README.md)。

## 最终交付文件

在项目根目录执行以下命令，可按当前工作区重新生成源码包：

```powershell
python scripts/package_final412.py
```

| 文件或目录 | 用途 |
| --- | --- |
| `.local/final412-delivery/youzhihui-course-source.zip` | 课程源码、运行说明、验收与演示材料；包含当前尚未提交的源文件 |
| `.local/final412-delivery/SHA256SUMS`、`manifest.json` | 整包校验和与逐文件清单；包内另有 `DELIVERY-MANIFEST.json` |
| `docs/final/` | 生产流程、浏览器、重启、恢复、提醒与备份的实际记录 |
| `.local/final412-02/演示账号.md` | 演示账号私密记录，由负责人保管 |
| `.local/final412-server/offsite-backup.tar.gz` | 完整私密备份副本，含真实配置，排除在源码包之外 |

现场操作按 [课程演示脚本](docs/final/课程演示.md) 进行，日常运行、更新和停止按 [运维说明](docs/final/运维交接.md) 进行。源码包排除真实环境配置、密码、私密备份、依赖与构建缓存；`.local/` 被 Git 忽略，克隆仓库后需重新生成交付包。

## 未实现范围与工程收尾

以下选做内容尚未实现，不计入已完成的首版功能：社区内容发现首页、校园求助的“已解决”状态与有帮助回复、相似帖子提示、组队招募、用户板块自治。当前首页已提供公告和帖子列表，管理员新增、编辑和停用板块已实现。

商品提醒按保存的硬条件判断资格，用途仅保存与展示，暂不按用途语义排序；通知限站内，不提供短信、邮件或微信推送。项目不包含校园 CAS、付款担保、退款、群聊、语音视频或聊天文件发送。

- **版本管理**：截至本次文档更新，4.11—4.12 仍有未提交修改与未跟踪文件。交付包包含当前工作区内容，Git 提交和远端保存需另按 `git status` 核对。
- **自动检查**：[GitHub 工作流](.github/workflows/engineering.yml) 已配置，主要覆盖 4.6 及此前的验收；尚无远端运行验证记录，4.8—4.12 专项脚本未全部接入该工作流。
- **文档时点**：部分早期阶段说明仍保留当时的“待后续验收”表述；判断当前状态时，以本 README、计划书及 `docs/final/` 最新记录为准。
- **运维扩展**：每日服务器备份和手动下载校验已实现，自动异地同步尚未配置；390px 窄屏已有浏览器检查，真实手机和第二台电脑独立安装未验证，后者为选做。

目录归档与代码整理结果见 [整理记录](docs/maintenance/README.md)。这些扩展和收尾事项不改变当前确认的 4.1—4.12 完成结论。
