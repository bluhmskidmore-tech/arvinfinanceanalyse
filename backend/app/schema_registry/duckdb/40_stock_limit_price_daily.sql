-- MOSS:STMT
-- 数值涨跌停价专用表：来源 tushare.stk_limit（up_limit / down_limit / pre_close 均为
-- 元单位的数值价格），替代 choice_stock_daily_observation 表 highlimit/lowlimit
-- 标志列的语义缺口（契约 docs/data_contracts.md §4.10 "highlimit/lowlimit 覆盖缺口"
-- 段：Choice 上游是"是/否"标志而非价格，choice_native 代际无可解析数值价）。
-- 独立表，不经 choice_stock_units 两代单位换算；vendor_version 自成白名单
-- （vv_tushare_stk_limit_*，见 backend/app/tasks/stock_limit_price_ingest.py）。
-- 写路径仅 backend/app/tasks/stock_limit_price_ingest.py（API/services 只读）。
create table if not exists stock_limit_price_daily (
  trade_date varchar not null,
  stock_code varchar not null,
  up_limit double,
  down_limit double,
  pre_close double,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar,
  primary key (trade_date, stock_code)
)
