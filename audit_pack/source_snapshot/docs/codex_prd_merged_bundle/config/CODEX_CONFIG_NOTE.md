# .codex 配置说明

本包未提供强绑定的 `.codex/config.toml`，因为项目可能已存在自己的 Codex 配置。

建议：
- 将测试、lint、类型检查命令写入仓库级 `AGENTS.md`
- 若仓库已有 `.codex/config.toml`，只补充项目本地命令与路径，不要覆盖全局规则
- 文档优先级、阶段边界和架构不变量以 `AGENTS.md` 与 PRD 为准
