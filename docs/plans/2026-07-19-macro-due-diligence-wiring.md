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
