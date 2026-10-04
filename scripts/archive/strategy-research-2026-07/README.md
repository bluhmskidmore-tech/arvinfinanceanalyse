# strategy-research-2026-07 历史归档说明

## 归档性质

本目录为 **2026-07 股票策略研究（Batch3 研究、门控状态翻转、进场溢价诊断、宏观乘数与滚动窗口阈值扫描）** 的历史静态快照。
目录内的所有脚本与归档测试均按归档时点原样保留，**仅作为历史研究与审计追溯证据，不保证可直接回放或独立运行**。

依据项目代码纪律与归档约定（见 `scripts/README.md`），禁止修改归档脚本代码。

---

## 已知失效导入清单

原策略研究脚本与配套测试归档至本目录后，测试套件与部分脚本中面向原 `scripts.*` 顶层的绝对导入无法直接解析：

| 文件路径 | 行号 | 失效导入语句 | 缺失模块 / 原因 |
| --- | --- | --- | --- |
| `tests_archived/test_gate_state_flip_diagnostic.py` | 8 | `from scripts.diagnose_gate_state_flips import (` | `scripts.diagnose_gate_state_flips`（原模块已移动至本目录 `diagnose_gate_state_flips.py`） |
| `tests_archived/test_walk_forward_threshold_scan.py` | 7 | `from scripts.walk_forward_threshold_scan import (` | `scripts.walk_forward_threshold_scan`（原模块已移动至本目录 `walk_forward_threshold_scan.py`） |
| `tests_archived/test_batch3_stock_strategy_research.py` | 6 | `import scripts.run_batch3_stock_strategy_research as batch3_research` | `scripts.run_batch3_stock_strategy_research`（原模块已移动至本目录 `run_batch3_stock_strategy_research.py`） |
| `tests_archived/test_batch3_stock_strategy_research.py` | 9 | `from scripts.run_batch3_stock_strategy_research import (` | `scripts.run_batch3_stock_strategy_research`（原模块已移动至本目录 `run_batch3_stock_strategy_research.py`） |
| `tests_archived/test_macro_multiplier_diagnostic.py` | 8 | `from scripts.diagnose_macro_multiplier import (` | `scripts.diagnose_macro_multiplier`（原模块已移动至本目录 `diagnose_macro_multiplier.py`） |
| `tests_archived/test_entry_premium_diagnostic.py` | 8 | `from scripts.diagnose_entry_premium import (` | `scripts.diagnose_entry_premium`（原模块已移动至本目录 `diagnose_entry_premium.py`） |
| `run_batch3_stock_strategy_research.py` | 19, 43 | `ROOT = Path(__file__).resolve().parents[1]` / `from scripts.run_portfolio_backtest import (` | 归档后 `parents[1]` 指向 `scripts/archive`，直接执行时若未设置 `PYTHONPATH` 包含仓库根目录，将无法解析顶层 `scripts.run_portfolio_backtest` |

---

## 回放与替代路径

1. **历史任务状态**：该目录保留 2026-07 阶段的策略探索与诊断工件。现行代码入口列于下方；代码位于 `core_finance` 不代表历史研究结论已经获得业务批准，也不证明当前引擎版本复验仍成立。
2. **现行替代路径**：
   - **滚动窗口验证（Walk Forward）**：现行活跃脚本为 `scripts/run_walk_forward_validation.py`；
   - **投资组合回测（Portfolio Backtest）**：现行活跃脚本为 `scripts/run_portfolio_backtest.py`；
   - **策略选股与风控规则核心**：见 `backend/app/core_finance/livermore_risk_exit.py`、`livermore_stock_candidates.py`、`gate_exposure_series.py`、`strategy_policy.py`、`vol_target_overlay.py`；
   - **盘前选股与执行校验**：现行活跃脚本为 `scripts/run_livermore_daily_pretrade_refresh.py` 与 `scripts/export_livermore_pretrade_check.py`。
