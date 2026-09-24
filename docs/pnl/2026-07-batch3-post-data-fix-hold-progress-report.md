# 2026-07 Batch 3 Post-Data-Fix Hold-Progress Report

- status: blocked
- db_path: F:\MOSS-V3\data\moss.duckdb
- priority_retest_rule: day5_underwater_exit
- priority_retest_rules: ['day5_underwater_exit', 'day3_underwater_exit', 'day3_underwater_reduce_half']
- reason: Hold-progress retest is blocked until data gates pass; current path-mode result is a research lead only.

## Research Leads

- day3_underwater_exit
- day3_underwater_reduce_half
- day5_underwater_exit

## Required Rule Gates

- fixed_20d return non-worse
- fixed_20d maxDD non-worse
- risk_0.005 return non-worse
- risk_0.005 maxDD non-worse
- p5/p10 left tail improves
- winner damage controlled
- at least two independent subsamples

## Current Blockers

- adjustment factor gaps remain in price paths
- clean adjustment subset share is below 80%
- daily_amount upstream unit remains unconfirmed
- raw liquidity thresholds still have zero passing rows

These rules remain retest leads only; none is a paper-trading rule while liquidity or adjustment blockers remain.
