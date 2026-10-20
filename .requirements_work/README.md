# .requirements_work · 文档处理记录

这里保存需求文档历次处理的脚本、备份、检查记录和页面预览。它是文档工作记录，不是论坛代码，也不是最新需求入口；当前内容见 [demand 目录](../demand/README.md)。

## 子目录

| 目录 | 保存内容 |
| --- | --- |
| [fras-update/](fras-update/) | 第三个仓库分析补入文档时的备份、预览和检查记录 |
| [markdown-rewrite-20261012/](markdown-rewrite-20261012/) | 精简、重写 Markdown 时保存的旧稿和处理摘要 |
| [requirements-cleanup/](requirements-cleanup/) | 需求文档整理时的备份、排版和结构检查 |
| [no-codex-comments-20261020/](no-codex-comments-20261020/) | 清除文档侧边批注时的备份和检查结果 |
| [t01-20261020/](t01-20261020/) | T01 整理过程中的候选稿、预览和一致性检查，最终要求以 demand 为准 |
| [total-edit-time-20261020-180308/](total-edit-time-20261020-180308/) | 调整 Word 总编辑时长时的备份与校验记录 |
| [final-render/](final-render/) | 一轮文档最终页面预览 |
| [render_docx-pages/](render_docx-pages/) | 文档页面 PNG 预览 |
| [submission-render/](submission-render/) | 提交稿渲染和页面素材 |
| [submission-qa/](submission-qa/) | 提交稿逐页检查预览 |

## 根目录里的文件

| 类型 | 主要文件 | 用途 |
| --- | --- | --- |
| 文档生成与整理 | `build_doc.py`、`revise_submit.py`、`complete_t01.py`、`rewrite_markdown.py` | 保存当时的文档处理步骤 |
| 仓库分析与写回 | `fras_inspect.py`、`fras_update_document.py`、`fras_publish.py`、`fras_export.ps1` | 保存第三个仓库分析及文档处理过程 |
| 批注与属性调整 | `remove_codex_comments.py`、`set_docx_edit_time.py` | 保存批注清理和编辑时长调整步骤 |
| 排版与渲染 | `render_*.py`、`render_*.ps1`、`verify_t01_render.py`、`clean_document_*.py`、`fras_rasterize.py` | 生成页面和检查显示效果 |
| 备份与中间稿 | `before-submission-revision.docx`、`artifact.md`、`plan-task-section.md` | 保存当时文稿，不能当成最新版 |
| 检查记录 | `*verification.json`、`*evidence.json`、`package-inventory.json` | 保存内容、属性、结构或样式检查结果 |
| 页面素材和工具依赖 | PDF、PNG、EMF、`requirements.txt` | 供文档预览及处理使用 |

历史脚本可能写回文档，也可能使用当时的路径，不作为当前项目的启动命令。需要运行准备阶段的检查时使用 [checks 说明](../checks/README.md)。返回 [项目总目录](../README.md)。
