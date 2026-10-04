# MOSS 全局审计修复验收记录

后续状态已更新：577 个历史风险日期已完成正式发布，本机 API 与后台任务已恢复并通过实际接口和队列验收，见 [正式发布记录](/F:/MOSS-V3/docs/MOSS_GLOBAL_REPAIR_PUBLICATION_2026-09-05.md)。下文保留发布前的代码与隔离数据验收原始记录，其中“尚未发布”等表述仅指当时状态。

本轮 21 项发现的代码修复与隔离数据验收通过。六个子代理分别负责查询契约、固收计算、损益归因、策略回测、后端性能和前端体验，主负责人整合修改、补做按需加载、独立回归及页面核对，并另安排固收、PnL 和缓存复核。**正式数据库尚未发布，运行中的服务尚未切换；本记录证明可审查的修复结果，不代表已上线。**

验收日期为 2026-09-05。工作目录为 `F:/MOSS-V3`，基准提交为 `abf0c59c9154c0ffd993e4497d10e5a1d3363212`。执行前工作区已有 888 项 Git 状态记录，因此本轮使用实际在途文件副本比较，没有按 HEAD 覆盖或回退他人修改，也没有提交 Git。计划与边界见 原修复方案（执行证据仅保存在本地），文件与哈希见 本轮差异清单（执行证据仅保存在本地）。

两份原有浏览器规格未进入最初目录快照，随后按已记录补丁逆向重建。其中一份初次重建多出一个空行，最终完整性检查发现后，已用首次编辑前的完整读取记录核验原始 SHA，并保留 [基准更正记录](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/baseline-reconstruction-note.json)。业务源文件基准没有因此改动。

覆盖结果如下。表内“通过”均指本轮技术及指定样本验收，业务范围尚未冻结的功能继续保留限制。

| 修复范围 | 原发现数 | 技术验收 | 详细证据 |
| --- | ---: | --- | --- |
| Cube 币种、品类汇总及存储错误 | 3 | 通过 | [查询回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/cube/REPORT.md) |
| 付息日期和负债计息 | 2 | 通过 | [固收回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/fixed-income/REPORT.md) |
| TTM、期初锚点及动作金额覆盖 | 3 | 通过 | [PnL 回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/pnl/RECEIPT.md) |
| Campisi 范围和缺失敏感度 | 2 | 通过，范围待定 | [披露契约](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/pnl/contract-notes.md) |
| 开盘估值及波动率目标生效日 | 2 | 通过 | [策略回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/strategy/RECEIPT.md) |
| 余额页面质量传播 | 1 | 通过 | [前端回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/frontend/FRONTEND-REPAIR.md) |
| 缓存失败传播及容量回收 | 2 | 通过 | [性能回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/performance/REPORT.md) |
| 总账导入同步阻塞 | 1 | 通过 | 同上 |
| 对比度、主题及浏览器断言 | 3 | 通过 | [浏览器证据](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-browser/browser-results.json) |
| 持仓分页格式化 | 1 | 通过 | [性能对照](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/performance/synthetic-before-after.json) |
| 持仓及风险按需加载 | 1 | 通过 | [新旧构建对照](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/loading/build-comparison.json) |
| 合计 | 21 | 技术修复通过 | 正式发布未执行 |

金额错误的根因已在相应层修正。Cube 不再跨币种口径或父子品类重复加总，余额请求必须显式指定单值 CNY，品类读取明确期间和单个已配置类别；口径未冻结的正式查询仍拒绝执行。Ledger 真正的存储失败返回 503，真实空表与故障分别处理。固收付息日期从原始到期日回推，二月截断只影响当期；负债现金流保留报告日事件，却不再多计一天利息。风险规则升级到 v8，现金流读取规则升级到 v2，债券 analytics 的 v3 不变。

归因现在保留完整期间输入。月末 TTM 固定读取 12 个自然月；缺月保持 partial，不能往前补齐。动作归因选择流量起点之前的快照，无法识别的损益留在未分配项。缺快照与已完成的空快照分开，只有日期、任务、来源、规则、缓存身份都匹配且当前源仍为空时，才可识别全清仓。Campisi 继续使用已匹配期初组合金额，但完整输入、未匹配金额、绝对金额和行数都已显示；缺少必要字段的差额进入残差，不能变成选券贡献。计算与页面字段同步记录于 [计算规则](F:/MOSS-V3/docs/calc_rules.md) 和 [页面契约](F:/MOSS-V3/docs/page_contracts.md)。

复核没有只接受开发者的通过结论。独立检查发现了闰日报告日构造失败、CS01 真实零被回退、全 NULL 市值在仓储层被改成零，以及空结果与正常结果的闭合说明颠倒，均已修复后重验。固收复核覆盖现金流边界及真实服务读取；PnL 追加 16 项真实内存 DDL/仓储/服务验证，以及 13 项期末快照和序列化反例。缓存复核另做 12 组三代交错、4,000 次混合操作、仪表盘并发、取消回执和 144 组分页等价比较，未发现本轮未决阻断。

性能改善已经量到实际工作量。八个并发失败请求只执行一次构建；完成缓存、过期索引以及闲置仪表盘锁可以回收，旧构建不能覆盖新代结果。持仓示例的格式化从全量 10,000 行减少为当前页 50 行，全体统计和集中度保持不变。持仓及风险页面复用现有域客户端并延迟加载，在同一组合成接口响应下，首次进入仍分别发出 7 次和 4 次请求，返回持仓页复用查询缓存；新构建实际加载的 JavaScript 分别减少 118,436 和 111,264 字节。生产 RSS 和 p95 没有测量，不据本地单次首屏计时承诺生产提速比例。

界面保留原有主题并修正可读性。19 处对比度反例全部通过，最低为 4.51。主负责人独立重跑 7 个桌面页面和 4 个手机页面，自动可访问性违规、页面异常和横向溢出均为零；人工截图复核又发现首页日期与陈旧提示重叠，已修正固定 92px 容器，并在 390、768、1440 宽度核对边界框和键盘聚焦。后续截图见 [首页修正证据](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/frontend/home-toolbar-browser/RESULT.md)。PnL 新披露在两种宽度共四场组件浏览器验证中可见，证据使用明确标注的组件 harness，未把它写成完整业务流程验收。

主负责人执行的整合检查包括以下项目。增量检查与整合测试存在重叠，不将其相加冒充独立用例总数。

| 检查 | 结果 | 可复现入口或证据 |
| --- | --- | --- |
| 后端 25 个相关文件整合 | 558 通过，2 跳过 | [运行器](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/run-root-checks.cjs)、[JUnit](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-backend.xml) |
| 期末快照最终增量 | 139 通过 | [JUnit](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-pnl-final.xml) |
| 前端 14 个文件整合 | 206 通过 | [日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-frontend.log) |
| 最终归因组件／首页增量 | 11／26 通过 | [归因日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-final-components.log)、[首页日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/frontend/home-toolbar-browser/vitest.log) |
| 两个 Playwright 规格 | 15 通过 | [日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-browser.log) |
| ESLint／TypeScript／改动 Python Ruff | 通过 | `npm run lint`、`npm run typecheck`、[Ruff 日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-final-ruff.log) |
| 六项 debt 审计及编码 | 通过，U+FFFD 为 0 | [日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-final-debt.log) |
| 最终 real 模式隔离构建 | 通过 | [日志](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/root-final-build.log) |
| 首页／市场／候选指标构建护栏 | 三项通过 | [隔离构建护栏入口](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/loading/prepare-guards.cjs) |

两个跳过来自既有银行样例文件缺失，没有冒充通过。excluded surface 的独立验收仍按现有边界排除；Cube 只做本轮纠错与拒绝错误正式查询的测试，不升格为正式功能。市场构建护栏仅允许已有共享 ChartCard、StateSurface 被构建器独立拆块后的名称，保留原字节上限；未提高债务基线来掩盖失败。构建输出位于本轮隔离目录，未覆盖已有 `frontend/dist`。

历史数据已完成候选验证。原库 `F:/MOSS-V3/data/moss.duckdb` 与治理目录在只读共享锁和前后哈希检查下取得一致副本，源 SHA-256 为 `ae5baf522b6ea75fd13fb90a267329f9290b88b4d04bbd2c86c70729b724716f`。受影响集合为 2025-01-01 至 2026-07-31 的 577 个风险日期，负债侧全部受影响，资产现金流全部不变。先完成三日期试算，再使用现有任务层重算其余日期，候选中 v7 残留为零；逐字段对账确认仅负债现金流、派生缺口/比例与规则/缓存版本改变，其余字段保持一致。旧数与独立计算的微小误差均在既有 DECIMAL 存储精度内。

候选详情见 [577 日期对账](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/historical-candidate/verification-all.json)、[物化回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/historical-candidate/rematerialize-all.jsonl) 和 [实际服务读取](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/historical-candidate/read-surfaces.json)。实际服务返回的 2026-07-31 数据还经原样接口响应拦截进入新构建，页面正确显示日期、v8 规则及 -89.22 亿元的 30 日缺口，见 [页面对账回执](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/historical-candidate/browser-receipt.json)。这次使用本地保存的真实候选响应；压力测试等其他端点没有混入合成结果，未宣称已验证运行中的正式 HTTP 服务。

PnL 底表没有重写。只读核查 2025-01 至 2026-07 共 19 个月末，没有重复报告日、重复自然键或 517 NULL，38 次实际仓储守卫均通过。2025 年前 11 个 TTM 窗口因建库前历史不足而 partial，随后 8 个窗口完整；候选中 558 个非月末日期若请求 TTM，将按未定口径返回 503。这是可请求日期范围，不是已经发生的错误请求数，见 [历史期间清单](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/pnl/historical-period-inventory.json)。

研究回测保存了同一输入快照，完成旧、新引擎的 path/horizon 对照，结果继续为非正式研究。七月归档报告记录 826 条执行，当前快照为 816 条，又缺少冻结输入身份，无法将当前更正版冒充该报告的精确重现；归档原件保留，重出范围为 PENDING。历史离线导出及外部报告没有统一目录，本轮无法确认哪些副本已经被下游使用，发布时仍需登记和更正。

结束前再次以只读连接核验原库，577 个日期仍为 v7，数据库 SHA-256 与执行前一致，见 [原库最终状态](F:/MOSS-V3/.codex-tmp/global-repair-2026-09-05/source-final-state.json)。

正式发布需要单独完成代码、数据和进程的一致切换。当前正式库仍保留 v7，部署 v8 读取代码时会拒绝这些旧规则日期，不能先切服务再把这一现象当成数据丢失。发布时应重新校验当前源与候选指纹，取得当时的一致备份，在现有任务流程中对明确的 577 日期执行 risk_tensor 物化，再验证日期列表、详情、历史与前端；源变化须重新对账，不能把整个旧候选库覆盖到正式库。所有 API 进程需采用同一代码和缓存身份，真实 broker 导入回执及生产性能观测也在该窗口完成。回退时必须保持事实和治理记录一致，不能将已知错误的旧结果重新标为正式正确。

仍待业务决定的内容与原方案一致：Campisi 全月还是期初组合、Cube 可加集合及正式资格、旧 Cube 请求默认币种、非月末 TTM、月度多版本权威、快照最大陈旧天数。相关黄金样本的业务批准仍为 PENDING。本轮以清楚披露、保留金额和拒绝含糊请求完成技术修正，没有替业务负责人作口径决定。

调用影响使用指定 GitNexus 项目的本地 CLI；提交索引与 HEAD 一致，但对工作区在途调用仍补做了精确搜索。响应缓存方法级影响为 HIGH/CRITICAL，已扩大到直接消费者和并发验证。当前会话无可调用的 MOSS 指标、血缘、目录或质量 MCP，使用现有契约、计算代码、真实 DDL、治理回执及隔离数据替代；未伪称完成外部业务认证。未抽查的其他页面、宏观评分、全部费用模型和生产身份配置不在本轮 21 项修复结论内。
