# 私募宏观对冲尽调笔记 → Macro Toolkit 接线优化（2026-07-19）

- 状态：工程闭环进行中（本会话接手：Task1–4 后端接线；不自动 commit）
- 边界：observation-only；`formal_use_allowed=false`；不改正式金融公式；不引入调度器；不猜 P0 owner 签核值
- 对齐笔记：`G:\OpenClaw\.openclaw\workspace\knowledge\wiki\sources\私募宏观对冲尽调笔记.md`
- 镜像模式：Crisis Score（`core_finance/macro/*.py` 纯函数 → `_macro_capability_results` → capability card）

## 目标

把笔记中尚未以 capability 结果卡暴露的核心模块接到 `/macro-toolkit` analysis：

| Task | 能力 | 验收 |
| --- | --- | --- |
| 1 | Merrill Clock（中国版三维动量 + 资产偏好） | `capability_results` 含 `merrill_clock_cn`；缺输入时 `unavailable`/`degraded` 可见 ✅ library+wired |
| 2 | CTA Trend + 与时钟/危机信号的聚合摘要 | `cta_trend_cn` 卡；可选轻量 aggregator 字段 |
| 3 | GARCH / DCC 波动与相关摘要 | `garch_multi_asset` 与/或 `dcc_garch_cn` 卡 |
| 4 | Risk Parity / 再平衡影子摘要 | `risk_parity_cn` 卡；`shadow` 语义 |
| 5 | 前端能力计划表与可见性对齐 | 定义表 `wired/visible`；页面能渲染新卡；debt:audit 不抬基线 |

## 约束

- 每个 Task：TDD → 实现 → 窄测 → commit → spec review → quality review
- 禁止扩大到 PIT schema、调度器、跨页 formal 指标
- `_CAPABILITY_DEFINITIONS` 的 `data_aliases` 必须写真实消费别名
- `decision_summary` 分母自动包含新非 decision 卡；需补测试
