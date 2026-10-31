# 计划书 4.9 实施计划：商品订阅与持续提醒

更新日期：2026 年 10 月 31 日。状态：**已按本计划实现，本机与试用站均通过验收；完成记录见 [4.9 使用与验收](README.md)。**

依据：[计划书 4.9](../../邮智汇_程设项目计划书.md)、[权限状态与共同匹配](../design/04_权限状态与共同匹配.md)、[OpenAPI 契约](../design/openapi.json)、[数据库结构](../../migrations/0002_forum_goods_messages_monitoring.sql)。

## 一、目标与验收

4.9 要交付一条完整链路：用户确认商品条件 → 保存提醒任务 → 后台按周期检查 → 找到合适商品后只提醒一次 → 用户可暂停、恢复、编辑、删除 → 重启后继续工作。

对应计划书的四条完成标准：

1. 发布一件符合要求的新商品后收到一次提醒。
2. 重复检查不重复通知。
3. 暂停、删除、商品已售和账号封禁后不产生新的无效提醒。
4. 重新启动后仍能继续检查。

演示时还应能看到：任务列表里的最近检查时间、下次检查时间、异常提示，以及通知能打开当前商品并显示最新状态。

## 二、现状与缺口

### 已经具备

| 能力 | 位置 | 说明 |
| --- | --- | --- |
| 订阅相关表 | `migrations/0002` | `subscriptions`、`subscription_runs`、`scheduler_slots`、`subscription_matches` 已建好，含租约、游标、重试、去重唯一键 |
| 通知保存/读取/已读/推送 | `chat/notifications.rs`、`chat/realtime.rs`、`outbox_events` | 已支持 `goods_match` 类型和 `match_id`，只差产生通知的调用方 |
| 内容变更游标 | `content.rs`、`content_changes`、`system_counters` | 商品/帖子共用递增编号，可做增量扫描 |
| 商品筛选语义 | `goods.rs::Filters`、`semantic.rs` | 已有关键词/语义搜索和价格、校区、类别、品牌、成色、手写笔硬过滤 |
| 封禁暂停任务 | `accounts/mod.rs` 封禁分支 | 已把该用户 `active` 任务改为 `paused` 并清租约 |
| 接口契约 | `docs/design/openapi.json`、`HTTP操作目录.md` | 10 个订阅/管理接口及 `Conditions`、`Subscription` 等 schema 已定义 |

### 主要缺口

1. **没有后端订阅模块**：`services/api/src` 里没有 `subscriptions.rs`，路由和 worker 都没接。
2. **没有可共用的后端匹配函数**：4.8 的确认条件由前端转成 `/api/v1/search` 查询参数，后端只有 `Filters`；没有 `Conditions` 结构和 `match_goods`。4.9 需要补上，否则订阅会另写一套过滤，和搜索逐渐不一致。
3. **没有前端入口**：AI 条件确认后不能保存提醒；没有“我的提醒”列表、编辑和记录页。
4. **没有 4.9 验收脚本、文档和部署记录**。

不需要新建表；先核对数据库版本与 OpenAPI 一致即可。若过程中要加字段或索引，再新增 `0008` 迁移并做升级测试。

## 三、技术方案

### 3.1 数据流

```text
用户确认条件
  → POST /api/v1/subscriptions（Conditions v1 + 周期 + confirmed）
  → subscriptions: state=active, next_due_at=now, needs_full_scan=1
  → 调度 worker（每 5 秒）
  → 领取到期任务 + 一个 scheduler_slot（租约 120 秒）
  → 读游标上界 H；首轮全量，之后只取 (cursor,H] 的商品变更
  → 事务外做硬条件匹配（可选语义排序）
  → 提交事务：锁用户/任务/槽/商品行，复核状态和租约
  → 插入 subscription_matches（任务+商品唯一）
  → 同事务写 notifications + outbox
  → 更新游标、last_checked_at、next_due_at
  → outbox 推送 notification.created；离线用户以后补读
```

暂停、删除、改条件、封禁都会让旧轮次在提交时发现版本或租约不一致而取消，**不能在暂停后补发通知**。

### 3.2 Conditions v1

严格按 OpenAPI：

```json
{
  "schema_version": 1,
  "min_price_cents": null,
  "max_price_cents": 250000,
  "campus_code": "shahe",
  "category_id": "1",
  "brand": "Apple",
  "model": null,
  "min_condition": "good",
  "required_attributes": {"stylus_support": true},
  "purpose": "记笔记"
}
```

校验规则：

- 所有字段必须出现，未知字段拒绝；`schema_version` 只能为 1。
- 价格 0～9,999,999 分；同时存在时 `min_price_cents <= max_price_cents`；0 表示免费商品，不当作未填写。
- 类别、校区必须是启用中的字典项；品牌/型号去首尾空白、长度 1～100、不含控制字符。
- 成色只能是 `new/like_new/good/fair`；`required_attributes` 只允许 `stylus_support`、`storage_gb`，未知属性拒绝。
- `purpose` 是软条件，长度 1～100。
- **至少有一个条件**（类别、品牌、型号、价格、校区、成色、属性、用途之一），否则拒绝，避免匹配全站。
- 原始需求 `original_query` 最多 1000 字，只用于本人查看，不进入通知、日志、管理列表。

前端映射（AI 面板确认后）：

| AI 结果/表单 | Conditions |
| --- | --- |
| 类别下拉（名称转 ID） | `category_id` |
| 品牌输入 | `brand`，空为 null |
| 最高价格 | `max_price_cents`，空为 null |
| 校区下拉 | `campus_code` |
| 手写笔“需要支持” | `required_attributes.stylus_support=true`；选“不支持/不限”不写入硬条件 |
| 最低成色 | `min_condition` |
| 其他需求 `preferences` | 合并为 `purpose`，超过 100 字截断并让用户确认 |
| 未出现的字段 | 全部 null/空对象，不猜测 |

### 3.3 调度与状态

- worker 每 5 秒扫描一次；最多同时执行 2 个任务（`scheduler_slots` 两行），任务租约 120 秒，单轮预算 60 秒。
- 领取：`FOR UPDATE SKIP LOCKED` 选到期任务，写随机 `lease_token` 和 `lease_until` 后立即提交，不在长事务里做匹配。
- `cycle_key` 表示一轮检查；`attempt_no` 0～3。首次失败等待 1 分钟、第二次 5 分钟、第三次 15 分钟；三次额外重试仍失败则 `state=error`，保留安全错误码。
- 成功：推进游标到 H、清空重试、`next_due_at=now+interval_minutes`、`needs_full_scan=0`。
- 首轮和改条件后 `needs_full_scan=1`，找当前在售商品；之后只处理 `(cursor,H]` 的变更。
- 暂停/删除：`config_version+1`、清空租约、`next_due_at=NULL`；工作线程提交时发现不一致 → run 记 `cancelled`，不写通知。
- 重启：启动时清理超过租约的 `running` run 和过期槽位，按一次失败进入重试或异常；有效任务继续按 `next_due_at` 执行。
- 账号封禁：worker 在开始前和提交前都检查 `users.status='active'`；封禁后不产生新通知，解封不自动恢复任务。

### 3.4 匹配与去重

- 候选范围：未删除、`state='on_sale'`、`moderation='clear'`、卖家账号正常；排除任务所有者自己的商品（避免给自己发提醒）。
- 硬条件：价格区间、校区、类别、品牌、型号、最低成色、要求属性。品牌/型号按去空白、忽略大小写精确比较；商品缺少该属性事实时不算匹配。
- 软条件：`purpose` 只用于排序和理由，不作为“不匹配”的依据，避免向量服务不可用时漏提醒。
- 语义排序可选：若 `purpose` 存在且本机向量服务可用，复用 `semantic.rs` 的向量相似度排序；不可用时按发布时间倒序，功能不降级为失败。
- 理由只引用商品实际字段：价格、校区、成色、品牌/型号、命中属性；不写“匹配概率”。
- 去重：`subscription_matches(subscription_id,goods_id)` 唯一键；用 `INSERT IGNORE` 并只在受影响行数为 1 时写通知。修改条件或商品重新上架都不删除历史去重记录。

### 3.5 通知

- 复用 `chat::notifications::create`：`kind='goods_match'`、`target_type='goods'`、`target_id=goods_id`、`match_id=match_id`。
- 摘要示例：`找到符合「2500 元以内的平板」的商品：iPad 9 代，¥1800.00，沙河`，最多 300 字。
- 通知与匹配在同一事务提交；提交后由 outbox 推送。推送失败不回滚已保存通知，离线用户通过通知列表补读。
- 目标商品之后被隐藏、删除或治理限制时，现有通知读取逻辑返回“内容当前不可访问”，不泄漏旧正文；已售/预留只显示最新状态，不继续推荐。

## 四、工作分解

### 阶段 0：契约冻结与骨架（约 0.5 天）

- 确认本文 3.2 的条件映射、首轮通知策略、错误码和状态码。
- 新建 `services/api/src/subscriptions.rs`，先放路由、`Conditions` 结构和空列表响应。
- 在 `lib.rs` 注册路由，在 `main.rs` 启动 worker（先只打日志）。
- 输出：`GET /api/v1/subscriptions` 返回空分页，`cargo test` 通过。

### 阶段 1：订阅 CRUD 与校验（约 1 天）

- `Conditions` 的 serde 严格解析、字典/价格/属性校验、SQL 硬条件构造。
- 实现：列表、创建、详情、编辑、暂停/恢复、删除、执行记录、历史提醒。
- 创建时锁用户行统计未删除任务，最多 10 个（暂停和异常也计入）；周期 5～1440 分钟。
- 编辑只允许 `paused`；保存必须带 `version`、`confirmed`、`resume_after_save`，`config_version+1`，改条件后全量重查但保留去重。
- 删除为软删除，清租约，保留 runs/matches。
- 管理端两个接口：脱敏任务列表（不含条件/原始需求/匹配历史）、暂停异常任务并写审计。
- 单元测试覆盖：未知字段、min>max、空条件、非法字典、品牌/型号长度、属性范围、周期边界。

**产出文件**：`services/api/src/subscriptions.rs`、`lib.rs`、`main.rs`、必要的 `goods.rs` 共用谓词抽取。

### 阶段 2：调度、匹配与恢复（约 1.5 天）

- 到期领取、双槽位、租约、cycle/attempt、全量/增量游标。
- 事务外匹配，事务内复核用户、任务、槽、商品状态和租约。
- 匹配去重、通知、outbox 同事务；暂停/删除/封禁使旧轮次失效。
- 失败重试 1/5/15 分钟，三次后 `error`；启动清理过期 run/槽位。
- 结构化日志：任务 id、run id、候选数、新匹配数、耗时、错误码；不记录条件原文和商品私密内容。
- 单元测试：退避序列、状态转换、租约失效、通知摘要截断。
- 集成脚本验证：首轮、增量、去重、暂停、恢复、删除、售出、封禁、重启、失败进入异常。

**产出文件**：`subscriptions.rs` 的 worker 部分、`main.rs`、`scripts/verify_reminders.py`、`scripts/Verify-Reminders.ps1`。

### 阶段 3：前端（约 1 天）

- `/me/subscriptions`：任务列表，显示名称、状态、周期、最近/下次检查、错误提示、匹配数；空状态和 10 个上限提示。
- 新建/编辑表单：类别、校区、价格区间、品牌、型号、成色、手写笔、用途、名称、周期；复用现有字典和金额转换。
- 详情：条件回显、执行记录、历史提醒；暂停、恢复、删除；编辑前自动暂停并说明“关闭窗口仍保持暂停”。
- AI 商品面板增加“保存为提醒”：用当前已确认/已修改的条件创建，填写名称和周期；未登录引导登录；409 上限时提示先删除。
- 主导航增加“提醒”入口；通知页现有“查看相关内容”直接可用。
- 处理加载、空、失败、无权限、窄屏；不把“页面显示”当作保存成功。
- 写前端遵循 `apps/web/AGENTS.md`：先读当前 Next.js 版本的 `node_modules/next/dist/docs/` 再改代码。

**产出文件**：`apps/web/app/me/subscriptions/page.js`、`apps/web/components/reminders/*.js`、`apps/web/components/goods/ai-panel.js`、`main-navigation.js`、样式文件、`scripts/reminders-browser.cjs`。

### 阶段 4：验收、文档与部署（约 1 天）

- 跑 `verify_reminders.py`，再跑账户/论坛/商品/聊天/4.6 全流程回归。
- 浏览器测试：保存提醒 → 卖家发布 → 买家收到通知 → 暂停后不再新增 → 恢复后继续；窄屏检查。
- 文档：`docs/reminders/README.md`（使用、范围、验证、边界），更新计划书首页状态和 4.9 完成记录、`README.md`、`docs/README.md`、`docs/acceptance/验收范围.md` 的 AC13/AC14/AC15、`docs/ai48/README.md` 的“4.9 未实现”表述、`scripts/README.md`。
- 部署：先在独立库/本机验收，再更新试用站；更新前备份数据库和上传文件，更新后线上双账号复验；清理验收商品/任务，保留处理记录。
- 更新 `邮智汇_服务器使用说明.md` 仅在运行方式变化时；记录 4.9 部署结果。

## 五、接口清单

| 方法 | 路径 | 说明 | 关键检查 |
| --- | --- | --- | --- |
| GET | `/api/v1/subscriptions` | 本人任务列表 | 排除 deleted；不返回他人条件 |
| POST | `/api/v1/subscriptions` | 确认并保存提醒 | 201；10 个上限；周期 5～1440；`confirmed=true` |
| GET | `/api/v1/subscriptions/{id}` | 本人任务详情 | 非本人 404 |
| PATCH | `/api/v1/subscriptions/{id}` | 编辑已暂停任务 | 仅 paused；version；`resume_after_save` |
| PATCH | `/api/v1/subscriptions/{id}/state` | 暂停/恢复 | active/paused；error 可恢复；封禁不能恢复 |
| DELETE | `/api/v1/subscriptions/{id}` | 删除 | 软删除；保留 runs/matches |
| GET | `/api/v1/subscriptions/{id}/runs` | 执行记录 | 只返回安全错误码 |
| GET | `/api/v1/subscriptions/{id}/matches` | 历史提醒 | 实时复核商品；不可见时 goods=null |
| GET | `/api/v1/admin/subscriptions` | 脱敏任务列表 | 不返回条件/原始需求/历史 |
| POST | `/api/v1/admin/subscriptions/{id}/pause` | 暂停异常任务 | 只暂停，不改条件，写审计 |

所有写接口走现有 CSRF 检查；响应沿用 `{"data":...}` / `{"error":{"code",...}}` 格式。

## 六、测试矩阵

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| T01 | 创建任务，条件齐全，周期 5 | 201；列表出现；`next_due_at` 已设置 |
| T02 | 第 11 个未删除任务 | 409 `TASK_LIMIT_REACHED`；提示先删除；暂停任务也计数 |
| T03 | 周期 4 或 1441；min>max；空条件；未知字段；非法类别 | 422；不落库 |
| T04 | 他人读取/编辑/删除/查看 runs | 404（不泄漏任务是否存在） |
| T05 | 首轮全量：先有 2 件符合、1 件超预算 | 2 条通知；超预算不通知 |
| T06 | 首轮后再次检查 | 不新增通知；match 数不变 |
| T07 | 首轮后发布新符合商品，快进到期 | 1 条通知；重复检查仍 1 条 |
| T08 | 发布已预留/已售/下架/治理限制/删除商品 | 不产生通知 |
| T09 | 卖家被封禁/商品被限制后 | 不产生新通知；历史通知显示不可用或最新状态 |
| T10 | 暂停后发布商品并快进到期 | 无新 run 成功、无通知；恢复后能补上暂停期间的变更 |
| T11 | 删除任务后发布商品 | 无通知；列表不再显示；数据库保留 matches 供去重/审计 |
| T12 | 编辑条件（暂停→改→保存不恢复） | 任务仍 paused；version+1；旧去重保留；恢复后全量重查 |
| T13 | 封禁任务所有者 | 任务 paused；旧租约失效；不产生通知；解封不自动恢复 |
| T14 | 重启 API | 有效任务继续；过期 running run 回收；不重复通知 |
| T15 | 模拟持续失败（临时改坏依赖，如重命名 content_changes） | 1/5/15 分钟重试；3 次后 error；恢复依赖并手动恢复后成功 |
| T16 | 通知只读本人；已读状态持久化 | 他人 404；刷新/重启后已读仍在 |
| T17 | 浏览器：AI 确认→保存→卖家发布→通知→暂停→恢复 | 页面状态与后端一致；窄屏可用 |

T05/T07/T10/T13 需要测试脚本直接改 `next_due_at` 快进，不能真的等 5 分钟。T15 只用于一次性测试库，不改开发库和试用站。

## 七、三人分工与排期

| 时间 | A（后端接口） | B（调度与验证） | C（前端与文档） |
| --- | --- | --- | --- |
| 第 1 天 | Conditions、CRUD、权限、10 个上限 | 领取/槽位/租约骨架、测试库脚本框架 | 任务页骨架、路由、导航、表单字段 |
| 第 2 天 | 编辑/暂停/删除/管理接口、单元测试 | 全量/增量扫描、匹配、通知事务 | 列表/详情/暂停恢复、AI 面板保存入口 |
| 第 3 天 | 与 B 联调提交事务和错误码 | 重试/恢复、集成脚本 T01～T16 | 浏览器脚本、空/错/窄屏、文案 |
| 第 4 天 | 回归、修问题、文档 | 回归、部署、线上复验 | 文档、截图/记录、清理测试数据 |

依赖关系：C 按 OpenAPI 先做静态页面，不必等 A 完成；A 和 B 在阶段 0 先约定 `Conditions` 结构和错误码。验收轮换：C 写后端脚本的一部分，A/B 交叉跑，避免“自己写自己验”。

## 八、风险与决策

1. **4.8 没有真正的共用匹配函数**：建议先把商品硬条件谓词抽成共用函数，`Filters` 和 `Conditions` 都调用。设计 04 要求品牌/型号去空白、忽略大小写，4.8 目前是精确匹配；统一后要跑 4.8 搜索回归，确认除大小写外结果不变。若不抽，至少加一致性测试，防止两套过滤条件漂移。
2. **首轮通知数量**：首轮全量会把当前所有符合商品逐件通知。课程演示通常先建任务再发商品，问题不大；若担心刷屏，可改成“首轮只建去重基线、不通知”，但这会看不到当前匹配，需要团队确认。本文默认逐件通知。
3. **语义服务不可用**：通知资格只由硬条件决定，向量只参与排序/理由；否则向量服务一挂就漏提醒。
4. **并发与暂停竞态**：提交前必须重新检查 `config_version`、`lease_token`、用户状态、商品状态；不能只靠前端按钮。
5. **测试时间**：周期最短 5 分钟，集成测试必须用数据库改 `next_due_at` 快进；不要靠 `sleep` 等真实周期。
6. **通知去重**：以 `subscription_matches` 唯一键为准，不能用“页面看起来只有一条”代替数据库约束。
7. **管理员权限**：4.9 只做脱敏列表和暂停接口，管理页面留给 4.10；管理员不能查看他人条件原文。
8. **时间口径**：数据库统一 UTC，前端按本地时区显示；租约、重试、游标都用数据库时间，避免机器时间不一致。
9. **迁移**：当前表结构够用，默认不加迁移；若加字段/索引，必须新增迁移并验证从 7 升级到 8 的独立库测试。

## 九、完成定义

- 计划书 4.9 的四条完成标准全部有对应测试记录。
- `verify_reminders.py` 通过，且账户/论坛/商品/聊天/4.6 全流程回归通过。
- 浏览器完成“保存提醒 → 发布商品 → 收到一次通知 → 暂停 → 不再提醒 → 恢复 → 继续”的完整演示。
- 文档记录实际范围、未做项（管理页面、跨板块提醒、外部推送）和验证边界。
- 试用站更新后线上复验通过，测试数据已清理，更新前备份可恢复。

## 十、本阶段不做

- 4.10 的完整管理页面和评论/商品/私信举报联动。
- 跨板块持续提醒、短信/邮件/微信等站外推送。
- 群聊、AI 校园问答等计划书明确排除的功能。
- 4.11 的 500 件商品 AI 效果对比和多人负载测试。
