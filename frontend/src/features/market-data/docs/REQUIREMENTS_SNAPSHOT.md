# 市场数据页需求快照（阶段「讨论」落地缺省）

在无法实时工作坊的前提下，采用**保守缺省**（与计划一致）；若与产品不一致，请只改本文件与对应常量。

## 已确认方向（来自计划与用户多选）

- 优化维度：体验与信息架构、性能、可维护性。
- **不**未经产品确认打开 `MARKET_DATA_SHOW_MACRO_OBSERVATION_AND_CATALOG_EVIDENCE` / `MARKET_DATA_SHOW_FX_ANALYSIS_SECTION`。

## 缺省决策

1. **一页主问题**：首屏优先回答「读面是否 ready、口径边界是否清晰」，其次进入利率/成交下钻。
2. **模块默认**：宏观深度 Tabs 默认「曲线」；联动区保持 **默认折叠**，用户点击展开后加载重内容（去掉 Collapse `forceRender`）。
3. **性能**：市场类只读查询统一 `staleTime`（如 60s）；宏观深度 Tabs 使用 **非激活销毁**（`destroyInactiveTabPane`），减少隐藏 Tab 下的图表/表挂载。
4. **元信息**：DataStatusStrip 去掉与 KPI 横带重复的「联动报告日」一行，保留 KPI 卡展示报告日。

## 验收句（可勾选）

- [x] 首屏主问句更短、仍能表达「口径 + 读面 ready」。
- [x] DataStatusStrip 不再重复展示「联动报告日」。
- [x] 切换至「信用利差」Tab 后仍能看到 `market-data-spreads-live-meta` 与联动元数据文案。
- [x] 展开「宏观-债市联动」折叠后，分析口径警示与表格与当前 mock 行为一致。
- [x] `npm test` 中 `MarketDataPage` 用例通过；`npm run debt:audit` 通过。
