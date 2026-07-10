-- MOSS:STMT
create unique index if not exists uq_fact_formal_pnl_fi_natural_key
on fact_formal_pnl_fi (report_date, instrument_code, portfolio_name, cost_center, accounting_basis, currency_basis)
-- MOSS:STMT
create unique index if not exists uq_fx_daily_mid_natural_key
on fx_daily_mid (trade_date, base_currency, quote_currency)
