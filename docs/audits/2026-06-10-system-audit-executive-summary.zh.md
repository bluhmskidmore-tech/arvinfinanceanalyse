# 2026-06-10 MOSS 系统审计执行摘要

## 一句话结论

本轮系统审计已经形成完整证据包和执行队列，并新增 owner/governance 跟进包把 5 个开放阻塞逐项路由到责任 owner、所需输入、治理输出和验证命令；但系统尚未达到业务闭环。当前仍开放：页面 owner approval、Ledger PnL 直接治理记录、10 个剩余计算/展示 P1 口径裁决、direct App MCP/GitNexus 证据、以及本地 secret hygiene。真实后端全量 browser smoke 已完成 47/47 通过，审计快照 verifier 报告 `follow_up_packet_count=5`、`follow_up_brief_blocker_count=5`、`calculation_prework_p1_count=10`，合同测试为 21 passed；这些只证明技术证据包自洽，不等于业务批准。

## 已完成的审计交付

| 交付物 | 当前作用 |
| --- | --- |
| `2026-06-10-system-wide-skills-audit.md` | 主审计报告：已关闭问题、开放问题、验证证据、残余风险。 |
| `2026-06-10-system-audit-index.md` | 本次审计文件入口。 |
| `2026-06-10-system-audit-action-register.md` | 后续执行队列，含 12 条优先级行动。 |
| `2026-06-10-system-audit-completion-checklist.md` | 审计完成度检查清单，保持 5 个 completion gate fail-closed。 |
| `2026-06-10-system-audit-completion-snapshot.json` | 机器可读完成快照：5 个开放阻塞、5 个 completion gate、`follow_up_packet_count=5`、`follow_up_brief_blocker_count=5`、`calculation_prework_p1_count=10`。 |
| `2026-06-10-owner-governance-follow-up-packet.json` | owner/governance 跟进包：路由 5 个开放阻塞，但不批准指标、页面、治理记录或 route certification。 |
| `2026-06-10-owner-governance-follow-up-brief.zh.md` | owner/governance 中文跟进简报：把 5 个开放阻塞转成可开会、可分派、可复核的责任清单。 |
| `scripts/verify_system_audit_completion_snapshot.py` / `tests/test_system_audit_*.py` | 审计包一致性 guard：当前窄测为 21 passed，并覆盖 10 个开放计算/展示 P1 的工程预备映射。 |
| `2026-06-10-calculation-logic-audit.md` | 计算/展示逻辑专项审计，记录 10 个剩余开放 P1；P1-08 已验证关闭。 |
| `2026-06-10-calculation-p1-owner-decision-matrix.md` | 10 个剩余 P1 的 owner 裁决矩阵，另记录 P1-08 关闭证据。 |
| `2026-06-10-owner-approval-mcp-evidence-summary.md` | 7 个 owner approval 待完成页面的 MCP/审批证据汇总。 |
| `business-display-coverage-report.json` | 26 个业务展示路由的覆盖映射，当前 0 route gap。 |

## 已关闭的主要技术问题

- Macro Toolkit 商品期货刷新从请求路径写入改为后台任务排队，降低 DuckDB 写边界风险。
- `react-router-dom` 依赖升级到安全版本，前端 `npm audit --audit-level=moderate` 为 0 漏洞。
- Market Data / Cross Asset / Bond Analysis / Stock Analysis 的 a11y 与 smoke gate 回归已修复。
- 浏览器 smoke 的 mock/real 数据源边界已拆清，避免用错误数据源证明错误结论。
- 真实后端全量 browser smoke 已在 `http://127.0.0.1:5888` real-mode 前端和 `http://127.0.0.1:7888` live backend 上重跑通过：47/47。
- 业务展示覆盖报告扩展到 26 个浏览器 smoke 业务路由。
- MCP 队列合约、catalog/date scope、owner approval gate 重新 fail-closed。
- PnL Attribution 缺 DuckDB 文件时返回空态 envelope，不再误触发正式 PnL storage 失败路径。

## 仍未闭合的关键门

| 门 | 当前状态 | 为什么不能签 |
| --- | --- | --- |
| 7 个页面 owner approval | 全部 `pending`；strict mode 仍失败 | 缺 owner name / role / decision / date / signature 和页面证据复核。 |
| Ledger PnL 直接治理记录 | dry-run candidate 字段齐全，但 `cache_manifest.jsonl` 没有写入记录 | dry-run 不是正式治理记录，不能证明页面/API 执行闭环。 |
| 计算/展示逻辑 P1 | 10 个 P1 开放；P1-08 已验证关闭 | 多数需要业务 owner 先裁决口径，再改规则、实现和测试。 |
| 真正 real backend 全量 smoke | 已重跑通过：47/47；结果见 `2026-06-10-real-backend-smoke-result.md` | 只关闭浏览器 smoke 门；不批准 owner、指标、页面、治理记录或 MCP/GitNexus 证据。 |
| MCP/GitNexus App 直连证据 | 本地 stdio MCP 可用，App 直连工具未暴露 | 需要新会话/工具面复核 direct App MCP 与 GitNexus evidence。 |
| 本地 secret hygiene | 2026-06-10T15:45:10+08:00 刷新：OSV 0 漏洞；redacted gitleaks 仍命中 ignored/untracked `config/.env` 两个 secret 名，未捕获 secret 值 | 需要环境 owner 轮换或确认，不能把值写入仓库。 |

## 推荐下一步顺序

1. 保持所有 owner / closure / formal-use gate fail-closed。
2. 先使用 `2026-06-10-owner-governance-follow-up-packet.json` 和 `2026-06-10-owner-governance-follow-up-brief.zh.md` 把 5 个开放阻塞交给对应 owner/governance 责任方；这些材料不授权 Ledger PnL `--write`，也不请求或捕获 secret 值。
3. 召开 10 个剩余计算/展示 P1 的 owner 裁决会，使用 `2026-06-10-calculation-p1-owner-decision-matrix.md`。
4. 对 Ledger PnL 走授权治理流程，写入或定位直接 page/API 记录，再重新跑治理验证。
5. 逐页完成 7 个 owner approval packet，Ledger PnL 放最后。
6. 工具面可用后重跑 direct App MCP / GitNexus evidence。
7. 后续若路由范围、后端目标或数据源配置变化，再按 runbook 重跑真实后端全量 browser smoke。
8. 在本地环境处理 `config/.env` secret 命中，不提交 secret 值。

## 不要误读

- `static-pass` 不是 business-contract-certified。
- dry-run governance record 不是 written record。
- mock smoke 不是 full real-backend smoke；已通过的 real-backend smoke 也不是 owner approval 或 route certification。
- 技术测试通过不是 owner approval。
- owner/governance 跟进包不是正式审批文件，也不授权 Ledger PnL `--write`。
- 本摘要不是正式审批文件。
Guard refresh: `pytest tests/test_system_audit_manifest_contract.py tests/test_system_audit_completion_snapshot_verifier.py -q` -> 21 passed; `python scripts\verify_system_audit_completion_snapshot.py` -> `follow_up_packet_count=5`, `follow_up_brief_blocker_count=5`, `calculation_prework_p1_count=10`, `errors=[]`. This is technical evidence only, not business approval.
