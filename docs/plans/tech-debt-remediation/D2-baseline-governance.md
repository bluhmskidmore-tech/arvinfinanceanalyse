# D2 审计基线变更签核规则

- 生效日期：2026-08-12
- 适用范围：
  - `debt:audit`（`scripts/audit_frontend_debt.mjs` 及其基线）
  - 视觉令牌审计（`scripts/audit_visual_tokens.mjs`，基线文件 `scripts/audit_visual_tokens.baseline.json`）
  - 后续新增的任何"棘轮式"债务审计基线

## 规则

1. **基线只允许下调。** 偿还债务后运行对应的 `--update-baseline` 使基线随实际债务下降，这是唯一的常规更新路径。
2. **任何上调必须技术负责人签核**，并在提交信息中注明上调原因（哪个文件、哪项指标、为什么必须新增债务、偿还计划）。
3. 无签核说明的基线上调视为违规变更，评审时应直接打回；审计红灯必须通过修代码解决，不得通过抬高基线"转绿"。
4. `scripts/audit_visual_tokens.mjs` 文件头已声明同一原则（"Baselines must only go down; do not raise them without explicit justification."），本文档将其升级为强制签核流程。

## 反面案例（2026-08-12 凌晨，实锤记录）

`scripts/audit_visual_tokens.baseline.json` 出现**未附任何签核与说明**的静默上调（截至本文档撰写时为未提交的工作区改动，`git diff HEAD` 可复现）：

- `frontend/src/styles/tokens.css`：hex 基线 105 → 122（+17）
- `frontend/src/theme/designSystem.ts`：hex 基线 203 → 205（+2）

注：任务口径曾记为"106 → 122"，按 `git diff` 实测起点为 105。该改动使 hex 总基线净增 19，且无提交信息、无负责人签核、无偿还计划，完全符合本规则第 3 条的违规定义。处置建议：提交前回退该基线上调，或按第 2 条补齐签核与原因说明。

## 执行要点

- 评审 checklist：凡 diff 触及 `*.baseline.json` / 债务基线，先核对方向（升/降），升则查签核。
- 基线更新命令（仅在偿还债务后使用）：`node scripts/audit_visual_tokens.mjs --update-baseline`
