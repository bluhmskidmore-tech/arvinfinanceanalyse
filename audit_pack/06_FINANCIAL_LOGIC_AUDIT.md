# 06 — 金融计算逻辑审计清单

扫描重点：`backend/app/core_finance/**`、`backend/app/services/*attribution*`、`bond_analytics`、PnL、`risk_tensor`。下列为 **入口级**条目，需在变更口径时用 golden + 业务方复核。

---

## 1. 损益归因工作台（volume / rate / TPL-market / composition）

| 项 | 位置 | 说明 |
|----|------|------|
| Volume–rate 分解 | `core_finance/pnl_attribution/workbench.py` — `build_volume_rate_attribution` | 读写 `dict`/`float`，与正式科目表衔接于 service 层 |
| TPL×利率相关性 | `build_tpl_market_correlation` | 文本叙事 + 相关系数字段；注意样本区间 |
| 损益构成 | `build_pnl_composition` | 与 `contracts.ts` 「不在前端计算」对齐 |
| 分析摘要 | `build_pnl_attribution_analysis_summary` | 对齐 `Tpl` 相关 narrative |

---

## 2. Carry / Roll-down（高级归因）

| 函数 | 文件 | 公式要点（自然语言） | 数值类型 |
|------|------|----------------------|----------|
| `build_carry_roll_down` | `pnl_attribution/workbench.py` | 按 `asset_class_std` 分组；**Carry% ≈ coupon% − FTP%**；**CarryPnL ≈ MV × carry_dec / 12**（月度）；**Roll% ≈ (curve_slope_bp/100)×ModDur**；**RollPnL ≈ MV × roll%/100 / 12** | **`float`**，`_f()` 助手；FTP 取自 settings `ftp_rate_pct`（Decimal → service 中转 float）|

**AUDIT**：除零：`mv`、`total_mv`、`den` 多数有分支；coupon/ytm 使用加权。单位：`mv` 与输出 PnL 须与 **`元`** 数据源一致——若读模型已是 **万元**，会出现 **量级错误**。

---

## 3. KRD / DV01（组合张量）

| 项 | 文件 | 说明 |
|----|------|------|
| Bucket 枚举与回退映射 | `core_finance/risk_tensor.py` | `krd_*` keys；非标准期限 map 近邻 |
| DV01 | 同行 | `portfolio_dv01 = sum(row.dv01)`；信用子集可加总 `spread_dv01` |

**AUDIT**：`Decimal` 聚合 + `warnings`；与 `bond_analytics` read_models 「铁律不重算」注释一致。

---

## 4. Campisi / 四效应（多实现路径）

### A）`compute_bond_four_effects`

| 函数 | `core_finance/bond_four_effects.py` | 输入：`bond` dict、`benchmark_yield_change`、`spread_change`、`num_days`、`report_date` | 输出：`Dict[str, Decimal]`（income / treasury / spread / selection / total）|
|------|----------------------------------------|-------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| 公式 | Docstring：**全价**：`(mv_end+ai_end)-(mv_start+ai_start)`；否则 **净价+票息** 近似 → **selection 吸收误差** |
| Decimal | ✅ 内核 Decimal |
| 风险 | **`_get_bond_field`** 中对 `pandas` 导入与 `except ...: pass`（见 `07`）；AC 类利率效应归零 |

### B）`build_campisi_attribution`（组合级简化）

| 文件 | `pnl_attribution/workbench.py` |
|------|----------------------------------|
| 状态 | **`spread`、`selection` 仍为 STUB（0）**，注释写明缺信用曲线 |
| 数值 | **`float`** 主导；组合层 `total_mv` 由各 `summaries` 市值汇总后再算权重 |

### C）资产负债 Workbook Campisi 表

| 文件 | `core_finance/balance_analysis_workbook.py` — `_build_campisi_table` | Formal 口径与账务事实表 |

---

## 5. 其它核心模块（关键词索引）

| 主题 | 文件 / 符号 |
|------|--------------|
| 曲线 / bootstrap | `core_finance/curve_engine/*`（新项目录）|
| Market derived | `market_derived.py` |
| Campisi 服务层 | `services/campisi_attribution_service.py`（HTTP 下层）|
| Attribution core（残差校验等） | `attribution_core.py` — `ReconciliationResult`、`QualityFlag`、`Decimal` |
| PnL 正式口径 / HTM,FVOCI,TPL | `core_finance/pnl.py`、`classification_rules.py` |
| Bond 收益率分解读模型 | `bond_analytics/read_models.py`、`bond_analytics_return` 路由 |
| 利率模式 / 贴现 | `interest_mode.py`、`rate_units.py` |

---

## 6. FTP / FTP 百分比

| 来源 | `governance/settings.py` — `ftp_rate_pct: Decimal = Decimal("1.75")` |
|------|----------------------------------------------------------------------|
| 用途 | Carry 工作台；变更属 **高风险口径** |

---

## 7. 单位与时间区间（共性风险）

| 风险 | 检查 |
|------|------|
| 元 / 万元 / 亿元 | 前端 formatter `wan`、`yi` vs 后端 `NumericUnit` |
| `%` vs `bp` | `normalize_annual_rate_to_decimal`、`rate_units` |
| MoM/YoY/区间天数 | `lookback_days`、`num_days`、含首不含首 |

---

## 8. 「需业务重核」勾选项（当前静态结论）

1. Carry/Roll：`/12` 假设与 **月度** PnL 切片是否全局一致？  
2. Campisi：**spread/selection STUB**。  
3. `bond_four_effects`：**缺 AI** 时使用净价近似 → **Residual 吸收**。  
4. `Attributed` KPI **Float JSON** 出库 vs **Decimal** 入库。  

---

## 9. Formal / Scenario 隔离

多层服务通过 `basis`、`formal_pnl_enabled`、`formal_pnl_scope_json` 与环境变量 **`MOSS_FORMAL_*`**；审计变更须同步 `tasks/` 物料化链路。
