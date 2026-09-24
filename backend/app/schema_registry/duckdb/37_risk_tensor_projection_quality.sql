-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists missing_maturity_market_value decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists missing_maturity_count integer
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists floating_rate_proxy_market_value decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists floating_rate_proxy_count integer
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists payment_frequency_fallback_market_value decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists payment_frequency_fallback_count integer
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists bullet_value_date_fallback_market_value decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists bullet_value_date_fallback_count integer
