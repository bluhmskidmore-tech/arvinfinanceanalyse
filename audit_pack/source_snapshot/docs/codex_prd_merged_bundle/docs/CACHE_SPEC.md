# CACHE_SPEC.md

## 1. 目标

本规范定义债券金融分析系统的运行时缓存策略。缓存必须服从系统治理边界：

- 正式金融计算只允许在 `backend/app/core_finance/` 实现。
- `backend/app/api/` 只做参数校验、鉴权、调用 service、响应映射。
- DuckDB 在请求链路中只读，写入只允许经由 `backend/app/tasks/` / worker。
- Scenario 与 Formal 在缓存、表、结果元数据上严格隔离。

## 2. 分层

### L0 前端查询缓存

用途：仅用于 UI 响应提速。

技术：TanStack Query。

适用对象：
- 首页总览
- 筛选器元数据
- 最近访问的 drill 首层聚合

禁止事项：
- 不得在前端补算正式金融指标
- 不得把前端缓存当作正式口径

失效方式：
- 监听响应中的 `result_meta.cache_version`
- 监听 `result_meta.source_version`
- TTL 仅作兜底

### L1 Redis 响应缓存

用途：缓存高频、幂等、聚合型 API 响应。

适用对象：
- `/ui/home/overview`
- `/ui/bonds/monthly-average`
- `/ui/pnl/formal-overview`
- `/ui/risk/summary`
- `/ui/meta/dimensions`
- Agent 的只读摘要结果

禁止事项：
- 不缓存任意 SQL
- 不缓存权限敏感大明细
- 不缓存 Formal/Scenario 混合结果
- 不缓存带人工未审批调整的临时结果

### L2 DuckDB 物化分析缓存

用途：分析事实表、宽表、重计算结果的物化缓存。

适用对象：
- `fact_bond_monthly_avg`
- `fact_interbank_monthly_avg`
- `fact_formal_pnl_fi`
- `fact_nonstd_pnl_bridge`
- `fact_pnl_bridge_daily`
- `fact_risk_tensor_daily`
- `fact_formal_analytical_bridge_daily`
- `fact_fx_converted_positions_daily`

写入规则：
- 只允许 worker / tasks 写入
- API 路径只读
- 构建作业必须写入 `cache_build_run`

### L3 PostgreSQL 缓存治理元数据

用途：记录缓存构建、失效、版本与审计。

核心表：
- `source_version_registry`
- `rule_version_registry`
- `cache_manifest`
- `cache_build_run`
- `cache_invalidation_log`
- `cache_refresh_policy`

## 3. 缓存键

统一结构：

```text
{domain}:{view}:{date_or_month}:{basis}:{position_scope}:{currency_basis}:{source_version}:{rule_version}:{filter_hash}
```

示例：

```text
bonds:monthly_avg:2026-03:formal:asset:CNY:sv_9f23:rv_20260409:fh_ab12
pnl:formal_fi:2025-12:formal:all:CNX:sv_71cd:rv_20260409:fh_88de
risk:summary:2026-03-28:formal:asset:CNY:sv_2a90:rv_20260409:fh_01ef
```

### 键组成说明

- `domain`：bonds / interbank / pnl / risk / bridge / fx / agent
- `view`：monthly_avg / summary / overview / cube
- `date_or_month`：报告日或报告月
- `basis`：formal / analytical / scenario
- `position_scope`：asset / liability / all
- `currency_basis`：CNY / CNX / USD / native
- `source_version`：数据源版本指纹
- `rule_version`：计算口径版本
- `filter_hash`：标准化过滤条件哈希

## 4. result_meta 要求

所有缓存命中的正式结果必须携带：

```json
{
  "basis": "formal",
  "formal_use_allowed": true,
  "source_version": "sv_xxx",
  "rule_version": "rv_xxx",
  "cache_version": "cv_xxx",
  "cache_hit": true,
  "generated_at": "2026-04-09T12:00:00+08:00",
  "trace_id": "..."
}
```

Scenario 结果必须为：

```json
{
  "basis": "scenario",
  "formal_use_allowed": false
}
```

## 5. 失效规则

### 5.1 数据源版本失效

以下表或源数据变化时，必须重新计算对应缓存：
- `PositionBonds`
- `PositionInterbank`
- `PnLRecord`
- `LedgerDailyPnL`
- `ManualAdjustment`
- `fx_daily_mid`
- `choice_market_snapshot`
- `choice_market_curve`

### 5.2 规则版本失效

以下规则变化时，必须整域失效：
- H/A/T → AC/FVOCI/FVTPL 映射
- 债券资产是否排除发行类债券
- FX 中间价折算规则
- observed / locf / calendar_zero basis 规则
- 514/516/517 归并规则
- maturity bucket / KRD bucket / risk bucket 规则

### 5.3 人工调整局部失效

以下数据变化时，只失效关联域：
- 人工估值覆盖
- 手工损益调整
- 成本中心映射更新
- 投资组合映射更新

### 5.4 TTL（兜底）

- 元数据：1 小时
- 首页总览：5 分钟
- 月均金额 / Formal PnL / 风险概览：15 分钟
- 深钻首层聚合：10 分钟
- Agent 摘要：5 分钟
- 明细页：不使用 Redis TTL，直接查 DuckDB

注意：TTL 不是主失效机制。`source_version` 或 `rule_version` 变化时必须立刻失效。

## 6. Redis 结构建议

### Key 命名

- `moss:resp:{cache_key}`：响应缓存
- `moss:lock:{domain}:{view}:{date_or_month}`：单飞锁
- `moss:meta:latest_cache_version:{domain}`：最新缓存版本
- `moss:job:{job_id}`：任务状态

### Value 结构

```json
{
  "payload": {"...": "..."},
  "result_meta": {"...": "..."},
  "created_at": "2026-04-09T12:00:00+08:00",
  "ttl_seconds": 900
}
```

## 7. PostgreSQL 表建议

### source_version_registry
- `domain`
- `scope_key`
- `source_version`
- `computed_at`
- `dependency_summary`

### rule_version_registry
- `rule_domain`
- `rule_version`
- `rule_digest`
- `released_at`
- `released_by`

### cache_manifest
- `cache_key`
- `domain`
- `view`
- `date_or_month`
- `basis`
- `position_scope`
- `currency_basis`
- `source_version`
- `rule_version`
- `duck_table_name`
- `redis_key`
- `row_count`
- `created_at`
- `expires_at`

### cache_build_run
- `run_id`
- `cache_key`
- `status`
- `started_at`
- `finished_at`
- `input_source_version`
- `input_rule_version`
- `trace_id`
- `error_message`

### cache_invalidation_log
- `id`
- `cache_key`
- `reason_type`
- `reason_detail`
- `invalidated_at`
- `trace_id`

## 8. 单飞与并发控制

- Redis 分布式锁用于防止同一缓存同时重建
- DuckDB 写入只允许 worker 获取写锁后执行
- 构建失败时不得回写半成品 manifest

## 9. Codex 实现约束

- 不允许在 endpoint 中写 Redis / DuckDB 缓存构建逻辑
- 统一通过 `CacheService` + `tasks/cache_refresh.py` 实现
- 每一个缓存域都必须补回归测试

## 10. 最低测试集

- `source_version` 变化触发缓存失效
- `rule_version` 变化触发缓存失效
- Formal 与 Scenario 不共享缓存键
- 人工调整只失效相关域
- 同参数重复请求命中缓存
- DuckDB 写入只发生在 worker 路径
