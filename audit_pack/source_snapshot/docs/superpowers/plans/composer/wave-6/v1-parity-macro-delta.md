# V1 → V3 Delta：宏观深度（MacroAnalysis M7–M16）

| V1 模块 | V3 已实现位置 | V3 client 方法 | 实施决定 | 目标 V3 文件 |
| --- | --- | --- | --- | --- |
| M7 货币政策立场等 `/api/macro/monetary-policy-stance` … | 无 | **无**（非 `getMacro*` 统一前缀；未在 `client.ts` 暴露） | ⏭️ 跳过（端点缺） | — |
| M8 收益率曲线形态 | `MarketDataPage` Choice `recent_points` 利率走势图 | `getChoiceMacroLatest` | 🔁 增强（收入「宏观深度」Tab） | `frontend/src/features/market-data/pages/MarketDataPage.tsx` |
| M9 信用利差预警 | 联动 `credit_spread` 槽位表 | `getMacroBondLinkageAnalysis` | 🔁 增强（同上 Tab） | 同上 |
| M10–M14、M16 等其余 `/api/macro/*` | 无对等 | **无** | ⏭️ 跳过（端点缺） | — |
| M11 流动性压力测试 / M15 情景-组合影响 | 联动 `environment_score` + `portfolio_impact` 摘要 | `getMacroBondLinkageAnalysis` | 🔁 增强（摘要 Tab；完整矩阵仍在下方折叠区） | 同上 |
| 宏观决策摘要卡片（V1 `decision-summary`） | 无 | **无** | ⏭️ 跳过（端点缺） | — |
| 目录与 vendor 元数据 | 页尾「宏观序列目录」 | `getMacroFoundation` | ✅ 已有 | 同上 |

## 待续

- 后端将 V1 `/api/macro/*` 收敛为受 envelope 约束的只读 API 并在 `client.ts` 登记后，再补齐 M7/M10–M14/M16 与决策摘要。
