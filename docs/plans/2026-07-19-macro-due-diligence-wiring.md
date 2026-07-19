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
| 前端 MOCK_CAPABILITIES 目录 + mock decision_summary 分数 | 由并行前端任务处理（不在本收口范围） | ↗ 移交 |

### SDD 两阶段评审收口（2026-07-19 下午）

| 评审 | 结论 | 修复项 |
| --- | --- | --- |
| Spec 合规评审 | ✅ 通过 | 排除集含 6 key 的说明已补入本文档 |
| 代码质量评审 | ✅ 通过（复评确认） | I-1 SLSQP 未检查收敛→`*_with_status`+`RISK_PARITY/RISK_BUDGET_SOLVER_NOT_CONVERGED`；I-2 DCC 配对静默跳过→`KeyError`+`DCC_GARCH_PAIR_SKIPPED_*`；M-1 退化协方差→`RISK_PARITY_COV_DEGENERATE` unavailable（新测试）；M-2 warning 令牌统一 UPPER_SNAKE；M-3/M-4 代码简化；M-5 mock 美林卡补黄金腿 |

已知外部残留：`test_macro_toolkit_scripts.py::test_macro_toolkit_api_exposes_analysis_payload` 因并行任务改 `yield_curve_shape`（`SPREAD_30Y_10Y_UNAVAILABLE`）预期漂移，由该任务线收口。

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
