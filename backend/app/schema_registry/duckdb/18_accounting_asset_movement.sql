-- MOSS:STMT
create table if not exists fact_accounting_asset_movement_monthly (
  report_date varchar,
  report_month varchar,
  currency_basis varchar,
  sort_order integer,
  basis_bucket varchar,
  previous_balance decimal(24, 8),
  current_balance decimal(24, 8),
  balance_change decimal(24, 8),
  change_pct decimal(24, 8),
  contribution_pct decimal(24, 8),
  zqtz_amount decimal(24, 8),
  gl_amount decimal(24, 8),
  reconciliation_diff decimal(24, 8),
  reconciliation_status varchar,
  source_version varchar,
  rule_version varchar
)
