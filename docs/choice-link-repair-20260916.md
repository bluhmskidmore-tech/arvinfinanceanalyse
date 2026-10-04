Choice 原生股票取数和 Tushare 更新路径均已完成真实验证，2026-09-16 的股票与新闻数据已落地，公开汇率缺失的五个交易日也已补齐。最后验收时间为 2026-09-17 08:15 左右，数据验收日期仍为 2026-09-16。API、前端与后台任务健康检查通过，维护标记已释放。完整日更仍有选股历史资格未通过的业务阻断，不能把数据更新成功解释为全链路业务验收通过。

Choice 原生路径另在隔离数据库中完成 5,220 只股票、8 类请求的取数和入库，禁用 Tushare 补齐，并让任何 Tushare 请求直接报错；实际执行完成，数据质量检查通过，无重复键。这证明了原生股票基础数据链路，不等于所有财务因子都独立来自 Choice。主库原有更新继续沿用明确标记来源的 Choice/Tushare 补齐流程，没有用隔离验证结果覆盖主库。两份数据中共同具有收盘价的 5,206 只股票一致；另外 14 只停牌股票的空值处理不同，没有把它们解释为同口径价格比较。

最初故障有三处：供应商诊断把交易日历的整数 is_open=1 判为结构错误；选股预检和新闻抓取仍使用旧版 Tushare HTTP 入口，定时任务也没有向这两步传递有效网卡地址；本机 API 长期持有 DuckDB 读取句柄，阻挡日更写入。已修正类型校验，复用现有 HTTPS 客户端和网络绑定，并在本机调度入口接入已有维护归属机制，暂停 API 后写入，成功或失败后均恢复服务。物理网卡仍在每次运行时自动解析，未固定为本次地址。

本轮继续定位到汇率 SSL_UNEXPECTED_EOF 的具体原因：标准库 urllib 通过位置参数传入 source_address=None，旧绑定逻辑只处理关键字参数，导致 Excel 下载没有走指定网卡。两个相关网络上下文现在同时处理位置参数和关键字参数，并保留显式指定的源地址。真实汇率抓取已恢复。

汇率补写复用 refresh_public_cross_asset_headlines，新增与现有沪深 300 定向恢复一致的 fx_only 单日范围；写入前要求目标日期恰好一条有限正数，事务覆盖事实、快照和目录，新快照不会被历史日期回退。实际只补写 9 月 10、11、14、15、16 日。SAFE 原始口径为每 100 美元对应人民币，沿用既有除以 100 的转换，9 月 16 日结果为 6.7628 CNY/USD。随后将该序列的来源目录从旧的本地表说明修正为 public_currency_boc_safe，并通过同一单日入口更新当日目录回执。

| 核对项 | 2026-09-16 结果 |
| --- | --- |
| Choice 原生隔离验证 | 5,220 只，8 类请求，完成，无 Tushare 补齐 |
| 主库股票日行情 | 5,220 行，5,220 只，无重复 |
| 股票池、行业、涨跌停质量、因子快照 | 每表 5,220 行 |
| 需要复权的正价格股票 | 5,206 只，复权因子覆盖 5,206 只 |
| 数值涨跌停价 | 5,220 行 |
| 主题覆盖 | 4,776 条成员关系，任务完成 |
| 当日候选记录 | 146 条 |
| 新闻补抓 | 抓取 1,195 条，新增 1,185 条，10 条去重 |
| 汇率恢复 | 五个日期补齐，最新 6.7628 CNY/USD |
| 汇率日期、来源、单位接口核对 | 全部通过，quality_flag=ok |
| 本轮未涉及的数据 | 股票全表、其他宏观序列、补写范围外汇率的行数和内容哈希均不变 |
| 服务检查 | API health/ready、后台任务 smoke、前端均通过 |

接口 /ui/macro/choice-series/latest 已返回上述日期、数值、单位及实际公开源。前端跨资产指标模型选择 EMM00058124，并以四位小数展示汇率，未增加前端换算。股票工作台此前已核对当日数据、stale=false 和 fallback_date=null。本轮没有改动前端代码或切换现有已验收构建；浏览器视觉界面未重测，页面数据核对采用实际读取接口及现有展示模型。所需 MCP 业务证据工具在当前会话不可用，因此使用本地任务、契约、数据库、接口和回归测试作为证据。

选股剩余阻断已核实为历史证据不足。补跑完成当日门控、候选及结果到期更新后，在 signal_confluence_replay_not_ready 停止；当次短窗口检查有 2 个阻断日期。另一个 24 个月只读缺口账本覆盖不同范围，其中当前规则可认证完成日期为 0、匹配样本为 0，而门槛为 20 日和 100 个样本，且存在历史来源和时点证据缺口。已有执行缺口修复脚本的 dry-run 返回 target_count=0，没有可用它直接修复的重复或缺失执行记录。接口仍返回 system_read_generation_missing，正式资格读取缺少发布代次。这需要完整的同版本历史认证回放与发布证据，不能靠重抓当日行情或放宽门槛解决；本次没有伪造资格记录。

原始日更回执 market-daily:2026-09-16:83e98fe32dc0 保持 business_failed，Windows 任务保留最近结果 1。后续恢复分别留存独立回执，没有覆盖原始失败记录，也没有重跑成功的整条股票摄入链路。调度入口处于 Ready，最近读取的下一次计划为 2026-09-17 18:45；真实业务资格仍可能使完整日更返回非零退出码。

本次会话改动的文件如下；这些文件中原有的其他工作区改动不属于本次修复。

- scripts/check_stock_supplier_access.py：交易日历整数 0/1 校验。
- scripts/scheduling/run_daily_data_refresh_host.ps1：启动日志、API 暂停、维护归属校验和服务恢复。
- scripts/scheduling/daily_data_refresh.ps1：向选股预检和新闻传递网卡地址。
- scripts/run_livermore_daily_pretrade_refresh.py：HTTPS 预检和网络绑定。
- scripts/refresh_tushare_news_backup.py、backend/app/tasks/choice_news.py：HTTPS 新闻抓取和同步入口的网络绑定。
- scripts/choice_stock_daily_refresh.py、scripts/macro_toolkit_freshness_refresh.py：补齐 source_address 的位置参数处理。
- backend/app/tasks/choice_macro.py：单日汇率恢复、数值校验和真实来源说明。
- tests/test_stock_supplier_access_check.py、tests/test_market_refresh_host_runtime.py、tests/test_market_vendor_routing.py：供应商校验、维护恢复和网络回归。
- tests/test_daily_data_refresh_scheduler.py、tests/test_tushare_news_ingest.py：传参及客户端回归，动态日期用例。
- tests/test_choice_stock_daily_refresh.py、tests/test_macro_toolkit_freshness_refresh.py、tests/test_choice_macro_fx_scope.py：位置参数、单日边界、单位、来源、幂等和事务回滚验证。

GitNexus 对修改的 Python 入口给出 LOW 风险，静态图遗漏的动态调用已用实际代码补查。直接影响为供应商诊断、股票与宏观网络上下文、新闻和选股日更入口，以及公共跨资产入库任务。本轮没有改变数据库结构、资格门槛、权限或正式金融计算。

本轮针对两个刷新脚本的 pytest 合计 75 项通过，汇率与既有沪深 300 单日恢复测试合计 27 项通过；初次测试暴露的无穷值校验缺口修正后通过。具体命令为：

    .venv/Scripts/python.exe -m pytest tests/test_choice_stock_daily_refresh.py tests/test_macro_toolkit_freshness_refresh.py -q
    .venv/Scripts/python.exe -m pytest tests/test_choice_macro_fx_scope.py tests/test_choice_macro_csi300_scope.py -q
    .venv/Scripts/python.exe -m ruff check scripts/choice_stock_daily_refresh.py scripts/macro_toolkit_freshness_refresh.py backend/app/tasks/choice_macro.py tests/test_choice_stock_daily_refresh.py tests/test_macro_toolkit_freshness_refresh.py tests/test_choice_macro_fx_scope.py
    node scripts/audit_encoding_integrity.mjs

Ruff 通过；编码审计扫描 4,565 个文件，新增 U+FFFD 为零。此前供应商、调度、维护、HTTPS、新闻及选股日更相关测试也已通过。真实验收包括 Choice 全市场隔离入库、五日汇率主库补写、哈希一致性和恢复后的 API 检查；没有把模拟测试当作外部供应商可用性证据。

关键回执均位于本机工作区：

- [Choice 原生全市场验证](F:/MOSS-V3/data/logs/choice_repair_20260916_native_full.json)
- [原始完整日更回执](F:/MOSS-V3/data/logs/market_daily_refresh_market-daily_2026-09-16_83e98fe32dc0.json)
- [股票摄入成功回执](F:/MOSS-V3/data/logs/choice_stock_daily_refresh_market-daily_2026-09-16_83e98fe32dc0.json)
- [新闻补跑回执](F:/MOSS-V3/data/logs/choice_repair_20260916_news.json)
- [五日汇率补写回执](F:/MOSS-V3/data/logs/choice_repair_20260916_fx_recovery.json)
- [汇率来源目录修正回执](F:/MOSS-V3/data/logs/choice_repair_20260916_fx_lineage_correction.json)
- [汇率最终数据库及接口核对](F:/MOSS-V3/data/logs/choice_repair_20260916_fx_verification_final.json)
- [汇率恢复前范围备份](F:/MOSS-V3/data/logs/choice_repair_20260916_fx_scope_before.json)
- [选股补跑回执](F:/MOSS-V3/data/logs/choice_repair_20260916_pretrade.json)
- [只读回放缺口账本](F:/MOSS-V3/data/logs/choice_repair_20260916_replay_gap_ledger.json)
- [此前股票历史一致性核对](F:/MOSS-V3/data/logs/choice_repair_20260916_data_verification.json)

修复前完整备份保留在 F:/MOSS-V3/data/backups/choice-repair-20260916/moss-before-20260916.duckdb。最后一次服务恢复已通过健康、就绪、后台任务及前端检查，maintenance=null。
