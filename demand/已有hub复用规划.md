# 北邮校园综合论坛开源仓库复用分析

本项目采用 **Next.js + React、Rust + Salvo + Tokio、MySQL + SQLx、Redis**。以 `hnu-doc` 为后端底座候选，借鉴 `jhserver` 的调度设计和 `FRAS-lab-website` 的界面、内容管理设计。账户使用自主注册登录，不接入校园 CAS。

以下说明基于已检查的源码版本，列出复用动作，不代表已完成迁移。准备阶段的构建、最小运行结果和最终取舍见 [4.1 与 4.2 检查报告](4.1与4.2_检查结果与使用说明.md)，正式业务仍待开发验收。

## 一 hnu-doc：后端工程底座

- **原用途：**学校试卷与资料管理后端。
- **技术：**Rust、Salvo、Tokio、SQLx、MySQL、Redis、JWT。
- **版本：**`d71b9976bcd6606b0e74855fda092338687218af`，源码已保存在 `.upstream`。
- **来源：**[仓库主页](https://github.com/gygy-hh/hnu-doc)。下表路径相对 `hnudoc/src/`。

### 保留与改造

| 模块 | 源码位置 | 执行动作 |
| --- | --- | --- |
| 服务启动与配置 | `main.rs`、`config.rs` | 保留启动结构，替换业务路由、配置及密钥 |
| 中间件与响应 | `middlewares/`、`result.rs` | 迁移日志、跨域、超时、异常处理和统一响应 |
| 数据库与缓存 | `infra/mysql/mod.rs`、`infra/redis.rs` | 迁移连接池；为论坛重建表、索引和事务 |
| 登录与权限 | `utils/jwt.rs`、`service/user.rs` | 改为自主账户，补会话撤销、角色及资源归属检查 |
| 图片与附件 | `infra/storage.rs` | 改为论坛上传，补真实类型检查、图片解码、大小限制及访问权限 |
| 搜索与审核 | `service/search.rs`、`service/pending.rs` | 借鉴分页和审核流程，重写帖子、商品检索及治理业务 |

### 必须替换

1. 删除学校认证流程及其专用依赖耦合，不迁移 `infra/verify.rs` 的门户验密逻辑。
2. 平台密码使用 Argon2id 等专用哈希，不保存学校门户密码或复制硬编码加密材料。
3. 新建论坛业务表，不将试卷、试卷集和待审核试卷表直接改名使用。
4. 重写全站搜索。现有科目名称 `LIKE` 查询不能提供帖子、商品的语义检索。
5. 按论坛需求补上传校验；MD5 文件名只解决去重，不能代替安全检查。

### 仍需开发

- 板块、帖子、评论回复、点赞收藏、商品及其状态。
- 普通用户、版主、管理员权限和自主注册登录。
- 全站搜索、WebSocket 私聊、AI 匹配、监控、通知及举报审计。

**复用检查：**先构建原后端并记录问题，再迁移通用组件。当前工作区声明 MIT，复用时保留声明并核对所需版权与许可文本。

## 二 jhserver：调度与通知设计

- **原用途：**面向特定游戏客户端协议的 C++ 服务端，包含游戏邮件和管理后台。
- **技术：**C++17、cpp-httplib、MySQL、Redis、HTML/JavaScript。
- **版本：**`8fb142e049f0eac1a53abf522cb861ccd944685a`，源码已保存在 `.upstream`。
- **来源：**[仓库主页](https://github.com/gygy-hh/jhserver)。

### 借鉴并用 Rust 重写

| 模块 | 源码位置 | 执行动作 |
| --- | --- | --- |
| 定时调度 | `src/mail.cpp`、`src/redis.cpp` | 借鉴 Redis 有序集合的到期任务处理，改为周期商品监控 |
| 通知管理 | `src/mail.cpp` | 借鉴个人及全站消息流程，新建持久通知表和已读状态 |
| 管理后台 | `src/admin.cpp`、`web/admin.html` | 借鉴管理列表及接口组织，用 React/Rust 实现 |
| 会话撤销 | `src/session.cpp` | 借鉴撤销流程，接入论坛统一登录与封禁规则 |
| 短时缓存 | `include/jh/cache.hpp` | 借鉴过期策略，按需用于热门内容和统计缓存 |

### 商品监控实现步骤

1. 创建或修改任务时解析自然语言，保存原始需求和用户确认的条件。
2. MySQL 保存任务规则、状态和执行时间；Redis 只保存调度索引。
3. 原子领取到期任务，对新增或更新商品进行硬约束过滤及语义匹配。
4. 用任务与商品的唯一关联去重，写入持久通知，再向在线用户推送。
5. 安排下次执行；支持暂停、删除、有限重试和重启恢复。

### 必须区分的边界

- 原调度主要用于一次性游戏邮件；周期监控、增量匹配和结果去重仍需开发。
- 游戏邮件不能代替私聊。会话、成员、聊天历史、未读及重连补读必须另建。
- 不引入第二套 C++ 业务服务器，不迁移游戏协议、存档及奖励逻辑。
- 不复制加盐 MD5 密码方案、模拟短信接口或原管理登录方式。

**复用检查：**本地版本包含 MIT `LICENSE`，复制代码时保留版权及许可文本。优先参考设计，不要求运行游戏服务器。

## 三 FRAS-lab-website：界面与内容管理设计

- **原用途：**实验室官网，提供公开内容展示、管理员登录、内容维护及文件上传。
- **技术：**Java 21、Spring Boot、Spring Security、JPA、MySQL、Flyway；Vue 3、TypeScript、Vite、Axios。
- **检查版本：**`892e0b14d2a784c833597ecb9fc91f2a41b996d2`，2026 年 10 月 20 日重新读取远端并复核代码；当时 `main` 与此版本一致。
- **来源：**[固定版本](https://github.com/gygy-hh/FRAS-lab-website/tree/892e0b14d2a784c833597ecb9fc91f2a41b996d2)。
- **本地源码：**[固定版本目录](E:/program_design_experiment/.upstream/FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2)，同时保存同名 ZIP；[来源与校验记录](E:/program_design_experiment/.upstream/FRAS-lab-website.source.json)。原始源码未改动，本次未构建或启动服务。

### 目录内容

| 目录或文件 | 内容 |
| --- | --- |
| `frontend/src/views/public/`、`components/public/` | 首页、研究方向、成果、成员、新闻、活动和联系页面，以及共用导航；属于公开信息展示 |
| `frontend/src/views/admin/` | 管理员登录和综合管理页，提供资料、轮播图及多类内容的列表、表单和上传操作 |
| `frontend/src/api/`、`utils/`、`router/` | HTTP 请求、业务类型、浏览器凭证保存及路由守卫；`i18n/`、`locales/` 提供中英双语 |
| `backend/src/main/java/com/fraslab/site/` | 按 `controller → service → repository/entity` 分层；另含安全认证、请求响应类型和异常处理 |
| `backend/src/main/resources/` | 应用配置及 Flyway 的 V1—V13 数据迁移；`backend/src/test/` 提供上下文加载测试和 H2 配置 |
| `docs/`、`deploy.ps1` | 开发过程说明及原站部署脚本；部分说明仍保留旧导师接口和旧迁移列表，应以当前代码为准；部署脚本只作参考 |

### 借鉴与适配

| 模块 | 源码位置 | 执行动作 |
| --- | --- | --- |
| 页面样式 | `frontend/src/style.css`、`components/public/PublicHeader.vue` | 借鉴导航、颜色变量、卡片、表单和响应式布局，改写为 React 页面；替换品牌、图片和实验室内容 |
| 管理界面 | `frontend/src/views/admin/AdminDashboardView.vue` | 借鉴列表、表单和状态反馈，拆成帖子、商品、公告管理页 |
| 接口封装 | `frontend/src/api/client.ts`、`utils/auth.ts` | 借鉴超时、类型定义和凭证注入，补统一错误、会话过期及服务端撤销处理 |
| 内容维护 | `NewsService.java`、`PublicController.java` | 借鉴管理列表与公开列表分离、仅展示已发布内容及时间排序；在 Rust 中实现公告和帖子状态管理 |
| 文件上传 | `AdminUploadController.java`、`FileStorageService.java` | 借鉴上传链路和路径检查，补文件白名单、真实类型及资源归属 |
| 数据迁移 | `backend/src/main/resources/db/migration/` | 借鉴按版本逐步增删字段的方式；为论坛重写 SQL，不导入实验室业务及示例账户数据 |
| 响应和异常 | `common/ApiResponse.java`、`common/GlobalExceptionHandler.java` | 参考统一结果和参数错误结构；在 Rust 中补安全错误信息、请求标识和日志关联 |

表中前端简写路径相对 `frontend/src/`；Java 文件位于 `backend/src/main/java/com/fraslab/site/` 下的相应业务目录。主要链路是：前端页面调用 API → 后端校验和业务处理 → 数据库持久化 → 返回页面；上传另经存储服务返回文件地址。

**复用判断：**页面视觉规范、管理交互和业务分层值得借鉴；Vue 组件和 Java 服务均需要适配既定 React/Rust 技术栈。它是内容管理参考，不作为论坛主底座，不增加第二套 Java 业务后端。双语、成员、科研成果等实验室功能不进入首版。

### 必须改造

1. Vue 组件改写为 React，Java 服务改写为 Rust；保留既定技术栈。
2. 重写多角色鉴权。`security/JwtAuthFilter.java` 对通过 token 校验的请求统一授予 `ROLE_ADMIN`，适合原管理员场景，不能直接用于普通用户和版主。
3. 补服务端会话撤销及封禁检查。原登录会检查账户启用状态，但后续 token 校验不重查账户状态；前端退出仅清除浏览器凭证。
4. 补分页、筛选和资源归属。`NewsRepository.java` 等返回完整列表；原内容没有论坛作者、板块版主等权限模型。
5. 重写上传校验。`AdminUploadController.java` 主要检查客户端 `Content-Type`，未知 `type` 未被明确拒绝；`FileStorageService.java` 已有随机文件名和路径边界检查，但仍需真实类型识别、图片解码、扩展名白名单和配额。原文件读取接口公开，不能承担私有附件授权。
6. 替换固定配置、示例账户和部署路径；`backend/.mvn/maven.config` 指定了原作者机器的 Maven 缓存目录。不要直接执行原部署脚本，也不沿用示例密钥和密码。
7. 补业务测试。现有后端仅有上下文加载测试，使用 H2 且关闭 Flyway，不能证明 MySQL 迁移、权限和上传链路正确；前端未定义测试脚本。本次仅完成静态阅读及源码归档校验。

### 仍需开发

- 普通用户注册、论坛互动、商品业务和细粒度权限。
- 私聊、持久通知、AI 语义检索、商品匹配及周期监控。
- 举报、审计及业务异常测试。

### 对本项目的具体落实

1. 在正式前端创建导航、卡片、列表、表单和上传组件，参考原页面的交互和样式，不整体搬运管理大页面。
2. 创建用户、板块、帖子、商品、举报、公告和任务管理页面；后台实现对应权限与状态转换。
3. 建立统一请求模块、分页结果、登录失效提示和错误反馈；持久化成功后再更新成功状态。
4. 新建论坛数据库迁移、文件元数据及访问规则，并验证空库迁移、非法上传、越权修改、封禁和会话失效。

上述动作纳入现有 T02、T04—T07 及后续业务开发，不另开一套工程。

**复用检查：**所查版本未发现许可证文件，直接复制前确认授权。优先借鉴设计；需求分析 Word 文档只保留系统要求，不写此仓库的名称、路径或引用链接。
