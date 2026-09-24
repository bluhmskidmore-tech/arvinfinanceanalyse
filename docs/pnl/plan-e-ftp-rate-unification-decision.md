# Plan E：FTP 利率统一 — 业务确认文档

状态：**已决策：方案 A，2026-07-07**
文档性质：决策请示文档 + 落地记录；第 8 节记录方案 A 的实际落地结果
关联字征测试：`tests/test_ftp_rate_cross_page_divergence.py`（已改写为"两页一致性"断言，见第 8.2 节）

---

## 1. 需要拍板的问题

**`/pnl-by-business`（业务种类损益页）的 FTP 利率，是否改为与 `/product-category-pnl`（产品分类损益页）相同的"按报表年份查表"口径？**

当前两页 FTP 利率来源不同：一页是硬编码常量，一页是按年查表。2026 年两页数值巧合相等，但 **2025 年及更早报表日期，两页 FTP 口径实际分歧 0.15 个百分点**（1.60% vs 1.75%）。只要 DuckDB 中存在 2025 年的正式 PnL 数据，用户在两页对账时就会看到不一致的 FTP 数字。

---

## 2. 现状事实对比表

| 对比项 | `/pnl-by-business`（业务种类损益页） | `/product-category-pnl`（产品分类损益页） |
| --- | --- | --- |
| 利率来源 | 硬编码常量，两处各写一份字面量 | 按报表年份查表 `FTP_RATE_PCT_BY_REPORT_YEAR`，年份未覆盖时 fallback |
| 代码位置 1 | `backend/app/services/pnl_service.py` 第 82 行：`FTP_RATE_PCT = Decimal("1.600000")` | `backend/app/core_finance/config/product_category_mapping.py` 第 18–21 行：`FTP_RATE_PCT_BY_REPORT_YEAR = {2025: Decimal("1.75"), 2026: Decimal("1.60")}` |
| 代码位置 2 | `backend/app/tasks/pnl_by_business_precompute.py` 第 27 行：同一字面量 `FTP_RATE_PCT = Decimal("1.600000")`（与位置 1 各写一份，非同一常量引用） | 取数函数：同文件第 245–249 行 `resolve_product_category_ftp_rate_pct(report_date, fallback_rate_pct=DEFAULT_FTP_RATE_PCT)`，未覆盖年份时返回 `fallback_rate_pct`（默认 `DEFAULT_FTP_RATE_PCT = Decimal("1.75")`，第 17 行） |
| 2025 年取值 | **1.60%**（不随年份变化） | **1.75%** |
| 2026 年取值 | **1.60%** | **1.60%** |
| 两页 2026 一致原因 | — | 巧合：年表里 2026 的取值恰好等于 pnl-by-business 的硬编码值 |
| 书面口径文档 | 无 | `docs/pnl/product-category-page-truth-contract.md` 第 75 行：「Baseline FTP policy is report-year based: 2025 uses `1.75%`; 2026 uses `1.60%`.」 |
| 契约测试锁定 | 无 | `tests/test_product_category_mapping_contract.py`（见 `product-category-page-truth-contract.md` 第 326 行证据清单） |
| 是否可外部传参改变利率 | 函数入参目前固定使用模块内常量，未走可传参路径 | `resolve_product_category_ftp_rate_pct(report_date, fallback_rate_pct)` 已支持按报表日期动态解析，可直接复用 |
| 利率对应的日期计算基础 | Act/365、simple interest（`backend/app/core_finance/pnl.py` 第 172–193 行 `compute_pnl_by_business_yield_and_ftp`：`ftp_cost = avg_balance × (ftp_rate_pct/100) × calendar_days/365`） | Act/365、simple interest（`backend/app/core_finance/product_category_pnl.py` 第 12 行 `DAYS_IN_YEAR = Decimal("365")`，第 193–194 行同构公式） |

**结论**：两页的 FTP **计算公式**本身一致（同为 Act/365 简单利息），分歧完全来自**利率取值来源**：一个是不随年份变化的硬编码常量，一个是有书面口径、有测试锁定的按年查表。

---

## 3. 分歧影响面：为什么用户会看到

`/pnl-by-business` 页面可选的报表日期列表来自 `fact_formal_pnl_fi` 全表查询，**没有任何年份过滤**：

- 证据：`backend/app/repositories/pnl_repo.py` 第 83–84 行 `list_formal_fi_report_dates()` → `self._list_report_dates("fact_formal_pnl_fi")`，无 `WHERE` 年份限制。

也就是说：只要 DuckDB 正式表中存有 2025 年（或更早）的数据，业务用户在下拉框中就能选到该日期，进而在 `/pnl-by-business` 页看到基于 1.60% 计算出的 FTP 成本/FTP 净损益/FTP 净收益率——而同一报表日期在 `/product-category-pnl` 页看到的是基于 1.75% 计算的结果。

**量级示意（假设性算例，非生产数据，仅用于说明分歧的资金影响量级）**：
以规模 100 亿元、计息 30 天、利率差 0.15pp（1.75% − 1.60%）估算：

```
FTP成本差 = 100亿 × 0.15% × 30/365 ≈ 123 万元
```

即同一笔 100 亿元规模、同一 30 天区间，两页给出的 FTP 成本可以相差约 123 万元。真实影响金额取决于实际报表日期的资产规模与计息天数，需业务在具体报表日期上复核。

---

## 4. 方案对比

### 方案 A（推荐）：`/pnl-by-business` 改用年表口径

将 `pnl_service.py` 与 `pnl_by_business_precompute.py` 中的硬编码 `FTP_RATE_PCT` 常量，改为调用 `product_category_mapping.py` 中已有的 `resolve_product_category_ftp_rate_pct(report_date, fallback_rate_pct)` 按报表日期解析利率。

理由：
- 该口径已有书面文档背书（`product-category-page-truth-contract.md` 第 75 行），不是新造规则。
- 该口径已有契约测试锁定（`tests/test_product_category_mapping_contract.py`），后续改动会被测试保护。
- 函数签名已支持外部传入 `report_date` 和 `fallback_rate_pct`，`pnl-by-business` 侧只需按报表日期调用，不需要新增基础设施。
- 改造成本低：两处硬编码常量替换为一次函数调用，公式本身（Act/365 simple interest）不需要改动。

### 方案 B：`/product-category-pnl` 反向改为固定 1.60%

将年表口径废弃，统一改成 `pnl-by-business` 的硬编码 1.60%。

理由（不推荐）：
- 需要撤销已经业务确认并写入 `product-category-page-truth-contract.md` 的书面口径（"2025 uses 1.75%; 2026 uses 1.60%"），等于否定既有决策。
- 需要重新计算 2025 年及此前所有已发布的产品分类损益历史数据，影响范围更大、审计成本更高。
- 现有契约测试（`test_product_category_mapping_contract.py`）会因此失败，需要连带修改测试锁定的历史事实。

### 方案 C：维持现状分歧，仅补文档声明"两页口径不同"

不改代码，只在两页文档中各自注明 FTP 利率口径不同，供对账时查阅。

理由（成本最低，但不推荐作为最终方案）：
- 实施成本最低，无需回归测试或历史数值变更。
- 但用户在两页对账时依然会看到 FTP 数字对不上，需要客服/业务反复口头解释口径差异，长期沟通成本高于一次性统一的成本。
- 不解决"同一报表日期两个数字"的根本问题，只是把分歧原因写进文档。

---

## 5. 选择方案 A 的影响（需业务明确知晓）

若采纳方案 A：

- **2025 年及更早报表日期**，`/pnl-by-business` 页面上历史展示的 **FTP 成本、FTP 净损益、FTP 净收益率** 数值会发生变化：隐含利率从 1.60% 上调到 1.75%，意味着扣除 FTP 后的净损益会比现在展示的历史数值**更小**（FTP 成本更高）。
- **2026 年及以后**（在年表覆盖范围内）数值不受影响，因为两页取值本就相等（均为 1.60%）。
- 这是"对历史展示口径的一次性修正"，不是"新增未来数据"。业务需要明确：这是**期望的口径修正**，而不是**破坏历史可比性的意外变动**。如果业务此前已经基于 `/pnl-by-business` 当前展示的 2025 年历史数值做过汇报、留档或对外披露，需要评估口径切换后的重新披露成本。

---

## 6. 待确认清单

请业务 owner 逐项勾选确认：

- [ ] ① 选择方案：□ 方案 A（推荐，统一为年表口径） / □ 方案 B（反向统一为固定 1.60%） / □ 方案 C（维持分歧，仅补文档）
- [ ] ② 若选方案 A：2025 年及更早报表日期在 `/pnl-by-business` 页面的历史数值变化（FTP 成本上升、FTP 后净损益下降）是否接受，作为一次性口径修正？
- [ ] ③ `settings.ftp_rate_pct`（配置项，默认 `1.75`，可用环境变量 `MOSS_FTP_RATE_PCT` 覆盖，定义于 `backend/app/governance/settings.py` 第 132 行）的语义定位是否明确为**"年表未覆盖年份时的默认兜底利率"**？（该配置当前同时被三条链路以不同语义消费，见附录 7.3）
- [ ] ④ 2027 年及以后年度的 FTP 利率，由谁负责、在什么时间点维护进 `FTP_RATE_PCT_BY_REPORT_YEAR` 年表？（避免年表覆盖不到期时，被动依赖 `settings.ftp_rate_pct` 兜底值）

---

## 7. 附录

### 7.1 证据文件清单（文件路径 + 行号，均为本文档撰写时逐一打开源码核实）

| 文件 | 行号 | 内容 |
| --- | --- | --- |
| `backend/app/services/pnl_service.py` | 82 | `FTP_RATE_PCT = Decimal("1.600000")` |
| `backend/app/tasks/pnl_by_business_precompute.py` | 27 | `FTP_RATE_PCT = Decimal("1.600000")`（与上一行是各自独立的字面量，非共享引用） |
| `backend/app/core_finance/config/product_category_mapping.py` | 17 | `DEFAULT_FTP_RATE_PCT = Decimal("1.75")` |
| `backend/app/core_finance/config/product_category_mapping.py` | 18–21 | `FTP_RATE_PCT_BY_REPORT_YEAR = {2025: Decimal("1.75"), 2026: Decimal("1.60")}` |
| `backend/app/core_finance/config/product_category_mapping.py` | 245–249 | `resolve_product_category_ftp_rate_pct(report_date, fallback_rate_pct=DEFAULT_FTP_RATE_PCT) -> FTP_RATE_PCT_BY_REPORT_YEAR.get(report_date.year, fallback_rate_pct)` |
| `docs/pnl/product-category-page-truth-contract.md` | 75 | 「Baseline FTP policy is report-year based: 2025 uses `1.75%`; 2026 uses `1.60%`.」 |
| `docs/pnl/product-category-page-truth-contract.md` | 326 | 证据清单中列出 `tests/test_product_category_mapping_contract.py` |
| `backend/app/repositories/pnl_repo.py` | 83–84 | `list_formal_fi_report_dates()` 对 `fact_formal_pnl_fi` 全表取日期，无年份过滤 |
| `backend/app/core_finance/pnl.py` | 172–193 | `compute_pnl_by_business_yield_and_ftp`：Act/365 simple interest 公式，`ftp_cost = avg_balance × (ftp_rate_pct/100) × calendar_days/365` |
| `backend/app/core_finance/product_category_pnl.py` | 12, 193–194 | `DAYS_IN_YEAR = Decimal("365")`；同构 Act/365 simple interest 公式 |
| `backend/app/services/executive_service.py` | 3088 | `_build_product_category_ytd_headline` 兜底路径中 `float(settings.ftp_rate_pct)`（首页 YTD headline 兜底重算入参，仅在读模型缺行时触发） |
| `backend/app/services/pnl_attribution_service.py` | 1254 | `carry_roll_down_envelope`：`ftp_rate_pct = float(get_settings().ftp_rate_pct)`，用于 carry-roll-down 归因计算 |
| `backend/app/governance/settings.py` | 132 | `ftp_rate_pct: Decimal = Decimal("1.75")`，`env_prefix="MOSS_"`（第 80 行），故可用环境变量 `MOSS_FTP_RATE_PCT` 覆盖默认值 |

### 7.2 字征测试说明

`tests/test_ftp_rate_cross_page_divergence.py`（已创建）当前锁定以下事实，用于在本决策落地前钉住现状、避免无意间被后续改动破坏而未察觉：

- `test_pnl_by_business_ftp_rate_constants_match_and_are_one_point_six`：确认 `pnl_service.FTP_RATE_PCT` 与 `pnl_by_business_precompute.FTP_RATE_PCT` 两处硬编码字面量数值相等，且均为 `1.600000`。
- `test_product_category_2026_ftp_rate_matches_pnl_by_business`：确认 2026 年年表利率（1.60%）与 `pnl-by-business` 常量数值相等（巧合一致）。
- `test_product_category_2025_ftp_rate_diverges_from_pnl_by_business`：确认 2025 年年表利率（1.75%）与 `pnl-by-business` 常量（1.60%）不相等，即口径分歧的断言。

若本决策采纳方案 A 并落地实现后，`test_pnl_by_business_ftp_rate_constants_match_and_are_one_point_six`（硬编码常量测试）与 `test_product_category_2025_ftp_rate_diverges_from_pnl_by_business`（分歧断言）预期会失败——这是**预期中的失败**，代表分歧已被修复，需要同步更新或移除该测试文件，并在本文档标注决策已落地。

### 7.3 `settings.ftp_rate_pct` 的三条消费链路（附带问题，非本次决策主问题）

`backend/app/governance/settings.py` 第 132 行定义的 `ftp_rate_pct`（默认 `1.75`，环境变量 `MOSS_FTP_RATE_PCT` 可覆盖），当前被以下三条链路以不同语义消费：

1. `product_category_mapping.resolve_product_category_ftp_rate_pct` 的 `fallback_rate_pct` 默认值链路——用作**年表未覆盖年份时的兜底利率**。
2. `backend/app/services/executive_service.py` 第 3088 行——首页 YTD headline 在读模型缺行、需要自 canonical 重算时的兜底入参。
3. `backend/app/services/pnl_attribution_service.py` 第 1254 行——carry-roll-down 归因计算的当前利率输入，与"报表年份"无关，是归因模型的固定参数。

这三处目前共享同一个配置值，但业务语义并不完全相同（"年表兜底" vs "首页兜底重算" vs "归因模型参数"）。待确认清单第③项即针对此问题，建议业务明确后续是否需要拆分配置项，但拆分本身不在本决策范围内，需另行立项评估。

---

## 8. 落地记录（方案 A，2026-07-07）

### 8.1 三年利率口径（年表，两页共用）

| 报表年份 | FTP 利率 |
| --- | --- |
| 2024 | 2.00% |
| 2025 | 1.75% |
| 2026 | 1.60% |

年表定义于 `backend/app/core_finance/config/product_category_mapping.py` 的 `FTP_RATE_PCT_BY_REPORT_YEAR`；`/pnl-by-business` 与 `/product-category-pnl` 均通过 `resolve_product_category_ftp_rate_pct(report_date, fallback_rate_pct)` 解析同一份年表，不再各自维护字面量。`/pnl-by-business` 侧统一以 `date(year, 12, 31)` 作为解析用的报表日期（因为该页请求参数是 `year` 而非任意 `report_date`），`fallback_rate_pct` 取 `settings.ftp_rate_pct`（年表未覆盖年份时的兜底值）。

### 8.2 代码改动摘要

- `backend/app/services/pnl_service.py`、`backend/app/tasks/pnl_by_business_precompute.py`：删除硬编码 `FTP_RATE_PCT = Decimal("1.600000")` 常量；改为在每条调用链顶层解析一次 `resolve_product_category_ftp_rate_pct(date(year, 12, 31), fallback)`，逐层以参数形式向下传递，不在循环体内重复解析。
- `tests/test_ftp_rate_cross_page_divergence.py`：已从"钉住分歧现状"改写为"钉住两页一致性"，覆盖 2024/2025/2026 三个报表年份。

### 8.3 `rule_version` 失效机制

`backend/app/repositories/pnl_repo.py` 中 `fetch_pnl_by_business_precompute` 新增 `expected_rule_version` 参数，与物化行中存储的 `rule_version` 列比对；不一致则返回 `None`，调用方（`pnl_service._fetch_pnl_by_business_precompute`）据此自动回退到 live 计算，不会返回按旧利率计算的物化结果。

`PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION` 已从 `rv_pnl_by_business_precompute_v1` 升级为 `rv_pnl_by_business_precompute_v2`，并从 `pnl_by_business_precompute.py`（写入方）迁移到 `pnl_repo.py`（读写两方共同依赖的仓储层），避免 `pnl_service`（services 层）反向 import `tasks` 层。部署后：数据库中历史写入的 `rule_version = v1` 的物化行会被判定为过期，读路径自动 live 重算并返回按新年表利率计算的结果；下一次定时物化任务运行后，会以 `v2` 重新写入物化表，之后读路径恢复走缓存。
