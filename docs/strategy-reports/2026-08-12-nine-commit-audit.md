# 独立复审报告:2026-08-12 九笔正式口径提交

九笔提交逐一读 diff 完毕,针对怀疑点跑了三批既有测试共 260 个,全部通过(`test_trading_status_caliber` / `test_livermore_candidate_outcome_maturity` / `test_portfolio_paths` 82 个;`test_choice_adjustment_factor_backfill` / `test_matched_baseline` / `test_livermore_theme_breakout` / policy / factor_screen / position_sizing 78 个;`test_market_data_livermore_candidate_history` / gap repair / duckdb 守卫 100 个)。生产库按纪律未触碰,存量影响用合成推演评估。以下按审计维度汇报。

---

## 维度 1:tradable / halted 语义互斥性 — 核心已核实,两处边角发现

**主结论:无语义裂缝。** `is_tradestatus_halted(v) ≡ 非空 && !tradable(v)`,由于空串被 `is_tradestatus_tradable` 判为 True,两个 helper 在**全域**(含空串/None/空白)严格互补:空串→既可交易又非停牌,复牌→两侧同判可交易,未知非空→既不可交易又判停牌(fail-closed),不存在"某处用 !tradable、另一处用 halted 而边界值分叉"的可能。`tests/test_trading_status_caliber.py` 的互补性断言与 SQL/Python 同口径断言覆盖了这一点,本地重跑通过。全部七类消费点(outcome maturity 任务、candidate history 服务、K 线锚定、`portfolio_paths` 顺延、`matched_baseline`、execution 物化、盘前导出、踩踏风险 universe)都已切到共享口径;全仓 grep 确认旧导出 `TRADING_STATUS_SQL_IN_LIST` / `is_trading_status` 及内联词表零残留(剩余命中均为注释)。服务侧 `_derive_forward_maturity` 用 `not is_tradestatus_tradable(...)` 而非 `is_tradestatus_halted`,写法不同但数学等价,无裂缝。

**发现 1【Low】K 线蜡烛窗口查询未排除 close 为 NULL 的空串占位行**
- 证据:`backend/app/repositories/market_read_repo.py:678-684`(`_fetch_stock_kline_candles`)与 `backend/app/repositories/livermore_market_read_repo.py:194-199` 只有 `tradable_status_sql_condition` + `limit N`;而同文件的**锚定日**查询特意加了 `close_value is not null`(注释明说供应商会预填全空占位行)。
- 影响:native 代际 `tradestatus=''` 且 close 为 NULL 的占位行,旧词表时代被"空串=非交易"挡掉,现在会占用 lookback 名额并输出空蜡烛,K 线窗口有效长度虚减。锚定日已保护,故只影响窗口内数据缺口日的展示。
- 建议:两处蜡烛/近 N bar 查询同样补 `close_value is not null`。

**发现 2【Low】数字/英文状态码语义静默反转**
- 证据:旧 `portfolio_paths._is_halted` 词表含 `"0"/"false"`(d2fc9313 删除,`backend/app/core_finance/portfolio_paths.py`),旧盘前导出 `_NORMAL_TRADE_STATUSES` 含 `"1"/"normal"/"trade"`(`scripts/export_livermore_pretrade_check.py`,d2fc9313 删除);新口径下 `"1"/"normal"/"trade"` 均为非空非词表 → 判停牌。`tests/test_matched_baseline.py:361` 把 seed 从 `'1'` 改成 `'Trading'` 说明作者知情。
- 影响:当前两代 vendor 落地值不含数字码,无实际影响;但若上游未来落数字状态码,会静默全停牌(卖出方向保守,但踩踏风险 universe 会整体剔空导致指标失真)。
- 建议:在 `docs/data_contracts.md` §4.10 明示数字码不在契约内,并对"未知非空值占比"加监控计数。

## 维度 2:stored_target_conflict 仲裁(b02a9bf4)— 已核,无发现

- **三元组一致性**:仲裁分支同时覆盖 date 列、raw(`livermore_candidate_outcome_maturity.py:661-664`,条件 `arbitration is not None` 强制重算)、adj(`:672-681`,**无条件**写 `updates[adjusted_column]`,新目标日因子缺失时 `_adjusted_return` 返回 None → 参数绑定落 NULL,禁止沿用旧日口径;测试 `test_outcome_maturity_arbitration_clears_stale_adjusted_return_when_new_factor_missing` 验证 `return_5d_adj is None` 且计入 `raw_matured_adjustment_missing`)。
- **因子键收集**:`_required_factor_keys` 改为无条件收集 computed 目标日(`:416-430`),仲裁分支必有新日因子可查,不会因 stored 冲突而漏取。
- **连带重算**:`ex_div_in_window` 在有仲裁时强制重算覆盖(`:723-728`),`data_status` 与重算后聚合状态同步(`:732-737`)——旧日期结论不残留。
- **留痕**:`conflict_arbitrations` 含 type/horizon/decision/reason/stored{date,raw,adj}/computed{date,close,raw,adj} 全量旧值,挂在带 `observational_only: True / formal_use_allowed: False` 的 audit 事件下,结构完整。
- **保守分支**:`arbitrate_conflicts=False` 时仅记 issue,`target_date/target_close` 保持 None,后续所有写入条件都因 `target_close is not None` 不满足而短路——真保守,测试验证行未被改动。
- **幂等**:仲裁后 date 列=computed,二跑走"stored==computed"一致分支,不重复仲裁,与提交声明的"166 单元清零、二跑幂等"一致。

## 维度 3:去重保留规则(44433b1b)— 确认不一致,1 项 Medium

**发现 3【Medium】写入侧与清理脚本的保留规则是两套口径**
- 证据:写入侧 `_execution_history_row_priority`(`backend/app/tasks/livermore_candidate_history_materialize.py:2046`)按 (已填 `*_net_adj` 收益数 ↑, candidate_rank ↓, run_id 字典序 ↑) 取最大;脚本 `scripts/dedupe_execution_history_rows.py:16` `KEEP_RULE="first_physical_row"`,`:97` 按 `rowid` 升序保留第一行。合成推演证实:两重复行 rank 相同、收益填充相同、仅 run_id 不同时,**写入侧保留 run_id 字典序最大的行(exp3c_shadow),脚本保留首物理行(先插入的 exp3b)**——选择不同的行。
- 影响评估:当前 14 个重复 key 来自同一 backfill run 的 exp3b/exp3c_shadow 变体,execution 数值只依赖 (signal_date, stock_code) 与行情,两行收益字段数值应相同,故存量清理**数值影响≈0**(仅 rank/run_id 留痕差异);且 backfill 源查询按 `candidate_rank nulls last` 排序插入(`:771`),rank 不同(1 vs 2)时两规则恰好同选 rank 1,巧合一致。真正的风险在未来:若窗口期存量再混入"旧 run 部分回补 + 新 run 完整回补"形态的重复,脚本会保留收益**不完整**的首物理行并删掉完整行,与写入侧修复后的选择分歧。
- 建议:脚本改为直接调用/复刻 `_execution_history_row_priority` 生成删除计划(维护窗口执行前改一行排序即可),`keep_rule_reason` 同步更新。

附带核过:backfill 的 `execution_row_count` 改为去重后计数(修复了旧的先计数后去重错位),daily replay 与 policy-variant 双跑幂等均有测试。无其它发现。

## 维度 4:Choice 复权因子推导(cc45a5c0)— 数学正确,1 项 Medium + 2 项 Low

**主结论:锚定数学成立。** `rel(d)=hfq/raw = k·factor_true(d)`(k 为 Choice 后复权基期常数),`scale=median(reference/rel)=1/k`,输出 `rel·scale=factor_true`;除权日无论落在锚定窗口内还是 needed 区间内,rel 与 reference 同步跳变,scale 恒定,输出因子正确(两种场景均有测试:锚定窗后除权 `test_anchored_derivation...`、reference 覆盖除权日 `test_overlap_event_pair...`)。容差拒绝(任一重叠日 `|scale_i/scale−1|>2e-3`)等价于相邻重叠日两源复权收益比偏差检验,fail-closed 整股拒写。与 `adjusted_returns.adjusted_return`((end·end_f)/(start·start_f)−1)的契约假设(hfq=raw·factor,基期常数在比值中消去)一致,混源(signal 日 tushare 因子 + forward 日 choice 因子)收益 == 纯 hfq 收益有端到端断言。写入只补缺失 cell、既有行(含 tushare 行)一律不覆盖,写前需备份/治理锁,默认 dry-run。

**发现 4【Medium】锚定无最小重叠天数门槛,单日重叠时校验退化为空**
- 证据:`backend/app/core_finance/choice_adjustment_factors.py:105-158` — `overlap_dates` 非空即走 anchored;单日重叠时 `scale_max_rel_deviation ≡ 0`、`return_consistency_pair_count = 0`,容差与收益一致性校验双双失效。`anchor_overlap_days=10` 只是取数窗口意向而非下限;`_verification_report` 不输出成功样本的 per-code `anchor_overlap_count`,单点锚定对人工审查不可见。
- 影响:既有 tushare 因子行稀少的股票(如新上市)若唯一重叠日任一源数据有误,scale 整体偏差直接乘进该股票全部推导因子,与 tushare 行交叉的 adjusted returns 系统性失真,且不会被拒绝。
- 建议:加 `min_anchor_overlap`(建议 ≥3)拒写或降级到 review;verification 报告列出 `anchor_overlap_count < N` 的 anchored 股票。

**发现 5【Low】锚定 reference 不区分来源,推导因子可自锚定级联**
- 证据:`scripts/backfill_stock_adjustment_factor_from_choice.py` `_resolve_fetch_windows` 的 factor 查询仅 `adj_factor is not null`,窗口内此前写入的 `sv_choice_adj_factor_*` 行会成为下一轮锚定基准。误差受容差约束幅度有限,但多轮链式传播无来源披露。建议 reference 查询排除本脚本前缀来源,或报告中区分锚定来源构成。

**发现 6【Low】`allow_unanchored` 写入 scale=1 相对因子,未来与 tushare 行混尺度**
- 证据:同文件 CLI `--allow-unanchored`(帮助文字已标 NOT recommended,默认关)。写入后该股票若再落 tushare 真因子行,同表同股票跨行因子比在两种尺度间失义,现有消费方不看 source_version。建议 execute 与 allow_unanchored 组合直接拒绝,或至少要求显式二次确认参数。

## 维度 5:theme v6 七篮子(fc76c755)— 等义性成立,1 项 Medium + 1 项 Low

**等义性已核**:v6 首项保留 v5 全部 10 个名称关键词、旧代码 801080 与全部行业名别名(`backend/app/core_finance/strategy_policy.py:178-196`),`parent_sector_codes` 增加 S270000 构成**超集**;由于 `_matches_theme`(`livermore_theme_breakout.py:313-325`)有行业名子串兜底("电子"),v5/v6 匹配面的实际差异仅限"sector_code=S270000 且行业名不含电子类词"的行,接近零。突破判定门槛与公式(强度阈值/集群/广度/排序)diff 证实未动,仅新增 `proxy_code` 字段与题材循环。新六个题材 key 为新值,天然不与历史混。

**发现 7【Medium】上游 theme 断代 v6,下游 hybrid_fusion 版本未动,同版本号跨代**
- 证据:`hybrid_fusion_candidates.py:68` 经 `_theme_stock_rows`(`:353-361`,setdefault 按题材 rank 去重;七个申万一级行业互斥,同股票跨题材冲突可忽略)把 theme items 并入候选池与 `consensus/burst/vcov` 评分输入;theme 覆盖面从单篮子约 33 只扩到七篮子约 1500+ 只成员,theme-only 候选直接进入融合池。而 `hybrid_fusion` 的 `FORMULA_VERSION` 仍为 `rv_hybrid_fusion_candidates_v4`(`test_strategy_policy.py` pin 确认本批未 bump)。
- 影响:同一 `rv_hybrid_fusion_candidates_v4` 标签下,2026-08-12 前后的融合行输入分布不同代;按 formula_version 聚合的回测/复盘会把两代混在一起。run 级 vendor payload 虽记录 `theme_breakout_formula_version`(`livermore_candidate_history_materialize.py:1282`),但行级不可直接判代。
- 建议:hybrid_fusion bump 一版,或在行级 evidence 中记录 theme 源版本。

**发现 8【Low】theme 行落库 evidence 缺 formula_version 治理字段**
- 证据:theme 行的 `signal_evidence`(`livermore_candidate_history_materialize.py:1452-1474`)含 theme_key/proxy_code 等但无 rv 版本;同提交批次里 factor_screen(`:1514`)/uptrend(`:1604`)/fresh_trend(`:1656`)都已补该治理字段。semiconductor 同 key 跨 v5/v6,行级只能靠"evidence 是否含 proxy_code"推断代际,是推断而非契约。建议对齐补齐。

## 维度 6:版本断代完备性 — 1 项 Medium

- execution v5:gap repair 按 formula_version 检测 stale 并优先重算(`livermore_candidate_history_materialize.py:1036-1041,1093`),修复通道存在;v5 pin 测试落位。已核。
- candidate_history outcome 侧:仲裁机制本身即存量修复通道,幂等闭环。已核。
- matched_baseline v3:**没有**按版本的 stale 检测,修复只能靠按日期段 delete-rewrite 的 backfill 人工重跑(`matched_baseline.py:169-181`)。

**发现 9【Medium】API 读取端汇总 execution / matched_baseline 存量时不看 formula_version**
- 证据:`livermore_candidate_history_repo.py:321-329`(matched_baseline 窗口读取)与 `livermore_candidate_history_service.py:1058-1093`(execution/baseline 窗口装载)、`_build_summary`(`:1693+`)及 `matched_baseline_stats_from_rows`(`matched_baseline.py:267+`)均无 formula_version 过滤、分组或披露。
- 影响:生产库重物化完成之前,v2 基线存量(128 对/190 行卖在停牌陈旧价)与 v4 execution 存量(2 个停牌 bar 入场行)继续原样进入 API 汇总统计,消费端看不到"含 stale 版本行"的任何标注。提交信息已声明修复押后到下次物化,属于已知窗口,但这正是"读存量却不看 formula_version 的消费点"。
- 建议:summary 增加按 formula_version 的行数分布(或 `stale_formula_row_count`),修复完成后可保留作为常设治理指标;matched_baseline 补一个按版本的 stale 检测入口,避免依赖人工记忆重跑。

## 其余三笔 — 已核,无发现

- **f0d1be47(rpt 样本外披露)**:纯披露,`SizingPolicy.oos_validation_status` 默认 `not_supported_by_walk_forward`,note/evidence_ref 原文透传,无计算变化。唯一附注:evidence_ref 指向 `tmp-strategy-reports/`(未入版本库目录),引用可能随清理失效,不影响计算。
- **a15e6a1a(回测披露前端)**:model 为 null 零渲染,basis_notes 与 entry_price_warning 同文案去重,无业务数值重算。已核,无发现。
- **f345cd1d(仓位提示前端)**:`raw_weight`(后端 0-1)仅格式化为百分比,oos 注记/覆盖率警示/gate 串联披露全程携带,旧响应缺块不渲染;oos 状态未知非空值映射为"状态待确认"(保守)。唯一展示取舍:tone 仅由 coverage_warning 驱动,oos 未获支持时仍 neutral(summary 已有限定词),不构成业务错误。已核,无发现。

---

## 总体结论

这批九笔提交的核心计算语义(tradable/halted 互补口径、outcome 冲突仲裁、Choice 因子锚定数学、theme 多篮子扩展、factor_screen v4 门控与流动性地板)**方向正确、实现自洽、测试覆盖扎实(260 个相关测试全绿),可以作为正式口径基线**;但需带三个条件项跟进——① 维护窗口执行清理脚本前先把保留规则与写入侧对齐(发现 3),② Choice 因子回补执行前补最小重叠天数门槛(发现 4),③ 在 matched_baseline v3 / execution v5 重物化完成之前,读取端汇总缺少 stale 版本披露这一点要么尽快补披露、要么把重物化排为高优先(发现 9);其余 Low 项(K 线占位行、数字状态码、theme 行 evidence 版本字段、hybrid_fusion 断代)可随下一批治理迭代处理。