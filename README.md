# 邮智汇 · 程序设计实验

> 隐私说明（2026-11-06）：服务器地址、站点域名和登录用户名已替换为示例标记；实际目标保存在本机私有配置中。历史验收数字保持原样。

邮智汇是以校园讨论为主体的综合论坛，提供论坛交流、二手商品、关键词与语义搜索、AI 商品需求理解、持续商品提醒、站内私聊和社区管理。使用自主账号，不接校园 CAS，也不代表用户已通过校园身份认证。

**文档更新：2026 年 11 月 6 日。按当前确认的首版范围，计划书 4.1—4.12 已完成。最近一次部署与最终验收日期为 2026 年 11 月 5 日，版本为 `final-20261105-01`。**

最终交付已覆盖完整业务流程、项目重启、独立备份恢复、演示与运维说明，证据见 [4.12 交付记录](docs/final/README.md) 与 [机器可读汇总](docs/final/production-verification.json)。2026-11-05 按负责人要求取消另一成员维护和 AI 标注双人复核两项要求；AI 标注方法仍如实记录为规则生成与抽样核对。

## 服务器试用

网站地址由维护者通过私密渠道提供；本机实际部署目标保存在被 Git 忽略的 `.local/server-target.json`。使用者可通过浏览器注册，不需要安装开发工具。服务器使用独立数据库，本机资料没有迁移或覆盖。

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
├─ demand/                           当前需求与公开说明；原始课程文档在私有归档
├─ docs/                             设计、运行、功能、验收和整理记录
│  └─ final/                        4.12最终证据、演示与运维说明
├─ archive/                          早期示例、旧讨论和HTML草图
│  └─ reference-code/               原始参考代码的阅读入口
├─ .upstream/                        参考仓库固定版本与许可说明
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
