# 私募宏观对冲尽调笔记 → Macro Toolkit 接线优化（2026-07-19）

- 状态：工程闭环已落地（Task 1–5；前端 mock 可见性对齐已 commit）
- 边界：observation-only；`formal_use_allowed=false`；不改正式金融公式；不引入调度器；不猜 P0 owner 签核值
- 对齐笔记：`G:\OpenClaw\.openclaw\workspace\knowledge\wiki\sources\私募宏观对冲尽调笔记.md`
- 镜像模式：Crisis Score（`core_finance/macro/*.py` 纯函数 → `_macro_capability_results` → capability card）

## 目标

把笔记中尚未以 capability 结果卡暴露的核心模块接到 `/macro-toolkit` analysis：

| Task | 能力 | 验收 | 状态 |
| --- | --- | --- | --- |
| 1 | Merrill Clock（中国版三维动量 + 资产偏好） | `capability_results` 含 `merrill_clock_cn`；缺输入时 `unavailable`/`degraded` 可见 | ✅ |
| 2 | CTA Trend | `cta_trend_cn` 卡 | ✅ |
| 3 | GARCH / DCC 波动与相关摘要 | `dcc_garch_cn` 卡（`garch_multi_asset` 未单独开卡） | ✅ |
| 4 | Risk Parity 影子摘要 | `risk_parity_cn` 卡；`shadow=true` | ✅ |
| 5 | 前端 mock / 可见性对齐 | mock 能力卡 + 页面证据计数；debt:audit 未抬基线 | ✅ |

### 评审残留项收口（2026-07-19 复审后）

| 残留项 | 处理 | 状态 |
| --- | --- | --- |
| decision_summary 观察卡投票 | 4 张 observation 卡（merrill/cta/dcc/rp）计入可用分母但不参与久期/信用方向投票；result 增加 `formal_use_allowed=false` 与 `observation_excluded_count`。注：排除集实际含 6 个 key——并行静默降级任务把 `cross_market_linkage`/`rate_turning_point` 也接为 observation 卡，同口径排除，属预期共存 | ✅ |
| Merrill `next_step` 英文脚手架 | 替换为中文观察口径文案（补齐 PMI 新订单/发电量等增长代理历史） | ✅ |
| DCC/RP 脚本 parity 守护 | 新增 `garch_standardize`、`classify_warning`、`solve_risk_parity`、`solve_risk_budget`、`risk_contributions` 库-脚本 parity 测试（脚本无 Wind 耦合，仅 akshare 顶层 import，本环境可导入） | ✅ |
| 前端 MOCK_CAPABILITIES 目录 + mock decision_summary 分数 | `70b17badb` 已对齐 observation 投票口径 | ✅ |

### SDD 两阶段评审收口（2026-07-19 下午）

| 评审 | 结论 | 修复项 |
| --- | --- | --- |
| Spec 合规评审 | ✅ 通过 | 排除集含 6 key 的说明已补入本文档 |
| 代码质量评审 | ✅ 通过（复评确认） | I-1 SLSQP 未检查收敛→`*_with_status`+`RISK_PARITY/RISK_BUDGET_SOLVER_NOT_CONVERGED`；I-2 DCC 配对静默跳过→`KeyError`+`DCC_GARCH_PAIR_SKIPPED_*`；M-1 退化协方差→`RISK_PARITY_COV_DEGENERATE` unavailable（新测试）；M-2 warning 令牌统一 UPPER_SNAKE；M-3/M-4 代码简化；M-5 mock 美林卡补黄金腿 |

已知外部残留：已由 `9b4854871` 锁定诚实降级契约（有 30Y → complete；无 30Y → degraded + `SPREAD_30Y_10Y_UNAVAILABLE`）。

### 下一步波次（2026-07-19 晚）

| Commit | 内容 |
| --- | --- |
| `89b45263c` | 观察模型共享 helpers + LEI 缺失月不再零填 |
| `9b4854871` | 锁定 yield_curve_shape 诚实降级测试契约 |
| `70b17badb` | mock decision_summary 对齐 observation 投票 |

SDD 复审：Spec ✅ / Quality ✅（Minor 已在下一波收口）。

### 波次 W（2026-07-19）：LEI 单测 + 共享排除常量 + 价格腿可读

| Task | Commit | 状态 |
| --- | --- | --- |
| W1 LEI 缺失月专项单测 | `b95f3a8d8` | ✅ |
| W2 mock/后端共享 observation 排除 JSON | `f4459d7f9` | ✅ |
| W3 CTA/DCC/RP 价格腿可读诊断+种子测试 | `1e811b4c4` | ✅ |

SDD 复审：Spec ✅ / Quality ✅（Important 残留：mock `missing_count` 语义与后端不完全一致；配置 import-time 加载需随包分发）。

**发布清单（R2）**：`config/macro_decision_observation_keys.json` 必须随部署包分发；路由改为懒加载后，缺文件不再在 import 时拖垮整个 macro_toolkit，但首次构建 `decision_summary` 会明确失败。

### Task W3：CTA / DCC / Risk Parity 多资产价格腿可读性（2026-07-19）

**诊断（wiring vs 缺数 vs 历史过短）**

| 环境 | 根因 | 证据 |
| --- | --- | --- |
| 分析 API 薄种子（`_seed_choice_tushare_macro_db`） | **历史过短 + 缺腿** | CSI300/CSI500/CU 仅 1 日快照；无 `fact_commodity_futures_daily` → `NH0100.NHF` 空；CTA/DCC/RP 诚实 `unavailable`（`*_HISTORY_SHORT` / `NANHUA_MISSING`） |
| 真实 `data/moss.duckdb`（含 2026-07-19 commodity ingest 后） | **非 wiring 故障** | `sh000300`/`sh000905` ≈732 行（至 2026-07-10）；`CU0`/`NH0100.NHF` ≈614 行（至 2026-07-17）；`_macro_capability_results` 三卡均为 `complete` + 可读 headline |
| 别名解析 | 无错位 | `sh000300`→`CA.CSI300`；`sh000905`→`CA.CSI500`；`CU0`→`CA.COPPER`；`NH0100.NHF`→`NHCI.NH`（commodity SQL） |

**工程动作**

- 未改生产接线（真实库路径已可读）；未跑 commodity 再刷新（CU/NHCI max=`2026-07-17` 已足够）。
- 新增 `test_multi_asset_observation_cards_readable_when_price_history_seeded`：temp DuckDB 注入 ≥260 日四腿历史，断言三卡 `complete`/`degraded` 且 primary metric / headline 非空。
- 薄种子 unavailable 契约保持（`test_macro_toolkit_api_exposes_analysis_payload`）。
- 薄分析种子 CTA/DCC/RP = unavailable by design（历史过短）；可读路径见 e2e 种子测试 / 真实 moss.duckdb。

**残留**

- 观察卡四腿不含黄金/原油（`AU0`/`SC0`）；脚本侧可有金油，capability 卡仍只消费 HS300/CSI500/铜/南华。
- 指数收盘相对商品略滞后（指数 max 2026-07-10 vs 商品 2026-07-17）；交集仍远超 DCC/RP 最小历史。
- 全站调度器仍不存在；商品/指数新鲜度仍依赖手动 ingest。

## 约束

- 禁止扩大到 PIT schema、调度器、跨页 formal 指标
- `_CAPABILITY_DEFINITIONS` 的 `data_aliases` 必须写真实消费别名
- `decision_summary` 分母自动包含新非 decision 卡
- GitNexus MCP 本轮不可用，改用 grep / 定向测试做影响面核对

## 验证

```bash
python -m pytest tests/test_merrill_clock_capability.py tests/test_macro_observation_capabilities.py tests/test_macro_toolkit_decision_summary.py tests/test_macro_toolkit_scripts.py::test_macro_toolkit_api_exposes_analysis_payload -q
# frontend
npm run test -- MacroToolkitPage.test.tsx -t "renders macro observation as a read-only" --run
npm run debt:audit
```
