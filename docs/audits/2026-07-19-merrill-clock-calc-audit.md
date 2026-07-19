# Merrill Clock CN 计算端审计（2026-07-19）

审计对象：commit `e5883600d` 接入的 `backend/app/core_finance/macro/merrill_clock.py` 及
`backend/app/api/routes/macro_toolkit.py` 中 merrill_clock_cn 能力路径。observation-only 口径
（`formal_use_allowed=false`），不影响正式金融链。

## 处置状态

| 级别 | 发现 | 状态 |
| --- | --- | --- |
| Critical C-1 | 增长动量整行 NaN 被 `DataFrame.sum(axis=1)` 静默当 0，停更/常数序列时以 complete 状态输出「滞胀/衰退」 | **已修复**：`compute_growth_momentum` 改为 `min_count=1` + 按行有效权重归一化。测试：`test_merrill_clock_stalled_growth_inputs_degrade_instead_of_fake_stagflation` |
| Medium M-1 | 权重按"列存在"归一化，部分行缺失时动量幅度被压缩约 45% | **已修复**（同 C-1）：测试 `test_growth_momentum_normalizes_by_row_available_weight` |
| High H-1 | 路由宽表 ffill 无陈旧上限 + 月末采样，停更被伪装成新月度样本 | **已修复**：`_load_macro_wide_rows` 按字段记录原始观测日，月频 ≤65 天 / 日频 ≤10 天停止 carry。测试：`test_wide_ffill_stops_after_monthly_stale_cap` |
| Medium M-2 | `industrial_va` 缺失口径矛盾；社融 warning 拼写两套 | **已修复**：`industrial_va` → `INDUSTRIAL_VA_UNAVAILABLE`（非阻断）；社融 → `SOCIAL_FINANCING_YOY_MISSING`。测试：`test_merrill_clock_industrial_va_missing_is_non_blocking`、`test_merrill_clock_social_financing_warning_matches_route_spelling` |
| Medium M-3 | decision_summary 等权计票：observation-only 卡与同源卡双票 | **已修复**（既有）：`_DECISION_SUMMARY_OBSERVATION_KEYS` 使 observation 卡计入分母但不参与方向投票 |
| Medium M-4 | 输入证据 `available` 不看新鲜度 | **已修复**：`_capability_input_evidence_item` 用 `assess_freshness` 标 `stale`/`stale_days`；required stale → `*_STALE` warning + data_status degraded。测试：`test_capability_input_evidence_marks_stale_required_inputs` |
| Low L-1 | 象限边界：动量恰为 0 归属衰退/滞胀侧 | 待文档化；可考虑 \|动量\|<ε 输出中性 |
| Low L-2 | DataFrame 入参分支不做月度重采样 | 待文档化或统一重采样 |

## 各维度结论（摘要）

- 象限判定符号与经典美林时钟一致，无符号错误。
- 输入诚实性：C-1/H-1/M-2/M-4 已修；M-3 已由 observation 投票隔离覆盖。
- 精度维度已检查无实质发现。
- 回归：`tests/test_merrill_clock_capability.py` 等 7 个宏观测试文件 **166 passed**（2026-07-19）。

完整报告见审计子代理输出（2026-07-19 会话）。
