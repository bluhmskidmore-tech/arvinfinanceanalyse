# 每日股票研究导出

`scripts/stock_research_daily.py` 导出指定交易日的完整 MOSS 已落地股票宇宙，并形成技术筛选后的观察名单。它只读 DuckDB，写入独立运行目录；不产生订单，不改 Livermore 门控或既有策略，不声称具有样本外验证支持。所有结果均为 `formal_use_allowed=false`、`rules.execution_allowed=false`。

```powershell
F:\MOSS-V3\.venv\Scripts\python.exe F:\MOSS-V3\scripts\stock_research_daily.py --as-of-date 2026-09-08 --output-dir D:\stock-research-runs\2026-09-08\run-001 --vendor-source-ip 172.16.115.248
```

日期和输出目录为必填参数。输出目录必须不存在或为空，避免失败时覆盖旧结果；示例 IP 应使用当前已验证的本机来源地址。可选参数为 `--duckdb-path` 和 `--min-amount-yuan`。后者默认 300,000,000 元，是本次研究工作参数，按目标日成交额判断，并非修改 MOSS 正式策略阈值。

脚本先读取目标日股票宇宙、行业和真实日行情，保留缺字段股票。目标日宇宙或日行情整日缺失时直接失败，不回退最新历史日期。宇宙的交易所范围依实际代码而定，不能把“完整已落地沪深宇宙”写成已经覆盖北交所的全 A 股。

行情金额和成交量复用 `choice_stock_units`：Tushare 千元、手转换成元、股；Choice 原生单位透传；未知来源单位保持空。价格使用原始收盘价乘历史复权因子，再除以目标日因子，将所有价格统一至目标日口径。MA20、MA60 分别要求完整 20、60 个市场交易日，20 日收益要求完整 21 个价格点；缺价格、缺复权或缺交易日不以更早数据或零补齐。交易日窗口由 Tushare `trade_cal` 独立核验，整个市场某日没落行情也会被识别并失败，不能靠“最后 61 个有数据日期”掩盖缺口。

技术入池要求价格高于 MA20、MA20 高于 MA60、20 日复权收益为正，且目标日成交额达到研究门槛。ST、停牌或未知非空状态、缺失数值涨停价、收盘涨停、一字价格条及所需历史不足都会记录否决原因。Choice 原生空白交易状态沿用本地既有正常交易语义，缺价格或成交额仍不能入池。符合技术条件的股票按 20 日收益、成交额和代码排序，只对前 20 只形成观察名单。

`quality.technical_data_gap_stock_count` 和 `technical_data_gap_reason_counts` 单独记录目标价、历史价、复权、数值限价、成交额单位及历史长度缺口；任一真实技术数据缺口都会使整体 `degraded` 并加入警告。每股同时保留 `technical_data_gap_reasons`。ST、正常停牌、成交额低于门槛或均线条件不成立等正常筛选否决不计作缺数，避免把“资料不足导致空榜”写成“数据齐全但全部淘汰”。

财务查询最近两个已结束季度报告期，通过 `fina_indicator_vip`、`cashflow_vip`、`income_vip` 按报告期分页读取。每页请求 `limit=2000`，`offset` 按响应原始行数推进，重复行也计入偏移；即使一页不足 2000 行，也继续请求，直到出现空页才标记本期分页完成。每个接口、每个报告期最多请求 100 页；返回超过请求上限的行数、出现相同页内容哈希或达到页数边界时，标记失败和可能截断。权限、网络或分页失败后，不用逐股补取掩盖本期整池读取不完整；只有分页正常完成后的缺口，才对技术前 20 只尝试普通接口。缺失仍为 `partial/missing`，脚本不购买积分或变更权限。

每页独立保留请求参数、原始响应、原始行数、去重后可用行数、页内容哈希和文件字节哈希，并记录 `pagination_complete`。原始重复行不从存档删除。空页只证明这次分页已结束，财务是否可用仍逐股检查实际覆盖、期间、披露日期及必要字段，不能据此宣称全池财务完整。每股按已通过公告日门槛的最新指标报告期选取；没有合格指标报告期时，以已披露现金流或利润表的最新期为准。刚到季度末而新季报尚未披露时，继续使用已披露前一期；一旦新期指标已披露，就用新期，缺表保持 partial，不跨期借用现金或利润。查询的两个期间与每股实际披露期间分别记录。

公告日必须有效且不晚于目标日；缺失 `ann_date` 不回退报告期末。现金流和利润表的 `f_ann_date` 若存在，也必须满足日期门槛。现金与利润只在相同报告期、`report_type=1` 合并最新报表口径下匹配；公司类型冲突时保持空。相同日期和业务值的重复记录合并使用，原始重复响应保留且在 manifest 计数。通过期间和时点筛选、属于同一最新公告日期组的稀疏重复，只有存在某一真实来源行能够兼容覆盖其他行的全部非空字段（包括元数据）时，才选择该行，并记录 `sparse_duplicate_reconciled`。零值是有效非空值，不拿零补缺失；真实非空值或元数据冲突仍拒绝。两行虽可互补、却没有单一来源行覆盖全部非空字段时，也不拼造合并记录。现在抓取的数据可能已修订，所有财务数据只能称当前研究快照，不能称历史回测 PIT。每次请求记录 `fetched_at`，每股保留选中公告日、实际公告日及修订标志。

收入同比使用 `or_yoy`，不混用营业总收入同比 `tr_yoy`。归母净利润同比、扣非同比、ROE 固定将百分数点除以 100；不会按数值大小猜测单位。财务金额按元；本次用天孚通信 2026 年半年报人工读数与真实接口交叉核验了经营现金流、归母净利润、扣非利润及增长率，官网字段表未逐项直接标明金额单位的局限应保留，不能说均由官网单位标签独立确认。经营现金流除以正的归母净利润得到 `ocf_to_parent_profit`，分母非正时为空。

财务分层要求收入、利润和扣非同比为正，ROE、扣非利润、经营现金流和归母净利润为正，且经营现金流/归母净利润不低于 1，才标记 `growth_cash_supported`。数据完整但不满足条件为 `growth_cash_risk`；数据不足为 `insufficient_data`。这是明确的研究条件，不是预期收益模型。估值只单独展示 PE TTM、PB；PE TTM 不可用或非正时标不可比较，达到 60 时提示研究估值风险，不计算混合口径 PEG。资金流按万元转元，只作辅助观察，不能证明主线或称为主力净流入。

目标日 MOSS 门控原样保留在 `market_gate`。OFF 不改变技术事实，但每股增加 `market_gate_OFF`，仍是纯观察。缺目标日已存门控时输出同目标日 `PENDING_DATA`、零敞口和明确缺失原因，整体为 `degraded`；不会使用旧日期门控。

| 产物 | 内容 |
| --- | --- |
| `result.json` | 完整宇宙、观察名单、门控、质量、规则和警告 |
| `manifest.json` | 请求参数、字段、抓取时间、状态、覆盖与 SHA256 |
| `raw/moss_snapshot.json.gz` | 可重算本次指标的完整股票输入快照 |
| `raw/NNN_endpoint.json` | 原始 Tushare 响应，失败也保留，凭据回显脱敏 |

`manifest.sources[].sha256` 对应文件实际字节；压缩快照的哈希针对 gzip 字节。`raw_files` 是运行目录内的相对路径清单，供 Wiki writer 复制。请求参数和产物均不得包含 token；认证复用现有 `resolve_tushare_token_with_settings_fallback`。网络来源绑定复用 `scripts.choice_stock_daily_refresh._vendor_source_network`。

结果顶层固定包含 `schema_version=1`、`target_date`、`generated_at`、`status`、`formal_use_allowed`、`universe_count`、`quality`、`market_gate`、`datasets`、`rules`、`stocks`、`shortlist`、`warnings`、`raw_files`。`status` 只有 `ready/degraded/failed`。失败退出码为 1，失败结果的股票和观察榜为空；财务权限或覆盖不足为 `degraded`，退出码仍为 0，供下游保存明确降级的研究事实。

每股字段包括 `code/name/sector/sector_code`，`close/pct_change/amount_yuan/ma20/ma60/return20`，`pe_ttm/pb/turnover_rate/volume_ratio/total_mv_yuan/circ_mv_yuan/net_mf_amount_yuan`，`report_period/ann_date/cashflow_ann_date/income_ann_date/cashflow_f_ann_date/income_f_ann_date/cashflow_update_flag/income_update_flag`，`revenue_yoy/profit_yoy/deducted_profit_yoy/roe/deducted_profit_yuan/ocf_yuan/parent_profit_yuan/ocf_to_parent_profit`，以及 `technical_pass/technical_rank/financial_coverage/financial_status/research_status/fail_reasons/notes`。收益、增长、换手及 ROE 使用比例值，金额为元，PE/PB/量比为倍数，缺失为 JSON null。`shortlist` 包含完整股票对象，先取技术前 20，再按财务分层排序，不改变 `technical_rank`。

官方接口依据：[交易日历](https://tushare.pro/document/2?doc_id=26)、[每日指标](https://tushare.pro/document/2?doc_id=32)、[资金流](https://tushare.pro/document/2?doc_id=170)、[财务指标](https://tushare.pro/document/2?doc_id=79)、[现金流量表](https://tushare.pro/document/2?doc_id=44)、[利润表](https://tushare.pro/document/2?doc_id=33)、[修订标志 FAQ](https://tushare.pro/document/1?doc_id=122)。每日指标和资金流单次上限为 6,000，普通财务指标为 100；每日指标和资金流达到已知单次上限时 manifest 标记可能截断。VIP 文档没有明示分页参数或统一上限；本实现依据 2026-09-09 的真实请求验证：三个 VIP 接口在 `limit=2`、`offset=0/2` 时均返回不同页面，现金流、利润表和指标接口在 `offset=6400/9000/10000` 时也分别返回有效财报。此为本次实测支持的 `limit/offset` 行为，不是官方文档保证；运行中仍保留分页边界防护，并检查实际股票覆盖。

离线验证命令：

```powershell
F:\MOSS-V3\.venv\Scripts\python.exe -m pytest tests/test_stock_research_daily.py -q
F:\MOSS-V3\.venv\Scripts\python.exe -m ruff check scripts/stock_research_daily.py tests/test_stock_research_daily.py
```

测试使用小型行情、财报、假 HTTP 响应和临时 DuckDB，覆盖拆股复权、短历史、整日与个股缺口、单位、公告时间、现金口径、重复数据、OFF、压缩快照复算及凭据脱敏，不读取生产或调用真实网络。
