# page-closure-evidence-2026-06 历史归档说明

## 归档性质

本目录为 **2026-06 总账 PnL / 证券投资台账页面收口证据包生成** 的历史静态快照。
目录内的所有脚本与归档测试均按归档时点原样保留，**仅作为历史审计与追溯证据，不保证可直接回放或独立运行**。

依据项目代码纪律与归档约定（见 `scripts/README.md`），禁止修改归档脚本代码。

---

## 已知失效导入清单

由于原顶层证据包脚本与配套测试在归档时移入本目录，历史测试脚本中的绝对导入无法直接解析；此外归档脚本内的 `ROOT` 计算路径已偏移：

| 文件路径 | 行号 | 失效导入语句 / 路径 | 缺失模块 / 原因 |
| --- | --- | --- | --- |
| `tests_archived/test_ledger_pnl_owner_evidence_packet.py` | 10 | `from scripts.ledger_pnl_owner_evidence_packet import build_packet` | `scripts.ledger_pnl_owner_evidence_packet`（原模块已随归档移动至本目录 `ledger_pnl_owner_evidence_packet.py`；第 14 行 `SCRIPT` 变量亦指向原 `scripts/` 顶层路径） |
| `ledger_pnl_owner_evidence_packet.py` | 9-11 | `ROOT = Path(__file__).resolve().parents[1]` | 归档后 `parents[1]` 指向 `scripts/archive` 而非仓库根目录，导致直接以脚本方式执行时其第 13、17、18、22 行导入顶层 `scripts.*` 模块失败（需在 `PYTHONPATH` 包含仓库根目录的环境下解析） |

---

## 回放与替代路径

1. **历史任务状态**：该目录归档了 2026-06 阶段总账 PnL 页面的业务负责人签字证据包生成实现。脚本归档或证据包生成不证明业务负责人已签字，也不证明页面审批已完成；实际状态须由对应审批校验和治理记录确认。
2. **现行替代路径**：
   - **页面就绪报告生成**：参考现存活跃脚本 `scripts/codex_page_readiness.py`；
   - **总账 PnL 负责人审批校验**：参考现存活跃脚本 `scripts/check_ledger_pnl_business_owner_approval.py`；
   - **治理凭证记录签发**：参考现存活跃脚本 `scripts/emit_ledger_pnl_governance_record.py`；
   - **投资组合首页收口记分卡与审批包**：参考现存活跃脚本 `scripts/portfolio_home_closure_scorecard.py` 及 `scripts/portfolio_home_business_owner_approval_packet.py`。
