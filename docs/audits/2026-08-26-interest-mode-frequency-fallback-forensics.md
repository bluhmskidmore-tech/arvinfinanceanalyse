# 取证报告：`interest_mode` 无法推出付息频率 → 全库回退年付（f=1）对久期/DV01 的量化影响

- 状态：**只读取证证据，不构成口径变更、不修改任何生产代码或数据**
- 审计范围：`backend/app/core_finance/interest_mode.py`、`bond_analytics/engine.py`、`bond_analytics/common.py`
- 取证日期：2026-08-26
- 数据快照：`data/moss.duckdb`（只读连接），`fact_formal_bond_analytics_daily` 最新 `report_date = 2026-07-31`
- 结论一句话：现状对全部 1,750 行正式债券分析行 100% 回退年付（f=1），若把付息频率统一改为半年付（f=2）做敏感性重算，组合市值加权修正久期从 **3.6958 年 → 3.7259 年（+0.81%）**，组合 DV01 合计从 **10,272.01 万元 → 10,355.05 万元（+83.04 万元，+0.81%）**；但**国债/地方政府债/政策性金融债/信用债的真实付息惯例并不相同，不能用统一的 f=2 结论覆盖全库**，本报告仅给出"如果是半年付会偏差多少"的敏感性数字，供业务裁决。

---

## 1. 背景（审计已确认的代码事实）

`backend/app/core_finance/interest_mode.py:39-59` 的 `resolve_interest_payment_frequency`：

```39:59:backend/app/core_finance/interest_mode.py
def resolve_interest_payment_frequency(value: object) -> tuple[str, bool]:
    frequency = classify_interest_payment_frequency(value)
    if frequency != "unknown":
        return frequency, False
    # 多数调用方（coupon_frequency_per_year / coupon_interval_months /
    # is_bullet_repayment / engine）会丢弃 fallback 标志，因此在源头做一次
    # 去重披露。"固定"/"浮动" 只声明利率风格、同样推不出付息频率，回退年付
    # 与任何未知取值等价，因此不再豁免告警：正式表 1750/1750 行都走这条分支，
    # 豁免会让 100% 的回退看起来像"没有回退"（2026-08 审计）。
    raw = str(value or "").strip()
    disclosure_key = raw or _EMPTY_VALUE_DISCLOSURE_KEY
    if disclosure_key not in _FALLBACK_DISCLOSED_VALUES:
        _FALLBACK_DISCLOSED_VALUES.add(disclosure_key)
        logger.warning(...)
    return "annual", True
```

`bond_analytics/engine.py:225-227` 用同一个 `interest_mode` 源字段同时得到「付息频率」「利率风格」两个不相关的分类：

```225:228:backend/app/core_finance/bond_analytics/engine.py
        interest_mode = _as_text(snapshot_row.get("interest_mode"))
        interest_payment_frequency, interest_payment_frequency_fallback_used = resolve_interest_payment_frequency(interest_mode)
        coupon_frequency = coupon_frequency_per_year(interest_mode)
        interest_rate_style = classify_interest_rate_style(interest_mode)
```

`interest_mode` 源字段实际只承载"固定/浮动"利率风格，推不出付息频率；`resolve_interest_payment_frequency` 对任何未知取值（含"固定""浮动"）一律回退 `"annual"`（f=1）并置 `fallback_used=True`。该结论已由 `tests/test_interest_mode.py:87-91` 写明并锁定为回归测试。

`coupon_frequency`（f）随后同时决定：
- `compute_macaulay_duration_and_convexity` 的现金流时点（每 1/f 年一笔）与折现除数 `(1+y/f)`；
- `estimate_modified_duration` 的修正久期除数 `MD = Mac/(1+y/f)`；
- 正式 DV01：`DV01 = CNY face_value × modified_duration / 10000`（`docs/calc_rules.md:328`）。

因此 f 的系统性错配会同时污染 Macaulay 久期（多期现金流建模）、修正久期（折现除数）、DV01、凸性四个正式指标。

---

## 2. 数据面取证

### 2.1 DuckDB 连接与最新报告日

- 路径：`backend/app/governance/settings.py:141` 默认 `duckdb_path = "data/moss.duckdb"`；`config/.env` 未覆盖该项，`git status` 确认仓库内 `data/moss.duckdb` 即在用库。
- 只读连接：`duckdb.connect('data/moss.duckdb', read_only=True)`。
- `fact_formal_bond_analytics_daily` 最新 `report_date = 2026-07-31`，共 **1,750 行**。

### 2.2 正式表回退占比

```sql
select
  count(*) as total_rows,
  sum(case when interest_payment_frequency_fallback_used then 1 else 0 end) as fallback_rows,
  round(100.0 * sum(case when interest_payment_frequency_fallback_used then 1 else 0 end) / count(*), 4) as fallback_pct
from fact_formal_bond_analytics_daily
where report_date = '2026-07-31'
```

| total_rows | fallback_rows | fallback_pct |
|---|---|---|
| 1750 | 1750 | **100.0%** |

`interest_payment_frequency × interest_rate_style` 分组：全部 1,750 行的 `interest_payment_frequency` 都是 `annual`（1,749 行 `fixed` + 1 行 `floating`），无任何行落在 `semi-annual` / `quarterly` / `monthly` / `bullet`，与审计判断一致——代码目前不产生任何真实频率或到期一次性还本付息标记。

与正式风险张量表的自我披露交叉核对（`fact_formal_risk_tensor_daily`，同一报告日）：

| 字段 | 取值 |
|---|---|
| `bond_count` | 1750 |
| `payment_frequency_fallback_count` | **1617** |
| `payment_frequency_fallback_market_value` | **296,988,300,000（≈2.9699e11）** |
| `portfolio_modified_duration` | 3.695797 |
| `portfolio_dv01` | 102,720,132.6 |

`payment_frequency_fallback_count=1617` 小于 1,750，是因为风险张量层已把 133 行"到期日缺失/已到期"（久期不适用，`modified_duration=0`）移出久期分母单独披露（`missing_maturity_*` / `no_remaining_term`），与频率回退无关；本报告第 3 节的重算口径与此完全一致（见 3.1 的方法学自检）。

### 2.3 `interest_mode` 原始取值分布

最新报告日快照 `zqtz_bond_daily_snapshot`（`report_date=2026-07-31`）：

| interest_mode | 行数 n | 市值 mv |
|---|---:|---:|
| 固定 | 1870 | 441,192,400,000 |
| 浮息（以央行利率为基准） | 1 | 69,296,000 |
| 浮息（以银行间同业利率为基准） | 1 | 16,115,800 |

跨全部历史报告日（`zqtz_bond_daily_snapshot` 全表）：

| interest_mode | 行数 n |
|---|---:|
| 固定 | 940,204 |
| 浮息（以银行间同业利率为基准） | 3,331 |
| 浮息（以央行利率为基准） | 578 |

**确认**：`interest_mode` 字段自建库以来只出现过"固定/两类浮息基准"三个取值，从未出现任何频率相关字面量（"半年""按月""季付""到期一次还本付息"等）。审计判断"该字段只承载利率风格、推不出付息频率"在全历史范围内成立，不是当期偶发。

### 2.4 按券种分组的市值权重（分母，供后续裁决使用）

`fact_formal_bond_analytics_daily`，`report_date=2026-07-31`：

| asset_class_std | 行数 | 市值 | 市值占比 |
|---|---:|---:|---:|
| rate（利率债） | 362 | 130,535,960,960 | 38.13% |
| credit（信用债） | 1088 | 105,883,897,469 | 30.93% |
| other（其他） | 300 | 105,885,300,000 | 30.93% |

按 `bond_type` 细分（市值降序，`asset_class_std` 并列）：

| bond_type | asset_class_std | 行数 | 市值 |
|---|---|---:|---:|
| 政策性金融债 | rate | 99 | 62,948,461,229 |
| 信用债券-企业 | credit | 578 | 55,652,166,987 |
| 其他 | other | 168 | 55,120,210,000 |
| 同业存单 | other | 132 | 50,765,106,912 |
| 地方政府债 | rate | 188 | 50,448,270,347 |
| 资产支持证券 | credit | 350 | 21,748,265,640 |
| 商业银行债 | credit | 115 | 19,572,492,414 |
| 国债 | rate | 42 | 17,036,066,144 |
| 信用债券-公用事业 | credit | 37 | 7,562,295,097 |
| 次级债券 | credit | 8 | 1,348,677,330 |
| 信用债券-企业（误分类到 rate） | rate | 2 | 103,163,240 |
| 凭证式国债 | rate | 31 | 0（已到期/无市值） |

---

## 3. 影响量化：f=1（现状）vs f=2（半年付敏感性）全量重算

### 3.1 方法与自检

对最新报告日全部 1,750 行，取表内已持久化的 `coupon_rate`、`ytm`、`years_to_maturity`、`face_value`、`interest_payment_frequency` 字段，用仓库现有函数原样重放 `engine.py` 的计算路径：

1. `coupon_rate_for_math = coupon_rate if not null else 0`，`ytm_for_math = ytm if not null else 0`（与 `engine.py:283-284` 同规则）；
2. `resolve_ytm_with_par_fallback(coupon_rate_for_math, ytm_for_math)` 得到 `effective_ytm`（`common.py:241-259`）；
3. `compute_macaulay_duration_and_convexity(..., coupon_frequency=f, single_cashflow_at_maturity=(interest_payment_frequency=="bullet"))`，分别取 `f=1` 与 `f=2`（`common.py:298-388`）；
4. `estimate_modified_duration(macaulay, effective_ytm, coupon_frequency=f)`（`common.py:481-497`）；
5. `DV01 = face_value × modified_duration / 10000`（与 `engine.py:326`、`docs/calc_rules.md:328` 同口径）。

`years_to_maturity ≤ 0` 的 133 行（到期日缺失或已到期，`modified_duration` 恒为 0）不受频率假设影响，予以剔除，剩余 **1,617 行**进入重算——该行数与口径与 `fact_formal_risk_tensor_daily.payment_frequency_fallback_count=1617`、`payment_frequency_fallback_market_value≈2.9699e11` **完全吻合**，交叉验证了范围界定的正确性。

**方法学自检**：用 `f=1` 重算的 1,617 行 DV01，与表内已持久化的 `dv01` 逐行比对，**0 行偏差 > 0.01 元**（最大偏差 = 0），确认重算路径与正式引擎口径完全一致，f=2 的差异纯粹来自频率假设本身，不掺杂其他计算误差。

组合层用表内已持久化的 `market_value` 做权重，`f=2` 场景使用重算值，`current` 场景直接使用表内已持久化的 `modified_duration`/`dv01`（两者与 `f=1` 重算完全相等，见上）。

### 3.2 组合级影响（1,617 行，市值合计 2,969.88 亿）

| 指标 | 现状（f=1） | f=2 敏感性 | 绝对差 | 相对差 |
|---|---:|---:|---:|---:|
| 市值加权修正久期（年） | 3.6958 | 3.7259 | +0.0301 | **+0.81%** |
| DV01 合计（元） | 102,720,132.6 | 103,550,501.8 | +830,369.1 | **+0.81%** |
| DV01 合计（万元） | 10,272.01 | 10,355.05 | +83.04 | +0.81% |

组合当前市值加权有效收益率（`effective_ytm`）约 **2.38%**，处于低利率环境；这是本次相对偏差（约 0.8%）明显小于背景材料中"y=5% 时分母差约 2.4%"理论值的主因——`(1+y/2)` 相对 `(1+y/1)` 的折现分母差随 y 近似线性缩小。逐行相对偏差分布：中位数 0.61%，p95 2.12%，最大 4.56%（长久期利率债，见 3.4）。

### 3.3 按券种分组（不给单一结论，供业务分层裁决）

| bond_type | asset_class_std | 行数 | 市值（元） | MD 现状 | MD f=2 | MD 相对差 | DV01 现状（万元） | DV01 f=2（万元） | DV01 差额（万元） | DV01 相对差 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 政策性金融债 | rate | 99 | 629.48 亿 | 3.4445 | 3.4772 | +0.95% | 2,103.66 | 2,123.30 | +19.63 | +0.93% |
| 信用债券-企业 | credit | 578 | 556.52 亿 | 3.0868 | 3.1143 | +0.89% | 1,699.47 | 1,714.57 | +15.10 | +0.89% |
| 同业存单 | other | 132 | 507.65 亿 | 0.9055 | 0.9100 | +0.50% | 461.04 | 463.34 | +2.30 | +0.50% |
| 地方政府债 | rate | 188 | 504.48 亿 | 7.5198 | 7.5785 | +0.78% | 3,438.60 | 3,465.26 | +26.66 | +0.78% |
| 资产支持证券 | credit | 350 | 217.48 亿 | 1.7941 | 1.8089 | +0.82% | 389.98 | 393.19 | +3.21 | +0.82% |
| 商业银行债 | credit | 115 | 195.72 亿 | 1.8117 | 1.8251 | +0.74% | 352.66 | 355.28 | +2.62 | +0.74% |
| 国债 | rate | 42 | 170.36 亿 | 8.3352 | 8.4009 | +0.79% | 1,175.54 | 1,184.62 | +9.08 | +0.77% |
| 其他 | other | 35 | 98.03 亿 | 3.7240 | 3.7312 | +0.19% | 352.96 | 353.67 | +0.71 | +0.20% |
| 信用债券-公用事业 | credit | 37 | 75.62 亿 | 3.0171 | 3.0487 | +1.05% | 220.15 | 222.48 | +2.33 | +1.06% |
| 次级债券 | credit | 8 | 13.49 亿 | 5.6291 | 5.7292 | +1.78% | 74.37 | 75.69 | +1.32 | +1.77% |
| 信用债券-企业（误归 rate） | rate | 2 | 1.03 亿 | 2.6905 | 2.7551 | +2.40% | 2.68 | 2.74 | +0.06 | +2.40% |
| 凭证式国债 | rate | 31 | 0 | — | — | — | 0.90 | 0.91 | +0.01 | +0.90% |

**中国市场真实付息惯例参考（不代表本系统已验证，业务需自行核实每只券的招募说明书条款）**：
- **国债（记账式）**：多为半年付息，`f=2` 更贴近实际；本组合内国债市值占比 4.98%（170.36 亿），若确认半年付，久期偏差 +0.79%（8.3352→8.4009 年），DV01 少算约 9.08 万元。
- **地方政府债**：发行惯例与记账式国债接近，多为半年付；市值占比 14.73%（504.48 亿），若确认半年付，久期偏差 +0.78%，DV01 少算约 26.66 万元——是本组合内 DV01 绝对偏差金额最大的券种。
- **政策性金融债（国开/口行/农发）**：市场惯例并不统一，存量中既有年付也有半年付（新发行以半年付居多，早期存量多为年付）；市值占比 18.36%（629.48 亿），若整体误判为年付而真实为半年付，久期偏差 +0.95%、DV01 少算约 19.63 万元，是本组合内偏差百分比最大的利率债品类，**建议逐券核实付息频率而非按大类假设**。
- **信用债券（企业/公用事业/次级/ABS/商业银行债）**：中国信用债存量以年付为主，但中票、部分商业银行债、次级债存在半年付案例；市值合计占比约 32.4%，若其中的半年付子集被误判为年付，久期偏差量级 0.74%~1.78%（次级债最敏感），DV01 少算合计约 25 万元量级。**不能整体假设信用债都是半年付**，需按券种/发行文件二次核实。
- **同业存单**：本身多为贴现或短期计息品种，剩余期限短（本组合加权久期仅 0.91 年），频率假设对其影响本就最小（+0.50%），业务优先级低。

### 3.4 单券极值示例（供核查抽样）

| instrument_code | bond_type | 市值（元） | 票息 | 有效 ytm | 剩余年限 | MD 现状 | MD f=2 | DV01 差额（元） |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 200004 | 国债 | 63.28 亿 | 3.39% | 3.53% | 23.64 | 15.789 | 15.876 | +45,065 |
| 09240201 | 政策性金融债 | 49.27 亿 | 2.64% | 2.03% | 4.44 | 4.114 | 4.178 | +29,981 |
| 150319 | 政策性金融债 | 17.74 亿 | 3.88% | 3.51% | 9.46 | 7.691 | 7.881 | +28,481 |
| 250205 | 政策性金融债 | 30.58 亿 | 1.57% | 1.60% | 8.43 | 7.771 | 7.860 | +27,507 |

单券最大相对偏差出现在长久期、较高有效收益率的利率债上，符合 `(1+y/f)` 折现效应随剩余期限与收益率放大的理论预期。

---

## 4. 局限性（必须与结论一并阅读）

1. **不是断言 f=2 正确**：本报告只回答"如果真实惯例是半年付，现状偏差多大"，是敏感性/影响量化，不是新口径。是否改为 f=2、按券种差异化 f，需业务方逐券核实发行文件付息条款后裁决。
2. **现金流引擎适用边界**：`compute_macaulay_duration_and_convexity` 的标准现金流建模（`docs/calc_rules.md:327` `duration_convexity_scope=vanilla_fixed_rate_only`）不适用于含权债（可赎回/可回售）、浮息债的真实浮动现金流重定价、以及碎期券的整期/引擎双口径差异（`docs/calc_rules.md` "Fractional-period duration dual caliber" 一节，已知另有 3.8%~8% 量级的独立偏差来源，与本报告的频率假设偏差**不可叠加或混淆**，两者是不同成因）。
3. **本次重算未识别"到期一次还本付息"（bullet）券**：因为 `interest_payment_frequency` 源头 100% 回退 `annual`，从未产生 `bullet` 标记，即便某些同业存单/短期融资券实际是到期一次性付息，本次 f=1/f=2 对比对它们仍按"周期性年付/半年付"建模，而非其真实的单笔现金流结构。这是与本次任务背景相同根因的另一个侧面影响，但超出本报告"f=1 vs f=2"的量化范围，仅作为已知限制列出。
4. **有票息缺 ytm 的行按 par 假设（ytm=coupon）计算**（`resolve_ytm_with_par_fallback`），本报告完整保留该既有假设一并计入重算，未单独剥离其独立影响。
5. **金额单位**：DV01 为 CNY 面值口径（`docs/calc_rules.md:328` `dv01_base=CNY_face_value`），非市值/净价口径；本报告表格中的"万元"栏为方便阅读换算，原始计算单位均为元。
6. **样本范围**：仅覆盖 `fact_formal_bond_analytics_daily` 最新报告日（2026-07-31）1,750 行中的 1,617 行（剔除到期日不可得/已到期的 133 行）。历史报告日、其他 `report_date` 未纳入本次重算，但 §2.3 已确认 `interest_mode` 取值分布在全历史范围内同构，可合理推断历史报告日的回退占比与偏差量级同为 100% / 同一数量级。

---

## 5. 复现说明

本次取证使用仓库 venv（`.\.venv\Scripts\python.exe`）以只读方式连接 `data/moss.duckdb`，并调用仓库现有函数 `resolve_ytm_with_par_fallback` / `compute_macaulay_duration_and_convexity` / `estimate_modified_duration`（均来自 `backend/app/core_finance/bond_analytics/common.py`）对 §2.2 SQL 取出的 1,750 行逐行重算 `f=1` 与 `f=2` 两组久期/DV01；过程未修改任何生产代码或数据，取证脚本与中间 CSV 为会话临时文件，未保留在仓库中。第 3 节的全部数字均可按本节方法与 §2 的 SQL 原样复现。
