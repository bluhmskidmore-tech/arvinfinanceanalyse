# WP-A2 · 刷新回执 `running` 六天仍被当作"正在跑"

- 泳道：L1 后端/运维，第 2 个（与 WP-A1 无共同文件，可并行）
- 层：Python（`backend/app/services/`）+ pytest
- 难度：中（逻辑小，但要保住缓存指纹与前端消费者的语义）
- 前置：无
- 后续：WP-G 的 `gate` 分区直接消费本包新增的状态

## 目标

`load_macro_toolkit_refresh_receipt_health()` 对 `status = "running"` 的回执增加"跑了多久"的判断：超过阈值（默认 6 小时，可配置）归为新状态 `abandoned`，`ready=False`，`missing_fields` 与 `analysis_warnings()` 明确说出"上次刷新自 X 起未完成，已 N 小时"，而不是今天这种把六天前的 `running` 与六秒前的 `running` 一律报成"完整性校验未通过：receipt.status、receipt.exit_code、…17 项"。

## 根因

`backend/app/services/macro_toolkit_refresh_receipt_service.py:96-205` 只做字段完整性校验，没有任何时间维度。`running` 存根天然缺 `status ∈ {success, degraded}`、`exit_code = 0`、`steps`、`latest_observation_dates`，于是被归为 `blocked`，`analysis_warnings()` 把 17 个缺失字段名拼成一句话透给页面（审计 H1 原文就是这句）。当前生产回执 `data/logs/macro_toolkit_freshness_refresh_receipt.json` 正是 2026-08-27T10:50:15Z 的 `running` 存根（445 字节，`steps: []`），上游原因见 WP-A1。

## 改动范围

`backend/app/services/macro_toolkit_refresh_receipt_service.py`：

1. 新增阈值常量与读取：`RUNNING_RECEIPT_STALE_AFTER_HOURS = 6.0`，允许 `Settings` 覆盖（若 `backend/app/governance/settings.py` 加字段，命名 `macro_toolkit_running_receipt_stale_hours`；不想碰 settings 就用环境变量 `MOSS_MACRO_TOOLKIT_RUNNING_RECEIPT_STALE_HOURS`，二选一，任选其一并在报告里说明）。
2. 在 `:142` 判定 `run_status` 之后：若 `run_status == "running"` 且 `generated_at` 可解析且 `now - generated_at > 阈值`，则 `status = "abandoned"`，`missing_fields` 追加 `receipt.abandoned_running`（保留原有其它缺失项不动，便于排查），并记录 `age_hours`（新增数据类字段 `running_age_hours: float | None = None`，默认 None，`as_payload()` 一并输出）。
3. `analysis_warnings()`（`:79-93`）增加分支：`status == "abandoned"` → `f"最近一次定时宏观刷新自 {generated_at} 起未完成（已 {age:.0f} 小时），方向性结论已关闭；原始指标仅作未验证证据。"`。`running` 且未超阈值的行为**保持不变**（仍是 `blocked` + 完整性文案），避免改变短暂运行窗口内的语义。
4. `_health()`（`:374-396`）的 `ready` 集合不变（`abandoned` 自然为 False）；`cache_fingerprint = f"{status}:{content_fingerprint}"` 已含状态，`abandoned` 会自动得到新指纹，使 `market_home_response_cache` 中按指纹分键的分析缓存失效——这是期望行为，报告里点明。
5. `now` 通过可注入参数获取（例如 `load_macro_toolkit_refresh_receipt_health(receipt_path=..., now=None)`，默认 `datetime.now(UTC)`），测试才能固定时间。

`tests/test_macro_toolkit_refresh_receipt_service.py`：在现有 `test_running_receipt_blocks_directional_analysis`（`:121`）旁新增

- `test_running_receipt_older_than_threshold_is_abandoned`：`generated_at = now - 7h` → `status == "abandoned"`、`ready is False`、`"receipt.abandoned_running" in missing_fields`、`analysis_warnings()[0]` 含"未完成"与"7 小时"、`cache_fingerprint` 以 `abandoned:` 开头且与同内容 `running` 的指纹不同。
- `test_running_receipt_within_threshold_stays_blocked`：`generated_at = now - 1h` → 行为与今天一致。
- `test_running_receipt_threshold_is_configurable`：阈值设 0.5h，`now - 1h` → `abandoned`。

## 不得触碰

- 不改 `REQUIRED_STEPS`、`EXPECTED_SOURCE_VERSION`、`RECEIPT_SCHEMA_VERSION` 等校验常量，不放宽任何现有校验。
- 不改 `scripts/macro_toolkit_freshness_refresh.py` 写回执的方式（心跳、`started_at` 等属另一个改动，本包不做）。
- 不改 `macro_toolkit_route_support.py` 里的 `_gate_*` 函数：它们只看 `ready`，新状态无需它们感知。
- 前端不改。但要**核一遍**新状态值不会撞到前端已有的字面量分支：`frontend/src/features/macro-toolkit/` 中的 `"blocked"` 判断全部针对 `dependency_gate.status` / `refresh.status`（补数任务），不是回执状态；`MacroToolkitDataHealthSections.tsx:420` 的 `repairTicketReceiptStatus` 需要看一眼是否把回执 `status` 直接渲染——若是，`abandoned` 会以英文原样透出，报告里记为后续项（DESIGN §7 不透英文枚举），本包不改前端。

## 验收

```bash
python -m pytest tests/test_macro_toolkit_refresh_receipt_service.py -q          # 全绿，含 3 个新用例
python -m pytest tests/test_macro_toolkit_scripts.py -q                           # 回执消费方回归
python -m pytest tests/test_live_route_page_contract_completeness.py -q
```

再用当前生产回执做一次真实读取（只读，不写）：

```bash
python -c "from backend.app.services.macro_toolkit_refresh_receipt_service import load_macro_toolkit_refresh_receipt_health as f; h=f(); print(h.status, h.ready, h.running_age_hours); print(h.analysis_warnings()[0])"
```

预期 `abandoned False <约 140+ 小时>`，第一条 warning 是"自 2026-08-27T10:50:15… 起未完成（已 N 小时）"。

## 报告要求

根因、改动文件、验证命令与结果、剩余风险（至少：阈值 6 小时对"正常长任务"是否过严，需 owner 确认；`abandoned` 目前仍与 `blocked` 同样阻断结论——是否应降级为 `review` 是交接单 H2 的裁决，本包不越权）。对 `backend/app/core_finance/` 的影响：无。
