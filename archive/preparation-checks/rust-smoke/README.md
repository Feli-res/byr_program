# rust-smoke · Rust 最小检查示例

这是独立编写的准备阶段示例，检查配置解析、Salvo 程序内部请求、SQLx/MySQL 和 Redis 读写，以及容器重启后能否读回原数据。它不监听正式业务端口，不包含账户、论坛或商品功能。

## 文件目录

| 文件 | 用途 |
| --- | --- |
| [Cargo.toml](Cargo.toml) | Rust 包和所需依赖 |
| [Cargo.lock](Cargo.lock) | 固定实际使用的依赖版本 |
| [src/main.rs](src/main.rs) | 写入读取及内部请求检查；`--verify-only` 跳过写入，只验证先前记录 |

## 如何运行

在项目根目录按顺序执行，不需要手工填写数据库密码：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File archive/preparation-checks/Prepare-Checks.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File archive/preparation-checks/Build-Smoke.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File archive/preparation-checks/Run-Smoke.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File archive/preparation-checks/Restart-And-Verify.ps1
```

脚本从 `.local/` 读取检查密码和随机数据令牌。首次写入后才能运行只读验证；检查表为专用库中的 `environment_probe`，不会创建论坛业务表。运行前先按 [checks 说明](../README.md) 准备工具，结果见 [results 目录](../results/README.md)。
