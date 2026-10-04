# .codex 配置说明

仓库已跟踪 `.codex/config.toml`（以及 `.codex/skills/`、`.codex/agents/`）；`.codex/` 下其余子目录（`tmp/`、`visual-audits/`、`reports/` 等）是运行产物，由 `.gitignore` 忽略。

建议：
- 将测试、lint、类型检查命令写入仓库级 `AGENTS.md`
- 修改 `.codex/config.toml` 时只补充项目本地命令与路径，不要覆盖全局规则
- 文档优先级、阶段边界和架构不变量以 `AGENTS.md` 与 PRD 为准
