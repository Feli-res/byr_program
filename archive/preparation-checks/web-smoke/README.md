# web-smoke · Next.js / React 最小页面

这个小页面只用于检查所选前端工具能否安装依赖、完成构建，并通过本机 HTTP 访问。它不连接论坛后端，没有注册、登录或其他业务功能。

## 文件目录

| 文件 | 用途 |
| --- | --- |
| [package.json](package.json) | 页面所用依赖和构建命令 |
| [package-lock.json](package-lock.json) | 固定实际安装的依赖版本 |
| [next.config.mjs](next.config.mjs) | Next.js 构建设置 |
| [app/layout.js](app/layout.js) | 页面基本结构 |
| [app/page.js](app/page.js) | 用于识别页面是否正确返回的最小内容 |

`node_modules/` 和 `.next/` 分别是下载依赖和构建产物，已被 Git 忽略。

## 如何运行

在项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File archive/preparation-checks/Check-WebTools.ps1
```

脚本安装锁定依赖、构建页面，短暂在 `127.0.0.1:25174` 启动检查服务，确认 HTTP 200 和页面标记后关闭自己启动的进程。结果见 [web-tools-result.json](../results/web-tools-result.json)，完整准备步骤见 [checks 说明](../README.md)。
