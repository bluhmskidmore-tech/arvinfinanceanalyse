# Bond Analysis Fixed-Income Convention Decision Draft

This draft is not business-owner approval. It records the remaining convention
decisions required before `PAGE-BOND-ANALYSIS-001` can be promoted beyond
candidate status.

Page ID: `PAGE-BOND-ANALYSIS-001`
Page slug: `bond-analysis`
Decision status: `draft_pending_owner_review`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Delegated Review Workstreams

| Workstream | Assigned role | Evidence target | Read-only conclusion |
| --- | --- | --- | --- |
| Clean/dirty market value | Fixed-income convention reviewer | `market_value`, `accrued_interest`, dirty market value bridge | Current implementation treats `market_value` as clean; dirty value is computed as `market_value + accrued_interest`. |
| Accrued-interest treatment | Accrual and PnL bridge reviewer | dirty value, carry, action attribution | Accrued interest enters dirty market value; current carry/action-attribution paths do not consume accrued interest as an independent attribution driver. |
| Day-count and compounding | Duration and convexity reviewer | YTM, Macaulay duration, modified duration, convexity | Current formulas use natural days divided by `365` and nominal annual YTM divided by coupon frequency; formal scope should be fixed-rate vanilla only. |
| DV01 basis | Risk metric reviewer | DV01 formula, currency unit, base amount | Current DV01 is `face_value * modified_duration / 10000`; recommended formal unit is `CNY_per_1bp` on CNY face-value basis. |
| Evidence tooling | Tooling reviewer | `moss-*` MCP tools and `gitnexus` availability | Current Codex App session does not expose required MCP tools; local docs, schema, tests, DuckDB, and launcher handshakes are fallback evidence only. |

## Decisions To Confirm

| Decision | Current evidence summary | Recommended owner choice | Status |
| --- | --- | --- | --- |
| `market_value` clean vs dirty | Current code treats `market_value` and `accrued_interest` as separate fields; `pnl_bridge` computes dirty value as `market_value + accrued_interest`. If `market_value` were dirty, bridge would double-count accrued interest. | Recommend `market_value_basis=clean`; define `dirty_market_value = market_value + accrued_interest`. | `recommended_pending_owner` |
| Accrued-interest treatment | `accrued_interest` is CNY-preferred in bond analytics. It enters dirty market value through bridge logic, but return-decomposition carry is modelled from coupon/face/days and PnL bridge carry uses `interest_income_514`; action attribution does not pass accrued interest as an independent input. | Recommend: dirty MV includes accrued interest; carry and action attribution must be disclosed as not directly accrued-interest based unless owner requests a new attribution component. | `recommended_pending_owner` |
| Day-count convention | Current engine and tests use natural day difference divided by fixed `365`; no Actual/Actual, 30/360, leap-year, or coupon-schedule day-count branch is implemented. | Recommend `day_count=ACT/365_approximation` for current candidate/fixed-rate vanilla scope. | `recommended_pending_owner` |
| YTM / duration / convexity compounding | Current formulas treat `ytm` as nominal annual yield and divide by coupon frequency from `interest_mode`: annual=1, semi-annual=2, quarterly=4, unknown/bullet=1. Convexity is simplified from duration, not a full cash-flow second derivative. | Recommend `yield_compounding=nominal_annual_with_coupon_frequency`; scope to fixed-rate vanilla bonds, with floating/callable/amortizing/defaulted bonds excluded or downgraded. | `recommended_pending_owner` |
| DV01 unit and base | Current implementation computes `dv01 = face_value * modified_duration / 10000`; foreign bonds prefer `face_value_cny`, with native fallback if formal CNY face value is missing. | Recommend `dv01_unit=CNY_per_1bp` and `dv01_base=CNY_face_value`; market/dirty value DV01 is out of current formal scope. | `recommended_pending_owner` |
| MCP evidence availability | Required MCP servers are registered, but this Codex App session does not expose `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, or `gitnexus` as callable tools. Local `moss-*` launchers handshake; `gitnexus` local bundle is missing under `.tmp-gitnexus-v13`. | Use local docs, schema, tests, DuckDB, and launcher handshake as fallback evidence; do not treat fallback evidence as formal closure until MCP/session exposure or approved equivalent is restored. | `tooling_gap_pending_recheck` |

## Interim Technical Position

- Foreign-currency bond amount fields in bond analytics are currently disclosed
  on a `CNY` basis where formal CNY closure is available.
- Native market value remains available as `market_value_native`.
- The page and API now disclose the CNY amount basis, but this does not replace
  business-owner approval of the fixed-income conventions above.

## Owner Sign-Off Text Placeholder

Business owner must explicitly choose and sign the convention set below:

- `market_value_basis`: `clean` recommended
- `dirty_market_value_formula`: `market_value + accrued_interest` recommended
- `accrued_interest_usage`: `dirty_price` recommended; `carry` and `action_attribution` are not direct accrued-interest consumers in current implementation
- `day_count`: `ACT/365_approximation` recommended
- `yield_compounding`: `nominal_annual_with_coupon_frequency` recommended
- `duration_convexity_scope`: `vanilla_fixed_rate_only` recommended; floating/callable/amortizing/defaulted bonds should be excluded or downgraded
- `dv01_unit`: `CNY_per_1bp` recommended
- `dv01_base`: `CNY_face_value` recommended
- `mcp_evidence_status`: `fallback_local_evidence_until_mcp_recheck`

## Evidence Links

- Clean/dirty evidence:
  - `backend/app/core_finance/pnl_bridge.py`: `_dirty_market_value(row)` adds market value and accrued interest.
  - `backend/app/core_finance/bond_analytics/engine.py`: `market_value` and `accrued_interest` are selected and emitted independently.
  - `backend/app/schema_registry/duckdb/02_bond_analytics.sql`: fact table stores `market_value`, `market_value_native`, and `accrued_interest` as separate columns.
  - `tests/test_bond_analytics_engine.py` and `tests/test_bond_analytics_materialize_flow.py`: USD CNY examples assert `market_value` and `accrued_interest` remain separate.
- DV01 evidence:
  - `backend/app/core_finance/bond_analytics/engine.py`: row DV01 is `face_value * modified_duration / 10000`.
  - `backend/app/core_finance/bond_analytics/dv01.py`: totals and face-weighted duration aggregate row DV01 and face value.
  - `docs/calc_rules.md`: current rule states formal DV01 uses face-value basis.
  - `tests/test_bond_analytics_api.py`: API asserts `amount_currency_basis=CNY`.
- Accrued-interest evidence:
  - `backend/app/core_finance/bond_analytics/engine.py`: `accrued_interest_native` and `accrued_interest_cny` are selected with CNY preference.
  - `backend/app/core_finance/pnl_bridge.py`: dirty market value adds market value and accrued interest.
  - `backend/app/core_finance/bond_analytics/read_models.py`: return-decomposition carry is modelled from coupon, face value, and days rather than reading `accrued_interest`.
  - `backend/app/core_finance/action_attribution.py`: action-attribution line payload maps market value, modified duration, and classification fields; it does not pass `accrued_interest`.
- Day-count / compounding evidence:
  - `backend/app/core_finance/bond_analytics/common.py`: years are computed as remaining natural days divided by `365`.
  - `backend/app/core_finance/bond_analytics/engine.py`: years to maturity also uses natural day difference divided by `365`.
  - `backend/app/core_finance/interest_mode.py`: interest mode maps to annual, semi-annual, or quarterly frequency, with unknown fallback to annual.
  - `backend/app/core_finance/bond_analytics/common.py`: Macaulay duration uses `coupon_rate / freq` and `ytm / freq`; modified duration uses `1 + ytm / freq`; convexity uses a simplified duration-based formula.
  - `tests/test_bond_analytics_engine.py` and `tests/test_bond_duration.py`: tests assert the `/365` convention and semi-annual frequency behavior.
- MCP evidence status:
  - `docs/MCP_RUNBOOK.md`: states existing Codex sessions do not hot reload MCP registration.
  - `.codex/config.toml`: registers `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus`.
  - `tests/test_project_mcp_servers.py`: handshake tests cover local MCP launchers.
  - `scripts/mcp/moss_mcp_launcher.py`: local `metric-contracts`, `lineage-evidence`, and `data-catalog` launchers can be used for temporary handshake evidence.
  - `scripts/mcp/gitnexus_mcp_launcher.mjs`: local GitNexus depends on `.tmp-gitnexus-v13`, which is currently missing in this workspace.

## MCP Recovery Steps

1. Open a fresh Codex thread/session so MCP registration can be loaded at startup.
2. Run `codex mcp list` and confirm the four required servers are enabled.
3. Run:
   `pytest -q tests/test_project_mcp_servers.py -k "moss_codex_mcp_entries_handshake_from_declared_cwd or moss_launcher_handshake_is_cwd_independent or metric_contracts_mcp_exposes_contract_docs"`.
4. For `moss-*`, use local launcher handshake as fallback:
   - `python scripts/mcp/moss_mcp_launcher.py metric-contracts`
   - `python scripts/mcp/moss_mcp_launcher.py lineage-evidence`
   - `python scripts/mcp/moss_mcp_launcher.py data-catalog`
5. Restore `.tmp-gitnexus-v13` before relying on `gitnexus`; current launcher target is missing.
