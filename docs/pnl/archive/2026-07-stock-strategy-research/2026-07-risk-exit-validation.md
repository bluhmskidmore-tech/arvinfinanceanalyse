# 2026-07 Risk Exit Validation

- status: completed
- formula_version: rv_livermore_risk_exit_ema10_volume_obsfallback_v3
- activation_condition: R3 remains observation-only. Promote only in a later batch if avg improves by at least 0.3pp versus R2 and p10 does not deteriorate.

```json
{
  "activation_condition": "R3 remains observation-only. Promote only in a later batch if avg improves by at least 0.3pp versus R2 and p10 does not deteriorate.",
  "duckdb_path": "F:\\MOSS-V3\\data\\moss.duckdb",
  "formula_version": "rv_livermore_risk_exit_ema10_volume_obsfallback_v3",
  "rules": {
    "factor_screen": {
      "R0_T20_hold": {
        "avg": null,
        "n": 1007,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    },
    "fresh_trend_watchlist": {
      "R0_T20_hold": {
        "avg": null,
        "n": 1159,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    },
    "hybrid_fusion": {
      "R0_T20_hold": {
        "avg": null,
        "n": 212,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    },
    "mean_reversion": {
      "R0_T20_hold": {
        "avg": null,
        "n": 595,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    },
    "stock_candidate": {
      "R0_T20_hold": {
        "avg": null,
        "n": 776,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    },
    "theme_breakout": {
      "R0_T20_hold": {
        "avg": null,
        "n": 550,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    },
    "uptrend_momentum": {
      "R0_T20_hold": {
        "avg": null,
        "n": 1168,
        "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
        "win": 0.0
      }
    }
  },
  "status": "completed"
}
```
