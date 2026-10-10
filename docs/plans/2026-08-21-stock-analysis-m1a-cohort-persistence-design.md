# `/stock-analysis` M1-A cohort 持久化设计（只读设计稿，未执行）

- 日期：2026-08-21
- 页面：`/stock-analysis`
- page id：`GAP-STOCK-ANALYSIS-PAGE`
- 当前授权边界：仅 `M1-A read-only only`
- 本文性质：评审用设计稿；不代表已批准 schema，不代表已执行 DB 写入

## 1. 目标

本文只回答一个问题：如果后续 owner 批准 `D6a/D6b`，`current_rule_certified` 应该如何以最小专用对象持久化，才能同时满足：

1. 保留现有 `as_produced` 历史不被覆盖。
2. 用可审计的 `cohort_id + version tuple` 表达 current-rule certified 样本。
3. 让 service/API 只能读取 active certified cohort，而不是从混合历史推断。
4. 支持 dry-run、receipt、幂等、备份、回滚和单写者控制。

本文不做任何 schema registry 写入，不创建表，不运行 migration，不触发 task 写库。

## 2. 当前状态与约束

### 2.1 当前已存在对象

现有 Livermore 历史主表有三张：

- `livermore_candidate_history`
- `livermore_candidate_execution_history`
- `livermore_stock_candidate_universe_history`

此外，ready 语义还依赖 matched baseline 生成/读取路径，但它不在上述三张 history 主表内，不能被当前清单遗漏：

- `backend/app/core_finance/matched_baseline.py`

见 [backend/app/schema_registry/duckdb/28_livermore_candidate_history.sql](/abs/path/F:/MOSS-V3/backend/app/schema_registry/duckdb/28_livermore_candidate_history.sql)、[backend/app/tasks/livermore_candidate_history_materialize.py](/abs/path/F:/MOSS-V3/backend/app/tasks/livermore_candidate_history_materialize.py) 与 [backend/app/core_finance/matched_baseline.py](/abs/path/F:/MOSS-V3/backend/app/core_finance/matched_baseline.py)。

### 2.2 为什么不能复用现表覆盖 `as_produced`

不能直接把 current-rule replay 写回现表，原因是结构和写语义都不满足双 cohort：

1. 现表没有显式 `cohort_id`。
2. `materialize_livermore_candidate_history()` 以日期为粒度删除后重写 `livermore_candidate_history` / `livermore_candidate_execution_history`。
3. `repair_livermore_candidate_execution_gap()` 以 `(signal_date, stock_code, signal_kind)` 逻辑键删除后重写执行行。
4. 读服务当前只是披露 `stale_formula_row_count`，没有把 ready 样本硬隔离到 current-rule cohort。
5. `signal-confluence` 当前是从历史窗口即时汇总 replay 状态，不是读取已认证 cohort。

因此，若继续复用现表：

- `as_produced` 会被 current-rule 修复污染；
- `latest run_id` 会被误当 active certified cohort；
- `ready` 仍会混入旧版本样本。

结论：`as_produced` 必须继续只读现表，`current_rule_certified` 必须有独立对象。

## 3. 设计原则

### 3.1 最小对象集

按 PRD 仅设计三个专用对象：

1. `stock_analysis_current_rule_cohort_manifest`
2. `stock_analysis_current_rule_replay_fact`
3. `stock_analysis_current_rule_date_certificate`

不在 M1-A 引入第四张 matched-baseline 专表；matched baseline 的 ready-grade 证据先落在 fact/date certificate 字段中。

### 3.2 逻辑身份

- `as_produced`：现有历史表，继续沿用原逻辑键，不补 `cohort_id`
- `current_rule_certified`：以 `cohort_id` 为一等身份
- `cohort_mode` 固定显式存储，不允许由 `run_id` 前缀推断

### 3.3 活跃 cohort 规则

- 一个页面同一 `cohort_mode='current_rule_certified'` 在任一时点只能有一个 `cohort_status='certified' and is_active=true` 的 manifest
- `is_active` 只能由单独 promotion task 切换
- “最新 run” 不等于 active

### 3.4 读路径 fail closed

service 未来只能：

1. 找 active certified manifest；
2. 用 `cohort_id + version tuple` 精确选 fact / certificate；
3. 找不到则返回 `insufficient` 或 `unsupported`；
4. 不得回退到 `livermore_candidate_history*` 混合历史。

## 4. 候选 DDL（未执行）

说明：

- 以下 SQL 是评审草案，不代表已批准。
- 逻辑主键在文义上必须成立；是否编码为 DuckDB 约束，留给 D6a 批准时按目标 DuckDB 版本确认。
- 为兼容现有历史快照和 task 写法，本文默认“逻辑唯一键 + 写前重复审计 + 索引”方案，而不是强依赖表级约束。

### 4.1 Manifest

```sql
create table if not exists stock_analysis_current_rule_cohort_manifest (
  cohort_id varchar,
  page_id varchar,
  cohort_mode varchar,
  cohort_status varchar,
  is_active boolean,

  requested_start_date varchar,
  requested_end_date varchar,
  observed_start_date varchar,
  observed_end_date varchar,
  certified_start_date varchar,
  certified_end_date varchar,
  evaluation_as_of_date varchar,
  governed_era_start varchar,
  governed_era_end varchar,

  stock_candidate_selection_policy varchar,
  decision_metric_basis varchar,
  coverage_authority_mode varchar,
  strict_coverage boolean,
  fallback_covered boolean,

  candidate_rule_version varchar,
  stock_candidate_selection_formula_version varchar,
  candidate_outcome_formula_version varchar,
  execution_formula_version varchar,
  matched_baseline_formula_version varchar,
  market_gate_rule_version varchar,
  signal_confluence_rule_version varchar,
  macro_formula_version varchar,

  candidate_source_version varchar,
  execution_source_version varchar,
  matched_baseline_source_version varchar,
  macro_source_version varchar,
  theme_overlay_fingerprint varchar,
  choice_catalog_fingerprint varchar,

  plan_digest_sha256 varchar,
  receipt_path varchar,
  receipt_sha256 varchar,
  backup_path varchar,
  backup_sha256 varchar,

  run_id varchar,
  idempotency_key varchar,
  promoted_from_cohort_id varchar,
  promoted_by_run_id varchar,

  completed_dates integer,
  completed_with_signals_dates integer,
  completed_no_signal_dates integer,
  pending_tail_dates integer,
  blocking_pending_dates integer,
  unsupported_dates integer,
  proxy_only_dates integer,
  matched_entry_count integer,
  t5_usable_count integer,
  t20_usable_count integer,
  stale_execution_row_count integer,
  stale_matched_baseline_row_count integer,
  audit_counts_json varchar,

  failure_reason_code varchar,
  primary_blocker_code varchar,
  blocker_summary_json varchar,
  notes_json varchar,

  created_at varchar,
  certified_at varchar,
  promoted_at varchar,
  superseded_at varchar,
  failed_at varchar
);

create index if not exists idx_sa_cr_manifest_page_mode_status
  on stock_analysis_current_rule_cohort_manifest(page_id, cohort_mode, cohort_status, is_active);

create index if not exists idx_sa_cr_manifest_run
  on stock_analysis_current_rule_cohort_manifest(run_id);

create index if not exists idx_sa_cr_manifest_plan_digest
  on stock_analysis_current_rule_cohort_manifest(plan_digest_sha256);
```

逻辑主键：

- `cohort_id`

逻辑唯一性：

- `(page_id, cohort_mode, is_active)` 在 `is_active=true` 时最多一行
- `plan_digest_sha256` 对 `draft|dry_run|certified` 语义应幂等

`cohort_status` 推荐主状态：

- `draft`
- `dry_run`
- `certified`
- `superseded`
- `revoked`
- `failed`

`failure_reason_code` 与 `cohort_status` 分离，避免把失败原因编码进主状态。推荐值至少包括：

- `duplicate_keys`
- `hash_mismatch`
- `version_mismatch`
- `missing_receipt`
- `missing_backup`
- `incomplete_coverage`
- `pit_not_replayable`
- `not_enough_matched_entries`
- `nonzero_stale_formula`
- `fallback_semantics_unapproved`
- `double_active_detected`

计数口径必须单独钉死，避免 requested / observed / certified 三段范围混算：

- `completed_dates`
- `completed_with_signals_dates`
- `completed_no_signal_dates`
- `pending_tail_dates`
- `blocking_pending_dates`
- `unsupported_dates`
- `proxy_only_dates`
- `matched_entry_count`
- `t5_usable_count`
- `t20_usable_count`
- `stale_execution_row_count`
- `stale_matched_baseline_row_count`

以上 promotion counters 一律按 `certified_start_date .. certified_end_date` 内的 signal dates 统计，不按 observed/requested 全范围计数。

为避免把支持区间与计数区间混为一谈，本文把时间语义拆成三层：

1. `certified signal-date range`
   - 即 `certified_start_date .. certified_end_date`
   - 只有落在该区间内的 `signal_date` 才参与 `completed/unsupported/proxy/matched/t5/t20` 等 promotion counters
2. `PIT input support lookback`
   - 可早于 `signal_date`
   - 仅用于 candidate selection/source replay 所需的历史输入支持
   - 不把更早日期本身计入 promotion counters
3. `outcome support interval`
   - 可晚于 `signal_date`
   - 对 T+5/T+20 maturity 来说，需要 `signal_date` 之后、且不晚于 `evaluation_as_of_date` 的 forward observations / exit proof
   - 若 `signal_date` 落在 certified range 内，即使 outcome proof 落在 `certified_end_date` 之后，只要 `<= evaluation_as_of_date`，仍属于该 signal 的支持证据，而不是新增计数日期

当前提到的 180 自然日窗口，只能表述为“resolved evaluation date 向前看的 rolling readiness snapshot window”，用于形成某次评估时的 readiness 观测快照；它不是通用“前置准备窗口”，也不能把 window 外日期本身计入 `completed/unsupported/proxy/matched` 等 promotion counters。

`requested_start_date .. requested_end_date` 与 `observed_start_date .. observed_end_date` 只用于审计和诊断，不能混入 promotion 判定。

若 reviewer 认为诊断计数仍需结构化落地，可选在 manifest 保留 `audit_counts_json`，只放 requested / observed audit-range counts；但这只是审计补充，不改变 promotion 语义，也不扩大 M1-A 实现范围。

### 4.2 Current-rule replay fact

```sql
create table if not exists stock_analysis_current_rule_replay_fact (
  cohort_id varchar,
  signal_date varchar,
  stock_code varchar,
  stock_name varchar,
  signal_kind varchar,

  candidate_rank integer,
  market_state varchar,
  signal_close double,
  selection_close double,
  breakout_level double,
  ema10 double,

  entry_date varchar,
  entry_price double,
  entry_price_kind varchar,
  entry_executable boolean,
  entry_block_reason varchar,
  entry_ex_div boolean,

  exit_date_5d varchar,
  exit_price_5d double,
  return_5d_gross_adj double,
  return_5d_net_adj double,
  exit_date_20d varchar,
  exit_price_20d double,
  return_20d_gross_adj double,
  return_20d_net_adj double,

  price_adjustment_mode varchar,
  buy_cost_bps double,
  sell_cost_bps double,
  slippage_bps double,

  candidate_data_status varchar,
  execution_data_status varchar,
  matched_baseline_status varchar,
  matched_baseline_control_count integer,
  matched_alpha_5d double,
  matched_alpha_20d double,
  control_entry_date varchar,
  control_exit_date_5d varchar,
  control_exit_date_20d varchar,
  control_eval_basis varchar,
  control_pit_proof_json varchar,

  candidate_rule_version varchar,
  stock_candidate_selection_formula_version varchar,
  candidate_outcome_formula_version varchar,
  execution_formula_version varchar,
  matched_baseline_formula_version varchar,
  stock_candidate_selection_policy varchar,
  decision_metric_basis varchar,
  coverage_authority_mode varchar,
  strict_coverage boolean,
  fallback_covered boolean,
  candidate_source_version varchar,
  execution_source_version varchar,
  matched_baseline_source_version varchar,
  run_id varchar,

  evidence_json varchar,
  created_at varchar
);

create index if not exists idx_sa_cr_fact_cohort_date
  on stock_analysis_current_rule_replay_fact(cohort_id, signal_date);

create index if not exists idx_sa_cr_fact_signal_lookup
  on stock_analysis_current_rule_replay_fact(cohort_id, signal_date, stock_code, signal_kind);
```

逻辑主键：

- `(cohort_id, signal_date, stock_code, signal_kind)`

逻辑唯一性说明：

- 同一 `cohort_id` 内，不允许同一股票同一信号日同一 signal kind 出现多行
- 同一 `signal_date` 若无候选，不在 fact 表写零行；由 date certificate 表达 `completed_no_strategy_signals`

### 4.3 Date certificate

```sql
create table if not exists stock_analysis_current_rule_date_certificate (
  cohort_id varchar,
  trade_date varchar,
  certificate_status varchar,
  reason_code varchar,

  affects_completed_stats boolean,
  candidate_count integer,
  executable_candidate_count integer,
  t5_usable_count integer,
  t20_usable_count integer,
  matched_entry_count integer,

  stale_execution_row_count integer,
  stale_matched_baseline_row_count integer,
  unsupported_source_count integer,
  proxy_only_evidence_count integer,
  blocking_gap_count integer,

  candidate_rule_version varchar,
  stock_candidate_selection_formula_version varchar,
  candidate_outcome_formula_version varchar,
  execution_formula_version varchar,
  matched_baseline_formula_version varchar,
  stock_candidate_selection_policy varchar,
  decision_metric_basis varchar,
  coverage_authority_mode varchar,
  strict_coverage boolean,
  fallback_covered boolean,
  candidate_source_version varchar,
  execution_source_version varchar,
  matched_baseline_source_version varchar,
  control_entry_proven_count integer,
  control_exit_proven_5d_count integer,
  control_exit_proven_20d_count integer,
  control_eval_proof_json varchar,
  source_coverage_json varchar,
  blocker_detail_json varchar,
  receipt_path varchar,
  receipt_sha256 varchar,
  run_id varchar,
  created_at varchar
);

create index if not exists idx_sa_cr_cert_cohort_date
  on stock_analysis_current_rule_date_certificate(cohort_id, trade_date);

create index if not exists idx_sa_cr_cert_status
  on stock_analysis_current_rule_date_certificate(cohort_id, certificate_status, trade_date);
```

逻辑主键：

- `(cohort_id, trade_date)`

合法 `certificate_status`：

- `completed_with_signals`
- `completed_no_strategy_signals`
- `pending_tail`
- `blocking_pending`
- `unsupported`
- `proxy_only`

## 5. 版本 tuple 设计

manifest 上需要冻结完整 version tuple，避免 service 在读时重新猜：

- `candidate_rule_version`
- `stock_candidate_selection_formula_version`
- `candidate_outcome_formula_version`
- `execution_formula_version`
- `matched_baseline_formula_version`
- `market_gate_rule_version`
- `signal_confluence_rule_version`
- `macro_formula_version`
- `candidate_source_version`
- `execution_source_version`
- `matched_baseline_source_version`
- `macro_source_version`
- `theme_overlay_fingerprint`
- `choice_catalog_fingerprint`
- `stock_candidate_selection_policy`
- `decision_metric_basis`
- `coverage_authority_mode`
- `strict_coverage`
- `fallback_covered`

date certificate 也必须保存同一套可核对版本字段，不能只保留 `cohort_id + trade_date`，否则单日证书无法独立回答“当天是按哪一套 candidate 选择公式 / outcome 公式 / matched baseline 口径认证的”。

解释：

1. `rule_version` 不够，因为 replay ready 同时依赖 candidate selection / candidate outcome / execution / matched baseline / confluence。
2. `source_version` 不够，因为同源不同公式仍可能改变 ready。
3. `run_id` 更不够，因为它只标识某次执行，不标识读语义。

额外约束：

- `stock_candidate_selection_policy` 与 `stock_candidate_selection_formula_version` 负责回答“这只股票为什么入选候选”。
- `candidate_outcome_formula_version` 负责回答“入选后收益与 usable 统计如何计算”。
- 二者不能混成一个 `candidate_formula_version`，否则后续 duplicate audit、版本漂移和 single-date certificate 都无法精确追责。

## 6. Active promotion 设计

### 6.1 promotion 前置条件

promotion 口径补充：

- 本节所有 `20+100` 与 `unsupported/proxy/stale/matched` 门槛，均只按 `certified_start_date .. certified_end_date` 计算。
- `t5/t20` usable 判定不是“读取更早数据”，而是要求对 certified range 内的 `signal_date` 拿到 `signal_date` 之后、且 `<= evaluation_as_of_date` 的 forward observations / exit proof。
- candidate selection/source replay 若需要更早历史，只能走 `PIT input support lookback`；lookback 只支撑该 signal 的可重放性，不把更早日期本身计入 promotion counters。
- 当前 180 自然日窗口只是 resolved evaluation date 向前的 rolling readiness snapshot window，用于评估时观察 readiness，不扩张 certified era，也不允许把 requested / observed audit-range 的 unsupported tail 混入 promotion 失败。
- 因此，即使 24 个月 requested audit range 内仍有 unsupported / pending / fallback 诊断，只要相关 signal date 不落在 certified era 内，就不能阻断该 certified era 晋升。

只有满足以下条件才允许把 manifest 从 `dry_run` 或 `draft` 晋升为 `certified + is_active=true`：

1. `completed_dates >= 20`
2. `matched_entry_count >= 100`
3. `blocking_pending_dates = 0`
4. `unsupported_dates = 0`
5. `proxy_only_dates = 0`
6. `stale_execution_row_count = 0`
7. `stale_matched_baseline_row_count = 0`
8. `decision_metric_basis = net_next_open_adj`
9. `receipt_path` 与 `receipt_sha256` 已落地
10. `plan_digest_sha256` 与当前批次输入重算一致
11. `coverage_authority_mode` 已明示且 owner 已签字
12. `strict_coverage = true`
13. `fallback_covered = false`
14. `control_entry_proven_count = matched_entry_count`
15. `control_exit_proven_5d_count = t5_usable_count`
16. `control_exit_proven_20d_count = t20_usable_count`

### 6.2 promotion 事务语义

未来写路径应以单事务执行，但要明确假设：DuckDB 不提供可依赖的行级锁语义，因此这里不能假设 “lock active row” 就足以防并发。promotion 必须依赖：

- 外部单写者锁；
- 单事务更新；
- 事务前后双 active 审计；
- fail closed。

推荐顺序：

1. 先取得外部锁 `lock:duckdb:stock-analysis-current-rule-cohort`
2. 事务内查询当前全部 `is_active=true` 的 candidate 集
3. 若 active 行数不是 `0` 或 `1`，直接失败并标记 `failure_reason_code='double_active_detected'`
4. 校验新 manifest 满足 promotion 条件
5. 将旧 active 行置 `is_active=false, cohort_status='superseded', superseded_at=...`
6. 将新行置 `is_active=true, cohort_status='certified', promoted_at=...`
7. 事务内再次审计 active 行数必须等于 `1`
8. 提交事务

双 active 防护备选：

1. 若目标 DuckDB 版本和约束策略允许，可增加单独 active pointer 对象，例如：
   - `stock_analysis_current_rule_active_pointer(page_id, cohort_mode, active_cohort_id, pointer_version, updated_at)`
2. 若不引入 pointer，则必须把 “查询全部 active + 事务内前后审计 + 外部单写者锁” 作为最低保障。

禁止：

- 仅按 `created_at desc`
- 仅按 `run_id desc`
- 仅按“最新 receipt”

## 7. Service 选数规则

未来读服务必须改为两段式：

### 7.1 manifest 选择

```sql
select *
from stock_analysis_current_rule_cohort_manifest
where page_id = 'GAP-STOCK-ANALYSIS-PAGE'
  and cohort_mode = 'current_rule_certified'
  and cohort_status = 'certified'
  and is_active = true
order by promoted_at desc;
```

若 0 行：

- 返回 `replay_closure=insufficient` 或 `unsupported`
- 不得回退到 `livermore_candidate_history_backtest_window_summary()`

若 >1 行：

- 视为治理损坏
- fail closed

实现要求：

- 不允许 `limit 1` 后再声称“可检测 >1”；检测双 active 必须先取全集或先做 `count(*)`。
- 应用层只接受“恰好 1 行 active certified manifest”这一结果；任何其他基数都返回 `insufficient`/治理错误。

### 7.2 fact / certificate 选择

所有读都必须带：

- `cohort_id`
- 完整 version tuple 校验

不可只按日期窗口扫全表。

建议：

- summary 只读 manifest + date certificate
- detail drilldown 再按 `cohort_id + signal_date` 读 fact

## 8. Migrate / backfill 顺序（未来执行计划，不在 M1-A 执行）

### 8.1 D6a 前

1. 交付本设计稿
2. 实现只读 gap ledger service / script
3. 用 gap ledger 证明 current-rule 可重放容量、版本分布、连续覆盖和 blocker 结构
4. owner 单独评审 D6a

### 8.2 D6a 后，D6b 前

1. 若没有其他 migration 先落地，新增 schema registry 文件 `45_stock_analysis_current_rule_cohort.sql`；`29` 已被 commodity schema 占用，不能复用
2. 在同一前提下新增 `v46` migration 注册；实际执行前仍须以当时 registry 最新编号重新核对
3. 新增只写 task，不改读路由
4. dry-run 生成 receipt，不写目标表；receipt 中必须分别给出：
   - requested audit range
   - observed range
   - certified signal-date range
   - PIT input support lookback 口径说明
   - outcome support interval 口径说明（`signal_date` 之后且 `<= evaluation_as_of_date`）
   - promotion counters（只按 certified signal-date range）
   - audit-only counts（requested / observed 诊断口径）
5. 复核 plan digest / row counts / duplicate audit / backup hash
6. owner 单独评审 D6b

### 8.3 D6b 后

1. 备份目标 DuckDB
2. 按月批次或更小批次写入 replay fact；批次切分不改变 certified range 统计口径
3. 生成 date certificate；certificate 只为 certified signal-date range 内日期生成 promotion 所需计数，requested / observed 诊断计数如需保留，进入 `audit_counts_json` 或 receipt
4. 汇总 manifest；manifest promotion counters 只能从 certified signal-date range 内的 signal dates 回卷，PIT input support lookback 与 outcome support interval 只作为这些 signal dates 的支持证据，不新增计数日期
5. 通过 promotion task 切 active
6. M1-C 再接 API / 页面

## 9. 幂等设计

### 9.1 plan digest

`plan_digest_sha256` 应至少覆盖：

- page id
- cohort mode
- requested/evaluation date range
- stock candidate selection policy
- complete version tuple
- source table fingerprints / source versions
- replay parameters（只保留影响结果的）

相同 plan digest 的 live run：

- 若已有 `certified` manifest，返回已存在结果
- 若已有 `dry_run` manifest，允许复用 receipt 或重新 dry-run，但不得新造第二个 active candidate

### 9.2 idempotency key

未来 task 入口应支持：

- 请求方传 `Idempotency-Key`
- 落在 manifest 的 `idempotency_key`
- 与 `plan_digest_sha256` 联合校验

### 9.3 receipt canonical bytes 与 SHA 校验时点

`receipt_sha256` 不能只写“某个 JSON 的哈希”，必须固定：

1. receipt 先按 canonical JSON 规则序列化为稳定 bytes
2. 对该 canonical bytes 计算 `sha256`
3. `receipt_sha256` 写入 manifest / date certificate
4. promotion 前再次从 receipt 文件重算 canonical bytes hash
5. 若重算值与存储值不一致，设置 `cohort_status='failed'` 且 `failure_reason_code='hash_mismatch'`

receipt 语义也必须固定，避免 hash 正确但业务口径混乱：

- receipt 必须把 `requested_range`、`observed_range`、`certified_range` 分开写；
- receipt 必须把 `promotion_counters` 与 `audit_only_counts` 分开写；
- `promotion_counters` 只能对应 certified range；
- `audit_only_counts` 可覆盖 requested / observed 诊断，但不得被 promotion 读取。

最小 canonical 约束建议写入 D6a 附件：

- UTF-8 编码
- key 排序固定
- 数值/布尔/null 序列化规则固定
- 不允许 pretty-print 差异影响哈希

### 9.4 duplicate 审计

每批 live write 前必须先跑：

```sql
select cohort_id, signal_date, stock_code, signal_kind, count(*) as dup_cnt
from stock_analysis_current_rule_replay_fact
group by 1,2,3,4
having count(*) > 1;
```

以及：

```sql
select cohort_id, trade_date, count(*) as dup_cnt
from stock_analysis_current_rule_date_certificate
group by 1,2
having count(*) > 1;
```

任一非空即失败，不进入 promotion。

## 10. 事务、性能与索引

### 10.1 单写者

未来写 task 应引入新锁，例如：

- `lock:duckdb:stock-analysis-current-rule-cohort`

不得复用现有 `lock:duckdb:livermore-candidate-history` 做跨用途 promotion。

说明：

- 这里显式按“DuckDB 无可依赖行级锁”处理。
- 因此单写者控制不建立在 DB 行锁之上，而建立在外部锁 + 单事务 + duplicate/active audit 之上。

### 10.2 事务边界

推荐事务边界：

1. 单批 replay fact 写入一个事务
2. 单批 date certificate 写入一个事务
3. manifest 汇总写入一个事务
4. active promotion 独立一个事务

这样单批失败不会污染既有 certified cohort。

如果 D6a 评审认为“manifest 内 is_active 布尔位 + 外部锁”仍不足以让 reviewer 放心，则应切换到 active pointer 方案，而不是在实现阶段继续模糊化。

### 10.3 索引与读路径

最关键的读条件只有两类：

- `cohort_id + trade_date`
- `cohort_id + signal_date + stock_code + signal_kind`

因此本文只建议这两组索引，避免无边界扩索引。

### 10.4 聚合性能

为避免当前 replay summary 的逐日读放大，未来 summary 应从 date certificate 聚合，不再每次 HTTP 调用重新扫候选历史窗口。

## 11. 备份、回滚、权限

### 11.1 备份

future live write 前必须记录：

- `backup_path`
- `backup_sha256`
- 备份创建时间
- 目标 DuckDB 绝对路径

manifest 上必须保存备份引用，receipt 里也要重复保存。

### 11.2 回滚

默认回滚不是删表或删行，而是：

1. 停用当前 active manifest
2. 重新激活上一个 certified manifest
3. 保留失败批次对象供审计

只有对象损坏且 owner 明确授权时，才允许从写前备份恢复。

### 11.3 权限与单写者

读路径：

- route / service 只读

写路径：

- 仅 task 层
- 仅持锁 writer
- promotion 单独 task

不允许：

- API 路由写库
- workbench/signal-confluence 读接口顺手做修复
- 前端发起隐式 promotion

## 12. 失败状态设计

manifest 主状态固定只用：

- `draft`
- `dry_run`
- `certified`
- `superseded`
- `revoked`
- `failed`

manifest `failure_reason_code` 推荐至少覆盖：

- `duplicate_keys`
- `hash_mismatch`
- `version_mismatch`
- `missing_receipt`
- `missing_backup`
- `incomplete_coverage`
- `pit_not_replayable`
- `not_enough_matched_entries`
- `nonzero_stale_formula`
- `fallback_semantics_unapproved`
- `double_active_detected`

coverage 相关失败需进一步明确：

- `completed_tushare_fallback` 语义当前未定，不能直接当作 `completed` 计入 certify。
- 因此 DDL 必须显式带 `coverage_authority_mode` / `strict_coverage` / `fallback_covered`。
- 在 owner 对 fallback 语义单独签字前，默认 `fallback_covered=false` 且任何 fallback date 不得进入 `certified` cohort。

matched baseline 相关失败也必须显式：

- 若无 control PIT 证明字段，则不得 certified。
- 仅有 control entry count、没有 control exit/evaluation proof，不足以支持 `matched_alpha_5d/20d` 进入 certified read path。

date certificate 推荐 blocker reason code 至少覆盖：

- `missing_required_source_table`
- `missing_full_strategy_coverage`
- `missing_execution_history`
- `missing_matched_baseline`
- `future_dated_execution`
- `pending_t20_tail`
- `stale_execution_formula`
- `stale_matched_baseline_formula`
- `proxy_theme_only`
- `no_strategy_signals`
- `fallback_semantics_unapproved`
- `missing_control_pit_proof`

## 13. D6a / D6b 审批门禁

### 13.1 D6a（schema 对象批准）前必须看到

1. 本设计稿
2. 只读 gap ledger 输出
3. current-rule 版本分布
4. 可认证连续时期证据
5. 受影响 service/task/read-path 边界
6. 回滚与单写者方案
7. `coverage_authority_mode / strict_coverage / fallback_covered` 的 owner 签字语义
8. duplicate audit 规则
9. candidate selection vs candidate outcome version 分拆方案
10. matched baseline control PIT proof 方案

当前结论：D6a 仍是 `NO-GO`。

原因不是文档缺失，而是证据闭环尚未完成，至少还有四个未闭合项：

1. strict 连续覆盖如何定义、如何审计、fallback 是否算 coverage，尚未签字；
2. duplicate audit 规则尚未在目标 current-rule 对象上跑出可复核样本；
3. candidate selection formula 与 candidate outcome formula 目前未完成制度化分拆；
4. matched baseline 的 PIT control proof 还没有闭环证据说明可支持 certified alpha。

### 13.2 D6b（数据写入授权）前必须看到

1. D6a 已批准
2. 目标 DB 绝对路径
3. 备份路径与校验哈希
4. dry-run receipt
5. 预计写入行数 / 分批计划
6. duplicate audit 为 0
7. hash / version mismatch 为 0
8. rollback drill 已设计清楚
9. strict coverage 连续区间已被独立审计
10. fallback dates = 0 或已被 owner 明确签字授权
11. control PIT proof 完整覆盖 matched alpha 统计口径

## 14. GitNexus / rg 影响面

### 14.1 本次文档变更

本次只有新文档，无代码符号变更；按根 `AGENTS.md`，文档变更不需要先做代码符号级 upstream impact。

### 14.2 后续 D6a/D6b 实装前必须做 GitNexus impact 的候选符号

建议至少对以下符号跑 upstream impact：

- `stock_analysis_workbench_envelope`
- `build_stock_analysis_workbench_envelope`
- `livermore_signal_confluence_envelope`
- `livermore_candidate_history_envelope`
- `livermore_candidate_history_backtest_window_summary`
- `materialize_livermore_candidate_history`
- `backfill_livermore_candidate_history`
- `backfill_livermore_candidate_execution_history`

### 14.3 当前用 `rg` 已确认的直接影响面

读路径：

- `backend/app/services/stock_analysis_workbench_service.py`
- `backend/app/services/livermore_signal_confluence_service.py`
- `backend/app/services/livermore_candidate_history_service.py`
- `backend/app/api/routes/market_data_livermore.py`

写路径：

- `backend/app/tasks/livermore_candidate_history_materialize.py`
- `backend/app/tasks/livermore_candidate_history_run.py`
- `backend/app/tasks/livermore_candidate_outcome_maturity.py`
- `backend/app/core_finance/matched_baseline.py`

测试面：

- `tests/test_market_data_livermore_candidate_history.py`
- `tests/test_market_data_livermore_api.py`
- `tests/test_stock_analysis_workbench_api.py`
- `tests/test_livermore_candidate_outcome_maturity.py`

说明：

- 以上是未来实现阶段的重点评审面，不代表本次文档已改动这些文件。

## 15. 推荐的 M1-A 产出边界

M1-A 只读落地建议严格限制为：

1. gap ledger service
2. gap ledger script
3. focused tests
4. 本设计稿

M1-A 不做：

1. schema registry 新文件
2. migration 注册
3. task 写库
4. route / service 切换到 cohort 读路径
5. 页面字段接线

## 16. 结论

最小、可审计、可回滚的方案不是继续挤压现有 `livermore_candidate_history*`，而是：

- 保持 `as_produced` 完全只读；
- 为 `current_rule_certified` 单列 manifest / replay fact / date certificate；
- 用 active promotion 而不是 latest run 决定读路径；
- 用 receipt SHA、plan digest、备份哈希和 duplicate audit 保证可追溯。

这份方案满足 PRD 第 5.4 节对 DDL、迁移、回滚和影响评估的覆盖要求，但当前审批结论仍是 `D6a NO-GO`：strict 连续覆盖、fallback 语义、duplicate 审计、candidate version 分拆、matched baseline PIT 证明都还没有闭环。它本身不构成 D6a/D6b 批准，也不授权任何数据库写入。
