-- MOSS:STMT
create table if not exists fact_formal_bond_analytics_daily (
    report_date         varchar,
    instrument_code     varchar,
    instrument_name     varchar,
    portfolio_name      varchar,
    cost_center         varchar,
    asset_class_raw     varchar,
    asset_class_std     varchar,
    bond_type           varchar,
    issuer_name         varchar,
    industry_name       varchar,
    rating              varchar,
    accounting_class    varchar,
    accounting_rule_id  varchar,
    currency_code       varchar,
    face_value          decimal(24, 8),
    market_value_native decimal(24, 8),
    market_value        decimal(24, 8),
    amortized_cost      decimal(24, 8),
    accrued_interest    decimal(24, 8),
    coupon_rate         decimal(18, 8),
    interest_mode       varchar,
    interest_payment_frequency varchar,
    interest_rate_style varchar,
    ytm                 decimal(18, 8),
    maturity_date       date,
    next_call_date      date,
    years_to_maturity   decimal(18, 8),
    tenor_bucket        varchar,
    macaulay_duration   decimal(18, 8),
    modified_duration   decimal(18, 8),
    convexity           decimal(18, 8),
    dv01                decimal(24, 8),
    is_credit           boolean,
    spread_dv01         decimal(24, 8),
    source_version      varchar,
    rule_version        varchar,
    ingest_batch_id     varchar,
    trace_id            varchar
)
-- MOSS:STMT
alter table fact_formal_bond_analytics_daily
add column if not exists market_value_native decimal(24, 8)
-- MOSS:STMT
alter table fact_formal_bond_analytics_daily
add column if not exists interest_mode varchar
-- MOSS:STMT
alter table fact_formal_bond_analytics_daily
add column if not exists interest_payment_frequency varchar
-- MOSS:STMT
alter table fact_formal_bond_analytics_daily
add column if not exists interest_rate_style varchar
-- MOSS:STMT
alter table fact_formal_bond_analytics_daily
add column if not exists next_call_date date
