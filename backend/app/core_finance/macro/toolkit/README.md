# Macro Toolkit

This package collects the standalone scripts migrated from:

`C:\Users\arvin\Desktop\02_项目代码与工具\macro_toolkit\scripts`

The scripts are kept isolated from the existing business metric calculators in
`app.core_finance.macro`. Use `iter_toolkit_scripts()` to list available
workflows and `run_toolkit_script(name)` to execute one with the legacy
`paths.py` import behavior preserved.

Default data source is aligned with the system: Choice rows from
`fact_choice_macro_daily` / `choice_market_snapshot`, formal FX from
`fx_daily_mid`, formal yield curves from `fact_formal_yield_curve_daily`, and
Tushare rows from `std_external_macro_daily` / `vw_external_macro_daily`. The
package provides local `WindPy` and `akshare` compatibility modules so migrated
scripts resolve those legacy imports to the system Choice/Tushare DuckDB data
instead of calling Wind or Akshare directly.

`w.wset("cffexmemberrank", ...)` remains explicit: the scripts and CSV output
contract exist, but no system DuckDB table currently materializes CFFEX member
rank data, so the compatibility layer returns a non-zero error instead of
pretending that empty data is valid.

Generated output defaults to `data/macro_toolkit/output`. Set
`MOSS_MACRO_TOOLKIT_OUTPUT_DIR` to override it.

Omitted source files are listed in `runner.OMITTED_SOURCE_SCRIPTS`.
