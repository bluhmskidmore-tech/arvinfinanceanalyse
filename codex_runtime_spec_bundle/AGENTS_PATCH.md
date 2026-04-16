# AGENTS_PATCH.md

将以下条目并入仓库根目录 `AGENTS.md`：

## 架构铁律

- 正式金融计算只允许在 `backend/app/core_finance/` 实现一次。
- `backend/app/api/` 只做薄层，不得写正式金融公式。
- `frontend/` 不得补算正式金融指标。
- Scenario 与 Formal 必须在语义、表、缓存和 `result_meta` 上隔离。
- DuckDB 在 API 路径只读，写入只允许通过 `backend/app/tasks/` / worker。

## 缓存规则

- 缓存采用四层：前端查询缓存、Redis 响应缓存、DuckDB 物化分析缓存、PostgreSQL 缓存治理元数据。
- 缓存失效必须以 `source_version` 和 `rule_version` 为主，TTL 仅作兜底。
- Redis 只缓存高频聚合结果；不得缓存任意 SQL、权限敏感大明细、Formal/Scenario 混合结果。
- 所有缓存命中的正式结果必须带 `result_meta`，至少包括：`basis`、`formal_use_allowed`、`source_version`、`rule_version`、`generated_at`、`trace_id`。
- 缓存键必须包含：`domain`、`view`、`date_or_month`、`basis`、`position_scope`、`currency_basis`、`source_version`、`rule_version`、`filter_hash`。

## 金融口径高风险区

以下修改必须补测试并显式说明影响：
- H/A/T 映射
- 发行类债券排除逻辑
- FX 中间价折算规则
- 514/516/517 归并规则
- 月均金额 basis 逻辑
- PnL bridge / risk tensor / KRD / DV01

## 交付要求

每次提交都必须输出：
- 变更文件列表
- 新增测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
