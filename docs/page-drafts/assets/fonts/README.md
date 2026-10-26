# 本地中文字体

本项目已下载并应用 **Noto Sans SC（简体中文）**，不依赖在线字体服务，也不安装到操作系统。

## 来源与许可

- 官方仓库：[notofonts/noto-cjk](https://github.com/notofonts/noto-cjk)。
- 固定版本：`f8d157532fbfaeda587e826d4cd5b21a49186f7c`。
- 下载日期：2026 年 10 月 23 日。
- 原文件：`Sans/SubsetOTF/SC/NotoSansSC-Regular.otf` 与 `NotoSansSC-Medium.otf`。
- 许可：[SIL Open Font License 1.1 原文](OFL.txt)，随项目保留。
- 原文件及网页文件的来源、SHA-256 和处理方式见 [source.json](source.json)。

字体先从官方固定版本下载，再转为 WOFF2，并应用到全部 HTML 入口。保留原名称和版权信息，没有按当前页面文字做裁剪；原 OTF 下载文件保存在本机忽略目录 `.local/font-work/`。

## 文件

| 文件 | 用途 |
| --- | --- |
| [NotoSansSC-Regular.woff2](NotoSansSC-Regular.woff2) | 常规字重 400，正文与辅助信息使用 |
| [NotoSansSC-Medium.woff2](NotoSansSC-Medium.woff2) | 中等字重 500，标题、强调文字使用 |
| [fonts.css](fonts.css) | 将两份字体以 data URL 内嵌，供离线双击 HTML 加载，避免本地文件字体请求的跨源差异 |
| [OFL.txt](OFL.txt) | 官方许可与版权说明 |
| [source.json](source.json) | 来源、转换和哈希记录 |
| [verification.json](verification.json) | 字体嵌入、哈希、字重、页面汉字覆盖和主要文字对比度检查结果 |

完整字库及内嵌 CSS 文件较大；这是当前本地草图的离线方案。正式前端阶段可按访问方式拆分字体范围及缓存，不把本地草图的加载方式直接当作最终部署方案。

## 字号与配色

参考 [Ant Design 中文字体规范](https://ant.design/docs/spec/font-cn/) 的 14px 基础字号、14/22 行高及克制字重层级，结合论坛长文阅读调整：

| 内容 | 字号与使用方式 |
| --- | --- |
| 常规界面、按钮、表单 | 14px，行高约 22px |
| 帖子标题、帖子正文、评论 | 16px 为主；长文行高 1.9，评论 1.8 |
| 作者、时间、标签、辅助说明 | 12px，使用可读的深灰，不再使用 9～11px 小字 |
| 页面标题 | 22px，窄屏 20px；帖子详情标题 24px |
| 标题强调 | 字重 500；正文 400，避免整页粗体和英文大写装饰 |

背景 `#f3f5f7`，内容白色；主要文字 `#242a33`、辅助文字 `#66717e`、主要交互蓝色 `#245b98`。在白底上，三种文字颜色的对比度均高于 4.5:1。价格、异常和状态另使用克制的功能色。

CSS 中字体族为 `Campus Sans SC`，它是对下载字体的网页别名；后备顺序为苹方、微软雅黑及系统中文无衬线字体。应用样式见 [style.css](../style.css)，返回 [页面说明](../../README.md)。
