# scripts/

仓库级运维、治理、审计与研究脚本目录。逐脚本盘点与归档建议见
`docs/plans/tech-debt-remediation/C5-scripts-inventory.md`（2026-08-12 基线：顶层 147 个 .py）。

## 目录结构

| 位置 | 内容 |
| --- | --- |
| `*.py`（顶层） | 业务/运维 CLI：数据刷新（`run_*`、`refresh_*`）、回填（`backfill_*`）、诊断（`diagnose_*`、`check_*`）、修复（`repair_*`）、治理与审计（`emit_*`、`audit_*`、`system_audit_*`、`portfolio_home_*` 等） |
| `dev-*.ps1`、`codex-*.ps1` | 本地开发环境编排（dev-up/dev-down/dev-postgres-* 等） |
| `install_*_timer.ps1` | Windows 计划任务安装脚本，调用同目录 Python 刷新 CLI |
| `mcp/` | MCP 服务器与启动器（含 `moss_project_mcp.py` 单体，勿新增对它的库式 import，见下） |
| `agent_eval/`、`stitch/` | agent 评测与 Stitch 设计生成的独立子模块（各有自述文件） |

## 新脚本规范（强制）

新增任何 `*.py` 必须以 docstring 开头，且包含 `Lifecycle:` 行：

```python
"""一行说明：这个脚本做什么、影响哪个页面/数据面。

Lifecycle: permanent        # 或 one-off；one-off 必须注明触发事件与完成条件
Verify: python -m pytest tests/test_xxx.py    # 推荐：给出验证命令
"""
```

- `Lifecycle: permanent`：常驻工具（被 CI/timer/dev 编排引用，或可反复重跑的运维入口）。
- `Lifecycle: one-off`：一次性脚本（绑定单一事故/日期/迁移）。完成后应随下一次清理批次移入 `archive/`。
- 命名沿用现有前缀习惯：`run_`（编排刷新）、`backfill_`（历史回填）、`diagnose_`/`check_`/`verify_`（只读诊断校验）、`repair_`（数据修复）、`export_`（导出）。
- 多数脚本有配对测试 `tests/test_<name>.py`；新常驻脚本应配测试。

## DuckDB 访问纪律（禁止裸 `duckdb.connect`）

- **读**：一律使用 `backend/app/repositories/duckdb_repo.py::read_only_connection(path)`，不要自己 `duckdb.connect(...)`（即使加了 `read_only=True`，也绕过了统一的重试与锁语义）。
- **写**：脚本本身不得直连写 DuckDB。写路径必须委托 `backend/app/tasks/` 下的物化/刷新任务（task write scope），参考 `run_risk_tensor_materialize.py`、`run_accounting_asset_movement_refresh.py` 的封装方式。
- 存量脚本中的裸连接是已登记的技术债（见 C5 报告 §5.3），修复前不要复制其写法。

## 归档约定

- 目标目录：`scripts/archive/<主题-日期>/`（例：`scripts/archive/decimal-backfill-2026-07-31/`）。
- 触发条件：`one-off` 脚本目的达成、或所属治理流程正式收口。
- 移动必须人工批准后用 `git mv` 执行，并**同步移动/退役配套测试**（大量 `tests/test_*.py` 直接 import `scripts.*`，先 `pytest --collect-only` 验证无 import 断裂再提交）。
- 归档 ≠ 删除：archive 内脚本不再保证可运行，仅作追溯。

## 其他约定

- 顶层脚本通过 `ROOT = Path(__file__).resolve().parents[1]` + `sys.path.insert` 引仓库根；请沿用该样式。
- 不要新增对 `scripts/mcp/moss_project_mcp.py` 的库式 import（现有 19 处待收敛，见 C5 报告 §7）；需要治理预检符号时等待 `scripts/governance_records/` 引擎落地或询问维护者。
- 脚本必须进 git：计划任务（timer）引用的脚本尤其不允许游离在版本库外。

## agent 评测单入口（agent_eval/run.ps1）

- 用法：`powershell -ExecutionPolicy Bypass -File scripts/agent_eval/run.ps1 -Task scripts/agent_eval/tasks/<task>.json [-BaseRef <ref>] [-OutDir <dir>]`。
- 行为：调用 `validate_task.py --measure --require-measured`，把 `scorecard.json` / `result.json` 写入 OutDir（默认 `.codex-tmp/agent-eval/runs/<时间戳>`），结束时打印 status/score，退出码透传（0 pass / 1 fail / 2 输入或环境错误）。
- 解释器发现顺序：`uv run --project backend -- python` → `py -3.11` → 环境变量 `MOSS_PYTHON`；本机 `python` 可能被无关 venv 遮蔽，故脚本从不直接调 `python`。
