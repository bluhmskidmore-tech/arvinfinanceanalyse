# 全局在线更新实现后的接续记录

本轮已实现共享只读快照选择、五页交互版本固定和完整发布器，并完成多组独立回归与隔离故障证明；正式上线和全局在线更新验收尚未通过。网页 Pro 第三轮返回 `REVISE`。本轮按交接规定的 `pro-codex-loop` 三轮上限结束，保留全部未提交改动，不提交、不推送、不重跑已成功财务。

## 当前运行状态

2026-09-15 11:36:38 北京时间只读核对：7888 API 健康与 5888 前端均为 HTTP 200，运行控制器无维护标记，前端仍使用 `.codex-tmp/pnl-live-cutover-20260914/accepted-build`。`MOSS-DataUpdateQueue` 为 Ready。随后精确进程核对发现既有 worker 父子进程 35036/37052，以及一个实际 keepalive 进程 48428；这些编号仅是观察记录，不能作为后续操作目标。

活动库仍为 3,668,979,712 字节，修改时间为 `2026-09-15T00:02:48.034Z`。完整读取 pointer `data/governance/system_read_publications/current.json` 不存在。没有执行正式完整 COPY/CAS、开启全局读取配置、切换服务、启动候选 7889 或提交新财务更新。旧服务在线不等于新机制已上线。

必须继续保留既有成功请求 `data_update_b0d6c34ba01b47b2b5873c230bd84b08`、日期 `2026-08-31`、PnL generation `financial-20260831-66e1166f10ebf174`。不能为验证新机制重跑该日整链。此前来源核对未发现合法新变更；旧未登记历史文件也不是自行补算依据。

## 已实现部分和验证边界

根因是 API 短只读连接与后台 writer 同时打开活动 DuckDB；已有 writer lock 不约束这些 API 读取，证据不支持连接泄漏。共享上下文现在只对匹配活动库身份的只读路径选择不可变 generation，写任务显式回到活动库。请求、响应流、缓存、原生线程、线程池、冻结结果血缘和精确 PnL 引用使用同一选择；权限、队列和审计仍实时读取。

核心文件为 `backend/app/repositories/duckdb_read_context.py`、`system_read_publication_repo.py`、`backend/app/tasks/system_read_publication.py`、`financial_result_publication.py`、`data_update_center.py`、`scripts/run_global_data_refresh.py`，以及 `frontend/src/router/SystemReadGenerationBoundary.tsx`、`frontend/src/api/systemReadGeneration.ts` 和首页实际刷新按钮。完整路径、影响分析及其他修改文件见计划与独立源码冻结记录。首轮三文件读边界已落地并以真实独立进程读写重叠证明通过，不是只写方案。

完整发布器复用既有锁、逻辑数据库复制、密封、容量保护和指针 CAS。正式来源切点验证及 bounded_v1 资源约束已接入。提交前失败不重跑财务整链，提交后恢复只补元数据。实际子进程终止测试覆盖两侧边界和锁释放，但不证明断电或硬件故障。

| 代表领域 | 新读取与交互接入 | 旧服务浏览器基线 | 新机制正式在线验收 |
| --- | --- | --- | --- |
| 首页 | 已接入；真实刷新按钮重新选择版本 | 已加载 | PENDING |
| 余额 | 已接入；原日期、币种和权限保留 | 已加载 | PENDING |
| 债券 | 已接入；candidate 边界保留 | 已加载 | PENDING |
| 风险 | 已接入；原单位和质量状态保留 | 已加载 | PENDING |
| 损益 | 精确绑定 sealed generation，日期与准备状态同步 | 已加载 | PENDING |

旧服务固定 5/10 并发两轮共 150 次 GET 全部成功，同源八项数值核对通过。债券基线 P95 分别为 1204.119/1757.752 毫秒；损益为 1125.226/667.129 毫秒，尚有超过一秒的样本。它们不是新版本的冷/热或更新中性能，不能删掉这些领域后宣称达标。损益不存在与其他页直接同口径的总额字段，未强行对账；同源检查也不是独立会计审计。

最终独立读取侧回归 14 文件 188 项通过；发布器五文件各自独立 Python 进程共 123 项通过；前端八文件 279 项通过。进程终止恢复两项、保留版本四项另有独立证明，不将不同测试集合简单相加成全仓通过。定向 lint、前端 typecheck、debt audit、bundle guard 通过；编码检查扫描 4513 文件，零新增 U+FFFD；核心改动 `git diff --check` 通过。旧 warmup 期望、facade lint 债务及测试加载器跨模块污染仍单独披露。

验证命令和结果逐项保存在 `.codex-tmp/system-online-update-20260915/independent-cycle2-read-side-final-audit.json`、`independent-cycle3-final-regressions.json`、`independent-cycle3-lifecycle-audit.json`。例如发布器命令为 `.venv/Scripts/python.exe -m pytest -q tests/test_system_read_publication.py`（23 项），进程终止命令为 `.venv/Scripts/python.exe -m pytest -q tests/test_system_read_publication_process_crash.py`（2 项）；其余四个后端文件须分别运行，不把已知旧测试加载器污染误写为整套通过。

父代理再次校验独立冻结清单 20 个文件，全部匹配，并补记主发布器等六个文件的哈希，见 `root-final-freeze.json`。独立最终回执 SHA-256 为 `dc4e98ee16633faf265b5b9e09bf454caf7e2e5dd3b646b9c465569561c3e976`。其中元数据短语 `qualified source-preview candidates=2` 不准确，应按下节证据理解为两个尚未核验的候选；原独立回执保留，父代理补充勘误，不改写独立测试原记录。

候选前端 `.codex-tmp/system-online-update-20260915/accepted-build-v2` 有 306 个文件，现有运行控制器已校验完整清单，未选用或部署。manifest SHA-256 为 `1e7dc350ebcd886dbfb3c44b2e428561a30b9692f6e6274472221f1d798eee66`。较早的 accepted-build 不含最后首页刷新增量，后续不得混用其证明。

## 第三轮复核和下一项精确修复

网页会话为 `https://chatgpt.com/c/6aa791c9-c0b0-83e9-88eb-2ea4002aa3ee`，可见模式 6 Pro。第一轮接受共享读取底座，第二轮接受读取/交互切片，第三轮为 `REVISE`，不接受正式激活和整体完成。网页只收到脱敏技术摘要，没有本地仓库访问或执行测试。

两次正式环境纯只读 bootstrap 资格检查分别在 `03:16:58Z` 和 `03:21:39Z` 停于 `source_preview.foundation`。前六域匹配不等于整体资格通过。后续定点核对证实，两个 completed terminal 的批次号为空、source-version 哈希相同；`_manifest_matches_current_facts` 仅在非空 `ingest_batch_id` 时调用预览 predicate，所以两者返回 `None`。它们并不是两个已合格来源的冲突。

原 producer 在没有新文件时合法传入 `ingest_batch_id or None`，`source_preview_repo._select_manifest_rows` 会按现有 allowlist、归档边界及 family/date/batch/path 规则选择。下一项应仅补资格检查的这个分支，复用原 producer 选择和身份组合，然后依既有 provenance 规则区分未核验与真实冲突。不能只比较两个终态哈希、选任意 latest、伪造旧 child run id，或重新导入来制造非空批次。证据在 `source-preview-null-batch-evidence.json`。

下一轮须先增加经真实 bootstrap 资格入口的失败回归，覆盖空/None 批次、两终态同哈希、按 family 的当前选择变化、非法归档路径与身份不符、显式批次兼容、拒绝时源状态不变及不创建 pointer。合成环境资格通过后再证明 bootstrap 发布；随后只读核验当前正式状态，不重算财务。该修复无需改 producer 行为、业务公式或 schema。

独立 writer freshness 是另一项必要门槛。当前只有已核验状态初始化及 `core_financial` 最后一步发布；`balance_daily` 明确返回 not_refreshed，缺请求关联的 standalone global CLI 会拒绝。市场计划任务等独立 writer 还未纳入完整版本发布，不能开启全局 flag 后默默长期显示旧市场数据。后续应沿已有调用证据补足必要触发/资格边界，不重建调度框架。

即使上述代码缺口补完，正式验收仍要求找到必要、合法的新来源变化，经现有数据中心请求和后台链路完成一次全服务在线更新，同时固定五域做 5/10 并发多轮冷/热读取，观察真实写连接与提交区间、版本切换、日期/来源及数值。当前没有这项证据，不以旧基线、维护恢复或合成成功替代。

## 接续入口

继续前先读取本文件、原 `docs/system-online-update-handoff-2026-09-15.md`、当前计划和验收记录，保留整个脏工作区。下一轮仍由 Sol 主实现、Luna max 独立验证，同时活跃子代理不超过三名；网页继续同一会话但明确新的有界范围。源码或服务状态变化后应重新核对，不能复用历史 PID、旧环境或旧源资格。（相关执行证据仅保存在本地，公开版本不附原文。）
