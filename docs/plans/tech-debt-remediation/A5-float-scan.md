# A5 — 正式链 float/Decimal 破口全量扫描清单

- 生成日期：2026-08-12
- 扫描范围：
  - `backend/app/core_finance/**`（全部 174 个 py 文件）
  - `backend/app/services/` 中正式链服务（`pnl_*`、`campisi_*`、`balance_*`、`bond_*`、`risk_*`、`liability_*`，共 24 个文件）
- 扫描口径：
  - 全部 `float(` 调用命中（rg `float\(`）
  - float 字面量参与金额/收益率/久期/DV01 运算（rg `[-+*/] *\d+\.\d|\d+\.\d+ *[*/]`，人工剔除 `Decimal("1.5")`、注释、字符串等假阳性）
  - `astype(float)` / `np.float` / `float64` / `to_numpy(` 在正式链核心文件（pnl/pnl_bridge/risk_tensor/fx_rates/balance_analysis_workbook/campisi/bond_duration/cashflow_projection/finance_metric_engine/var_engine）：**零命中**
- 正式链判定依据：`backend/app/AGENTS.md`「Default Backend Boundary」——正式计算主线 = formal balance / formal PnL / formal FX / formal yield curve / PnL bridge / risk tensor / core bond-analytics formal read surfaces。`qdb_gl_monthly_analysis`、`liability_analytics_compat`、macro-data、market-data 分析面等在显式排除清单内。
- 定性四类：
  - **A** = 真破口（float 中转参与正式数值计算，精度可能丢失）
  - **B** = 展示/排序/日志/输出边界（无数值风险）
  - **C** = 分析型/策略/情景口径（非正式口径，低优先）
  - **D** = 已有 Decimal 防护，或 float 是数值算法/时间量纲的合理选择且出口有防护

---

## 0. 总体结论

1. **正式链“账面金额主干”是干净的 Decimal 域**：`pnl.py`、`pnl_bridge.py`（除 1 处时间量纲）、`fx_rates.py`、`balance_analysis_workbook.py`、`balance_workbook/*`、`risk_tensor.py`、`bond_four_effects.py`、`bond_duration.py`、`bond_analytics/dv01.py`、`cashflow_projection.py`、`finance_metric_engine.py`、`var_engine.py`、`campisi_decision_grade.py` 以及全部 `balance_*` / `pnl_*`（bridge/source/summary 等）/ `bond_dashboard` / `risk_tensor` 服务，`float(` 与 float 字面量运算均为**零命中**。
2. **真破口（A 类）集中在三个位置**：
   - Campisi 归因的**输入侧**（曲线/利差/合并头寸经服务层 Decimal→float 中转，再在 `campisi.py` 内做 float 算术后 `Decimal(str())` 回转）；
   - `pnl_attribution/workbench.py` **整个模块在 float 域计算金额**（carry/rolldown/利差/久期效应 PnL 估算，文档自述“float payloads for API”）；
   - `rate_units.py` 两个归一函数**返回 float**（被四效应等正式路径消费）。
3. **单次 Decimal→float→Decimal 转换的相对误差 ≤ 2⁻⁵²≈2.2e-16**，对 1e8 元级单券金额约 1e-8 元，远低于正式闭合阈值 0.01 元（`campisi_attribution_service.py:1840`）与展示精度。当前 A 类的**实际数值影响是分级里最轻的一档**，主要风险是口径治理不一致、误差在 float 域累加路径（A-9/A-10）随规模放大，以及对账残差引入非业务噪声。
4. 此前审计的失实线索本次逐一澄清（见 §1）。

命中总量（行级）：`core_finance/**` 约 700 行命中 `float(`；其中正式链文件 ≈ 150 行，其余为分析/策略/宏观模块（C 类）。正式链服务 5 个文件命中 112 行（`campisi_attribution_service` 68、`pnl_attribution_service` 37、`liability_analytics_service` 4、`bond_analytics_service` 2、`risk_scenario_stress_service` 1）。

---

## 1. 单源线索核实（任务指定）

### 1.1 `campisi.py:219`「曲线插值 float 中转」——**部分属实，行号定位有偏**

- 实际的 219 行不是曲线插值，而是**信用利差变动**的 float 算术中转：

```209:219:backend/app/core_finance/campisi.py
    s0 = usable_spread_bp(market_start, rating)
    s1 = usable_spread_bp(market_end, rating)
    if s0 is None or s1 is None:
        logger.warning(
            "Credit spread change requires positive %s on both sides; start=%s, end=%s. Returning 0.",
            key,
            "present" if s0 is not None else "unavailable",
            "present" if s1 is not None else "unavailable",
        )
        return Decimal("0")
    return Decimal(str((s1 - s0) / 10000.0))
```

  `s0`/`s1` 来自 `usable_spread_bp`（`campisi.py:188` `float(value)`），减法与 `/10000.0` 均在 float 域完成后才 `Decimal(str())` 回转。**定性 A**（见 A-3）。
- 真正的“曲线插值 float 中转”在 `campisi.py:152-155`（基准收益率变动评估器）与 `campisi.py:118`（公开插值出口），同样定性 A（见 A-2/A-13）。

### 1.2 `risk_scenario_stress_service.py` 冲击路径——**float 属实，但口径为 scenario，定性 C**

冲击算术确实在 float 域：`_numeric_raw`（238 行）把物化张量的 `raw` 转 float，`shock_bp = 10.0`（84 行）、`impact = -regulatory_dv01 * shock_bp`（86 行）、`-cs01 * 10.0`（114 行）、流动性 `(1±0.10)` 压力（136/149-152 行）。但信封显式声明 `basis="scenario"`（31-32 行），payload 内置警告“**not a formal PnL, limit decision, or trading instruction**”（65-68 行），全部行标记 `human_review_required=True`。属 Formal/Scenario 分离下的情景口径 → **C**（见 C 表）。输入来源 `fact_formal_risk_tensor_daily` 本身由 Decimal 域物化，float 仅发生在 scenario 覆盖层。

### 1.3 背景澄清：`risk_tensor.py:406`——**确证无 float**

406 行为 `payment_frequency_fallback_count += 1`（计数器）；相邻 407 行金额累加走 `_safe_decimal`。全模块 `float(` 与 float 字面量运算零命中，市值/DV01/现金流全部 Decimal 域。此前审计条目不成立。

---

## 2. A 类 —— 真破口清单（逐处，含代码摘录与数据流）

> 说明：下列条目均满足“float 中转参与正式数值计算”。误差量级均为单次转换 ~2.2e-16 相对误差（除非标注“float 域累计”）。“下游”指 float 值最终参与的正式计算。

### A-1 `campisi.py:52` + `campisi.py:58` — 国债曲线值 float 中转与 ×100.0 单位放大

```47:59:backend/app/core_finance/campisi.py
    out: dict[str, float] = {}
    for k in _TREASURY_KEYS:
        value = m.get(k)
        if value in (None, ""):
            continue
        numeric = float(value)
        if numeric > 0:
            out[k] = numeric
    # Keep the threshold in rate_units so curve-unit heuristics stay consistent.
    if out and not detect_percent_unit_from_curve(list(out.values())):
        for k in out:
            out[k] = out[k] * 100.0
    return out
```

- 数据流：repo 曲线（Decimal，经服务层 A-5 已转 float）→ `float(value)` → 单位启发式命中时 float `*100.0` → `_fit_percent_curve` 内 `Decimal(str(curve[k]))`（90 行）回 Decimal。
- 下游：样条拟合 → 基准变动 Δy → `compute_bond_four_effects` 的 `treasury_effect = -mod_dur * Δy * mv_start`。
- 风险点：`*100.0` 在 float 域放大表示误差（如 `0.0255*100 ≠ Decimal("2.55")`），误差 ~1e-15 个百分点。

### A-2 `campisi.py:153-155` — 基准收益率变动 float 相减 + /100.0

```152:155:backend/app/core_finance/campisi.py
    def _evaluate(maturity_years: float) -> Decimal:
        y0 = float(_engine_interpolate(fitted_start, float(maturity_years)))
        y1 = float(_engine_interpolate(fitted_end, float(maturity_years)))
        return Decimal(str((y1 - y0) / 100.0))
```

- 数据流：曲线引擎输出（Decimal，8 位量化）→ `float()` → float 相减、`/100.0` → `Decimal(str())`。
- 下游：`campisi_attribution`（376 行 `bench_change`）→ 每券 `treasury_effect`。相邻期限收益率相减是**相消运算**（catastrophic cancellation 敏感点），虽然引擎出口已量化 8 位小数使得实际误差被限制在 ~1e-9 个百分点，但这是正式效应公式的直接输入。
- 同型：`campisi.py:118`（`interpolate_treasury_yield_pct` 出口 `float(...)`，消费方见 A-12）。

### A-3 `campisi.py:188` + `campisi.py:219` — 信用利差 bp float 中转（见 §1.1 摘录）

```185:196:backend/app/core_finance/campisi.py
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Unparseable credit spread value for %s: %r; treated as unavailable.",
            key,
            value,
        )
        return None
    return numeric if numeric > 0 else None
```

- 数据流：market dict 利差（bp，服务层 A-5 已 float 化）→ `float(value)` → `(s1 - s0) / 10000.0` float 算术（219 行）→ `Decimal(str())`。
- 下游：`spread_effect = -mod_dur * spread_change * mv_start`（`bond_four_effects.py:142`）。

### A-4 `campisi.py:426-431`（四效应）/ `520-528`（六效应）/ `443`、`543`（by_bond 输出）— totals float 化后回流正式闭合

```424:432:backend/app/core_finance/campisi.py
    _ZERO = Decimal("0")
    totals = {
        "income_return": float(sum((r["income_return"] for r in by_bond), _ZERO)),
        "treasury_effect": float(sum((r["treasury_effect"] for r in by_bond), _ZERO)),
        "spread_effect": float(sum((r["spread_effect"] for r in by_bond), _ZERO)),
        "selection_effect": float(sum((r["selection_effect"] for r in by_bond), _ZERO)),
        "total_return": float(sum((r["total_return"] for r in by_bond), _ZERO)),
        "market_value_start": float(sum((r["market_value_start"] for r in by_bond), _ZERO)),
    }
```

- 求和本身在 Decimal 域（好），float 仅发生一次于出口（代码注释 406-408 行自述“Converted to float only at the CampisiResult output boundary”）。**但 `totals["total_return"]` 并非纯展示**：
  - `campisi_attribution_service.py:1309` 与 `:2314`：`campisi_total_return=Decimal(str(result.totals.get("total_return") or 0))` → 进入 `_build_formal_closure`（1196-1209 行）与 `fact_formal_pnl_fi.total_pnl` 做残差闭合。
- 即 float 单次往返污染正式闭合残差，误差 ~1e-8 元（1e8 元级 total_return），低于 0.01 元闭合阈值（1840 行），当前不可观察但属口径破口。

### A-5 `campisi_attribution_service.py:357`、`387`、`399`、`401` — 曲线/利差 repo Decimal → float market dict

```354:358:backend/app/services/campisi_attribution_service.py
    for tenor, field in _TREASURY_TENOR_MAP.items():
        val = curve.get(tenor) or curve.get(tenor.lower()) or curve.get(tenor.replace("Y", "y"))
        if val is not None:
            market[field] = float(val)
    return market
```

```397:401:backend/app/services/campisi_attribution_service.py
        credit_3y = _curve_3y_on_or_before(curve_repo, trade_date, curve_type)
        if credit_3y is not None:
            spread[_SPREAD_FIELD_BY_RATING[rating]] = float((credit_3y - treasury_3y) * Decimal("100"))
    for rating, credit_3y in _choice_credit_3y_yields_on_or_before(curve_repo.path, trade_date).items():
        spread[_SPREAD_FIELD_BY_RATING[rating]] = float((credit_3y - treasury_3y) * Decimal("100"))
```

- 数据流：`YieldCurveRepository`（Decimal）→ float market dict → A-1/A-3 的 float 算术。399/401 行 Decimal 减法先做（好），随后仍转 float 装入 dict。
- 下游：Campisi 四/六效应全部利率输入。这是 A-1/A-3 破口的**源头段**。

### A-6 `campisi_attribution_service.py:569`、`571`、`593` — 加权票息/YTM、应计利息合计 Decimal → float 返回

```568:572:backend/app/services/campisi_attribution_service.py
    if denominator > 0:
        return float(numerator / denominator)
    if equal_weight_count:
        return float(equal_weight_sum / Decimal(equal_weight_count))
    return None
```

```589:593:backend/app/services/campisi_attribution_service.py
def _sum_optional_decimal(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [_decimal_value(row.get(field)) for row in rows if not _is_missing(row.get(field))]
    if not values:
        return None
    return float(sum(values, Decimal("0")))
```

- 数据流：`_weighted_row_value`（Decimal 域加权）→ float → `merge_positions` 的 `coupon_rate`/`ytm`/`accrued_interest`（540-543 行）→ `campisi_attribution` → `bond_four_effects` 中 `normalize_annual_rate_to_decimal`（本身也是 float，见 A-11）→ `Decimal(str())`。
- 下游：`income_return = coupon × face × num_days / 365`、应计利息全价口径 `total_return`。**应计利息是金额**（`_sum_optional_decimal` 输出直接进 `accrued_interest_start/end`），float 中转金额而非仅利率。

### A-7 `campisi_attribution_service.py:681-683` — 合并头寸市值/面值 Decimal → float

```673:691:backend/app/services/campisi_attribution_service.py
        merged.append({
            "bond_code": code,
            "instrument_id": code,
            "position_key": "|".join(key),
            "portfolio_name": key[1],
            "cost_center": key[2],
            "accounting_class": key[3],
            "currency_code": key[4],
            "market_value_start": float(s.get("market_value") or 0),
            "market_value_end": float(e.get("market_value") or 0),
            "face_value_start": float(s.get("face_value") or 0),
            "accrued_interest_start": s.get("accrued_interest"),
            "accrued_interest_end": e.get("accrued_interest"),
            "coupon_rate_start": coupon_dec or 0.0,
            "yield_to_maturity_start": ytm_dec or 0.0,
            "asset_class_start": _campisi_asset_class(s, e),
            "rating_start": s.get("rating") or e.get("rating") or "",
            "maturity_date_start": s.get("maturity_date") or e.get("maturity_date"),
        })
```

（684-685 行的 `accrued_interest_start/end` 取自 `_sum_optional_decimal` 的 float 返回，见 A-6；686-687 行 `coupon_dec`/`ytm_dec` 取自 `normalize_annual_rate_to_decimal` 的 float 返回，见 A-11。）

- 数据流：`_aggregate_position_rows` 聚合（`_sum_decimal`，Decimal 域，586 行）→ **float 化装入 merged 行** → `campisi.py:413` `Decimal(str(row.get("market_value_start") or 0))` / `bond_four_effects.py:76-78` `safe_decimal(...)` 回 Decimal。
- 下游：四/六效应的 `mv_start/mv_end/face` 全部金额输入。1e10 元级市值单券误差 ~1e-6 元。

### A-8 `campisi_attribution_service.py:1047-1056`（含 enhanced 1062-1064）— formal bridge 金额 Decimal → float 记录

```1043:1058:backend/app/services/campisi_attribution_service.py
        record = {
            "bond_code": _text_value(bridge_row.get("instrument_code")),
            "asset_class": _formal_asset_class(bridge_row, position),
            "maturity_bucket": _formal_maturity_bucket(position, start_date),
            "market_value_start": float(
                _numeric_raw(bridge_row.get("beginning_dirty_mv"))
                or _decimal_value((position or {}).get("market_value_start"))
            ),
            "income_return": float(income),
            "treasury_effect": float(treasury),
            "spread_effect": float(spread),
            "selection_effect": float(selection),
            "total_return": float(total),
            "mod_duration": float(_decimal_value((position or {}).get("mod_duration"))),
            "has_accrued_interest": not _is_missing((position or {}).get("accrued_interest_start")),
        }
```

- 数据流：正式 PnL bridge 行（Decimal，1035-1042 行 `_numeric_raw` 域内算出 income/treasury/spread/selection）→ float 记录 → `_formal_totals`（1108 行）与 `_aggregate_formal_rows`（1092-1094 行）再经 `_decimal_value` 回 Decimal 求和 → 再 float 输出。
- 定性 A 的原因：这是**中链 DTO**而非最终输出——totals/by_asset_class 从 float 行重建，且 `_formal_bridge_to_campisi_result`（1125-1131 行）的 `totals["total_return"]` 同样回流 A-4 的正式闭合（2314 行）。

### A-9 `campisi_attribution_service.py:1192` — 期限桶 float 域累加

```1190:1193:backend/app/services/campisi_attribution_service.py
        )
        for key in bucket:
            bucket[key] += float(row.get(key) or 0.0)
    return out
```

- 数据流：A-8 的 float 行 → **在 float 域逐券累加**（`market_value_start`/`income_return`/`treasury_effect`/`spread_effect`/`selection_effect`/`total_return` 六个金额字段）→ `_formal_bridge_to_maturity_buckets` 输出期限桶视图。
- 与 A-8 的区别：这里是真 float 求和，误差 O(n)·ulp 累积，n 券桶内 ~n×1e-8 元。是服务内唯一一处金额 float 累加。

### A-10 `pnl_attribution/workbench.py` — 模块级 float 域金额计算（carry/rolldown/利差/KRD）

模块文档自述（1-5 行）：“PnL attribution workbench — pure functions over in-memory fact rows (**float payloads for API**). Formal calculations live here”。信封侧 `source_surface="formal_attribution"`（`pnl_attribution_service.py:170/198`）。核心金额算术全部 float：

```709:712:backend/app/core_finance/pnl_attribution/workbench.py
    total_mv = sum(_f(r.get("market_value")) for r in bond_rows)
    items: list[dict[str, Any]] = []
    port_carry = port_roll = port_static = 0.0
    t_carry_pnl = t_roll_pnl = t_static_pnl = 0.0
```

```721:734:backend/app/core_finance/pnl_attribution/workbench.py
        mv = sum(_f(r.get("market_value")) for r in rows)
        w = (mv / total_mv * 100.0) if total_mv > 0 else 0.0
        num_c = sum(_f(r.get("market_value")) * _f(r.get("coupon_rate")) for r in rows)
        den = mv
        coupon_dec = (num_c / den) if den > 0 else 0.0
        coupon_pct = coupon_dec * 100.0
        ytm_dec = _weighted_ytm_float(rows)
        ytm_pct = ytm_dec * 100.0 if ytm_dec is not None else None
        num_d = sum(_f(r.get("market_value")) * _f(r.get("modified_duration")) for r in rows)
        dur = (num_d / den) if den > 0 else 0.0
        funding = ftp_rate_pct
        carry_pct = coupon_pct - funding
        carry_dec = carry_pct / 100.0
        carry_pnl = mv * carry_dec / 12.0
```

```947:961:backend/app/core_finance/pnl_attribution/workbench.py
    total_dur_eff = 0.0
    shift_bp = treasury_shift_bp if treasury_shift_bp is not None else 0.0
    for b in dist_end:
        tenor = str(b["tenor_bucket"])
        mv = float(b["market_value"])
        w = (mv / total_mv * 100.0) if total_mv > 0 else 0.0
        # Bucket metric is avg modified duration (not true KRD contribution).
        avg_md = float(b.get("avg_modified_duration", b["krd"]))
        rows_s = by_bucket_start.get(tenor, [])
        rows_e = _rows_for_bucket(covered_end, tenor)
        ye = _weighted_ytm_float(rows_e)
        ys = _weighted_ytm_float(rows_s)
        ychg = ((ye - ys) * 10000.0) if ye is not None and ys is not None else None
        contrib = -mv * avg_md * (shift_bp / 10000.0)
        total_dur_eff += contrib
```

- 逐行命中（40 处）：`38`、`40`（`_f` 通用 Decimal→float 转换器）；`225`（10Y 曲线值）；`236`、`246`（期限解析，时间量纲）；`256`、`267`、`268`（`_finite_float`/加权 YTM 输入）；`283`（曲线插值出口 float 化）；`309`、`360`、`372`、`385`（行覆盖判定输入）；`523`、`524`、`539`、`540`、`541`（TPL 相关性分析，分析属性）；`727`（加权 YTM）；`817`、`818`（组合市值/久期）；`828`、`829`、`850`、`851`（YTM 变动 → 利差效应 bp）；`938`、`939`、`940`（市值/久期/DV01）；`951`、`954`、`957`、`958`（KRD 桶市值/久期/YTM）；`1007`（最大贡献值输出）；`1020`-`1024`（汇总 float 输出）。
- 数据流：`fetch_bond_analytics_rows`（repo Decimal）→ `_f()` float → 金额×利率×久期在 float 域乘加（含 `carry_pnl`、`rolldown_pnl`、`contrib` 等**元级金额**）→ float payload 直出 formal_attribution 信封。
- 定性 A（模块级设计债）：与「正式计算 Decimal 域」的治理规则冲突；这些是模型估算值（非会计闭合数），float 累加误差在展示精度（2-4 位小数）内不可见，但 `sum(mv*coupon)` 类累加随组合规模线性放大。备注：`279` 行 `_weighted_ytm_decimal = _weighted_ytm_float` 的兼容别名命名会误导调用方以为是 Decimal 实现。

### A-11 `rate_units.py:74/86`、`143/159-160` — 利率归一函数返回 float

```71:86:backend/app/core_finance/rate_units.py
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0:
        return None
    if v > 20:
        logger.warning(
            "normalize_percent_rate_to_decimal: value %s > 20 (i.e. rate > 20%%), "
            "treating as dirty data, returning None",
            v,
        )
        return None
    return v / 100.0
```

（`normalize_annual_rate_to_decimal` 同型：143 行 `float(raw)`，159 行 `v / 100.0`，160 行 `return v`。）

- 数据流：正式路径消费——`bond_four_effects.py:47-51` `_annual_rate_decimal` = `Decimal(str(normalize_annual_rate_to_decimal(value)))`；`campisi_attribution_service.py:556`、`668`、`671`；`pnl_bridge.py` 经 `_percent_rate_to_decimal`（内部同源）。
- 不一致点：同文件顶部的显式转换器（`pct_to_decimal` 等，23-50 行）全部返回 Decimal，仅这两个启发式归一函数返回 float，形成正式链上的系统性 float 中转点（票息、YTM）。`/100.0` 为 float 除法。

### A-12 `attribution_daily.py:102-113` — 日度 rolldown 曲线插值 float 中转

```102:118:backend/app/core_finance/attribution_daily.py
            rolled_years = max(float(current_years) - (period_days / 365), 0.0)
            current_rate = interpolate_treasury_yield_pct(market_end, current_years)
            rolled_rate = interpolate_treasury_yield_pct(market_end, rolled_years)
            roll_fx = compute_bond_four_effects(
                bond,
                num_days,
                bench_dec,
                spread_dec,
                report_date,
                coupon_frequency=cf,
            )
            rate_delta = Decimal(str((current_rate - rolled_rate) / 100.0))
            rolldown_dec = (
                safe_decimal(roll_fx["mod_duration"])
                * rate_delta
                * safe_decimal(merged_position.get("market_value_end"))
            )
```

- 数据流：`interpolate_treasury_yield_pct`（float 出口，campisi.py:118）→ float 相减 `/100.0` → `Decimal(str())` → rolldown 金额。与 A-2 同型（相邻期限相消运算）。
- 降级因素：`compute_daily_attribution_row` 当前**无生产调用方**（仅 `tests/test_attribution_daily.py` 消费；campisi.py 与 read_models.py 仅在注释中提及口径一致性）。输出边界 126-132 行的 `float(...)` 为 B。

### A-13 `campisi.py:118` — 公开插值函数 float 出口

```115:118:backend/app/core_finance/campisi.py
    fitted = _fit_percent_curve(curve)
    if fitted is None:
        return 0.0
    return float(_engine_interpolate(fitted, float(maturity_years)))
```

- `interpolate_treasury_yield_pct` 的唯一非测试消费方是 A-12（attribution_daily）。曲线引擎返回 Decimal，此处主动降级为 float 作为 API。与 A-12 合并处置。

---

## 3. B 类 —— 展示/排序/日志/输出边界（无数值风险）

判定共性：float 转换发生在 Decimal 域计算**完成之后**的输出 DTO、日志格式化、排序键或阈值消息处，无回流。

| 文件:行号 | 代码摘录（缩略） | 定性理由 |
| --- | --- | --- |
| `core_finance/campisi.py:611-614` | `("income", abs(float(income))), ...` | 主驱动因子排序键，仅决定标签顺序 |
| `core_finance/campisi.py:426-431/443/520-528/543` | 见 A-4 | 除 `total_return` 回流闭合（A-4）外，其余字段为输出边界 B；此处双记提示 |
| `core_finance/attribution_daily.py:126-132` | `"carry_return": float(carry_dec), ...` | 输出契约边界（注释自述 85-87 行），Decimal 域已完成残差恒等式 |
| `core_finance/attribution_core.py:55-61` | `"explained_pnl": float(self.explained_pnl), ...` | `to_dict` 输出边界；对账在 Decimal 域（102-121 行阈值比较用 Decimal） |
| `core_finance/attribution_core.py:105/110/115/120` | `f"残差比例 {float(...)*100:.2f}% ..."` | 日志/诊断消息格式化 |
| `core_finance/attribution_core.py:346` | `f"口径不一致: 差异 {float(diff):.2f} 元..."` | 诊断消息；`diff`/`pct` 均 Decimal 算出 |
| `core_finance/action_attribution.py:266-268/288-290/319-321/337-340/356-359/389-391/409-411/441/444-446` | `"pnl_economic": float(pnl), ...` | 行动归因输出记录；金额累加在 Decimal 域（如 414 行 `allocated += unallocated_pnl`） |
| `core_finance/benchmark_excess.py:113-146` | `"excess_return_bp": float(excess_bp), ...` | 计算全程 Decimal（95-108 行），docstring 自述“float/bp-friendly values for API layer” |
| `core_finance/yield_by_period.py:51/58/109-111/159-160/216-217` | `float(total_pnl / scale * Decimal("100"))` | 收益率 pct 在 Decimal 域算完后 float 输出 |
| `core_finance/reconciliation_checks.py:56-57/68-70/93-94/101-103/124-125/132-134` | `"diff": float(diff)` | 2026-07-19 审计 M-4 已改造：比较/差额 Decimal 域（17-28 行 `_comparison_decimal`），float 仅为 payload 兼容 |
| `core_finance/liability_cockpit.py:130/137/146/156/163/172/293-295` | `f"NIM = {to_float(nim):.4%}"` 等 | 告警文案与贡献行输出；NIM/成本计算 Decimal 域 |
| `core_finance/qdb_gl_monthly_analysis.py:2216/2221` | `float(normalized)`（quantize 0.01 后） | Excel/展示值输出（且该流在 AGENTS.md 排除清单内）；2186 行为注释命中 |
| `core_finance/alert_engine.py:93` | `rule.detail_template.format(value=float(value), ...)` | 告警文案格式化；阈值比较在 Decimal |
| `core_finance/krd.py:270` | `get_tenor_bucket(float(duration or Decimal("5")))` | 期限桶标签选择，非数值输出 |
| `core_finance/bond_analytics/engine.py:252` | `tenor_bucket=get_tenor_bucket(float(years_to_maturity))` | 同上，分桶标签 |
| `core_finance/decimal_utils.py:104-106` | `def safe_float(x)...` | 工具定义；全仓无消费方（休眠），无风险 |
| `services/campisi_attribution_service.py:810/836/855/869` | `"market_value": float(_sum_decimal(...))` | 输入质量/重复行诊断输出（Decimal 求和后转出） |
| `services/campisi_attribution_service.py:1099-1102` | `row = {key: float(value)...}; sorted(..., -abs(float(...)))` | 资产类聚合输出与排序键；聚合在 Decimal（1092-1094 行） |
| `services/campisi_attribution_service.py:1108` | `float(sum((_decimal_value(...)), Decimal("0")))` | Decimal 求和后出口（输入已是 A-8 float 行，破口记在 A-8） |
| `services/campisi_attribution_service.py:1222-1225/1243` | `"residual_to_formal_pnl": float(residual)` | 闭合结果输出；残差在 Decimal 域（1205 行）算出 |
| `services/campisi_attribution_service.py:1794-1801` | `"dv01_difference": float(component_dv01 - portfolio_dv01)` | 决策级 DV01/CS01 校验输出；差额 Decimal 域 |
| `services/campisi_attribution_service.py:1807/1819/1838/1851/1865` | `float(components...)` / 比率 | 决策视图输出边界；闭合判定 Decimal 域（1833-1840 行，阈值 0.01 元） |
| `services/campisi_attribution_service.py:1923-1929/1934` | `"carry": float(bucket["carry"])...` | 能力矩阵输出；桶累加 Decimal 域（1902-1912 行） |
| `services/campisi_attribution_service.py:2137-2138/2151-2157/2164-2166/2174-2176` | `"formal_pnl": float(row["formal_pnl"])...` | 决策级视图输出边界 |
| `services/pnl_attribution_service.py:589-591` | `percent_points = float(raw); raw=percent_points/100.0` | Numeric DTO 构造（pct→ratio），展示契约层 |
| `services/pnl_attribution_service.py:637/639/681` | `_numeric_dict(float(v), ...)` / `float(raw)*100.0` | payload 数字字段 Numeric 化 / 摘要 pct 换算 |
| `services/pnl_attribution_service.py:1711-1716/1731-1737/1744-1752/1756` | `total_mv = float(totals.get(...)); round(mv, 4)` | `CampisiResult`（已 float）→ payload 适配与 round，展示层 |
| `services/pnl_attribution_service.py:1218` | `corr_f = float(corr)` | 相关系数输出 |
| `services/bond_analytics_service.py:439` | `raw = None if value is None else float(value)` | Numeric DTO 构造（显式 `raw_scale="percent"`） |
| `services/bond_analytics_service.py:558` | `float(matched_mv / total_mv * 100)` | 覆盖率 pct 展示（Decimal 除法后转出，round 2） |
| `services/liability_analytics_service.py:254-255` | `"nim_stressed": float(nim_decimal - NIM_STRESS_SHOCK_DECIMAL)` | Decimal 减法后 float 输出（压力展示行） |
| `services/liability_analytics_service.py:331/335` | `out.append({"x": float(years), "y": float(ytm), "z": float(z)...})` | 散点图坐标输出 |
| `core_finance/liability_analytics_compat.py:91-94/326-327/347-348/363-364/379-380/405-408/427-429/559-562/615-631/767-773/785-787/799-824/863-864`（共 53 处 `to_float`） | `"amount": to_float(amount)` 等 | 全部为 Decimal 域计算后的 legacy payload 输出转换；且该模块在 AGENTS.md 排除清单（非正式主线） |

---

## 4. C 类 —— 分析型/策略/情景模块（非正式口径，低优先）

判定共性：模块整体属分析/策略/宏观/情景口径（AGENTS.md 排除面或 Formal/Scenario 分离的 scenario 侧），输入多为行情价格/成交额/指数等 float 原生数据。

### 4.1 情景与市场分析（任务重点核实项）

| 文件 | 命中行号 | 理由 |
| --- | --- | --- |
| `services/risk_scenario_stress_service.py` | `float(`:238；float 字面量：84（`shock_bp=10.0`）、114（`*10.0`）、136（`shock_pct=0.10`）、149-152（`(1±shock_pct)`） | 见 §1.2：`basis="scenario"`、明示“not a formal PnL”、逐行 `human_review_required`；冲击算术 float 属实但口径隔离完整 |
| `core_finance/market_derived.py` | 19、89、98、139、143、152 | 市场衍生工具（bp 差、月度曲线插值）；**全仓仅 `tests/test_market_derived.py` 消费，生产休眠** |
| `core_finance/credit_spread_analysis.py` | 213 | 信用利差分析页；且该处为插值目标年限（时间量纲） |
| `services/pnl_attribution_service.py` | 322、359、407、471、760-761、973、978、1115-1119、1282 | TPL vs 国债相关性/月度趋势分析组件：国债 10Y、DR007 float 化（322/359/407/471），514/516/517 金额 float 求和仅用于趋势叙事（973/978/1115-1119）；1282 为 FTP 设置读取（进入 A-10 workbench 的 funding 输入，风险记在 A-10） |
| `core_finance/pnl_attribution/workbench.py` | 523、524、539、540、541 | 同模块内的 TPL 相关性子块（Pearson r、趋势合计），纯解读性输出；模块金额算术已记 A-10 |

### 4.2 策略/候选/回测模块（全部 C）

| 文件 | 命中行号（`float(`） |
| --- | --- |
| `core_finance/portfolio_backtest.py` | 274、304、345、368、439-441、716、739、746、762、793-794、823、829、842-844、872、896、941、949-953、1017、1030、1034、1118、1121、1253、1260、1464-1476（共 37） |
| `core_finance/livermore_stock_candidates.py` | 213-219、320-325、669-677、778-781、784-812（共 29） |
| `core_finance/candidate_history_proxy_backtest.py` | 78、81、84、115、118、179、231、394、402-404、453-454、475、481、505、522、526（共 18） |
| `core_finance/vol_target_overlay.py` | 25、55、59、94-95、104、115、143、148、153、202、221、224、249-261（共 17） |
| `core_finance/hybrid_fusion_candidates.py` | 443、500、648-656、667、670、726、732、736（共 13） |
| `core_finance/livermore_sector_rank.py` | 71-73、151-153、163-164、173-175、231、238（共 13） |
| `core_finance/matched_baseline.py` | 329、339、351、702、740、792、796、804、814、833-834、934、939（共 13）——股票对照基线/自举置信区间 |
| `core_finance/portfolio_paths.py` | 106-107、112-113、190、227、260-261、296、304、315、318（共 12） |
| `core_finance/mean_reversion_candidates.py` | 133-136、200、211、214、217、222、231（共 10） |
| `core_finance/uptrend_momentum_candidates.py` | 140、178-180、231、242、245、248、253、262（共 10） |
| `core_finance/livermore_risk_exit.py` | 88、93-94、120、152、191、194、197、204、211（共 10） |
| `core_finance/livermore_theme_breakout.py` | 164-170、382、389、396（共 10） |
| `core_finance/fresh_trend_watchlist_candidates.py` | 178、218、222-224、279、326、329、332、337、346（共 11） |
| `core_finance/gate_exposure_series.py` | 101、159、192、228、265、318、323、326（共 8） |
| `core_finance/factor_screen_candidates.py` | 130、179、235（共 3） |
| `core_finance/gate_macro_overlay.py` | 104、221、225（共 3） |
| `core_finance/cycle_macro_score.py` | 220、269（共 2） |
| `core_finance/adjusted_returns.py` | 55（另 51 行 float 字面量算术）——策略成本调整收益 |
| `core_finance/hybrid_fusion_config.py` | 104（配置解析） |
| `core_finance/market_breadth.py` | 62（涨跌家数差，计数性质） |

### 4.3 宏观模块 `core_finance/macro/**`（全部 C，按文件计数）

非脚本模块：`dual_frequency_equity.py` 36、`macro_etf_strategy.py` 36、`a_share_stampede_risk.py` 27、`helpers.py` 20、`equity_strategies.py` 16、`risk_parity.py` 13、`equity_shadow_portfolio.py` 13、`crisis_score.py` 9、`liquidity_stress.py` 8、`yield_curve_shape.py` 8、`macro_portfolio_impact.py` 7、`merrill_clock.py` 6、`crisis_commodity_shadow.py` 6、`credit_spread_percentile.py` 4、`credit_spread_risk.py` 4、`dcc_garch.py` 3、`monetary_policy_stance.py` 2、`cta_trend.py` 2、`leading_indicator.py` 1、`rate_turning_point.py` 1、`toolkit/WindPy.py` 3。

独立研究脚本 `macro/toolkit/scripts/*`（CLI，不接正式链）：`generate_bond_macro_report.py` 88、`backtest_cn.py` 15、`cta_trend_cn.py` 8、`regime_switch_cn.py` 6、`risk_parity_cn.py` 6、`performance_metrics_cn.py` 5、`evening_report.py` 5、`signal_aggregator.py` 4、`rebalance_cn.py` 4、`dcc_garch_cn.py` 4、`bond_futures_data.py` 3、其余（`risk_monitor`/`merrill_clock_cn`/`crisis_score_cn`/`crowding_cn`/`bond_futures_signals`）各 1。

`core_finance/macro_bond_linkage.py`（宏观-债券联动，43 处：242-243、451、455、617、761-762、897-901、949-955、985、990-991、1056、1067、1082-1083、1087、1096-1097、1102-1103、1194、1201、1207、1348、1377、1397、1403、1433、1472、1478、1508、1520、1996、2040）——相关性/分位数/领先滞后统计，float 数值方法合理。

### 4.4 负债/ADB 分析链（C，含一处值得跟踪的 float 加权）

| 文件:行号 | 摘录 | 理由 |
| --- | --- | --- |
| `core_finance/adb_analytics.py:43-44/240-242/267/273-274` | `"daily_balance": float(spot)` | 趋势/占比输出边界 |
| `core_finance/adb_analytics.py:154-156/177-181/311-314` | `balance = float(...); weighted = balance * rate; totals[category] = (0.0,0.0,0.0)` | **加权负债利率在 float 域累加**（`weighted_rate` 输出 round 4）。负债分析不在正式主线（AGENTS.md 排除 `liability_analytics_compat`，liability 面板为分析属性），故记 C；若日均成本口径升级为正式指标，此处应升级为 A |
| `core_finance/adb_rate_normalize.py:69`（及 78-89 的 `/100.0`） | `number = float(candidate)...return number / 100.0` | ADB 利率单位归一返回 float（与 A-11 同型，但消费面在分析链） |

---

## 5. D 类 —— 已有防护 / 数值算法或时间量纲的合理 float

| 文件:行号 | 摘录 | 防护/理由 |
| --- | --- | --- |
| `core_finance/curve_engine/interpolation.py:139` | `ys = [float(p.rate) for p in points]` | 三次样条 Thomas 算法在 float 域求解（纯 Python 数值算法，Decimal 不适用开方/迭代场景）；**出口量化防护**：207 行 `Decimal(str(round(result, 8)))`，误差被钉在 5e-9 个百分点内；线性回退分支 222 行 `frac = Decimal(str((target-y0)/span))` 仅时间比例走 float，利率混合在 Decimal（223 行） |
| `core_finance/curve_engine/nelson_siegel.py:121/157` | `ys = [float(p.rate)...]` | NS/Svensson 最小二乘拟合，数值优化必须 float |
| `core_finance/curve_engine/bootstrapper.py:97/103/129/147` | `c = float(par_point.rate)/100.0`；`df = 1.0/(1.0+c)**t` | 折现因子自举含分数次幂 `**(1.0/t)`（127 行），Decimal 无法直接支持；出口量化：131 行 `Decimal(str(round(z, 6)))` |
| `core_finance/curve_engine/bootstrapper.py:173/179` | `diff_bps = (float(pt.rate) - vendor_rate) * 100.0` | 交叉验证诊断（bp 差、阈值告警），不进正式结果 |
| `core_finance/bond_analytics/read_models.py:123/700/829` | `_interpolate_fitted_curve(fitted, float(years_to_maturity))`；`rolled_years = max(float(...) - period_days/365, 0.0)` | 时间量纲（年限）作插值查询键；701 行立即 `Decimal(str(rolled_years))` 回 Decimal，利率/金额算术全 Decimal（702 行） |
| ~~`core_finance/bond_duration.py:61`~~ **（2026-08-13 复核：该命中已不存在）** | ~~`max(0.0, (maturity - report).days / 365.0)`~~ | 这处 float 期限代理随 W-fi-2026-08 P2 一并删除：`_estimate_duration_proxy_years`（3.0）与 `SA`/`SCP` 前缀短路（0.25）均已移除，缺到期日改由 `common.resolve_missing_maturity_duration` 统一返回 `DURATION_UNAVAILABLE`（0）。当前 `bond_duration.py` 对 `float(` 与 `365.0` **均为零命中**，与 §0.1 结论一致；Macaulay/修正久期/凸性仍全 Decimal（委托 `common.py`） |
| `core_finance/pnl_bridge.py:578` | `return float(_coerce_decimal(materialized))` | `_years_to_maturity` 时间量纲，仅作 `_curve_rate` 查询键（561-570 行）；桥金额全 Decimal |
| `core_finance/campisi.py:90` | `CurvePoint(years=float(t), rate=Decimal(str(curve[k])))` | 年限 float（整数期限精确表示），利率同一行回 Decimal |
| `core_finance/campisi.py:262`（`_years_to_maturity`）与 `services/campisi_attribution_service.py:1010`（`_formal_maturity_bucket`） | `days / 365.0` | 时间量纲：插值输入与期限分桶 |
| `core_finance/attribution_core.py:211/273` | `int(round(float(maturity_years) * n))`；`CurvePoint(years=float(t), ...)` | 期数取整与曲线年限，现金流折现本体 Decimal（209-214 行） |
| `core_finance/pnl_attribution/workbench.py:236/246/309/360/372/385` | `months = float(t[:-1])` 等 | 期限标签解析与覆盖性判定（时间量纲/有效性检查）；模块金额破口已记 A-10 |
| `core_finance/bond_analytics/common.py`（零 `float(` 命中） | `safe_decimal`：20-31 行（NaN/Inf 归零防护）；久期/凸性全 Decimal；`build_curve_points` 年限 float + 利率 `safe_decimal`（324 行） | 正式久期/DV01 数学的 Decimal 防护基座 |
| `core_finance/reconciliation_checks.py:17-28` | `_comparison_decimal` | 对账比较 Decimal 化改造（2026-07-19 M-4），float 仅出口（见 B 表） |
| `core_finance/qdb_gl_monthly_analysis.py:2182-2187` | `Decimal(str(value))` + `is_finite()` 防 NaN | Excel 输入侧 Decimal 防护（2186 行的 `float("nan")` 为注释文字） |

---

## 6. `Numeric raw_scale="auto"` 定义与消费面（任务指定记录项）

### 6.1 定义

- `backend/app/schemas/common_numeric.py:25`：`NumericRawScale = Literal["auto", "percent", "ratio"]`；
- `:16`：`NumericUnit = Literal["yuan","pct","bp","ratio","years","count","dv01","yi"]`；
- `:42`：**`Numeric.raw: float | None`——治理契约的 raw 值本身就是 float 类型**（前端消费的机器可读值），这是全部输出边界 float 化（B 类）的契约根源；
- `:77`：`numeric_from_raw(..., raw_scale: NumericRawScale = "auto")` 默认 auto；
- `:126-136`：启发式实现——`unit=="pct"` 且 `abs(raw) > 1.0` 视为百分点 `/100.0`，否则视为已归一比率；
- `:19-24` 注释明示歧义：真百分点值落在 (0,1] 时（如 0.85% 传 0.85）会被误判为比率 → 渲染成 “85.00%”。

### 6.2 消费面

显式规避 auto（已治理）：

| 调用点 | raw_scale |
| --- | --- |
| `services/bond_analytics_service.py:441` | `"percent"`（435-437 行注释说明防 <1% 值误判） |
| `services/yield_curve_term_structure_service.py:222` | `"percent"` |
| `services/dashboard_service.py:114` | `"percent"`（107 行注释） |
| `services/cashflow_projection_service.py:136` | `"ratio"`（129 行注释） |
| `services/risk_scenario_stress_service.py:175/187/188/198` | `"ratio"`（173-174 行注释：比率可合法 >1） |
| `services/pnl_attribution_service.py:635-637` | spec 三元组显式 `"ratio"` 时走 `_ratio_pct_numeric` |

仍依赖默认 auto 的面（spec 二元组未声明第三元）：

- `services/pnl_attribution_service.py:635`（`raw_scale = spec[2] if len(spec) == 3 else "auto"`）
- `services/explicit_numeric.py:53/88`（通用 spec 解包，默认 auto）
- `schemas/liability_analytics.py:18/58`、`schemas/bond_dashboard.py:18/58`、`schemas/cashflow_projection.py:19/55`（各自 `_NUMERIC_FIELDS` 二元组条目默认 auto）

`numeric_from_raw(` 调用密度（消费规模）：`schemas/bond_analytics.py` 37、`schemas/bond_dashboard.py` 33、`schemas/risk_tensor.py` 23、`services/risk_scenario_stress_service.py` 13、`schemas/cashflow_projection.py` 5、`schemas/pnl_bridge.py` 3、`schemas/liability_analytics.py` 3、其余 ≤2。

残余风险：pct 字段 + 默认 auto + 真实值可落 (0,1] 的组合（收益率、利差、期间收益类字段）。建议后续任务对上述 5 个 spec 文件的 pct 二元组逐字段补 `"percent"`/`"ratio"` 声明，并考虑将默认值从 `"auto"` 收紧为必填。

---

## 7. A 类修复优先级排序与预估影响

量级基准：Decimal→float 单次往返相对误差 ≤2.2e-16；1e8 元金额 → ~1e-8 元；float 域累加 n 项误差 O(n·ulp)。正式闭合阈值 0.01 元（`campisi_attribution_service.py:1840`）、决策残差阈值 Decimal("0.01")（:1918）。

| 优先级 | 条目 | 修复建议 | 预估影响与理由 |
| --- | --- | --- | --- |
| **P1** | A-10 workbench 模块（40 处） | 模块级改造：`_f` → `safe_decimal`，金额乘加改 Decimal 域，出口统一 float 化；或在契约中把该面正式降级为分析口径 | 唯一“金额×利率×久期在 float 域**累加**”的正式面（`carry_pnl`、`contrib` 等元级金额）；误差随券数线性放大；且与“正式计算 Decimal 域”治理规则正面冲突。改动面大（约 15 个函数），需 golden 快照对比验证 |
| **P2** | A-5→A-1/A-2/A-3 输入链（campisi 服务 4 处 + campisi.py 5 处） | `curve_to_market_dict`/`_fetch_*_spread` 保持 Decimal；`_coerce_percent_curve` 收 Decimal、`*100` 用 `Decimal("100")`；219 行改 `(Decimal(s1)-Decimal(s0))/Decimal("10000")` | 覆盖 Campisi 四/六效应全部利率输入；单点误差 ~1e-15 个百分点，经 `-D×Δy×MV` 放大后 ~1e-7 元/券量级。改动局部、可用现有 `tests/test_campisi*` 黄金样本回归 |
| **P3** | A-6/A-7 合并头寸链（服务 6 处） | `merge_positions` 直接传 Decimal（`bond_four_effects` 的 `safe_decimal`/`_annual_rate_decimal` 已兼容任意输入类型，改动零风险） | 金额（市值/面值/应计利息）float 中转；1e10 元级误差 ~1e-6 元。改造后 A-4 出口前的整条链保持 Decimal |
| **P4** | A-8/A-9 formal bridge 记录与桶累加（服务 ~14 处） | `_formal_bridge_bond_rows` 保留 Decimal 记录、出口统一转换；1192 行桶累加改 Decimal | A-9 是 float 域求和（O(n) 累积）；期限桶视图为正式面板展示。改动局部 |
| **P5** | A-4 totals 闭合回流（campisi.py 6+9 处 + 服务 2 处） | `CampisiResult` 增设 Decimal totals 或闭合处直接用 Decimal 域 total（P3/P4 完成后自然消解） | 当前误差 ~1e-8 元，0.01 元阈值内不可观察；优先级最低的真破口 |
| **P6** | A-11 rate_units 两函数（4 处） | 返回类型改 `Decimal | None`（`v` 解析后 `Decimal(str(v)) / _HUNDRED`），与同文件显式转换器对齐 | 系统性中转点（票息/YTM 进四效应必经），但误差单次有界；**签名变更影响面广**（campisi 服务、bond_analytics engine、pnl_bridge、多处测试），需一次性协调，建议独立小任务 |
| **P7** | A-12/A-13 attribution_daily rolldown（3 处） | 与 P2 同改：`interpolate_treasury_yield_pct` 提供 Decimal 出口 | `compute_daily_attribution_row` 当前无生产调用方（仅测试），休眠面；随 P2 顺带处理 |

整体判断：**所有 A 类破口的当前数值影响都在正式闭合与展示精度的可观察阈值之下**（最大单点 ~1e-6 元级），不存在需要紧急修数的错账风险；清偿价值在于（1）消除 float 域累加随组合规模放大的尾部风险，（2）让“正式链 Decimal 域”规则可被静态检查（如 ruff 自定义规则/审计脚本以 `float(` 为哨兵），（3）降低对账残差里的非业务噪声。建议按 P2→P3→P4→P5 的顺序在 Campisi 链内一次收口（同一测试面），P1 与 P6 各立独立任务。

---

## 8. 附录：正式链零命中文件清单（负面证据）

以下正式链文件 `float(`、float 字面量算术、`astype(float)`/`np.float`/`float64`/`to_numpy(` 均为零命中（Decimal 域干净）：

- core_finance：`pnl.py`、`pnl_constants.py`、`pnl_by_business_insights.py`、`product_category_pnl.py`、`fx_rates.py`、`risk_tensor.py`、`balance_analysis_workbook.py`（仅 Decimal 字面量与注释）、`balance_workbook/builder.py`、`balance_workbook/_analysis_tables.py`、`balance_workbook/_utils.py`（命中均为 `Decimal("1.5")` 类字符串与注释）、`balance_workbook/_ifrs9_tables.py`（命中为字符串 “4.3 …”）、`bond_four_effects.py`、`bond_duration.py`（除 D 表 61 行时间量纲）、`bond_analytics/common.py`、`bond_analytics/dv01.py`、`cashflow_projection.py`（342 行为注释）、`finance_metric_engine.py`、`var_engine.py`、`campisi_decision_grade.py`、`interest_mode.py`、`field_normalization.py`、`safe_decimal.py`、`calibers/**`、`config/**`、`source_preview_parsers.py`
- services：`pnl_service.py`、`pnl_bridge_service.py`、`pnl_source_service.py`、`pnl_task_dispatch.py`、`pnl_by_business_summary.py`、`pnl_by_business_unallocated.py`、`pnl_by_business_adjustments.py`、`pnl_by_business_candidate_insights.py`、`pnl_bond_bucket_merge.py`、`balance_analysis_service.py`、`balance_analysis_workbook_service.py`、`bond_dashboard_service.py`、`risk_tensor_service.py`、`liability_knowledge_service.py`

（完）
