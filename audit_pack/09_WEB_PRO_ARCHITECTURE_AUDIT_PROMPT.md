# Web Pro Architecture Audit Prompt

下面这段用于网页端 Pro 模型。先上传 `moss_v3_audit_pack.zip`，再复制粘贴本提示词。

---

你是一名资深业务系统架构审计专家。请基于我上传的 MOSS-V3 审计资料包，对整套系统做一次架构设计审计。

## 审计材料读取顺序

请先阅读：

1. `00_AUDIT_PACKAGE_README.md`
2. `02_PROJECT_OVERVIEW.md`
3. `TOP10_PRIORITIES.md`
4. `03_BACKEND_API_MAP.md`
5. `04_FRONTEND_PAGE_API_MAP.md`
6. `05_DATABASE_MODEL_MAP.md`
7. `06_FINANCIAL_LOGIC_AUDIT.md`
8. `07_RISK_AND_BUG_SCAN.md`
9. `08_RUN_AND_TEST.md`

`01_PROJECT_TREE.md` 很大，只在需要定位目录结构时查阅。需要代码证据时，到 `source_snapshot/` 中按路径打开源码。

## 系统背景

MOSS-V3 是一个业务系统，不是通用技术平台。当前优先级是：

1. 业务指标正确性
2. 页面级闭环
3. 数据血缘、可追溯性和验证
4. 最小、可审查、可回滚的改动

当前不优先：

- 后端平台大重构
- 通用基础设施抽象
- 框架美化
- 基础层重建
- 无关性能优化
- 大规模重写

## 审计重点

请重点判断当前架构是否支撑以下目标：

1. 业务指标从数据源到页面展示是否能闭环追踪。
2. API response -> frontend adapter -> state/query -> selector/computed model -> component -> chart/table 的链路是否清晰。
3. 后端 API、service、repository、core_finance、tasks、governance 的边界是否合理。
4. 正式金融计算是否集中在 `backend/app/core_finance/`，前端是否存在重复计算或口径漂移风险。
5. mock、fallback、reserved/503、真实 API 是否容易混淆。
6. 单位、精度、Decimal/float、日期口径、as_of_date、缓存日期、trade date/month-end/YTD 是否有系统性风险。
7. 前后端契约是否足够强，是否存在 `dict[str, object]`、手写 TS 类型、response_model 缺失导致的漂移。
8. 当前测试和验证体系是否能保护关键业务链路。
9. 哪些是架构问题，哪些只是局部实现问题。
10. 哪些建议值得现在做，哪些建议应该明确不做，避免过度架构化。

## 必须抽查的业务链路

请至少抽查 3 条完整链路，并写出证据路径：

1. 一个损益或归因类页面。
2. 一个债券/持仓/组合类页面。
3. 一个经营/KPI/驾驶舱类页面。

每条链路请尽量覆盖：

- 前端页面或组件
- 前端 API client / adapter / selector / formatter
- 后端 route
- 后端 service
- repository 或 core_finance 计算
- schema / response model
- mock / fallback / reserved surface
- 相关测试

## 输出格式

请按以下结构输出：

### 1. 总体结论

- 架构健康度：健康 / 有风险 / 高风险
- 结论用 5-8 句话说明，必须基于上传材料。

### 2. Top 10 架构问题

按 P0/P1/P2/P3 分级：

- P0：阻断构建、阻断验证、可能直接导致错误业务结论
- P1：高概率导致指标口径漂移、数据泄露、页面闭环失败或维护失控
- P2：明显技术债，会放大后续改动成本
- P3：整理项或长期优化

每个问题必须包含：

- 级别
- 问题标题
- 证据路径
- 影响
- 为什么这是架构问题，而不只是局部 bug
- 推荐改法
- 最小改动范围
- 验证方式

### 3. 业务指标正确性风险

单独列出：

- 单位风险
- 精度/舍入风险
- Decimal/float 风险
- 日期口径风险
- mock/fallback 污染真实展示风险
- 前后端重复计算风险
- stale data / reserved surface 风险

### 4. 架构边界评价

分别评价：

- frontend
- API routes
- services
- repositories
- core_finance
- tasks/materialization
- governance/lineage
- tests

每层都要说明：职责是否清晰、主要风险、建议边界。

### 5. 不建议做的事情

请明确列出至少 5 条现在不该做的架构动作，例如大重构、抽象平台层、微服务化等，并说明为什么不适合当前阶段。

### 6. 2-4 周可执行路线图

请给一个小步修复路线图，分成：

- 第 1 周：阻断项和验证闭环
- 第 2 周：关键业务链路契约化
- 第 3-4 周：系统性债务收敛

每一项必须可验证、可回滚、尽量小改动。

## 约束

- 不要泛泛而谈。
- 不要只评价目录结构。
- 不要建议大重写。
- 不要假设未上传材料中的事实。
- 如果材料不足，请明确指出需要补充哪些文件或链路。
- 所有判断必须引用文件路径或资料包中的证据。
