-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists rate_risk_market_value decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists rate_risk_dv01 decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists rate_risk_modified_duration decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists duration_excluded_market_value decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists duration_excluded_count integer
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists upstream_rule_version varchar
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists upstream_cache_version varchar
