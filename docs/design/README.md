# 4.3：页面、数据和操作约定

日期：2026 年 10 月 23 日。范围：计划书 4.3，对应任务 T02。

这份设计包把“网页显示什么、后端保存什么、两边怎样配合”固定下来。开发时先读对应模块的页面清单，再按接口字段和状态规则制作。

## 文件目录

| 文件 | 用途 |
| --- | --- |
| [01_页面与操作清单.md](01_页面与操作清单.md) | 页面入口、填写项、按钮、身份、出错提示及跳转 |
| [02_数据与关系.md](02_数据与关系.md) | 要保存的信息、关系图、主要索引和数据边界 |
| [数据字段字典.md](数据字段字典.md) | 从 SQL 草案提取的全部字段类型、空值和默认值；配合数据说明阅读 |
| [schema.sql](schema.sql) | MySQL 8.4 建表与初始字典草案；尚未纳入正式迁移 |
| [03_接口与消息约定.md](03_接口与消息约定.md) | 统一格式、会话、错误、聊天事件及请求实例 |
| [HTTP操作目录.md](HTTP操作目录.md) | 全部 HTTP 操作、允许身份和后端检查规则 |
| [openapi.json](openapi.json) | 可由工具读取的接口路径、参数和数据类型 |
| [ws-events.json](ws-events.json) | 实时连接首帧、聊天、未读、通知和失效事件的字段定义 |
| [04_权限状态与共同匹配.md](04_权限状态与共同匹配.md) | 谁能操作、状态怎样变化、消息和任务如何防重复及恢复 |
| [06_帖子举报与AI辅助处理.md](06_帖子举报与AI辅助处理.md) | 后续增补设计：帖子举报、管理员处理、通知和AI建议，待实现 |
| [07_共用AI调用接口.md](07_共用AI调用接口.md) | 后续增补设计：共用模型入口、适配器、任务登记与未来扩展，待实现 |
| [05_完成核对.md](05_完成核对.md) | 与计划书和 T01 的对应关系、真实检查结果与下一步 |
| [page-map.json](page-map.json) | 页面、功能编号、操作编号的对应记录 |
| [verification.json](verification.json) | 设计文件与数据库草案的检查结果，不是业务测试报告 |
| [build_contracts.py](build_contracts.py) | 用 Python 标准库生成 OpenAPI 及 HTTP 目录；修改接口约定后执行它 |
| [check_design.py](check_design.py) | 复核接口引用、页面映射、字段、用例对应及本地链接 |
| [check_database.py](check_database.py) | 显式加 `--run`，仅在项目检查容器的唯一临时库执行SQL，结束后删除临时库并恢复容器原运行状态 |
| [database-verification.json](database-verification.json) | MySQL草案的真实建表与约束检查记录 |
| [requirements-checks.txt](requirements-checks.txt) | 可选的OpenAPI/JSON Schema检查依赖，不是正式应用依赖 |

接口的维护入口是 `build_contracts.py`，不要单独修改生成的 JSON 和 HTTP 表格。数据字段以 `schema.sql` 为准，字段字典由检查脚本同步提取，含义见第 02 份说明；调整设计时同步相应操作规则。

## 先看哪一份

1. 看 [HTML 草图](../../archive/early-docs/page-drafts/index.html) 和页面清单，确认页面怎么用。
2. 前端读接口说明及操作目录；后端再读数据、权限、状态和共同匹配规则。
3. 使用 [完成核对](05_完成核对.md) 检查模块有没有漏掉正常、失败、越权及重启场景。

执行设计文件核对：

```powershell
python docs/design/build_contracts.py
python docs/design/check_design.py
```

完整契约校验需安装 `requirements-checks.txt` 中的工具；当前电脑已放在被忽略的 `.local/design-qa/python`，检查脚本会自动读取。缺依赖会明确记录partial，不冒充完整通过。MySQL实测另用 `python docs/design/check_database.py --run`，需要Docker Desktop和现有检查环境；不会连接服务器或使用生产库。

## 当前边界

**4.3 的设计交付已完成。**已提供页面草图、数据草案、接口、实时消息、权限状态和搜索/提醒共用约定。草图仍使用模拟数据；尚未建立正式应用、部署数据库或运行 AC01—AC20。浏览器视觉兼容性和业务性能也不在本次设计检查中标为通过。

模型供应商、向量组件的实际接入与效果对比在 4.8 验证，输入输出已在本次固定；服务器部署在 4.12 验证。下一步进入 **4.4：建立正式前后端工程并接通最小流程**，再按计划完成账户等功能。

需求依据：[T01](../../demand/T01_首版需求基线与验收清单.md)。返回 [docs 目录](../README.md) / [项目总目录](../../README.md)。

2026年10月29日增补：第06、07份为后续待实现设计。旧HTTP契约中的举报处理只包含裁定字段；新增的一并隐藏、重新分析和管理通知权限在实现时同步更新生成器及契约。本次不改写原始SQL草案、正式迁移或既有验收记录。
