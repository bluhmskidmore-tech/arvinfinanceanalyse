# 2026-07-19 全系统计算端审计报告

- 审计方式：5 个领域专项只读审计并行执行（PnL 归因 / 固收与风险引擎 / 余额与会计口径 / 宏观与策略信号 / 共享计算基础设施），随后进行跨领域汇总与数据取证。
- 范围：`backend/app/core_finance/` 全部正式与分析计算模块及其服务接线、相关测试与口径文档。
- 结论级别定义：Critical（正式口径已知输出错误且无披露）/ High（很可能输出错误数字或临近失效）/ Medium（口径不一致、边界缺陷、静默退化）/ Low（文档漂移、死代码、轻微偏差）。
- 前次审计对照：`docs/audits/2026-06-10-calculation-logic-audit.md`（本次确认其 P1 engine 单位启发式已修复；多项 P2/P3 仍开放）。

## 总体结论

**未发现 Critical。** 正式口径主链（余额投影、FX fail-closed、H/A/T 映射、发行类剔除、固收核心公式、514/516/517 归并、正式财务指标契约）健康度高。共 **11 项 High、约 30 项 Medium**，集中在展示/分析层与四个跨领域根因。

各域评级：PnL 归因 B+、固收 B+、宏观策略 B+、共享工具中等偏好、余额会计（正式层高 / 展示层中低）。

## 数据取证结果（2026-07-19）

### 取证 1：`ytm_value` / `coupon_rate` 落库单位 = 百分数口径（裁决依据）

对 `data/moss.duckdb` 的 `fact_formal_zqtz_balance_daily`（1,762,324 行）只读查询：

| 指标 | ytm_value | coupon_rate |
|---|---|---|
| 非空行数 | 1,395,052 | 1,761,850 |
| 中位数 | 2.3794 | 2.38 |
| P95 | 4.1667 | 4.34 |
| 落在 [2,20) 百分数典型区间 | 998,448 行 | 1,238,816 行 |
| 落在 [0.2,2) 灰区 | 389,414 行 | 369,036 行 |
| 落在 (0,0.2) 小数典型区间 | 252 行 | ~0（153,998 行为 0） |

样例行：`25青岛城投SCP005` coupon=1.82、ytm=1.82；`26永泰城建SCP001` coupon=1.61（只能解释为 1.82% / 1.61%）。

**裁决结论：落库单位为百分数。**

- `docs/data_contracts.md:136` 声明"统一为小数口径"——**与数据矛盾，文档错误**。
- `adb_rate_normalize.RATE_INPUT_OVERRIDES` 的 percent 声明（无条件 ÷100）与数据一致，**正确**。
- `rate_units.normalize_annual_rate_to_decimal` 的 `>2 才 ÷100` 启发式：**[0.2,2) 灰区约 39 万行（占非空 ytm 的 28%、非空 coupon 的 21%）会被误当小数放行**（如 1.82 → 按 182% 参与计算），凡直接以该启发式消费此表利率字段的路径（campisi / bond_four_effects / credit_spread_analysis 等）对灰区券存在 100 倍量级风险。
- 附带发现脏数据：ytm 最大值 20720.9302（698 行 ≥20）、最小值 -0.0089、coupon 最小值 -0.75，修复时应一并设防。

### 取证 2：514/517 VAT 时间窗——窗口截止是已文档化的业务决定（H-3 定性修正）

`fact_formal_pnl_fi`：report_date 范围 2025-01-31 ~ 2026-06-30，共 18 个月末报告日，2026-07 尚未物化。进一步核查发现 `docs/pnl/pnl-by-business-2026h1-vat-backfill-runbook.md` 明确规定"**2025 年及 2026-07-01 之后不应用本次回溯规则**"，且 `tests/test_pnl_phase2_start_pack.py::test_phase2_fi_vat_policy_is_limited_to_2026_h1` 已将"2026-07-31 不剔税"冻结为预期行为。

**修正结论：PnL H-3 从"静默失效的时间炸弹"降级为"已裁决口径 + 一项数据治理残余风险"。** 无需代码修复。残余风险：若 7 月源文件实际仍为含税格式（上游未按约定切换），代码无法检测——应在 2026-07-31 首次物化后人工核对一次 514 金额量级（与 6 月同资产对比是否突增约 6%）。

## 跨领域根因（修复优先级最高）

1. **利率单位无单一权威口径**（共享 H-1、余额 H-1/M-5、固收 H-1、PnL M-2）：取证已裁决为百分数；需修文档、统一归一路径为按字段显式声明单位、消灭启发式灰区。
2. **三颗时间炸弹**：514/517 VAT 窗口已过期（PnL H-3，先加越界 fail-loud 守卫）；CFETS 假日表仅 2 个假日（共享 H-3，下一个未登记假日会让正式 FX 物化断裂）；QDB 7 张 sheet 硬编码 `startswith("2026")`（余额 M-8，2027-01 静默消失）。
3. **前视偏差两处**：门控择时/波动率目标曲线同日敞口吃同日收益（宏观 H-1）；FX 分析兜底 30 天外可取未来汇率（共享 H-2）。
4. **同名指标多义与双实现分叉**：KRD 一名三义（固收 H-2）、DV01 面值/市值双口径（固收 M-2）、HHI 双量纲（固收 M-5）、Campisi 包/单体单位相反（余额 M-3）、carry 天数含头含尾不一致（PnL M-5）、舍入模式 HALF_UP/HALF_EVEN 全库混用（共享 M-1、PnL L-1）。

## 各域 High 发现清单

### PnL 与业绩归因（3 High）
- **H-1** `yield_by_period.py:107-164`：季度/年度桶分母为"k 个月末余额之和"而年化因子按日历天数，年化收益率被系统性低估约 k 倍；quarterly/yearly 零测试覆盖。
- **H-2** `bond_four_effects.py:143-148`：全价基准 total_return 漏计期内票息现金流，跨付息日窗口的选券效应被系统性打负。
- **H-3** `pnl.py:44-45`：514/517 VAT 剔税与累计归一规则硬性截止 2026-06-30，过期后静默恢复不剔税口径，无任何告警。

### 固收与风险引擎（2 High）
- **H-1** `credit_spread_analysis.py:192-196`：`_normalize_ytm_to_pct` 的 `<1 则 ×100` 启发式是前审已修盲区的漏网点，正式信用利差页路径。
- **H-2** `bond_analytics/read_models.py`：~~线上 KRD 页 `krd` 字段实为桶内平均修正久期~~ → **已修（披露型改名）**：权威字段 `avg_modified_duration`，`krd` 为弃用别名；算法未改。真 KRD 贡献仍见 `krd.py`，ΣDV01 仍见 `risk_tensor`。

### 余额与会计口径（2 High）
- **H-1** `balance_analysis_workbook.py:44-53,1223-1230,1594`：利率单位三重矛盾（桶边界按百分数刻度、Campisi 冻结小数口径、spread_bp 少 100 倍），两套测试冻结相反假设。取证已裁决落库为百分数，可据此统一。
- **H-2** `balance_analysis_workbook_service.py:50-113`：主表按原币混币种直接相加，payload 却回显 CNY 口径标签，仅 currency_split 一张表使用折算行。

### 宏观与策略信号（1 High）
- **H-1** `vol_target_overlay.py:101-114`、`portfolio_backtest.py:768-780`：gate 敞口按同日 key 应用于同日收益（T 日收盘决定的敞口吃 T-1→T 收益），系统性美化择时基准；同仓库 `equity_strategies.py` 已实现正确的滞后口径。

### 共享计算基础设施（3 High）
- **H-1** `adb_rate_normalize.py` vs `rate_units.py` vs `docs/data_contracts.md:136`：同名利率字段单位声明三处矛盾（已由取证 1 裁决）。
- **H-2** `fx_rates.py:83-87`：分析口径 30 天窗口外兜底取 `valid[-1]` 未过滤未来日期，历史回放存在前视偏差。
- **H-3** `fx_calendar.py:12-15`：CFETS 假日表硬编码仅 2 个假日，缺 2026 其余全部假日与 2027+ 年历；被三条正式 FX 链路作为准入门槛，未登记假日会导致正式物化任务断裂。

## Medium 发现摘要（按域）

- **PnL**：FX 折算效应用面值 vs 全价市值两处口径不一致（M-1）；(0.2,2] 灰区利率启发式盲区（M-2，已由取证证实）；years_to_maturity 的 `or` 把 0 与缺失混淆回退 3Y（M-3）；量价归因规模可能重复计数且总计行无 recon（M-4）；carry 天数含头含尾不一致（M-5）；配置效应板块收益漏 spread/fx 分量（M-6）；rolldown 文档与实现口径相反（M-7）。
- **固收**：krd.py 短端持仓被丢桶、平行情景短端零冲击（M-1，未接线）；面值 DV01 与市值情景 PnL 双口径并存（M-2）；一遍式 bootstrap 长端 ~3.9bp 方法偏差（M-3，未接线）；闭式久期银行家舍入吞碎期、与 common.py 分叉（M-4）；var_engine/risk_metrics 未接线未测、HHI 双量纲（M-5）；利差基准按桶锚点年限取值错配 ±25bp（M-6）；付息频率默认值双路径不一致（M-7）。
- **余额**：GL 逐科目滚动闭合无校验（M-1）；两处"对账"实为同源自恒等（M-2）；balance_workbook 包与单体双实现分叉、包版缺 full_rows 修复（M-3）；reconciliation_checks 全 float 且缺键当 0（M-4）；利率归一三方口径并存（M-5，已由取证裁决）；到期日缺失三种口径均静默（M-6）；FX 长假回看仅 3 天（M-7）；QDB 2026 硬编码（M-8）。
- **宏观**：领先指标缺失月被 0 污染均值（M-1）；路径回测单日复权因子缺失整条回退 raw 价（M-2）；信贷脉冲输入校验整体拒绝致宏观分项静默消失（M-3）；回测入场敞口/entry_date 回退轻度前视（M-4）；matched baseline 剔除退市控制样本（M-5）；流动性下限只标记不过滤、脚本与服务口径不一致（M-6）。
- **共享**：quantize 舍入 HALF_UP/HALF_EVEN 全库约各半混用（M-1）；interest_mode 缺 monthly 分支、fallback 标志被丢弃（M-2）；balance_workbook 自建 Decimal 助手 NaN 可静默传播（M-3）；分析端大量绕过 rate_units 用魔法数字换算（M-4）；safe_decimal/to_decimal 对 `Decimal('NaN')` 不设防（M-5）；hat_mapping rationale 与实现漂移（M-6）。

（Low 级发现与逐项证据、修复方向、测试缺口清单见各子审计报告原文，本文件为汇总索引。）

## 修复计划（已确认授权：先修跨领域根因）

| 顺序 | 项目 | 动作 | 状态（截至 2026-07-20） |
|---|---|---|---|
| 1 | 514 VAT 越界守卫 | ~~fail-loud 守卫~~ 取消：窗口截止为 runbook 文档化业务决定（见取证 2）；改为 7/31 物化后一次性人工核对 514 量级 | 已裁决无需修 |
| 2 | 利率单位统一 | 新增 `rate_units.normalize_percent_rate_to_decimal`；engine/`cashflow_projection` 消费 zqtz 利率字段改显式 percent（÷100）；`project_bond_cashflows` 增加 `coupon_rate_unit` 声明（risk_tensor 传 decimal）；`credit_spread_analysis._normalize_ytm_to_pct` 改显式小数×100+脏数据防护；修正 `docs/data_contracts.md` 错误声明；测试 fixture 全部改百分数并新增灰区回归 | ✅ 已修，测试通过 |
| 3 | CFETS 假日表 | 补齐 2024-2026 CNY 法定假日（国办发明电〔2025〕7号等）与 USD 联邦假日；加"覆盖年份之外的工作日 fail-loud"守卫；`fx_rates` 正式 carry-forward 从固定 3 天回看改为"上一营业日"语义（覆盖春节 9 天长假，同修余额 M-7） | ✅ 已修，测试通过 |
| 4 | QDB 2026 硬编码 | 7 处 `startswith("2026")` 改为 `SEGMENT_SHEETS_MIN_REPORT_MONTH = "202601"` 下界比较，2027+ 不再静默消失；新增回归测试 | ✅ 已修，测试通过 |
| 5 | 前视偏差 | `fx_rates` 分析兜底过滤未来日期（无前值 fail-loud）；`vol_target_overlay` / `portfolio_backtest.build_benchmark_comparison` gate 敞口改 T+1 生效（与 equity_strategies 口径一致）；新增回归测试并更新受影响断言 | ✅ 已修，测试通过 |
| 6 | PnL H-1 季/年分母 | `yield_by_period`：跨日桶分母改为各 `report_date` 组合规模均值（P1-05 方案 A）；写入 `docs/calc_rules.md`；补 quarterly/yearly 数值测试 | ✅ 已修，测试通过 |
| 7 | PnL H-2 跨付息日票息 | `bond_four_effects` 全价路径补 `coupon_cash ≈ income − ΔAI`；跨付息日不再把选券打负 | ✅ 已修，测试通过 |
| 8 | 固收 H-2 KRD 一名三义 | 读模型主字段改为 `avg_modified_duration`（桶内平均修正久期）；`krd` 保留一版弃用别名；曲线风险页标签同步更正；算法不变 | ✅ 已修（披露型改名） |
| 9 | 余额 H-2 workbook 币种 | `_build_balance_workbook_payload` 主表/全量行改按请求 `currency_basis` 取数（方案 A）；currency_split 仍用 CNY 折算行；更新 cross-scope 与 service 假 repo 断言 | ✅ 已修，测试通过 |
| 10 | PnL M-3 years 回退 | `campisi_decision_grade`：`None` 才回退 3Y，`0` 保留；缺失时写 `years_to_maturity_missing_fallback_3y` diagnostics | ✅ 已修（含披露） |
| 11 | 共享 M-5 / M-2 | `safe_decimal`/`decimal_utils` 非有限值 → default；`interest_mode` 已含 monthly + fallback 告警 | ✅ 已核实通过 |
| 12 | 宏观 M-1 / M-3 | 领先指标缺失月跳过均值并披露样本数；信贷脉冲整序列拒绝打 warning | ✅ 已核实 + 补测 |
| 13 | PnL/固收 M-5 carry 天数 | `read_models.summarize_return_decomposition` carry 改为 exclusive `(end-start).days`（下限 1），与 campisi/attribution_daily 对齐 | ✅ 已修，测试通过 |
| 14 | 共享 M-3 workbook Decimal | `balance_analysis_workbook._decimal_value` 与 `balance_workbook._utils` 对 NaN/非有限值回退 0 | ✅ 已修，测试通过 |
| 15 | PnL M-1 FX 基数 | `pnl_bridge` FX 改优先脏市值原币（无市值才回退面值），与脏市值桥 / `read_models.fx_effect` 对齐；写入 `calc_rules.md` | ✅ 已修，测试通过 |
| 16 | PnL M-6 配置效应 | 板块收益补入 `fx_effect`；**故意不含 spread**（超额分解已有独立 `spread_effect`，计入会双重计数） | ✅ 已核实并收口 |
| 17 | 余额 M-4 reconciliation | `reconciliation_checks` 已用 Decimal + 缺键显式处理（非 float 静默 0） | ✅ 已核实通过 |
| 18 | PnL M-4 量价归因 | `pnl_repo` 先聚合/分类 PnL，再让 strict 与 relaxed 共享同一余额持仓唯一消费集合，规模/余额行数只按 position 计一次；后端新增 `total_recon_error`，前端直接消费权威残差 | ✅ 已修，真实数据取证 + 测试通过 |
| 19 | 共享 M-6 H/A/T rationale | 删除已下线 helper 的陈旧说明，明确 `infer_invest_type` 为唯一生产分类器；映射算法与矩阵不变 | ✅ 已修，测试通过 |
| 20 | 余额 M-3 双实现漂移 | `balance_workbook.builder` 改为公开兼容入口并完整转发权威 monolith builder（含 `*_full_rows`） | ✅ 已修，测试通过 |
| 21 | 宏观 M-2 复权因子 | 路径内缺失因子只用历史已知值前向填充；无可用前值才 raw fallback，并输出缺失/填充/回退计数 | ✅ 已修，测试通过 |
| 22 | 余额 M-6 到期日缺失 | 风险预警末尾追加中文披露，仅统计 asset/liability 四类正式事实行；明确期限缺口、组合剩余期限 proxy、加权期限与日历的既有差异化语义 | ✅ 已修（披露型），测试通过 |
| 23 | 固收 M-6 利差基准期限 | 逐券优先按实际 `years_to_maturity` 在线性国债曲线上插值；实际期限缺失/无效才回退 `tenor_bucket` | ✅ 已修，真实数据取证 + 测试通过 |
| 24 | PnL M-7 roll-down | `calc_rules` 与 bridge/read-model/daily attribution 已统一为期末曲线、期末剩余期限和“上斜为正”口径；历史审计描述保留 | ✅ 已核实关单，测试通过 |
| 25 | 固收 M-7 付息频率 | Bond Analytics 物化已显式消费 `interest_mode→coupon_frequency_per_year`；Campisi 仍按资产类别启发式取 1/2，未改默认值或历史数值 | ⚠️ 权威边界已披露，Campisi 待 owner/重算裁决 |
| 26 | 共享 M-1 舍入 | 全仓已无显式 `ROUND_HALF_EVEN`，但多处 `Decimal.quantize(...)` 未传 `rounding`，仍隐式使用默认 HALF_EVEN | ⚠️ 复核未关单，禁止误标已收敛 |

**PnL M-4 取证（2026-07-20）**：2026-06-30 的正式 PnL 表在旧连接键上有 13 个多行持仓，
仅精确键即可确认重复计入余额规模 12,458,999,460 元。计入 `BOND-` 代码归一后，
同一匹配 scope 内重复为 22,943,406,360 元；另有 strict/relaxed 跨 scope 复用同一余额
26,240,639,140 元。旧读模型规模 394,297,400,667.06659468 元，完整修复后为
345,113,355,167.06659468 元，合计纠正 49,184,045,500 元（491.840455 亿元）。
修复改为先聚合/分类 PnL，再按实际余额持仓身份跨 strict/relaxed 唯一消费；
损益合计仍为 593,434,554.50815953 元。
该改动只修分析读模型，不改写正式事实表。同期总计未解释残差
`total_recon_error = -10,610,636.66` 元现由后端权威计算并显式返回。

**余额 M-6 取证（2026-07-20）**：本地只读正式库 2026-06-30、CNY 单一口径共有
1,703 条正式事实行缺失 `maturity_date`：债券投资资产 127、发行类负债 0、
同业资产 100、同业负债 1,476。披露告警按事实行计数、不去重、不纳入
`position_scope="all"` 映射异常行，并追加在既有业务风险之后，避免改写页面首要风险。
`moss-data-catalog` MCP 本轮发现失败，以上数量改用配置指向的本地正式 DuckDB 只读查询取证。

**固收 M-6 取证（2026-07-20）**：本地只读正式库与同日国债曲线均取
2026-06-30。1,092 条信用债分析行中有 1,091 条因实际剩余期限与桶锚点不同而改变；
市值加权平均信用利差由 134.33544178 bp 调整为 134.93541530 bp，净增
0.59997352 bp，单券绝对改变量最大 35.65741550 bp。该改动只影响信用利差实时分析
读数，不改事实表、schema 或 API 字段；实际期限缺失时的旧桶口径由回归测试冻结。
本轮 `moss-metric-contracts` MCP 发现失败、`moss-lineage-evidence` 仍在加载，故改用
本地服务调用链、`calc_rules`、定向测试与正式 DuckDB 只读取证；外部契约/血缘复核仍为残余风险。

**固收 M-7 / 共享 M-1 复核（2026-07-20）**：Bond Analytics engine 已把
`interest_mode` 的权威解析结果显式传入 Macaulay 久期、修正久期和凸性；四/六效应
也会把调用方显式频率继续传给底层久期与凸性 helper，相关 88 项测试通过。但 Campisi
合并行未保留 `interest_mode`，仍用资产类别启发式频率，故只披露边界、不改数值。
舍入方面，显式 `ROUND_HALF_EVEN` 虽已清零，但 `pnl.py`、`bond_duration.py`、
`var_engine.py` 等仍存在未传 `rounding` 的 `quantize`，在默认 Decimal context 下
等价于隐式 HALF_EVEN；共享 M-1 因此继续开放。

### 重要发现补充：engine 灰区回归属"潜伏 Critical"

修复 2 取证时干跑发现：当前代码（前审将阈值 >1 改为 >2 的"修复"基于错误单位假设）一旦重物化任何报告日，
每天约 550 只灰区低票息券（coupon ∈ [0.2, 2)，如 1.82%）会被当作小数 182% 写入
`fact_formal_bond_analytics_daily`，久期/DV01/凸性全错（实测 modified_duration 0.0097 vs 正确 ≈1）。
现存事实表数据由旧行为物化、数值正确；本次修复与现存数据一致，无需重物化历史。

## 事件记录：`data_input/` 于审计修复期间被清空（已恢复）

- 时间线：本地 2026-07-19 ~09:35 `tests/test_qdb_gl_monthly_analysis_core.py` 的 real_202603 测试尚能读取
  `data_input/pnl_总账对账-日均/`（44 passed）；~09:46（最终回归批次运行期间）`data_input/` 目录 mtime 更新且变为空，
  同批次内 qdb real 测试以 StopIteration 失败。
- 已排除：文件未被移入 `data/archive`（归档 mtime 为 4 月）、未移入 `tmp-governance/runtime-clean`、非符号链接、
  `cleanup-dev-artifacts.ps1` 明确保护 `data_input`、最近 3 小时其他终端命令未触及 `data_input`、
  backend 代码中无删除 `data_input` 的路径。删除来源尚未定位（怀疑回归批次 env 未隔离时误清真实目录）。
- 恢复（2026-07-19）：按 `data/governance/source_manifest.jsonl` 取最新 `completed` 行，
  从 `data/archive/{family}/files/` 按 `source_file` 原名还原到
  `data_input/`（zqtz/tyw 根目录）与 `data_input/pnl{,_514,_516,_517}/`。
  清单覆盖 1144 源、落盘缺失 0。
- 恢复后核对：`ZQTZSHOW` 546、`TYWLSHOW` 545；`pnl_总账对账-日均` 54 文件（含真实 202603，
  ~333KB/~382KB，非 basetemp 合成 fixture）；`kpi_bootstrap.json` 仍缺失（仓库内无归档副本）。
- 验证：`pytest tests/test_qdb_gl_monthly_analysis_core.py -k real_202603` → **14 passed**。
- 残留风险：删除来源未定位；`kpi_bootstrap.json` 若有业务依赖需从外部备份补回。

**余额 H-2 已按方案 A 实施（2026-07-19）**：主表/跨 scope 全量行按请求 `currency_basis` 取数；API 默认 CNY 时不再混币直加。
取证摘要：2026-06-30 资产端 native 直加相对 CNY 折算低估约 51.4 亿（1.51%）。

已裁决/已修：514 VAT（runbook）；KRD 披露型改名；workbook CNY；多项 Medium（见修复表 9–22）。

**仍开放（较低优先级 / 需谨慎）**：
- 固收 M-7：Bond Analytics 物化已走 `interest_mode→coupon_frequency_per_year`；Campisi 合并行仍不带 `interest_mode` 且按资产类别启发式取 1/2，切换前需 owner 裁决与全期回归/重算。
- 固收 M-4：闭式久期碎期分叉——若在正式物化路径则勿改数值（需重物化裁决）。
- 共享 M-1：显式 `ROUND_HALF_EVEN` 已消失，但未指定 `rounding` 的 `Decimal.quantize` 仍按默认 HALF_EVEN；需逐指标 owner 裁决后迁移，不能全仓机械替换。
- 其它 Medium（固收 M-1/M-2/M-5、余额 M-1/M-2、宏观 M-5/M-6、共享 M-4 等）仍未处理；本轮新增闭环见修复表 23–26。
