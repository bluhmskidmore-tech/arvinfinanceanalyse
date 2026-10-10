# 2026-07 Adjusted vs Unadjusted Return Report

- Window: 2024-09-25 to 2026-06-23
- Candidate rows updated: 5493
- Universe rows updated: 1186
- Execution rows updated: 5493
- Ex-div affected candidate rows: 672 / 5493

## Market State x Signal Kind

| market_state | signal_kind | n_raw | avg_5d_raw | win_5d_raw | n_adj | avg_5d_adj | win_5d_adj | conclusion_flipped |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| HOT | factor_screen | 330 | -2.0680% | 25.1282% | 330 | -1.7620% | 26.4103% | no |
| HOT | fresh_trend_watchlist | 440 | 1.8860% | 45.0000% | 440 | 2.5280% | 45.8333% | no |
| HOT | hybrid_fusion | 133 | 0.0884% | 37.2549% | 133 | 0.7202% | 39.2157% | no |
| HOT | stock_candidate | 341 | 2.3382% | 45.9064% | 273 | 1.9441% | 36.8421% | no |
| HOT | theme_breakout | 236 | 3.7284% | 52.8689% | 215 | 3.7287% | 49.1803% | no |
| HOT | uptrend_momentum | 660 | 3.3464% | 51.2500% | 660 | 3.6557% | 51.8056% | no |
| OFF | theme_breakout | 84 | 3.0033% | 55.9524% | 42 | 2.7642% | 29.7619% | no |
| OVERHEAT | factor_screen | 441 | -1.9181% | 21.9251% | 441 | -1.8275% | 22.6381% | no |
| OVERHEAT | fresh_trend_watchlist | 320 | 2.0562% | 41.0526% | 320 | 2.8668% | 41.8421% | no |
| OVERHEAT | stock_candidate | 193 | -0.2693% | 36.2694% | 171 | 0.3744% | 34.1969% | yes |
| OVERHEAT | theme_breakout | 131 | -1.2887% | 36.6412% | 121 | -0.9228% | 35.1145% | no |
| WARM | factor_screen | 60 | -0.4955% | 46.6667% | 60 | 0.2345% | 51.6667% | yes |
| WARM | fresh_trend_watchlist | 300 | 4.4713% | 63.0000% | 300 | 4.5737% | 63.3333% | no |
| WARM | hybrid_fusion | 60 | 3.6242% | 63.3333% | 60 | 3.9465% | 65.0000% | no |
| WARM | mean_reversion | 581 | 1.6587% | 54.6392% | 554 | 1.8354% | 52.4055% | no |
| WARM | stock_candidate | 275 | 2.4850% | 43.6364% | 237 | 3.2281% | 39.2727% | no |
| WARM | theme_breakout | 88 | 1.7023% | 52.2727% | 82 | 2.0390% | 51.1364% | no |
| WARM | uptrend_momentum | 450 | 3.1915% | 57.3333% | 450 | 3.2748% | 57.5556% | no |

## Notes

- Adjusted returns use close/open prices multiplied by same-date adj_factor ratio.
- Rows with missing adj_factor keep adjusted return columns null and carry adjustment_evidence.
