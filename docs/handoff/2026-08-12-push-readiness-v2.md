# Push 就绪度快照 v2 与合流移交清单（2026-08-12 22:00）

- 快照 HEAD：`e9ccadae`（本文档落库时会再进一位）
- 背景：两个并行会话共用本仓库。本会话（技术债会话）完成 PRD 27 项修复 + 25 笔提交；并行会话（重构会话）正在滚动落库约 15 个工作主题，工作区尚有约 460 行脏条目。
- 本文档由 10 个只读检查代理的报告汇总而成，是两会话间的正式交接件。v1 仅存在于对话中，本文件为首个落库版本。

## 一、就绪度结论（分层）

| 层 | 结论 | 依据 |
|---|---|---|
| 技术债会话成果完整性 | 完好 | 21/21 提交均为 HEAD 祖先、零 revert、7 项关键修复现效抽查全部在位、35 个新测试收集正常 |
| 后端（主树） | 零可复现失败 | HEAD 全量 8734 passed；334 failed + 53 errors 经双树判别 5/5 + 手递包 17/17 全部归因验证树缺 gitignored 运行时数据；qdb_gl 家族真收敛 |
| 前端（HEAD） | 类型绿、测试预计已清 | typecheck 干净树 exit 0；vitest 曾余 4 文件/6 失败（滞留补丁），`ee1aa6ca` 已落库对应测试与脚本，**合流点需复跑确认** |
| 金融语义（对方 37 提交审查） | 无新缺陷 | 缺失→零/单位/日期窗口/Decimal/断言放宽五类模式均未发现新违规，多个提交为正向修复；口径核对（字典行、FTP 标签）一致 |
| CSS dedup 战役 | 系统性缺陷，已半数处置 | 见第二节 |
| 七道棘轮 | 5 绿 2 红 | 红灯为真实债务增长，见阻断清单 1、2 |

## 二、css-dedup 全量分诊（15 个提交）

“zero visual change”声称经抽样证伪（3/3 命中）后，用选择器级层叠胜者 pre/post 对比（`scripts/css_cascade_triage.py`，三通道：顶层胜者、媒体上下文内胜者、跨媒体顺序）对全部 15 个 dedup 提交机器分诊：

| 提交 | 文件 | 翻转数 | 状态 |
|---|---|---|---|
| `3a54c18a` | dashboardHome.module.css | 15+（含移动端折叠开关隐藏） | **已修复** `2884433f`（整文件还原） |
| `3a54c18a` | dashboardHomeShell.module.css | 0 | 干净 |
| `e37a30c4` | BondAnalyticsViewContent.module.css | 5（降级分支 display/border/渐变） | **已修复** `ce3037d7` |
| `42bd8f3a` | BalanceAnalysisPage.css | 1（跨媒体 justify/min-height） | **已修复** `ce3037d7`（反向补丁，保留 `151636de`） |
| `a7d75d43` | balanceWorkbench.css | 27（含 token→裸色降级） | **已修复** `e9ccadae`（整文件还原） |
| `4d362585` | MarketDataPage.css | 4（含 `!important` 语义丢失） | **已修复** `e9ccadae` |
| `cb2b4f42` | marketHome.module.css | 20（背景/边框/过渡大面积） | **移交**（文件在对方在途改动中） |
| `ed00225d` | dashboardCockpit.css | 3（含 grid-template-columns 结构翻转） | **移交**（在途） |
| `8b452668` | riskOverview.module.css | 1（roBlockedBand align-items/gap） | **移交**（在途，且其后有 `47f02bde` bugbot 修复，需以 HEAD 现状复核） |
| `25999c45` `d334c71e` `fddcdbc5` `0b4a2baf` `ca8f2d64` `75cff39a` | 各 1 文件 | 0 | 干净 |

**工具根因（修复前请停用 dedup 工具）**：`scripts/css-dedup/tsx-evidence.js` 只记录 ≥2 类名共现集合，单类名元素（`className={styles.x}` 最常见写法）永不进证据；`lib.js` coMatch 对同名选择器恒真共匹配仍要求证据，证据缺失时冲突被静默吞掉放行移动。放大器：采证据时 `getChoiceNewsEventsBatch` 尚未落库导致首页新闻区块渲染失败无 DOM 证据。

**分诊方法局限**：只覆盖简单类选择器与同选择器胜者变化，复合选择器与跨选择器特异性交互未建模；分诊 CLEAN ≠ 证明无回归，但 FINDINGS>0 = 确定违反零变化声称。用法：`python scripts/css_cascade_triage.py <commit> [...]`。

## 三、push 阻断清单（按优先级）

1. **debt:audit 提交态红**：`a97c282d` 使 `ProductCategoryPnlPage.tsx` 5229 行 > 基线 5158（提交信息声称跑过审计但行数棘轮未理）。拆组件偿还，或按 D2 基线治理规则补签核上调。
2. **mypy 棘轮红**：工作区态 1532 错误 vs 基线 1499。提交态部分（`choice_adjustment_factors` 等 theme-breakout/stock 系列）需修复或再基线；怀疑在途的 `duckdb_repo.py` fetch 返回类型标注改动扇出 6 个已提交文件（`tuple[Any, ...] | None is not indexable` 同签名），合流前请确认。
3. **视觉基线无签核上调**：`7e529e61`（nocturne palette）把 tokens.css hex 105→122、designSystem.ts 203→205，与 D2 基线治理文档点名的反面案例逐字节一致，且当前实际值恰好满格。请补签核说明或回退基线并偿还 19 个 hex。
4. **3 个带翻转 dedup 提交**（marketHome 20 / dashboardCockpit 3 / riskOverview 1）：文件都在你方在途改动中，请在各自主题落库前用分诊脚本核对并还原被翻转的层叠（可参考 `2884433f`/`e9ccadae` 的还原模式）。
5. **工作区收敛**：约 15 个主题、预估 14–18 批提交（2–4 小时）；约 115 个生成物（截图 PNG、probe 脚本、`.tmp-*` 目录）建议一次删除动作清掉，不占提交批次。
6. 全部收敛后：干净树复跑 typecheck + vitest + 全量 pytest + 七道棘轮，绿灯即可 push（本地 codex/V1 领先 origin 约 80 提交）。

## 四、移交明细（非阻断）

- **缓存竞态 2 处**（早前移交单遗留）：仍未修复，缺陷在你方在途改动内，随主题落库时处理。
- **Campisi bridge 字典覆盖缺口**：`68158cc8` 的字典注册对 bridge 路径覆盖不完整，MTR-PAT-308/309 需补 bridge 条款、306-308 需补证据列，建议补进 `tests/test_campisi_component_goldens.py`。
- **evidence_ref 悬空**：`position_sizing.py:41` 的 `OOS_VALIDATION_EVIDENCE_REF = "tmp-strategy-reports/walk-forward-first-run.md"` 经 API 披露，但该文件不在任何提交树也不在工作区。请补交证据文件或改指向已入库文档。
- **coverage_note 分类器 fail-open**：`market_data_livermore_service.py:268` 关键词白名单判错误注记，新错误措辞会被静默当 informational；主降级通道不受影响，低危。
- **mypy 残项**：choice_stock +1（实测 13 vs 基线 12）。
- **测试可移植性（结构性）**：334 个干净检出失败全部依赖仓库外运行时数据（`data/moss.duckdb`、`data_input/*.xls`），且随新测试恶化（262→334）。建议按 `tests/ci_skip_registry.json` 机制扩围登记 skip-if-missing，或提供最小 fixture 数据集。
- **提交纪律**：乱序落库（源码引用未落库符号）在审查范围内实证 1 例、自认 ≥9 例，多个时间窗口 HEAD 不可用、不可 bisect。建议原子提交：符号与其引用同批落库。

## 五、技术债会话本轮动作记录（今晚）

- `0a54b138`：落库我方最后一个延期测试文件（macro refresh per-series 明细透出，27 passed）；配套 normalize hunk 已被你方 `2bad6989` 吸收，我方延期清单归零。
- `2884433f` / `ce3037d7` / `e9ccadae`：五个文件的 dedup 层叠回归还原（明细见第二节）。
- 核销：手递包家族真回归已由你方 portfolio-home 收口修复（主树 17/17 passed）；explained_pnl、selection 重写、票据 nullable 三项确认收口且测试绿；白名单迁移、skip registry 登记、uv.lock 重同步三项确认自愈。
