# MOSS 修复正式发布与运行验收

正式风险数据、本机运行接口和真实浏览器已经全部通过本次发布验收。2025-01-01 至 2026-07-31 的 577 个日期已全部采用 v8 规则，实际接口可用日期从 0 恢复为 577，受阻日期从 577 降为 0。前端入口为 [MOSS 首页](http://localhost:5888/)，指定日期入口为 [2026-07-31 风险页](http://localhost:5888/risk-tensor?report_date=2026-07-31)。

此前风险页不可用，是读取代码已经要求 v8，而正式库仍保留 v7。此次使用已验收的任务脚本重算明确的 577 个日期，并恢复 API、后台任务和前端；没有将整个旧候选库覆盖到正式库。此前代码、计算和界面的回归结果见 [复验记录](/F:/MOSS-V3/docs/MOSS_GLOBAL_REPAIR_REVERIFY_2026-09-05.md)，本记录补齐正式数据与实际运行服务的验收。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 正式风险数据 | 577 日、全部 47 列等于验收候选 | [独立后验收](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/review/verification-post.json) |
| 其他事实表 | 65 张表、16,490,573 行与备份相同 | 同上 |
| 数据库结构与迁移账 | 与备份相同 | 同上 |
| 发布治理 | 577 次成功、一次失败后重试，578 次完整尝试 | [全部操作回执](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/rematerialize.jsonl) |
| 实际 HTTP | 三日期详情、24 点历史与验收结果一致，均为 200 | [HTTP 验收](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/http-verification.json) |
| 并发读取 | 8 次详情、4 次日期读取全部成功 | 同上 |
| 后台队列 | Redis 实际投递并收到 worker 心跳 | [后台验收](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/worker-verification.json) |
| 代码与前端构建 | 95 个相关代码/测试文件、271 个构建文件哈希一致 | [版本完整性](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/code-build-integrity.json) |
| 真实浏览器 | 风险页 1440/390、首页和持仓通过，页面异常与失败响应均为 0 | [浏览器验收](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/browser-verdict.json) |

2026-07-31 的 30 日流动性缺口在正式库中为 -8,922,043,296.02964467 元，接口按两位小数显示 -8,922,043,296.03 元，实际桌面和手机页面均显示为 -89.22 亿元。现有数据仍存在到期日、付息频率等缺失，`quality_flag=warning` 继续保留。数值、单位、精度和质量状态分别核对，未把警告改成数据完整。

浏览器直接访问持续运行的 5888，未使用 mock、请求路由或响应替换。风险页两种宽度均看见正确报告日、v8 规则、金额及预警，文档没有横向溢出；首页和持仓页实际 GET 链也已核对。首页初次截图有三个请求仍在执行，另行等待其真实响应，均在约 3.1 至 4.3 秒返回 200，没有漏项，见 [首页补证](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/home-completion.json)。主负责人独立查看了 [桌面风险页](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/risk-tensor-1440.png)、[手机金额与版本](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/risk-tensor-390-liquidity.png)、[首页](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/home-1440.png) 和 [持仓页](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/positions-1440.png)，据此完成最终验收。

发布前先暂停 API 和空闲 worker，并在只读锁下完整备份数据库及 192 个治理文件。副本和源文件指纹一致，备份位于 [backup](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/backup/)，完整文件清单见 [备份回执](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/backup/snapshot-receipt.json)。发布前数据库 SHA-256 为 `ae5baf522b6ea75fd13fb90a267329f9290b88b4d04bbd2c86c70729b724716f`，发布完成后为 `32654ed49ae47bbfc265e77b1389fe2067960c9b735c1b621d741312f109f28f`。

三日期试发布通过后，首轮批量执行遇到另一任务重新启动 API 所产生的数据库锁，并立即停止。独立复核证明失败日期没有丢行、改值或新增 manifest；双方协调维护窗口后完成重试。该次失败的 queued/running/failed 状态和原始回执完整保留。最终新增 1,734 条任务状态、577 条 manifest，原有治理前缀和其他 45 个非锁治理文件未变，详见 [失败核对](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/review/failed-attempt-evidence.json)。

API 与 worker 使用原有开发脚本以隐藏后台进程恢复，API 启动跳过重复存储迁移；健康检查中的 PostgreSQL、DuckDB、Redis、对象存储和首页预热均已就绪。5888 直接服务已经验收的 real 模式构建，代理 7888，没有覆盖原 `frontend/dist`。进程与日志见 [服务恢复回执](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/runtime-restarted.json) 和 [前端启动回执](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/frontend/startup.json)。这些服务保留运行，供本机使用。

恢复服务后再次计算正式数据库 SHA-256，与发布完成时完全相同，见 [运行后数据完整性](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/runtime-data-integrity.json)。本轮文档及证据采用 UTF-8，编码审计扫描 4,265 个文件，未发现新增替换字符；文档差异空白检查通过。

本次由 GPT-6 Astra 独立复核数据发布，GPT-5.6 Sol 负责前端恢复及浏览器验证，主负责人执行备份和正式任务，并核验实际 HTTP、队列回执和最终证据。发布调用现有 `scripts/rematerialize_fixed_income_versions.py`，限定 `--modules risk_tensor`、明确日期和 `--stop-on-failure`，没有开启强制重算或外部曲线获取。可复现执行记录和参数分别保存在 [dry-run](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/dry-run.execution.json)、[samples](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/samples.execution.json) 和 [resume](/F:/MOSS-V3/.codex-tmp/global-publish-2026-09-05/resume.execution.json)。原始中断记录也保留在同目录。

此次完成的是本机正式数据与服务恢复。Campisi 范围、Cube 正式使用资格、非月末 TTM 等业务待决项继续为 PENDING，旧离线导出和外部报告没有自动替换；已有研究回测的冻结输入缺口也未被此次发布消除。首页仍披露治理待办来源未接入，持仓页仍披露黄金样本与指标契约待确认，手机上的长版本标识换行较密。本地短时并发读取不是生产性能基准。本轮未改业务代码、数据库结构或这些待决口径，也未提交 Git。
