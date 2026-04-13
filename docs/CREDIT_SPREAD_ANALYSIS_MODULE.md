# 信用利差分析模块说明

## 1. 模块定位

信用利差分析当前分成两条读路径，前端信用利差页同时消费两者：

- 旧摘要接口：`GET /api/bond-analytics/credit-spread-migration`
  - 用途：保留既有利差情景冲击、评级迁徙情景、集中度、OCI 敏感度等摘要视图。
  - 特征：它是 legacy summary / migration 读面，不是逐券利差明细口径。

- 新 detail 接口：`GET /api/credit-spread-analysis/detail`
  - 用途：提供逐券信用利差、期限结构、历史分位数、高低利差债券明细。
  - 特征：它是本轮新增的深度分析读面，面向投资决策参考。

前端页面的当前约定：

- 旧摘要继续驱动情景冲击、迁徙、集中度、OCI 敏感度。
- 新 detail 驱动：
  - `加权平均利差（个券）`
  - `利差期限结构`
  - `历史分位`
  - `高利差债券 / 低利差债券`

## 2. 单位约定

### 2.1 YTM

`fact_formal_bond_analytics_daily.ytm` 当前按**小数口径**存储：

- `0.032` 表示 `3.20%`
- `0.045` 表示 `4.50%`

`backend/app/core_finance/credit_spread_analysis.py` 在计算逐券利差时，会先把该值标准化到百分比点位，再参与和曲线的差值计算。

### 2.2 Treasury Curve / Yield Curve

`yield_curve_daily.rate_pct` / `fact_formal_yield_curve_daily.rate_pct` 按**百分比点位**存储：

- `2.50` 表示 `2.50%`
- `3.10` 表示 `3.10%`

因此逐券利差的正式换算为：

```text
ytm_pct = ytm_decimal * 100
credit_spread_bps = (ytm_pct - benchmark_yield_pct) * 100
```

例：

- `ytm = 0.035`
- `benchmark_yield = 2.50`
- 则：
  - `ytm_pct = 3.50`
  - `credit_spread_bps = (3.50 - 2.50) * 100 = 100 bp`

### 2.3 旧摘要接口中的 `weighted_avg_spread`

旧摘要接口里的 `weighted_avg_spread` 仍保留为 legacy summary 字段，不应再被解释为“个券加权平均利差”的唯一真值。

前端当前已改为：

- 个券平均利差只展示新 detail 接口里的 `weighted_avg_spread_bps`
- 旧摘要接口继续承担情景、迁徙、集中度等 legacy summary 责任

## 3. 历史窗口

新 detail 接口的历史上下文由 `compute_spread_historical_context` 生成，规则如下：

- 锚点日：历史序列中最大的 `report_date`
- 近 1 年窗口：`trade_date >= anchor_date - 365 天`
- 近 3 年窗口：`trade_date >= anchor_date - 1095 天`

分位数定义：

```text
percentile = count(historical_spread <= current_spread) / total * 100
```

返回字段语义：

- `percentile_1y`：当前利差在近 1 年序列中的百分位
- `percentile_3y`：当前利差在近 3 年序列中的百分位
- `median_1y` / `median_3y`：窗口内中位数
- `min_1y` / `max_1y`：近 1 年窗口范围

## 4. Fallback 行为

### 4.1 曲线读取规则

新 detail 接口当前只依赖 `treasury` 曲线：

1. 先读请求日的 exact snapshot：`fetch_curve_snapshot(requested_trade_date, "treasury")`
2. 若 exact snapshot 缺失，则允许回退到“请求日及以前”的最近可用 snapshot
3. 不允许 future-date fallback

### 4.2 outward 行为

当发生 latest fallback 时：

- `result_meta.vendor_status = "vendor_stale"`
- `result_meta.fallback_mode = "latest_snapshot"`
- `warnings` 中显式加入 `YIELD_CURVE_LATEST_FALLBACK...`

当请求日及以前都没有可用 treasury curve 时：

- detail 接口不静默伪造曲线
- `result_meta.vendor_status = "vendor_unavailable"`
- `result_meta.fallback_mode = "none"`
- `warnings` 中显式加入 `No treasury curve available ...`

### 4.3 前端行为

当前前端信用利差页采用“summary 主路 + detail 增强”的降级策略：

- 旧摘要接口失败：整页报错
- 新 detail 接口失败：页面仍展示旧摘要内容，并在 warning 区显式提示

当前 warning 文案：

```text
深度利差明细暂不可用：HTTP <status>
```

## 5. 后续注意事项

- 如果未来把 `fact_formal_bond_analytics_daily.ytm` 改成百分比点位存储，必须同步修改 `credit_spread_analysis.py` 的 `ytm` 标准化逻辑。
- 如果未来 detail 接口开始依赖 `aaa_credit` 或其他 credit family 曲线，需要单独补文档，不应复用本说明里的 treasury-only 约定。
- 前端不得自行在浏览器内重算正式利差；任何正式口径调整只能落在 `backend/app/core_finance/`。
