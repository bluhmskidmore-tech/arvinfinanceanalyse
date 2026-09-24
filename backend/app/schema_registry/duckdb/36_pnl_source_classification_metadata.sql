-- MOSS:STMT
alter table fact_formal_pnl_fi add column if not exists instrument_name varchar
-- MOSS:STMT
alter table fact_formal_pnl_fi add column if not exists asset_class varchar
