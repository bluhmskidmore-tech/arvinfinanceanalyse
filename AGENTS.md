# AGENTS.md

## Mission and scope

Priority order:
1. business metric correctness
2. completion of the requested page/workflow behavior
3. traceability and validation
4. minimal, reviewable changes

- Work on the smallest page or workflow scope that completes the request.
- Never guess an ambiguous metric definition, unit, date, or lineage; report the ambiguity with evidence.
- Platform refactors, generic infrastructure, base-layer rebuilds, framework beautification, and unrelated performance work are out of scope unless the current task proves they are the root cause.

本次用户要求决定交付范围。本文件及路径下的 `AGENTS.md` 规定默认开发流程；页面 README、历史交接记录和工具说明不能把局部修复自动扩大为整页验收或正式发布。明确的 CI、正式发布和数据写入要求只在任务涉及相应流程时适用。

### Minimal implementation discipline

- Before adding code, inspect the relevant subtree for an existing helper, contract, adapter, or established pattern; reuse it when it satisfies the verified requirement.
- Do not add an abstraction, dependency, configuration surface, or indirection unless the requested scope or demonstrated root cause requires it.
- Prefer the smallest correct change at the correct layer. “Small” never permits bypassing a metric definition, lineage, trust-boundary validation, data-loss protection, security, accessibility, or the required verification.

## Navigation and local instructions

- Before broad exploration, scan `docs/agent_codebase_map.md`, then work from the relevant subtree.
- Read the closest applicable `AGENTS.md` / `CLAUDE.md`; path-specific rules override general workflow guidance.
- Frontend verification policy lives in `frontend/AGENTS.md`; startup and local feedback commands live in `frontend/README.md`. Page READMEs describe module boundaries and relevant test entry points, rather than repeating the general workflow.
- Backend application work must follow `backend/app/AGENTS.md` and `backend/CLAUDE.md`.
- Test work must follow `tests/AGENTS.md` and `tests/CLAUDE.md`.
- Avoid broad searches through generated data, dependencies, caches, logs, build outputs, and temporary directories.
- `docs/audits/` and `docs/plans/` are a historical evidence web, not day-to-day reading. Many entries are pinned by hard-coded paths in `tests/` and `scripts/`, so they cannot be relocated. Open a specific file by name when a task needs it; do not scan these directories.
- Prefer targeted MCP/GitNexus evidence over loading whole governance documents, raw datasets, or logs into context.
- Reply and report wording follows the `## 表述方式` section of the personal Codex instructions (`~/.codex/AGENTS.md`): conclusion first, explanation in prose, bullets only for short same-kind items. The dense bullet format of this policy file keeps rules unambiguous and is not the target style for replies, reports, or written deliverables.

## 数据更新的默认执行路径

用户说“更新了输入数据”“全局更新”“刷新系统”时，先读 [数据更新中心的代理执行约定](docs/data_update_center.md#代理代办更新的执行约定)，按本次变更的明确报告日复用数据中心预检、请求和后台任务。该章节统一规定范围选择、源版本与活跃请求核对、权限、失败恢复及结果验收；不得绕过请求回执链路，历史补算按该章的授权和依赖证据判断。

## Business evidence

- Inspect only the business paths affected by the current change.
- For an affected displayed metric, verify the relevant path from API response through transformation/state to the rendered value or visualization.
- Check units, precision, null semantics, date basis, stale/fallback state, mocks, and filters only where material to the affected path.
- Use project metric-contract, lineage, catalog, and quality evidence according to the nearest path rules and demonstrated risk.
- If required evidence tooling is unavailable, identify the unavailable source, the local substitute, and the residual risk. Do not invent business meaning.

## Protected boundaries

Do not proactively modify these without explicit instruction or direct root-cause evidence:

- database schema
- authentication or permission frameworks
- queue, scheduler, or cache foundations
- global SDK wrappers
- shared infrastructure layers
- app-wide state architecture
- unrelated backend services

## File encoding

Source files are BOM-less UTF-8. PowerShell 5.1 text defaults on this machine can corrupt Chinese text.

- Never read or write a file containing CJK through PowerShell text cmdlets or shell redirection. Use Node's `fs` (Buffer-based) or a dedicated editing tool for batch text changes.
- Viewing is affected too: piping `git diff` through PowerShell renders CJK as mojibake even when the file on disk is intact. Verify file content with Node before concluding a file is damaged.
- `node scripts/audit_encoding_integrity.mjs` (part of `debt:audit`) fails on any new U+FFFD replacement character. Its baseline is empty, so corruption is caught on first occurrence.
- Do not hand-patch replacement characters. Recover the original text from git history or the authoring session; when neither holds a clean copy, report it instead of guessing.

## GitNexus

The indexed project for this working tree (`F:\MOSS-V3`) is `moss-v3-main-current-20260809`.

Do not use `moss-v3-codex-v1`: despite the name, that index points at a separate worktree
(`~/.codex/worktrees/772c/MOSS-V3`) and will return callers and risk levels for a different tree.

- Check the affected definitions and direct callers before changing behavior. For page-local code with clear callers, targeted current-source searches and relevant tests are sufficient; GitNexus is not a mandatory step for every symbol.
- Use upstream GitNexus impact analysis for shared or cross-page symbols, API contracts, formal calculation boundaries, or changes whose callers remain unclear. Reuse one analysis for related edits while its evidence remains current.
- Warn before editing when impact is HIGH or CRITICAL and choose verification for the affected callers. Risk level alone does not revoke existing authorization; stop for an unresolved scope, permission, destructive-action, or evidence boundary.
- Use process queries for unfamiliar flows and symbol context for callers/callees.
- Use semantic rename tooling for cross-file symbol renames; a local rename with verified references may use targeted editing.
- When a task uses GitNexus, run change detection before committing its code changes; documentation-only commits do not require it.
- When relying on the index, compare `.gitnexus/meta.json`'s `lastCommit` with `git rev-parse HEAD`; a mismatch means the index is stale. A match does not prove coverage of the working tree: inspect changes and untracked files on the affected paths, including changes made after indexing.
- For new or changed symbols not demonstrably covered by the index, verify current definitions and direct callers with targeted source searches and relevant tests. `Target not found`, zero callers, and a LOW result are not proof of no impact; report coverage gaps and the local evidence used.
- A stale or incomplete index may be replaced by targeted current-source evidence. Re-index with `npx gitnexus analyze --skip-agents-md` only when the affected scope cannot be established reliably that way; rebuilding the whole index is not a prerequisite for a local fix.
- Impact analysis is not required for documentation, copy, styles, or configuration edits that do not change code symbols.

Detailed GitNexus workflows live under `.claude/skills/gitnexus/`; load only the workflow needed by the task.

## Work and validation protocol

开始时简述本次要完成的行为和通过条件，随后定位、修改、相关验证、交付。新功能核对可观察结果，重构核对行为一致性。结束时先说明结果，再给出必要的原因、验证和未解决问题，细节随改动规模调整。

### 默认开发闭环

- 只执行能验证本次改动的检查。局部修复不默认追加全系统审计、全量债务检查、完整页面验收或正式发布流程；共享边界、相关失败或明确的交付要求才扩大范围。
- 用户已授权的修复和必要的可逆操作直接完成，不因任务分级、风险标签或选用工具重复询问。只有确实缺少必要信息或授权、涉及破坏性操作等边界时才暂停，并说明具体原因。
- 对未变化的代码、依赖、配置和验证环境复用已有证据；同一批稳定改动集中做一次收尾检查。新改动、失败或覆盖缺口只重跑相关检查，不重复作者、子代理和主代理已完成的验证。
- 并行仅用于可以独立推进的子项，明确文件归属，主代理检查连接处和遗漏。技能或代理的参考列表不等于必须审计所有模块。
- 范围内必需检查通过后即交付。其它模块的发现单独说明，不阻塞已经验证的局部修复；直接影响当前结果正确性、安全性或数据完整性的问题仍须解决或明确阻断。
- 普通任务的最终答复就是变更回执。不额外创建候选源码副本、专项报告、多级台账或测试/构建回执；只有实际隔离需要、既有运行工具必需输入、用户明确要求或正式交接时才生成。

### 本地生效与正式交接

用户要求修复本地页面时，完成必要的本地构建和运行更新属于该修复的闭环；复用现有启动、登记和构建保护，不另造部署流程。声称生效须核对用户实际 URL、加载的版本和受影响行为，不能只凭构建成功、health 200 或其它端口成功。

局部修复在本地入口生效，不自动触发完整首页、全站或正式发布验收。只有用户要求完整验收、正式发布或版本交接，才运行对应交接流程；按实际检查范围报告，不把局部通过说成整页通过。未授权的外部发布和业务数据写入仍需相应授权。

### 临时产物与结项清理

- 新任务的临时产物统一放在 `.codex-tmp/<任务名>/`，本地报告默认放在 `output/`；工具缓存沿用既有配置，存量运行构建和证据不因新约定自动迁移或删除。
- 同一任务复用一个明确归属的临时目录。只有验证确实需要隔离时才复制源码、数据库或创建独立依赖环境；已有隔离副本能够满足条件时继续复用，不为每次复验另建一套。
- 保留必要源码差异和验证结果，停止本任务不再使用的测试进程。可重建缓存和临时环境按需清理，不作为修复交付的前置条件；删除受工具权限限制时说明并保留，不反复尝试绕过。未解决故障的最小复现材料继续保留。
- 当前运行构建、必要回退版本、未交付改动、业务数据和唯一证据不得当作缓存删除。清理前核对运行路径、Git 跟踪和工作树归属，使用已核验的明确路径；托管工作树使用归档工具处理。
- `scripts/cleanup-dev-artifacts.ps1` 是现有通用缓存清理入口，默认只预览。历史任务目录和验收目录仍按其保护边界单独核对，不通过放宽保护规则、全盘通配删除或每次额外生成完整备份来结项。

### 验收证据与接手纪律

- 接手时核对受影响路径的当前源码和测试；涉及运行问题时再核对运行版本。保留已有改动并区分本轮修改，历史报告和相同 HEAD 不能替代当前证据。
- 行为缺陷优先用最小反例证明改前失败、改后通过；无法安全复现时说明原因和替代证据，不回退共享工作区、访问生产数据或解除隔离守卫。改前也通过的测试不能单独证明修复。
- 按风险选择相关边界用例，保留在所属测试模块；纯文案、样式和文档沿用轻量验收，不为可逆且低影响的改动新增镜像实现的测试。需要更多验收细节时再读 [验收文档 §1.1–1.3](docs/acceptance_tests.md#11-完成声明的证据)，不要求每次加载或全跑。
- 子任务汇合由主代理检查受影响的连接处。需要独立复核时，应检查反例和遗漏，不只重复作者测试；未做不能声称做过，不强制每次派子代理。
- 区分代码检查、隔离测试、真实运行、业务对账，给出相关证据与未验证范围；明确 mock、显式参数及缩小选择的边界。跳过不算通过，重叠测试不累加，无关层次可不适用。
- 新旧失败分开报告，称为原有失败须有证据；不以删断言、放宽权限、关守卫或抬基线换取全绿。有失败不笼统报全部通过；声称 CI 覆盖须核对选择器与执行记录，测试文件存在不等于已执行。
