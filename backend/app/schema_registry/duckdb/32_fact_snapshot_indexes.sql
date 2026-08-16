-- MOSS:STMT
create index if not exists idx_fact_formal_pnl_fi_report_date
on fact_formal_pnl_fi (report_date)
-- MOSS:STMT
create index if not exists idx_fact_nonstd_pnl_bridge_report_date
on fact_nonstd_pnl_bridge (report_date)
-- MOSS:STMT
create index if not exists idx_fact_formal_zqtz_balance_daily_report_date
on fact_formal_zqtz_balance_daily (report_date)
-- MOSS:STMT
create index if not exists idx_fact_formal_tyw_balance_daily_report_date
on fact_formal_tyw_balance_daily (report_date)
-- MOSS:STMT
create index if not exists idx_zqtz_bond_daily_snapshot_report_date
on zqtz_bond_daily_snapshot (report_date)
-- MOSS:STMT
create index if not exists idx_tyw_interbank_daily_snapshot_report_date
on tyw_interbank_daily_snapshot (report_date)
-- MOSS:STMT
create index if not exists idx_fact_formal_risk_tensor_daily_report_date
on fact_formal_risk_tensor_daily (report_date)
-- MOSS:STMT
create index if not exists idx_fact_formal_bond_analytics_daily_report_date
on fact_formal_bond_analytics_daily (report_date)
-- MOSS:STMT
create index if not exists idx_fact_formal_yield_curve_daily_trade_date_curve_type
on fact_formal_yield_curve_daily (trade_date, curve_type)
-- MOSS:STMT
create index if not exists idx_product_category_pnl_formal_read_model_report_date_view
on product_category_pnl_formal_read_model (report_date, view)
-- MOSS:STMT
create index if not exists idx_product_category_pnl_canonical_fact_report_date
on product_category_pnl_canonical_fact (report_date)
-- MOSS:STMT
create index if not exists idx_fact_pnl_by_business_precompute_year_as_of_date
on fact_pnl_by_business_precompute (year, as_of_date)
-- MOSS:STMT
create index if not exists idx_fx_daily_mid_trade_date_base_currency
on fx_daily_mid (trade_date, base_currency)
