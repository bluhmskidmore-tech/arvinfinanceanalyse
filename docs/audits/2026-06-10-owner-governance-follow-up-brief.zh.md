# 2026-06-10 MOSS Owner/Governance 跟进简报

## 用途

这份简报把 `2026-06-10-owner-governance-follow-up-packet.json` 翻译成可开会、可分派、可复核的中文跟进清单。它只用于推动 5 个开放阻塞进入对应 owner/governance 流程，不批准指标、页面、治理记录或 route certification，不捕获 business owner 签核，不授权 Ledger PnL `--write`，也不读取、不请求、不捕获 secret 值。

当前快照结论：
- `current_status=not_complete`
- Packet path: `docs/audits/2026-06-10-owner-governance-follow-up-packet.json`
- `follow_up_packet_count=5`
- `open_blocker_count=5`
- `business_contract_certified_routes=0`
- 所有 owner / closure / formal-use gate 继续 fail-closed

## 跟进顺序

| 顺序 | Blocker | 责任 owner 类型 | 必须产出的结果 | 不能做什么 |
| --- | --- | --- | --- | --- |
| 1 | `calculation-display-p1-decisions` | business owner + metric governance | 10 个剩余 P1 的权威口径裁决，并把结论写入 `docs/calc_rules.md`、page contract 或 metric dictionary 后再实现和测试。 | 不从 UI 文案、预览数据或当前测试通过结果推断正式口径。 |
| 2 | `ledger-pnl-direct-governance-record` | governance owner + Ledger PnL business owner | 明确授权写入或定位 direct record；记录必须覆盖 `PAGE-LEDGER-PNL-001`、`/api/ledger-pnl/summary`、`ledger_pnl.summary:2026-05-31:ALL`。 | 不把 dry-run 当 written record，不在未授权时运行 Ledger PnL `--write`。 |
| 3 | `owner-approval-7-pages` | page business owners + engineering QA gatekeeper | 7 个页面逐页补齐 owner name、role、decision、approval date、signature 和页面证据复核确认。 | 不用 browser smoke、测试通过或跟进包替代 owner approval。 |
| 4 | `direct-app-mcp-gitnexus-evidence` | engineering tooling owner | 新 Codex App 会话暴露 MOSS MCP / GitNexus 工具，或 tooling owner 记录工具暴露阻塞。 | 不把 local stdio MCP 成功当作 direct App-surface closure。 |
| 5 | `local-secret-hygiene` | environment owner + security owner | 环境 owner 在仓库外轮换、移除或接受本地 findings；clean-runner 或安全 owner 记录不含值的结论。 | 不读取、不粘贴、不提交 `config/.env` 或任何 credential value。 |

## 会前输入材料

| Blocker | 会前必须带入 |
| --- | --- |
| `calculation-display-p1-decisions` | `docs/audits/2026-06-10-calculation-logic-audit.md`; `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md`; `docs/calc_rules.md` |
| `ledger-pnl-direct-governance-record` | `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-snapshot.json`; `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-runbook.md`; `docs/audits/2026-06-10-owner-approval-mcp-evidence-summary.md` |
| `owner-approval-7-pages` | `docs/audits/2026-06-10-owner-review-brief.zh.md`; `docs/audits/2026-06-10-owner-decision-capture-template.zh.md`; `docs/audits/2026-06-10-owner-approval-mcp-evidence-summary.md`; `docs/audits/2026-06-10-owner-approval-fail-closed-snapshot.json` |
| `direct-app-mcp-gitnexus-evidence` | `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json`; `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md`; `.codex/config.toml`; `.mcp.json`; `docs/MCP_RUNBOOK.md` |
| `local-secret-hygiene` | `docs/audits/2026-06-10-local-secret-hygiene-snapshot.json`; `docs/audits/2026-06-10-local-secret-hygiene-runbook.md`; `test_output/security-scans/osv-report.json`; `test_output/security-scans/gitleaks-report.json` |

## 会后验证

| Blocker | 会后验证命令或证据 |
| --- | --- |
| `calculation-display-p1-decisions` | 针对每个已裁决口径运行 formatter、adapter、selector、service 或 API 测试；最后运行 `python scripts\verify_system_audit_completion_snapshot.py`。 |
| `ledger-pnl-direct-governance-record` | 先 dry-run `python scripts\emit_ledger_pnl_governance_record.py`；只有在 governance owner 明确授权后，才能按 runbook 处理写入或定位 direct record。 |
| `owner-approval-7-pages` | 运行 `python scripts\codex_page_readiness.py --all`、对应 owner approval strict checker，以及 7 个 owner approval status tests。 |
| `direct-app-mcp-gitnexus-evidence` | 在 fresh Codex App session 用 tool surface 检索 MOSS MCP / GitNexus 工具，并保留 direct App 证据或 tooling owner 阻塞记录。 |
| `local-secret-hygiene` | 运行 redacted security scan、`git check-ignore -v config/.env`、`git ls-files -- config/.env`、`git status --ignored --short -- config/.env`；不得把 secret 值写入任何输出。 |

## 非批准边界

- 本简报不批准任何计算口径、页面、治理记录、route certification 或 formal use。
- 本简报不捕获 owner 签名，不替代 `2026-06-10-owner-decision-capture-template.zh.md` 或单页 owner approval packet。
- 本简报不授权 `python scripts\emit_ledger_pnl_governance_record.py --write`。
- 本简报不读取、不请求、不捕获、不轮换、不清除、不批准任何 secret 值。
- 本简报不把 local stdio MCP evidence 升级为 direct App MCP / GitNexus evidence。
