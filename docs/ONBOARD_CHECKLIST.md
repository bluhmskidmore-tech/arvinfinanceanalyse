# MOSS V3 快速 Onboard 清单

按顺序勾选即可；细节都在所链文档与脚本里，本文不重复长文。

## 约 5 分钟：跑起来

- [ ] 读过 [AGENTS.md](../AGENTS.md)（优先级与「不该动什么」）
- [ ] Windows：一键启动
      `powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1`
      （分开启动与探针说明见 [GETTING-STARTED.md](GETTING-STARTED.md)）
- [ ] 打开 Frontend：`http://127.0.0.1:5888`
- [ ] 确认 API：`http://127.0.0.1:7888/health`
      以及 `http://127.0.0.1:7888/api/bond-analytics/dates`（与 [README.md](../README.md) 一致）

**可选（Docker）**：`docker compose up api worker frontend postgres redis minio` — 端口与本地脚本不同，见 [README.md](../README.md) 与 [GETTING-STARTED.md](GETTING-STARTED.md)。

## 约 30 分钟：边界与改哪里

- [ ] [DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md)（文档听谁的）
- [ ] [CURRENT_EFFECTIVE_ENTRYPOINT.md](CURRENT_EFFECTIVE_ENTRYPOINT.md)
- [ ] [DEVELOPMENT.md](DEVELOPMENT.md)（开发约束与目录落点）
- [ ] 准备改具体页面前再读 [page_contracts.md](page_contracts.md)
- [ ] 分层方向记一句：`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`；正式金融计算只在 `backend/app/core_finance/`

## 最小验证（按需选一类）

**前端**（在 `frontend/`）：

```bash
npm run lint
npm run typecheck
```

**后端**：

```bash
python -m pytest -q
```

更全的说明见 [TESTING.md](TESTING.md) 与根 [README.md](../README.md)。

## AI 协作会话（可选）

新开对话时若要少轮次对齐上下文，可自建 `.omx/context/<任务 slug>-<时间戳>.md`（UTC），写清：任务一句、已知事实、未决问题、可能改动的路径（与常见「规划前 intake」字段一致即可）；无 `.omx` 目录时手动创建即可。

---

**延伸阅读**： [architecture.md](architecture.md)、[CONFIGURATION.md](CONFIGURATION.md)、[CURRENT_BOUNDARY_HANDOFF_2026-04-10.md](CURRENT_BOUNDARY_HANDOFF_2026-04-10.md)。
