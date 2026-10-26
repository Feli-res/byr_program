# HTTP 操作目录

日期：2026 年 10 月 23 日。以下为接口设计目录；账户、4.6.1 论坛及通用上传已实现，实际结果见 [账户说明](../accounts/README.md) 与 [论坛说明](../forum/README.md)，其他操作按后续阶段实现。完整字段类型见 [openapi.json](openapi.json)，使用方式、错误及事务边界见 [03 接口与消息约定](03_接口与消息约定.md)。

| 操作编号 | 请求 | 用途 | 允许身份 | 后端必须检查 |
| --- | --- | --- | --- | --- |
| `getCsrf` | `GET /api/v1/csrf` | 获取请求保护凭据 | `public` | 设置签名 CSRF Cookie；禁止缓存；登录或会话变化后重新获取。 |
| `register` | `POST /api/v1/auth/register` | 自主注册 | `anonymous` | 账号去首尾空白并小写后唯一；角色固定 user；密码不去空白，Argon2id；不自动登录。 |
| `login` | `POST /api/v1/auth/login` | 登录 | `anonymous` | 按账号或 IP 统计 15 分钟失败数，5 次后限制 15 分钟；封禁与强制重置不能获得会话；7 天绝对到期。 |
| `logout` | `POST /api/v1/auth/logout` | 退出当前会话 | `member` | 撤销数据库会话，清除 Cookie，并关闭该会话的实时连接。 |
| `getMe` | `GET /api/v1/me` | 获取本人资料 | `member` | 有效身份及本人的数据范围。 |
| `updateMe` | `PATCH /api/v1/me` | 修改本人资料 | `member` | 只能改本人资料；头像必须本人已验证 avatar 文件；配额、版本检查。 |
| `changePassword` | `POST /api/v1/me/password` | 修改本人密码 | `member` | 核对旧密码；写新哈希并撤销全部会话，不返回或记录密码。 |
| `completePasswordReset` | `POST /api/v1/auth/reset-password` | 使用一次性凭据改密 | `anonymous` | 凭据未消费、未撤销、30 分钟内；只允许此操作，消费并改密在同一事务；完成后重新登录。 |
| `listBoards` | `GET /api/v1/boards` | 查看板块 | `public` | 有效身份及本人的数据范围。 |
| `listCategories` | `GET /api/v1/goods-categories` | 获取商品类别 | `public` | 有效身份及本人的数据范围。 |
| `listCampuses` | `GET /api/v1/campuses` | 获取校区选项 | `public` | 有效身份及本人的数据范围。 |
| `listPosts` | `GET /api/v1/posts` | 查看帖子列表 | `public` | 仅公开且未删除；置顶优先，其后创建时间或点赞评论数，最终 id 倒序打破平局。 |
| `createPost` | `POST /api/v1/posts` | 发布帖子 | `member` | 板块启用，作者取会话；文件同属本人，图片≤9、PDF≤2；绑定与内容变更记录一起提交。 |
| `getPost` | `GET /api/v1/posts/{post_id}` | 查看帖子详情 | `public` | 隐藏或删除返回 404；管理员也通过受控管理接口处理隐藏内容。 |
| `updatePost` | `PATCH /api/v1/posts/{post_id}` | 编辑自己的帖子 | `owner` | 作者、version、公开状态均匹配；隐藏内容作者不能编辑；更新附件、索引变更记录。 |
| `deletePost` | `DELETE /api/v1/posts/{post_id}` | 删除自己的帖子 | `owner` | 作者校验，软删除；评论及附件公开访问立即失效；记录索引移除。 |
| `listComments` | `GET /api/v1/posts/{post_id}/comments` | 查看回复 | `public` | 帖子可见；按创建时间和 id 正序，隐藏删除的评论仅返回占位，不返回正文。 |
| `createComment` | `POST /api/v1/posts/{post_id}/comments` | 评论或回复 | `member` | 父评论必须同一帖子且可回复；作者从会话获得；正文不执行 HTML。 |
| `deleteComment` | `DELETE /api/v1/comments/{comment_id}` | 删除自己的评论 | `owner` | 归属检查，软删除保留父子结构。 |
| `addLike` | `PUT /api/v1/posts/{post_id}/like` | 点赞 | `member` | 帖子可见；数据库组合唯一键保证重复操作不重复插入。 |
| `removeLike` | `DELETE /api/v1/posts/{post_id}/like` | 取消点赞 | `member` | 幂等删除本人关联，不改他人记录。 |
| `addFavorite` | `PUT /api/v1/posts/{post_id}/favorite` | 收藏 | `member` | 帖子可见；数据库组合唯一键保证重复操作不重复插入。 |
| `removeFavorite` | `DELETE /api/v1/posts/{post_id}/favorite` | 取消收藏 | `member` | 幂等删除本人关联，不改他人记录。 |
| `listMyPosts` | `GET /api/v1/me/posts` | 查看本人帖子 | `member` | 仅本人；隐藏记录不允许编辑；页面管理 DTO 不得把此接口用于公开查询。 |
| `listMyFavorites` | `GET /api/v1/me/favorites` | 查看本人收藏 | `member` | 已隐藏删除的目标不返回正文，列表剔除并调整 total。 |
| `listGoods` | `GET /api/v1/goods` | 查看商品列表 | `public` | 默认 on_sale；可主动指定其他公开状态；治理限制及删除目标不可公开返回。 |
| `createGoods` | `POST /api/v1/goods` | 发布商品 | `member` | 0～9999999 分；字典有效；其他校区必须地点；本人图片 1～6 张；原子绑定及内容变更。 |
| `getGoods` | `GET /api/v1/goods/{goods_id}` | 查看商品详情 | `public` | 状态为预留、已售等仍可公开查看；治理下架或删除返回 404。 |
| `updateGoods` | `PATCH /api/v1/goods/{goods_id}` | 修改自己的商品 | `owner` | 卖家与版本匹配；治理限制不可编辑；已售只允许查看，不重新发布。 |
| `deleteGoods` | `DELETE /api/v1/goods/{goods_id}` | 删除自己的商品 | `owner` | 软删除，附件与搜索立即不可见，不删除历史通知及去重记录。 |
| `setGoodsState` | `PATCH /api/v1/goods/{goods_id}/state` | 预留、已售、下架或上架 | `owner` | 只接受状态图中的流转；sold 终态；管理员解除限制不自动上架。 |
| `listMyGoods` | `GET /api/v1/me/goods` | 查看本人商品 | `member` | 仅本人，包括预留和下架；受限内容仅通过本人受限 DTO 返回，不暴露他人附件。 |
| `uploadFile` | `POST /api/v1/files` | 上传头像、帖子或商品文件 | `member` | 按 purpose 检验真实内容、解码、单文件大小与 200 MiB 配额；只接受 multipart/form-data；未绑定 24h 后清理。 |
| `readFile` | `GET /api/v1/files/{file_id}/content` | 读取有权访问的文件 | `public` | 先检查绑定目标权限再读取磁盘或返回 304；未绑定仅上传者可读；私聊不接受文件。 |
| `deleteUnboundFile` | `DELETE /api/v1/files/{file_id}` | 清理本人未绑定文件 | `owner` | 仅未绑定文件；先标记清理，真正删除文件后再扣配额；重复删除幂等。 |
| `getFileQuota` | `GET /api/v1/me/file-quota` | 查看本人文件配额 | `member` | 有效身份及本人的数据范围。 |
| `searchPublic` | `GET /api/v1/search` | 关键词或语义全站搜索 | `public` | q 必填；语义失败回关键词并标记 degraded；返回前重查公开状态、版本和商品筛选；私聊/通知/任务不入索引。 |
| `parseProductNeed` | `POST /api/v1/ai/parse-product-need` | 解析自然语言商品要求 | `member` | 每人每分钟最多 5 次；业务总超时 15 秒且不自动重试；拒绝不符合字段 schema 的输出，未知硬条件留空，失败可手填。 |
| `previewGoodsMatches` | `POST /api/v1/goods/matches` | 确认条件后找商品 | `member` | 共用 match_goods；先精确过滤预算、校区、类别、品牌、型号、成色与明确属性，再语义排序；只在售。 |
| `listConversations` | `GET /api/v1/conversations` | 查看本人会话 | `member` | 仅双方成员；按 updated_at,id 倒序。 |
| `openConversation` | `POST /api/v1/conversations` | 从商品页联系卖家 | `member` | 商品公开且对方可联系；卖家由商品确定，不接受伪造 sender_id；双方排序唯一，拒绝自己联系自己；已有会话返回同一 id。 |
| `getConversation` | `GET /api/v1/conversations/{conversation_id}` | 获取会话及未读状态 | `participant` | 管理员身份不绕过成员校验。 |
| `listMessages` | `GET /api/v1/conversations/{conversation_id}/messages` | 读取历史或重连补消息 | `participant` | after/before 互斥；默认最新20条按 sequence 正序返回；历史用 before，补读用 after。 |
| `sendMessage` | `POST /api/v1/conversations/{conversation_id}/messages` | 发送文字消息（HTTP） | `participant` | 与 WS 共用同一保存命令；会话内递增 sequence；同 client_message_id 相同正文返回原消息，正文不同报冲突；提交后确认。 |
| `setConversationRead` | `PUT /api/v1/conversations/{conversation_id}/read` | 更新本人已读位置 | `participant` | 只单调推进，不超过已存在的 last_sequence；未读只数对方消息。 |
| `createWsTicket` | `POST /api/v1/ws-tickets` | 获取一次性实时连接票据 | `member` | 单次使用、30 秒过期，绑定当前会话；Redis 不可用返回 503，可使用 HTTP 读写；票据不得放 URL。 |
| `listNotifications` | `GET /api/v1/notifications` | 查看本人通知 | `member` | 再次检查目标状态；隐藏删除目标只返回不可用占位，不泄漏旧标题、图片或条件。 |
| `readNotification` | `PUT /api/v1/notifications/{notification_id}/read` | 标记本人通知已读 | `owner` | 仅接收者；重复操作幂等。 |
| `readAllNotifications` | `PUT /api/v1/notifications/read-all` | 全部标为已读 | `member` | 只修改当前用户，事务中固定此次通知范围。 |
| `listSubscriptions` | `GET /api/v1/subscriptions` | 查看本人的商品提醒任务 | `member` | 默认排除 deleted；不得查询别人的私人条件。 |
| `createSubscription` | `POST /api/v1/subscriptions` | 确认并保存商品提醒 | `member` | 用户行锁下计数未删除任务，最多10；周期5～1440分钟；确认 schema 后保存，首轮全量匹配。 |
| `getSubscription` | `GET /api/v1/subscriptions/{subscription_id}` | 查看本人任务条件 | `owner` | 管理员无默认查看他人条件的权限。 |
| `updateSubscription` | `PATCH /api/v1/subscriptions/{subscription_id}` | 编辑已暂停任务 | `owner` | 编辑前先暂停；config_version 匹配；保存时显式选择是否恢复；改条件后全量检查但保留历史去重。 |
| `setSubscriptionState` | `PATCH /api/v1/subscriptions/{subscription_id}/state` | 暂停或恢复任务 | `owner` | 可从 error 手动恢复；暂停立即撤销旧轮次提交资格；封禁账号不能恢复。 |
| `deleteSubscription` | `DELETE /api/v1/subscriptions/{subscription_id}` | 删除任务 | `owner` | 标记 deleted、失效租约，保留去重和历史记录；不再提交通知。 |
| `listSubscriptionRuns` | `GET /api/v1/subscriptions/{subscription_id}/runs` | 查看本人任务执行记录 | `owner` | 仅返回错误码，不返回模型密钥或内部堆栈。 |
| `listSubscriptionMatches` | `GET /api/v1/subscriptions/{subscription_id}/matches` | 查看本人任务历史提醒 | `owner` | 实时复核商品可见性；不可见目标 goods=null。 |
| `createReport` | `POST /api/v1/reports` | 举报帖子、评论、商品或骚扰消息 | `member` | 目标当时可见；消息举报者必须为接收者；服务端截取被举报消息和必要上下文最多5条，不能由客户端指定整段私聊。 |
| `listMyReports` | `GET /api/v1/me/reports` | 查看本人举报结果 | `member` | 有效身份及本人的数据范围。 |
| `getMyReport` | `GET /api/v1/me/reports/{report_id}` | 查看本人单条举报 | `owner` | 不返回处理者私有信息或他人举报。 |
| `listAnnouncements` | `GET /api/v1/announcements` | 查看已发布公告 | `public` | 只 state=published。 |
| `getAnnouncement` | `GET /api/v1/announcements/{announcement_id}` | 查看公开公告 | `public` | 草稿及撤回返回404。 |
| `adminListUsers` | `GET /api/v1/admin/users` | 管理用户列表 | `admin` | 有效身份及本人的数据范围。 |
| `adminSetUserStatus` | `PATCH /api/v1/admin/users/{user_id}/status` | 封禁或解封 | `admin` | 锁 administrators 后锁用户；不可封禁最后可用管理员；封禁撤销全部会话、暂停任务；解封不自动恢复任务；同事务审计。 |
| `adminSetUserRole` | `PATCH /api/v1/admin/users/{user_id}/role` | 分配角色和板块 | `admin` | 统一锁防止并发移除最后可用管理员；只有 moderator 可绑定版面；撤销的版面权限立即生效；审计。 |
| `adminIssuePasswordReset` | `POST /api/v1/admin/users/{user_id}/password-reset` | 管理员核实后发一次性凭据 | `admin` | 不得对自己使用；不能使最后可用管理员失去可用性；撤销旧凭据和所有会话；有效30分钟，明文只在本次响应出现，不入日志；审计。 |
| `adminCreateBoard` | `POST /api/v1/admin/boards` | 创建板块 | `admin` | 名称唯一；审计。 |
| `adminUpdateBoard` | `PATCH /api/v1/admin/boards/{board_id}` | 修改板块配置 | `admin` | 禁用后不能新发帖，已有公开帖仍可读；不删除历史数据；审计。 |
| `adminListPosts` | `GET /api/v1/admin/posts` | 查看权限范围内的帖子状态 | `moderator_or_admin` | 版主仅授权板块；返回管理所需正文，所有结果不进入公共搜索缓存。 |
| `adminModeratePost` | `PATCH /api/v1/admin/posts/{post_id}/moderation` | 置顶、隐藏或恢复帖子 | `moderator_or_admin` | 版主核对板块授权；删除不恢复；状态变更、内容变更日志、审计同事务。 |
| `adminModerateComment` | `PATCH /api/v1/admin/comments/{comment_id}/moderation` | 隐藏或恢复评论 | `moderator_or_admin` | 从所属帖子核对板块授权；删除不恢复；审计。 |
| `adminModerateGoods` | `PATCH /api/v1/admin/goods/{goods_id}/moderation` | 治理下架或解除限制 | `admin` | restrict 设 off_shelf 与 restricted；release 仅解除限制，卖家自行恢复在售；审计和索引更新。 |
| `adminListReports` | `GET /api/v1/admin/reports` | 查看职责范围内举报 | `moderator_or_admin` | 版主仅本人授权板块的帖子/评论举报；商品和私信举报仅管理员。 |
| `adminGetReport` | `GET /api/v1/admin/reports/{report_id}` | 查看必要举报上下文 | `moderator_or_admin` | 与列表同范围；私信只展示被举报内容和必要上下文，不提供会话历史入口。 |
| `adminResolveReport` | `PATCH /api/v1/admin/reports/{report_id}` | 处理举报并通知举报人 | `moderator_or_admin` | 检查范围、版本和待处理状态；与处理通知、outbox和审计同事务；内容治理另走治理命令。 |
| `adminListAnnouncements` | `GET /api/v1/admin/announcements` | 查看公告草稿及状态 | `admin` | 有效身份及本人的数据范围。 |
| `adminCreateAnnouncement` | `POST /api/v1/admin/announcements` | 创建公告草稿 | `admin` | 初始 draft，不公开；审计。 |
| `adminUpdateAnnouncement` | `PATCH /api/v1/admin/announcements/{announcement_id}` | 编辑、发布或撤回公告 | `admin` | 遵守公告状态图；发布后修改需先撤回；审计。 |
| `adminListTaskMetadata` | `GET /api/v1/admin/subscriptions` | 查看脱敏任务运行情况 | `admin` | 绝不返回 original_query、conditions、匹配历史和通知内容。 |
| `adminPauseTask` | `POST /api/v1/admin/subscriptions/{subscription_id}/pause` | 暂停异常任务 | `admin` | 只暂停不修改他人条件；记录审计并使旧租约失效。 |
| `adminListAuditLogs` | `GET /api/v1/admin/audit-logs` | 查看治理记录 | `admin` | 只允许白名单变化字段；不记录密码、token、原始需求、私聊正文。 |
| `healthLive` | `GET /api/v1/health/live` | 服务存活 | `public` | 只判断进程能否响应，不调用外部模型。 |
| `healthReady` | `GET /api/v1/health/ready` | 依赖就绪 | `public` | 数据库与Redis必需；任一不可用返回503；模型故障不阻止基础论坛就绪。 |
| `getMyPost` | `GET /api/v1/me/posts/{post_id}` | 读取本人隐藏帖用于查看状态 | `owner` | 仅作者；删除返回404；隐藏内容只读，不可借此恢复编辑或公开附件。 |
| `getMyGoods` | `GET /api/v1/me/goods/{goods_id}` | 读取本人受限商品状态 | `owner` | 仅卖家；删除返回404；仅管理自己的内容，不解除治理限制。 |
| `adminGetPost` | `GET /api/v1/admin/posts/{post_id}` | 读取职责内帖子用于治理 | `moderator_or_admin` | 版主检查授权板块；允许查看治理所需隐藏内容；不改变公开可见性。 |
| `adminListGoods` | `GET /api/v1/admin/goods` | 查看商品治理列表 | `admin` | 仅管理员；返回公开或受限商品，不包含私人需求。 |
| `adminGetGoods` | `GET /api/v1/admin/goods/{goods_id}` | 读取商品治理详情 | `admin` | 仅管理员；不授权代卖家修改正文、价格。 |
| `adminGetAnnouncement` | `GET /api/v1/admin/announcements/{announcement_id}` | 查看公告草稿详情 | `admin` | 仅管理员，草稿不可由公开接口获取。 |
