# MOSS 开发交付改进执行状态

日期：2026-09-24。依据：[开发交付 PRD](prd-system-development-delivery-2026-09-24.md)。本文件记录当前事实与下一步；隔离调查不代表日常入口已经更新。

## 当前任务

开发基线、同日报告日验收和本地 CI 接线均已纳入隔离集成分支。当前状态为“已纳入集成分支”，且干净工作树的定向复验已经完成；下一步是从该提交发起面向 `codex/V1` 的 PR、取得托管 CI 回执，再决定日常入口的发布与真实数据验收。日常入口尚未切换。

## 源码与工作区

| 项目 | 已核事实 |
| --- | --- |
| 共享工作区 | `F:\MOSS-V3`，`codex/V1`，HEAD `a97f0f3a268500ded23ba4233d55e1e0c96b70a3` |
| 共享工作区状态 | 2026-09-24 盘点为 1,024 条状态路径，含本 PRD 文件；已有暂存修改及大量他人改动，未清理 |
| 远端开发目标 | `origin/codex/V1` = `1c9f297ab29580e3da86bf16b67663e47d943046`，本轮只读远端查询确认 |
| 隔离集成树 | `C:\Users\arvin\.codex\worktrees\dev-delivery-prd-20260924\MOSS-V3` |
| 隔离分支 | `codex/dev-delivery-prd-20260924`，从 `1c9f297a` 创建；首期代码提交至 `6eedef57`，门禁补漏与本状态文件提交后的最新 HEAD 以 `git rev-parse HEAD` 为准 |
| 已纳入修复 | Agent Eval `6a984cd5` 等价移入为 `c25a940d`；余额变动日期守卫 `f19caa85` 等价移入为 `b32ceb48`；余额日期 DTO 与启动守卫为 `20e394f2` |
| 更新与门禁 | 数据更新基础、公开投影、同日验收和页面为 `f12a8846`；V1 窄 CI 选择与作业为 `6eedef57` |
| 未纳入候选 | `d382d034d` 的系统/金融发布原语未被当前 `balance_daily` worker 调用；`1b3cd9fc5` 产品损益与利差切片不在首期同日链路 |

以上是 Git 版本信息。实际日常前端构建的源码快照与后端运行进程需要另行对照，不能由这张表推断为同一版本。

## 运行入口只读证据

本机 `127.0.0.1:5888` 当前由 Vite preview 提供 `F:\MOSS-V3\.codex-tmp\frontend-builds\runtime-sync-20260923-v4\dist`。运行控制的 `frontend.json` 标记 accepted、real，清单 SHA-256 为 `32a92d5f1a5d745b4c915c17a8030097eb52c0cee92323368acf41948f91a549`，只读核对 309 个文件以及首页与入口 JS 的 HTTP 响应均匹配。来源记录写有 snapshotCommit `aff41b729`、目标 `1c9f297a` 和前端源码树摘要 `7983fb8f`。`aff41b729` 是本地工作快照，并非远端 V1 的干净提交；运行构建包含数据更新中心，不能据此推断远端 V1 已有该功能。

本机 `127.0.0.1:7888` 由共享工作区 `.venv` 的 Python 启动 Uvicorn。`/health`、`/health/ready` 与只读 `/ui/balance-analysis/dates` 返回成功，但运行进程没有可确认的源码提交标识，不能以健康状态断言代码版本。当前共享工作区有未提交的后端相关改动。用户正在使用的浏览器地址、后端精确源码快照和规则代码版本均为 `PENDING`。

本轮读到的本机 Node 为 24.13.0，根目录 `.venv` Python 为 3.14.2。CI/隔离验证环境可能不同；执行测试前还要记录解释器、依赖和实际模块导入路径。

## 首期业务链路的调查结果

`origin/codex/V1` 的代码树没有数据更新中心 API、服务、后台任务、页面或相应测试。`f8b03741c` 提供所需基础入口，但其公开响应会泄露 `requested_by`、`cancelled_by` 和步骤内部 `result`；必须同时移入 `d382d034d` 的白名单投影和反例，不能整笔移植该提交。当前 `GET /api/system-read-publication` 返回 `enabled=false`，设置默认值也为关闭；因此本轮 `balance_daily` 只接正式余额计算与指定日期核验，系统只读发布失败场景为“不适用”。`d382d034d` 新增的金融发布原语没有被该版 worker 调用，延后处理。

新增 `tests/test_data_update_balance_integration.py` 以 `2025-12-31` 为同日样本，真实执行 HTTP 提交、worker、正式余额/债券分析/风险张量物化、DuckDB 写入和余额日期及总览接口。合成 USD 资产 100、负债 10、汇率 7.2 的独立预期分别为人民币 720、72、合计 792；定向测试 1/1 通过。真实文件摄取、初始快照及汇率外部获取以合成边界替代，计划任务探测模拟。执行前日期接口因缺少正式血缘返回 503，执行后同日读取成功。浏览器合成用例验证完成回执的同日链接、读端缺日期提示以及等待/失败状态，共 4/4 通过；未模拟接口被拦截，未访问真实后端。`balance_daily` 当前没有独立系统发布阶段，发布失败场景为“不适用”。

页面日期客户端原先接受外壳合法而 `result: null` 的响应，随后在 hook 中访问 `result.report_dates` 抛错。完整客户端和页面实际使用的 deferred 客户端已拒绝缺失、空值与非数组日期，合法空数组仍通过。反例改前 6 项失败、2 项通过，改后 8/8 通过，页面原有错误状态与重试入口继续接管。

## CI 与验证状态

主 `.github/workflows/ci.yml` 仍只在目标为 `main` 的 PR 上运行。本轮扩展仅针对 `codex/V1` PR 的 `.github/workflows/caliber-pr-gate.yml`，现有后端、前端、Agent Eval、条件 Windows 四个作业。后端数据更新源码变化会选中同日集成测试，相关页面变化会选中定向 Vitest 和合成浏览器用例；调度脚本变化会触发 Windows PowerShell 契约，避免 Ubuntu 跳过后误报通过。正式计算路径另选已有 `backend_release_suite.py`，本轮无此类变化。`--dry-run origin/codex/V1` 实际显示同日、浏览器和 Windows 范围均为 true，release 为 false。Agent Eval 本地 7/7 为 void，因为同一 PR 修改评测框架；它只证明编排可运行，不算可信业务探针通过。

独立门禁审查发现，本分支新增的 `test_data_health_schtasks_query.py` 原先没有被健康检查服务变更或测试文件自身变更选中。改前选择器反例退出 1；现已在 `CALIBER_GATE_MAP` 中补齐两个路径的映射，改后映射与工作流测试 37/37、新增测试 1/1、Ruff 和 `--dry-run origin/codex/V1` 均通过。此次干跑的 `matched_tests` 包含该新增测试。托管 GitHub Actions 仍无实际运行记录。

审查还发现两项未来路径选择缺口：单独修改 `frontend/src/features/balance-analysis/` 不会选中同日浏览器用例，单独修改 `formal_balance_pipeline.py` 只选正式 release 套件而不选同日集成用例。当前差异已因余额客户端改动选中浏览器，且未改正式流水线，因此不是本分支的漏跑项；以后动这两处源码时应先补对应选择器反例。

本轮用 `F:\MOSS-V3\.venv\Scripts\python.exe` 从隔离树导入当前 backend，版本为 Python 3.14.2；CI 子代理另用 Python 3.11/pytest 9.0.3 复核 Windows 脚本测试。主代理执行的后端数据更新、调度、健康与同日验收七组测试 60/60 通过，安全修复后 `test_data_updates.py` 与同日测试复跑 30/30。前端四组定向测试 40/40，生产构建及 bundle 守卫通过。余额分析启动守卫首次用未设置数据模式的构建运行失败；改用脚本自带的 real 构建后，又暴露旧合成 DTO 导致自动加载检查失败。更新夹具且不改断言后，`guard:balance-startup:runtime` 和主代理复跑均通过。余额分析整页测试单独重跑 29/29，日期语义与启动守卫 7/7；并行时该页曾超时，单独重跑正常。浏览器合成用例 4/4，React `key` 警告修复后相关用例复验 1/1。CI 映射与工作流测试 37/37，本机 PowerShell 契约以 `--noconftest` 跑 15/15，无跳过。类型检查、相关 ESLint、Ruff、`debt:audit` 及差异检查均通过；全量前端 lint 为 0 错误、1 条未改文件提示。

独立安全复核用真实源单元格解析错误和嵌套字段注入验证：原始诊断保留在隔离治理回执，公开 GET、POST、取消及预检不回显敏感标记，定向 3/3 通过。代价是页面只显示受控失败文案，详细排障须看治理回执。GitNexus 在隔离树建索引成功，提交前检测数据中心 26 文件/397 符号、CI 4 文件/42 符号均为 LOW；建索引时部分 Python scope extraction 报 `Invalid argument`，不能把未覆盖位置的 LOW 当作无影响，已用当前源码直接调用与测试补证据。上述均为隔离代码与合成输入证据，尚未运行真实更新、托管 CI、部署或业务对账。

首期代码提交后的干净工作树依次复跑后端同日 30/30、前端定向 40/40、CI 映射与工作流 37/37；本轮门禁补漏提交后又复跑映射、工作流及新增健康检查测试 38/38，退出码均为 0。最新 `git status --porcelain` 为空。相对 `origin/codex/V1` 的 56 个变更文件经过 `git diff --check` 及 Node 严格 UTF-8 解码、BOM、U+FFFD 检查，均无异常。这些是本地已提交源码的验收结果，仍不代表远端 PR、当前日常运行构建或真实业务对账。

关键本地命令均以隔离树为工作目录，退出码为 0：

```text
F:\MOSS-V3\.venv\Scripts\python.exe -m pytest tests/test_data_updates.py tests/test_data_update_balance_integration.py -q
npm.cmd --prefix frontend run test -- dataUpdatesClient.test.ts DataUpdateCenter.test.tsx PlatformConfigPage.test.tsx balanceAnalysisClient.datesContract.test.ts
F:\MOSS-V3\.venv\Scripts\python.exe -m pytest tests/test_caliber_gate_mapping.py tests/test_ci_workflow_contents.py -q
F:\MOSS-V3\.venv\Scripts\python.exe -m pytest tests/test_data_health_schtasks_query.py -q
F:\MOSS-V3\.venv\Scripts\python.exe scripts/check_caliber_gate.py --base-ref origin/codex/V1 --dry-run
npm.cmd --prefix frontend run guard:balance-startup:runtime
```

## 当前待办与阻塞

1. 在取得代码向 GitHub 推送的具体授权后，将本分支发起目标为 `codex/V1` 的 PR，核对 Ubuntu、条件 Windows、浏览器和 Agent Eval 作业的实际运行记录；当前没有 PR 或托管 CI 编号。
2. 日常入口发布前核对用户实际 URL、前端构建身份、后端源码与规则版本、数据中心计划任务配置。当前真实入口地址与后端版本仍为 `PENDING`。没有执行真实数据更新或业务对账的授权与证据，不能写“日常入口已生效”。
3. 同一报告日的 `balance_daily` 与 `core_financial` 可以同时处于活动状态，可能重复处理余额。首期遵照 PRD 保留现有受理规则，后续应单独定义跨范围互斥及已完成请求的来源版本判断，并补反例。

当前没有阻止隔离实现的问题。外部推送、日常服务切换和真实数据刷新须分别基于明确范围与授权；回退采用既有构建或提交选择机制，不以恢复数据库副本模拟代码回滚。

## 独立复核与下一项任务

同日报告日链路的独立只读审查没有发现新的可复现错误日期、假成功、误写或公开诊断泄露。审查者单独复跑合成集成用例为 `1 passed`。测试替代了文件摄取、初始快照与外部汇率读取，因此证据止于合成快照进入正式物化、请求回执和同日读取；真实输入解析及业务对账仍待验证。

运行交付只读审查确认当前 5888 前端的清单及 309 个文件哈希一致，但它来自共享树的旧工作快照。7888 健康接口正常，实际加载的后端源码提交与规则版本无法核实。共享树的 `scripts/dev_runtime_control.py` 即使执行 `status`、`frontend-plan` 或 `frontend-probe` 也会创建或打开操作锁；本轮没有调用它。该脚本不在隔离交付树中。现有前端构建可凭清单回退，后端运行源码缺少可恢复快照；发布前必须先确定用户实际 URL、后端部署与回退方式、候选构建身份，再单独取得服务切换授权。不能用共享树 HEAD 或数据库副本冒充后端回退依据。

下一项独立任务只处理同日跨范围活动请求冲突。当前受理服务只复用同日同范围的活动请求，完整财务刷新又包含正式余额处理；以不同请求编号提交同日 `balance_daily` 和 `core_financial` 会产生两个依次执行的 run。最小改动限于 `backend/app/services/data_update_service.py`、`tests/test_data_updates.py` 和 `docs/data_update_center.md`：保持同编号同参数返回原回执、同日同范围活动请求复用，新增同日异范围活动请求的 HTTP 409；终态后仍允许新请求。反例需覆盖两个提交顺序及等待、运行、重试状态，并证明治理流只新增首个 run。回退只撤销该局部提交，不删除历史回执。已完成请求的来源版本自动判重需另定来源范围、版本时点和人工重跑语义，不能在缺少口径时顺手实现。
