# 本地维护与已验收前端恢复

本轮把 API、worker、统一启动入口和 keepalive 的进程变更接入同一份维护状态，并允许它们恢复明确选定的前端构建。维护状态持久保留，只有持有本次 owner token 的操作才能退出。进入维护表示禁止这些入口继续启动、停止或恢复服务；`drained=false` 明确表示既有进程尚未被证明排空。

根因是旧启动脚本没有共同的维护状态，保活任务可以在发布暂停期间重新启动进程；环境初始化中的 `print-env` 还会间接打开 DuckDB。前端保活原来仅检查开发服务源码端点，无法识别已经验收的 preview 构建。本轮把有限数据库探测与进程创建放在锁内，等待子进程退出和 HTTP 就绪放在锁外。PowerShell 与 Python 使用同一个锁文件，叶子启动在创建进程前再次检查状态。

前端选择保存在 `tmp-governance/runtime-clean/control/frontend.json`。accepted 模式启动前核对清单自身 SHA-256、逐文件 SHA-256、完整文件集合、页面实际 module 入口和 Node/Vite 的最低执行条件。无效候选不会覆盖旧选择，坏构建不会自动回到开发模式。HTTP 探针核对首页及其实际入口脚本；这项静态身份核对不替代业务页面验收。未设置选择时保留原开发模式，accepted 模式使用真实数据及本地 API 代理。

## 操作方法

以下命令在仓库根目录的 PowerShell 中执行。`$maintenance` 保存本次 owner token；跨会话操作前应妥善保存回执。控制器不会自动停止或启动真实服务。

```powershell
$maintenance = & .\.venv\Scripts\python.exe scripts/dev_runtime_control.py enter --reason "restore accepted frontend"
if ($LASTEXITCODE -ne 0) { throw "Cannot enter maintenance" }
$maintenance = $maintenance | ConvertFrom-Json
```

进入维护后，按现有发布流程停止需要维护的进程，并单独核对端口、worker 和数据库持有者。只有完成这些检查，才能开始要求排空的数据维护。不要把 `launch_blocked` 当成停机或数据库排他锁证明。绕过这些入口直接打开数据库的工具不受本协议控制。

选择已验收构建时必须使用验收回执中的清单哈希，不能临时重算一个哈希来代替验收。下面是本轮只读核验过的现有构建；它仍依赖 `.codex-tmp` 文件被保留。

```powershell
& .\.venv\Scripts\python.exe scripts/dev_runtime_control.py select-frontend `
  --owner-token $maintenance.owner_token `
  --build-root .codex-tmp/global-repair-2026-09-05/build `
  --manifest .codex-tmp/global-repair-2026-09-05/build-manifest.json `
  --manifest-sha256 6d497a3bed68a8fb1f2f56e1fcb1efe00c33291f314bfad41c8f1bbe79cf0e23
if ($LASTEXITCODE -ne 0) { throw "Accepted build selection failed; maintenance remains active" }
```

完成维护后，退出时会再校验所选构建。失败时保留维护状态。退出只解除阻断；运行中的 keepalive 可在下一轮恢复，或使用统一启动脚本手动恢复。

```powershell
& .\.venv\Scripts\python.exe scripts/dev_runtime_control.py leave --owner-token $maintenance.owner_token
if ($LASTEXITCODE -ne 0) { throw "Maintenance remains active" }
& .\scripts\dev-up.ps1
```

`start_dev.cmd` 也委托 `dev-up.ps1`，统一启动本地服务。若服务已经由 keepalive 恢复，应先查看状态，避免重复手动启动。

## 验证范围

隔离测试使用临时目录和假的命令，覆盖维护阻断、owner 校验、无效选择保留、构建损坏、真实 PowerShell/Python 跨进程互斥，以及环境初始化不能越过维护状态。既有启动与 worker 生命周期测试继续执行。验收记录保存在 `.codex-tmp/release-closure-2026-09-05/`。

现有构建的 271 个文件通过完整清单验证，5888 端口实际返回的首页和入口脚本与清单一致。本轮没有切换真实 frontend.json，没有启用真实维护状态，也没有重启服务或连接正式数据库。已在运行的旧 PowerShell keepalive 进程仍持有原脚本定义，需要在后续实际维护时按新脚本重新启动，才能采用本协议。
