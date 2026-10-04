# 运行切换验收记录

2026 年 9 月 5 日，前端已从临时 preview 脚本切换到 `dev-frontend.ps1` 正式入口，新版 `dev-keepalive.ps1` 已启用。维护期间禁止恢复、解除维护后自动恢复这两个行为均经过实际停机验证。当前维护状态已解除。停机验证使用原验收构建；收尾期间运行配置另有更新，最终提供的构建见下文。

## 实机发现与补修

第一轮实际停止前端后，保活没有恢复服务。原因是 Windows PowerShell 5.1 在 `ErrorActionPreference=Stop` 下，将 Python 健康探针的 stderr 转成 `NativeCommandError`，直接进入整轮异常处理，跳过了前端恢复分支。这是先前隔离测试未覆盖的调用行为。

先通过新前端入口恢复访问，再将 `Test-FrontendReady` 的探针调用限定在 `RemoteException` 捕获范围内。探针不可达返回 `False`，让调用者继续恢复；标准输出被丢弃，保证函数只返回一个布尔值。解释器解析仍在捕获范围外，恢复前的构建校验和维护门禁保持有效。正式金融计算没有改动。

修复后再次进入维护，停止前端并观察保活。维护期间端口保持关闭，保活连续拒绝恢复；解除维护后，保活于 17:36:50 启动前端，17:36:53 确认恢复，约 13 秒重新可用。此后连续心跳显示 PostgreSQL、API 和前端健康，PostgreSQL 恢复失败计数为零。

## 构建、页面及接口核对

构建位于 `.codex-tmp/global-repair-2026-09-05/build`，271 个文件通过原清单完整哈希验证。清单 SHA-256 为 `6d497a3bed68a8fb1f2f56e1fcb1efe00c33291f314bfad41c8f1bbe79cf0e23`。实际首页与 `assets/index-BBa62Erc.js` 的 HTTP 内容与清单一致，恢复进程使用 `vite preview` 和该构建目录。

浏览器刷新 `/risk-tensor?report_date=2026-07-31` 后可以正常读取风险页，报告日、主风险桶和原有数据质量预警均保留。API 健康、就绪检查、风险张量直连及前端代理均返回 200。风险接口的完整业务结果在切换前后相等，直连与代理相等；除追踪编号和响应生成时间外，25 个元信息字段保持一致。本轮未做新的响应式布局或业务计算验收。

前端切换初期，API、worker 和原有 PostgreSQL 服务保持原进程。后续观察中，保活于 17:41:54 检测到 API 健康探针失败，启动恢复，并于 17:42:08 确认 API 重新可用。最终 API 进程为 29728；恢复入口继承了跳过启动迁移设置，但会加载当前工作区后端代码。恢复后再次核对健康、就绪、风险直连与代理响应，均返回 200，完整业务结果及 25 个稳定元信息字段仍与切换前一致。worker 和 PostgreSQL 保持原进程及启动时间，原有七个暂存文件保留。本次核对只覆盖上述接口，不构成对全部未提交后端改动的验收。

收尾期间，17:49:32 日志再次记录维护门禁，随后前端选择已变为 `.codex-tmp/market-overview-20260905/build`。这次配置更新不是本验收步骤发起的；未将其覆盖回旧构建。保活于 17:49:45 按新选择恢复前端，后续连续心跳健康。最终核对新清单的 270 个文件及首页、入口脚本的 HTTP 哈希，均一致；风险接口结果仍与最初基线相等。这里验证的是当前选择与运行文件一致，不扩大为对该构建全部功能的验收。

## PostgreSQL 与回归测试

私有 55432 集群中，先确认 `moss_release_control_test` 不存在，再新建该专用测试库。使用已核验候选执行完整 Alembic 升级，到达 `c2e94f6a8b10`，随后两项 PostgreSQL 并发测试通过。测试库和 UUID 命名的测试记录保留供复核，未改运行集群配置。

对既有 `moss` 数据库只读检查发现，其版本已经是 `c2e94f6a8b10`，三张 release 表均存在，因此无需再次迁移。没有向该库执行迁移或写入测试数据，现有审批注册表的 PENDING 状态不因技术验证通过而改变。

运行维护相关测试共 81 项通过。新增四项回归使用真实 PowerShell 子进程，覆盖成功、stdout 加非零退出、stderr 加非零退出，以及恢复分支确实被调用；旧实现的 stderr 场景稳定失败，修复后通过。测试进一步要求探针只返回一个布尔值，设置了 20 秒子进程超时。新增测试 Ruff 检查通过。

具体命令包括 `python -m pytest tests/test_dev_keepalive_probe_recovery.py tests/test_dev_runtime_control.py tests/test_dev_runtime_maintenance_scripts.py tests/test_dev_worker_lifecycle_scripts.py tests/test_native_dev_script_contents.py -q` 和 `python -m pytest tests/test_release_control_postgres_concurrency.py -q`，均使用仓库 `.venv/Scripts/python.exe`；后一命令强制指向专用测试库。

完整回执保存在 `.codex-tmp/runtime-switch-2026-09-05/`。维护与构建恢复的操作方法见 [维护文档](MOSS_RUNTIME_MAINTENANCE_2026-09-05.md)。本次是前端运行入口及保活协议切换，不代表整个未提交工作区已经部署或全部技术债已经消除。
