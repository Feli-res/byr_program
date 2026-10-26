# 邮智汇 · 程序设计实验

邮智汇是面向北邮师生的校园论坛项目，计划提供讨论、二手商品、文字私聊，以及 AI 搜索、商品匹配和持续提醒。使用自主账号，不接校园 CAS。

**更新日期：2026 年 10 月 26 日。当前已完成需求、设计、正式工程和账户功能的本机验证，下一步为 4.6：论坛、商品和聊天。**

## 从哪里开始看

| 想了解什么 | 阅读入口 |
| --- | --- |
| 当前有哪些成果、哪些还没做 | [当前成果汇报](邮智汇_当前成果汇报.md) |
| 项目是什么、全过程怎么完成 | [项目计划书](邮智汇_程设项目计划书.md) |
| 第一版必须做什么、怎样检查 | [T01 需求与验收清单](demand/T01_首版需求基线与验收清单.md) |
| 怎样启动、停止和检查程序 | [工程运行说明](docs/engineering/README.md) · [账户功能说明](docs/accounts/README.md) |
| 页面计划做成什么样 | [HTML 页面草图](docs/page-drafts/index.html) · [打开说明](docs/page-drafts/README.md) |
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
| 网站首页 | <http://localhost:3000/> |
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

需要重新验收时，先停止正在运行的开发程序，再分别执行以下检查。检查会停止、重启本机开发服务：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Verify-Dev.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Verify-Accounts.ps1
```

详细配置、准备步骤和故障处理见 [工程说明](docs/engineering/README.md) 与 [账户说明](docs/accounts/README.md)。真实配置位于被 Git 忽略的 `deploy/.env`；本机工具、缓存和日志位于 `.local/`。

## 目录

```text
.
├─ README.md                         项目总入口和本机使用方法
├─ 邮智汇_当前成果汇报.md              已完成内容、检查结果和后续任务
├─ 邮智汇_程设项目计划书.md             项目目标和 4.1—4.11 的任务
├─ apps/web/                         正式 Next.js / React 前端
├─ services/api/                     正式 Rust / Salvo 后端
├─ migrations/                       4 个正式数据库版本文件
├─ deploy/                           本地 MySQL、Redis 和配置示例
├─ scripts/                          准备、启动、停止和验证命令
├─ .github/workflows/                GitHub 自动检查配置
├─ demand/                           需求、验收清单和参考代码分析
├─ docs/
│  ├─ page-drafts/                   HTML 页面草图和本地中文字体
│  ├─ design/                        页面、数据、操作和权限设计
│  ├─ engineering/                   4.4 运行说明和检查记录
│  └─ accounts/                      4.5 账户说明和检查记录
├─ checks/                           准备阶段的示例、脚本和结果
├─ .upstream/                        三个参考仓库的固定版本与归档
├─ Old_docs/                         早期讨论资料
├─ .requirements_work/               文档处理记录、备份和预览
└─ .local/                           本机工具、缓存和日志，不提交
```

各目录说明：[前端](apps/web/README.md) · [后端](services/api/README.md) · [数据库版本](migrations/README.md) · [部署设置](deploy/README.md) · [脚本](scripts/README.md) · [需求](demand/README.md) · [设计与记录](docs/README.md) · [准备检查](checks/README.md) · [参考代码](.upstream/README.md) · [旧资料](Old_docs/README.md) · [文档处理记录](.requirements_work/README.md)。

## 下一步与最终交付

下一步按计划书完成 4.6：先做论坛发帖与互动，再做商品、上传和关键词搜索，最后接入私聊、通知及“联系卖家”。接入实时聊天后，还要补验退出、改密或封禁后，旧实时连接在 5 秒内关闭。

最终目标是在 **4 核 16 GB、IP 为 `85.121.122.124` 的服务器**运行网站，用户输入网址即可使用。当前仅完成本机验证，尚未部署到该服务器；服务器访问、HTTPS、多人使用时的速度及备份恢复仍需后续实测。第二台电脑独立安装为选做，GitHub 自动检查已配置但尚未远端运行。