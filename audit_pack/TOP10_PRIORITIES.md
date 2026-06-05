面向 ChatGPT 二次审计：**当前仓库静态 + 最近一次命令输出的 Top 10 优先项**（非最终安全结论）。

1. **`npm run build`（`tsc -b`）失败**：负债分析页 **`ApiClient` 方法缺失**（`getCockpitWarnings`、`getContributionSplit`）；组件 props 契约断裂（**`GridContainer` / `DashboardBondHeadlineSection`**）；`KpiCard` / **`crossAssetTrendChart`** 类型与图表配置漂移。——**阻断生产构建**。  
2. **`pytest` 收集失败**：测试仍 import **`executive_service._HOME_SNAPSHOT_DOMAINS`**，与实现脱节。——**CI 不可测**。  
3. **运行时版本漂移**：本机 **`Python 3.14.2`** 跑 pytest，与团队常见 **`3.11–3.12`** 组合可能不一致。——**环境与依赖_wheel 风险**。  
4. **端口与环境矩阵**：`7888/5888`（脚本+Vite）、`8000/5173`（Compose+OpenAPI scaffold+测试 **`localhost:8000`**）、UI 文案写死 **`7888`**。——**联调与文档信任危机**。  
5. **归因 / 损益只读 API 大范围无 ACL**：`/api/pnl-attribution/**` GET 不加 `Depends`；`/api/cube/dimensions/{fact_table}` **无认证**。——**内网假定若破坏则数据面过宽**。  
6. **`build_campisi_attribution`**：`spread`、`selection` **明示 STUB=0**。——**产品叙述若未标注会误导**。  
7. **`core_finance` float 与 Decimal 断层**：账本核 `Decimal` ↔ 工作台 `float` ↔ ORM `Numeric`/`float` 注解。——**端到端 pennies 漂移**。  
8. **`client.ts` mega-file**：持续增长违反 `AGENTS.md` frontend debt guardrails；Mock 与真实混处。——**可维护性与误用 Mock  risk**。  
9. **Executive / Macro / News 「503 Reserved」**：OpenAPI 列路由但运行时直接拒绝。——**「接口存在但不能用」**。  
10. **CORS：`allow_credentials=True` + split origins**：生产误配时扩大浏览器侧滥用面。——**上线前需收紧原点列表**。
