# 邮智汇 · 程序设计实验

邮智汇是面向北邮师生的校园论坛项目，计划提供讨论、二手商品、文字私聊，以及 AI 搜索、商品匹配和持续提醒。使用自主账号，不接校园 CAS。

**更新日期：2026 年 10 月 28 日。账户及 4.6 的论坛、上传、商品搜索、聊天通知和全流程验收已在本机完成，下一步为 4.7：AI 搜索与商品匹配。**

## 4.6 已完成什么

| 板块 | 网页上能做什么 | 后台已经处理什么 |
| --- | --- | --- |
| 4.6.1 论坛和上传 | 发帖编辑、回复、点赞收藏、我的内容；选择图片和PDF | 真实保存、分页、文件归属与大小数量检查、版面授权、隐藏删除后的文件访问 |
| 4.6.2 商品和普通搜索 | 发布编辑商品、图片排序、预留已售下架；关键词和价格校区筛选 | 整数分、商品状态、版本冲突、管理员限制、帖子商品统一搜索及当前权限过滤 |
| 4.6.3 聊天和通知 | 联系卖家、双方实时文字聊天、历史未读、通知列表与已读 | 会话复用、先存后确认、重试去重、离线补读、私聊成员权限、旧登录连接失效 |
| 4.6.4 全流程验收 | 同一批数据完成“登录→发帖回复→发布商品→搜索→联系卖家→聊天→通知” | 管理联动、改密封禁、故障恢复、重启后数据一致，以及原有功能回归 |

本轮新增8组跨模块检查、3个真实浏览器测试通过；工程、账户、论坛、商品、聊天回归全部通过，14项Rust单元测试和3项金额测试通过，前后端构建通过。详情见 [4.6整体验收](docs/acceptance/README.md) 与 [逐项验收范围](docs/acceptance/验收范围.md)。

目前搜索采用关键词。AI语义检索、商品匹配和持续监控在4.7、4.8接入；匹配/举报通知的产生分别在4.8、4.9实现。本轮不代表AI效果、完整性能或服务器部署已经通过。

目录整理已完成：旧示例和草图归档，测试辅助方法共用，前端按用途拆分。重新构建后的文件体积约从20.29 GB降至7.41 GB，详见 [整理结果](docs/maintenance/README.md)。

## 从哪里开始看

| 想了解什么 | 阅读入口 |
| --- | --- |
| 当前有哪些成果、哪些还没做 | [当前成果汇报](邮智汇_当前成果汇报.md) |
| 项目是什么、全过程怎么完成 | [项目计划书](邮智汇_程设项目计划书.md) |
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
| 发布与我的商品 | <http://localhost:3000/goods/new> · <http://localhost:3000/me/goods> |
| 私聊与通知 | <http://localhost:3000/messages> · <http://localhost:3000/notifications>；商品详情可联系卖家 |
| 商品管理 | <http://localhost:3000/admin/goods>，管理员使用 |
| 注册、登录 | <http://localhost:3000/register> · <http://localhost:3000/login> |
| 个人资料 | <http://localhost:3000/profile>，登录后使用 |
| 账户管理 | <http://localhost:3000/admin/users>，管理员登录后使用 |
| 开发读写检查 | <http://localhost:3000/dev-check>，保存并刷新检查测试记录 |

本机开发库中已按要求创建以下账号，登录验证通过。账号不区分大小写，昵称与下列账号写法相同；密码由项目负责人掌握，文档不保存。

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
├─ 邮智汇_程设项目计划书.md             4.1—4.11任务
├─ apps/web/                         正式前端，组件按forum/goods/chat拆分
├─ services/api/                     正式Rust后端
├─ migrations/                       5个不可改写的数据库版本
├─ deploy/                           数据库容器和运行设置
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

4.6四个板块已完成本机实现与验收，下一步为 **4.7：按意思搜索和商品AI匹配**。目录清理和代码整理已完成，见 [实际结果](docs/maintenance/README.md)；旧资料归档、正式工具独立、测试方法共用及前端文件拆分均已复验。

最终目标是在 **4 核 16 GB、IP 为 `85.121.122.124` 的服务器**运行网站，用户输入网址即可使用。当前仅完成本机验证，尚未部署到该服务器；服务器访问、HTTPS、多人使用时的速度及备份恢复仍需后续实测。第二台电脑独立安装为选做，GitHub 自动检查已配置但尚未远端运行。