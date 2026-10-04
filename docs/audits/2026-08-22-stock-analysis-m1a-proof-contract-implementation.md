# `/stock-analysis` M1-A 证明合同实施复核

- 日期：2026-08-22
- 页面：`/stock-analysis`
- 页面边界：`observational_only`、`formal_use_allowed=false`
- 本轮结论：证明合同与 schema proposal 已落地；D6a / D6b 生产认证仍为 `NO-GO`

## 1. 本轮完成项

1. 日历 receipt 合同
   - 固定来源 `tushare.trade_cal:SSE`。
   - 语义固定为 `realized_calendar_as_observed`，不冒充历史时点发布快照。
   - 覆盖完整自然日、拒绝重复日期并生成稳定哈希。
   - 默认 `provisional`；只有 `approved + owner_approval_id` 才允许认证。
2. current-rule 零信号证书
   - 只接受 `rv_livermore_stock_candidates_bundle_v7 + exp3b`。
   - requested / resolved / certificate 日期必须一致。
   - 只接受 policy-active 的真实零候选；`null`、阻断、future business date、future availability 均 fail closed。
   - 要求 strict coverage、无 fallback、已批准的开市日日历 receipt。
3. matched-baseline evaluation-cutoff proof
   - entry 固定为 next open，T+5 / T+20 exit 不得晚于 evaluation date。
   - observation / adjustment factor 必须带 `source_version + run_id`。
   - source availability 必须由显式 receipt 证明，且 `available_at <= evaluation_as_of_date`；缺证据或未来证据均不可用。
   - control universe 重复逻辑键直接失败，不静默去重或虚增样本。
   - 汇总只披露“存在至少一个可用 control entry 的唯一 candidate key 数”，不冒充页面 `matched_entry_count`。
4. current-rule cohort schema proposal
   - 三表 proposal：manifest、replay fact、date certificate。
   - proposal 可在内存 / 临时 DuckDB 幂等执行并验证字段与索引。
   - 未注册 v46；生产 `register_all()` 仍以 v45 结束，普通启动不会创建三张 proposal 表。

## 2. 本轮明确未做

- 未修改 `data/moss.duckdb`，未应用 v46。
- 未新增 materialize / promotion 写 task。
- 未把 calendar、zero-signal 或 baseline proof 接入 runner / gap ledger 的正式结论。
- 未修改 service、API、前端或页面读路径。
- 未把 caller 自报的 source availability receipt 当成已获 source authority 背书。
- 未替 owner 决定 carry-forward、fallback 或“每个 candidate 是否必须固定 20 个 controls”。

## 3. 验证结果

| 验证范围 | 结果 |
| --- | --- |
| calendar receipt + zero-signal certificate | `27 passed` |
| matched-baseline proof | `20 passed` |
| cohort schema proposal + schema registry guards | `40 passed` |
| selection runner + gap ledger 回归 | `28 passed` |
| API lifespan + worker bootstrap 回归 | `32 passed` |
| 定向 Ruff / py_compile / diff-check | 通过 |

真实库只读抽查：

- 2025-09-24 current-rule selection：4 个候选。
- 在不提供 source availability receipt 时，4 个抽样 control 的 usable entry 为 0，证明链保持 fail closed。
- DuckDB SHA-256 前后均为 `896FB0AB723ABF2044F80155919443314D82B759F53DEEB83BB7C9B690DC3E2F`。

## 4. 仍然阻断生产认证的事项

1. calendar authority 尚未由 owner 批准；当前不得生成 approved receipt。
2. strict coverage 仍只有孤立日期，未形成可认证连续区间。
3. source availability receipt 目前只是待接入的技术合同，尚无受控生成 task、持久化路径和独立 authority attestation。
4. matched-baseline 20-control 覆盖规则尚未签字；不得用“任一可用 control”替代页面 20 / 100 门槛。
5. schema 仍是 proposal-only；D6a 批准后才可注册迁移，D6b 批准后才可写 cohort。
6. 页面继续只消费现有 observational 结果，不能展示“生产闭环已完成”。

## 5. 最终判定

- M1-A 证明合同：`PASS`
- schema 设计与临时执行：`PASS (proposal-only)`
- D6a schema 自动迁移：`NOT AUTHORIZED`
- D6b 数据写入：`NOT AUTHORIZED`
- `/stock-analysis` 生产数据认证闭环：`NO-GO`

