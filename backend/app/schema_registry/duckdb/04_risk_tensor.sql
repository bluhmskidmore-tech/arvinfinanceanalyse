-- MOSS:STMT
create table if not exists fact_formal_risk_tensor_daily (
    report_date                   varchar,
    portfolio_dv01                decimal(24, 8),
    krd_1y                        decimal(24, 8),
    krd_3y                        decimal(24, 8),
    krd_5y                        decimal(24, 8),
    krd_7y                        decimal(24, 8),
    krd_10y                       decimal(24, 8),
    krd_30y                       decimal(24, 8),
    cs01                          decimal(24, 8),
    portfolio_convexity           decimal(24, 8),
    portfolio_modified_duration   decimal(24, 8),
    issuer_concentration_hhi      decimal(24, 8),
    issuer_top5_weight            decimal(24, 8),
    asset_cashflow_30d            decimal(24, 8),
    asset_cashflow_90d            decimal(24, 8),
    liability_cashflow_30d        decimal(24, 8),
    liability_cashflow_90d        decimal(24, 8),
    liquidity_gap_30d             decimal(24, 8),
    liquidity_gap_90d             decimal(24, 8),
    liquidity_gap_30d_ratio       decimal(24, 8),
    total_market_value            decimal(24, 8),
    bond_count                    integer,
    quality_flag                  varchar,
    warnings_json                 varchar,
    source_version                varchar,
    upstream_source_version       varchar,
    liability_source_version      varchar,
    liability_rule_version        varchar,
    rule_version                  varchar,
    cache_version                 varchar,
    trace_id                      varchar
)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists asset_cashflow_30d decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists asset_cashflow_90d decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists liability_cashflow_30d decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists liability_cashflow_90d decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists liability_source_version varchar
-- MOSS:STMT
alter table fact_formal_risk_tensor_daily add column if not exists liability_rule_version varchar
