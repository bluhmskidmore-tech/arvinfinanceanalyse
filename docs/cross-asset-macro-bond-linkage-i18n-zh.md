# 宏债联动 / 跨资产（`macro_bond_linkage.py`）文案中英对照

面向后端：在**不改变 JSON 里枚举 key**（如 `stance: "supportive"`）的前提下，将面向用户的 **`summary`、规则文案、动态模板、warnings** 替换为中文。

- **源码位置**：`backend/app/core_finance/macro_bond_linkage.py`
- **说明**：`impacted_views` 仍用 key（`duration` 等），由前端 `formatImpactedViewsForDisplay` 显示中文；证据链 `evidence` 中若需中文，可同步改前缀列于文末。

---

## 1. 枚举（API 存英文，仅 UI 或文档展示用的中文别称）

| 英文 (API) | 建议中文短标签 |
|------------|----------------|
| `supportive` | 偏有利 / 支持性 |
| `neutral` | 中性 |
| `restrictive` | 偏紧 / 压制 |
| `conflicted` | 有冲突 |
| `bullish` | 偏多（研究视角） |
| `bearish` | 偏空 / 偏防御（研究视角） |
| `ready` | 已就绪（若用于 UI 文案；轴状态可沿用前端「已就绪」） |
| `pending_signal` | 待信号 |

| `axis_key` (API) | 中文名（与前端轴标题对齐） |
|------------------|----------------------------|
| `global_rates` | 全球利率 |
| `liquidity` | 流动性 |
| `equity_bond_spread` | 股债相对估值 |
| `commodities_inflation` | 商品与通胀 |
| `mega_cap_equities` | 大市值结构 |

---

## 2. 传导轴：`_build_global_rates_axis`

| English (current) | 建议中文 |
|-------------------|----------|
| Rate direction signals are easing and support adding duration risk. | 利率方向信号偏宽松，对拉长久期风险有支撑。 |
| Rate direction signals are tightening and argue for tighter duration risk budgets. | 利率方向信号偏紧，宜收紧久期风险预算。 |
| Rate direction is mixed and does not justify a strong duration call. | 利率方向信号混杂，不宜给出强烈的久期方向判断。 |

---

## 3. 传导轴：`_build_liquidity_axis`

| English | 建议中文 |
|---------|----------|
| Funding conditions are supportive and favor rates, NCD carry, and high-grade credit. | 资金环境偏松，对利率、NCD 票息与高等级信用更友好。 |
| Funding conditions are restrictive and argue against extending risk through NCD or credit. | 资金环境偏紧，不宜通过 NCD 或信用过度拉长风险。 |
| Liquidity conditions are balanced and warrant neutral implementation. | 流动性环境中性，宜保持中性的实现与久期/敞口。 |

---

## 4. 传导轴：`_build_commodities_inflation_axis`

| English | 建议中文 |
|---------|----------|
| Inflation pressure is subdued enough to support rates and high-grade spread carry. | 通胀压力相对温和，对利率端与高等级利差票息有支撑。 |
| Inflation and growth pressure argue against aggressive duration or spread compression calls. | 通胀与增长压力并存，不宜激进拉长久期或押注利差压缩。 |
| Growth and inflation signals conflict, so commodity-linked inflation pressure is inconclusive. | 增长与通胀信号打架，商品关联的通胀压力尚难定论。 |
| Commodity and inflation signals are neutral for current bond research views. | 商品与通胀信号对当前债市研究判断整体中性。 |

---

## 5. 传导轴：股债 + 大票（含规则与动态句）

### 5.1 `EQUITY_BOND_SPREAD_RULES` 内 `summary`

| English | 建议中文 |
|---------|----------|
| Equity-bond spread remains wide and equities are rising, which restrains bond risk appetite. | 股债利差仍处高位且权益上行，对债市风险偏好形成压制。 |
| Equity-bond spread is wide, but equities are falling, leaving the cross-asset message conflicted. | 股债利差虽宽，但权益走弱，跨资产信息存在冲突。 |
| Equity-bond spread has compressed enough to support a more constructive bond view. | 股债利差已压至一定区间，对债券观点可更建设性。 |

### 5.2 `MEGA_CAP_EQUITY_RULES` 内 `summary`

| English | 建议中文 |
|---------|----------|
| Mega-cap concentration is high and leadership is rising, which leans against adding bond beta aggressively. | 大市值集中度高且龙头在走强，不宜激进加大债券久期/贝塔。 |
| Mega-cap concentration is high but leadership is fading, which supports a more defensive equity backdrop for bonds. | 大市值集中度高但龙头动能走弱，对债券而言权益侧更偏防御。 |

### 5.3 无信号时（pending）

| English | 建议中文 |
|---------|----------|
| Pending governed equity spread proxy; do not infer from unrelated signals. | 受治理的股债利差代理未就绪，请勿用无关序列推断。 |
| Pending governed mega-cap equity leadership proxy; do not infer from unrelated signals. | 受治理的大市值龙头代理未就绪，请勿用无关序列推断。 |
| missing governed proxy series | 受治理的代理序列缺失 |

### 5.4 动态 `context`（`summary` 拼接用，需保留占位符与日期格式）

**股债轴**（`equity_bond_spread`）原模板：

`CSI300 equity-bond spread is {x}ppt (earnings yield {a}% - CN10Y {b}%), with CSI300 move {m} on {date}.`

建议中文：

`沪深300 股债溢价约 {x} 个百分点（盈利收益率 {a}% - 中债 10Y {b}%），指数当日涨跌 {m}，交易日 {date}。`

**大票结构轴**（`mega_cap_equities`）原模板：

`CSI300 top10 weight concentration is {t10}% (top5 {t5}%) on {date}, with latest index move {m}; leaders include {leaders}.`

建议中文：

`沪深300 前十大成分股权重合计 {t10}%（前五大 {t5}%），权重日 {date}，最近指数涨跌幅 {m}；主要龙头包括 {leaders}。`

（实现时可保留 `n/a` 不译或译为「无」。）

---

## 6. 研究判断 `research_views`：久期 `_build_duration_view`

| English | 建议中文 |
|---------|----------|
| Backend research supports longer duration because the equity-bond spread axis is supportive. | 研究判断倾向更长久期：股债相对估值传导轴偏有利。 |
| Backend research supports longer duration across rates, NCD, and high-grade credit. | 研究判断倾向在利率、NCD 与高等级信用上拉长或维持久期空间。 |
| Backend research favors keeping duration tight across rates, NCD, and high-grade credit. | 研究判断倾向在利率、NCD 与高等级信用上保持偏紧的久期。 |
| Duration inputs conflict: rates are supportive, but the equity-bond spread axis is restrictive. | 久期判断存在冲突：利率侧偏有利，但股债相对估值轴偏紧。 |
| Duration inputs conflict across rate direction and inflation pressure; keep duration balanced. | 利率方向与通胀/商品压力在久期上存在冲突，宜保持久期平衡。 |
| Duration inputs are mixed, so keep the duration stance neutral. | 久期相关输入偏混杂，久期上宜保持中性。 |

---

## 7. 研究判断：曲线 `_build_curve_view`（按 `stance` 字典）

| Stance (API) | English | 建议中文 |
|--------------|---------|----------|
| `bullish` | Curve conditions favor owning front-end rates and NCD carry rather than flattening defensively. | 曲线环境更偏持有短端与 NCD 票息，而非为防御而过度拉平。 |
| `bearish` | Curve conditions argue for staying defensive on rates and NCD curve exposure. | 曲线环境对利率与 NCD 曲线风险暴露偏防御。 |
| `conflicted` | Curve inputs disagree across duration and liquidity; avoid a large curve tilt. | 久期与流动性在曲线上的信号不一致，避免大幅曲线押注。 |
| `neutral` | Curve inputs are balanced and do not support a strong rates or NCD curve tilt. | 曲线输入较均衡，不支撑强烈的利率或 NCD 曲线倾向。 |

---

## 8. 研究判断：高等级信用 `_build_credit_view`

| English | 建议中文 |
|---------|----------|
| High-grade credit should stay defensive because both equity-bond spread and mega-cap leadership are restrictive. | 股债相对估值与大市值结构两条轴均偏紧，高等级信用宜保持防守。 |
| High-grade credit is supported, but the tranche remains limited to high-grade spread risk only. | 高等级信用有支撑，但范围仍应限定在高等级的利差/票息内。 |
| High-grade credit should stay defensive while liquidity or inflation pressure remains restrictive. | 在流动性或通胀/商品端仍偏紧时，高等级信用宜守势。 |
| High-grade credit inputs conflict; keep spread exposure selective and high quality only. | 高等级信用各输入有冲突，利差敞口应精选、只做高质量。 |
| High-grade credit inputs are balanced, so keep spread exposure neutral. | 高等级信用各输入较均衡，利差敞口宜中性。 |

---

## 9. 研究判断：品种 `_build_instrument_view`（按 `stance` 字典）

| Stance (API) | English | 建议中文 |
|--------------|---------|----------|
| `bullish` | Prefer rates first, then NCD carry, with high-grade credit as a controlled extension. | 配置顺序上优先利率，其次 NCD 票息，高等级信用在可控范围内延伸。 |
| `bearish` | Keep implementation defensive across rates, NCD, and high-grade credit until pressure eases. | 在压力未缓解前，对利率、NCD 与高等级信用的实现均偏防守。 |
| `conflicted` | Instrument preferences are mixed; keep allocations balanced across rates, NCD, and high-grade credit. | 各品种倾向混杂，在利率、NCD 与高等级信用间保持均衡。 |
| `neutral` | No strong instrument tilt is supported across rates, NCD, and high-grade credit. | 在利率、NCD 与高等级信用上无强烈品种偏斜。 |

---

## 10. 证据行前缀（`evidence` 列表，可选一并中文化以便日志可读）

| English prefix | 建议中文 |
|----------------|----------|
| `global_rates:` | `全球利率：` |
| `liquidity:` | `流动性：` |
| `commodities_inflation:` | `商品与通胀：` |
| `equity-bond:` | `股债：` |
| `mega-cap:` | `大票结构：` |

（若与既有日志/对账工具耦合，可暂缓改前缀。）

---

## 11. 实施注意

- **枚举值** `stance`、`axis_key` 等保持英文，避免破坏前端/合约与单测的字符串匹配。  
- **长句 `summary`、规则文案、动态模板、warnings** 可一次性换成中文。  
- 动态行注意 **f-string 占位符、日期/百分号** 与中文标点的混排。  
- 与前端已做的轴标题/影响维度中文展示保持一致：轴名见本文 §1 表格。

---

*本表与 `2026-04` 前后 `macro_bond_linkage.py` 中字符串对应；若源码已改，以仓库为准并同步更新本表。*
