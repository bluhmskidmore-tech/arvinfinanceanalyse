# Stock Analysis 最终功能与性能验收矩阵

日期：2026-07-18  
页面：`/stock-analysis`  
主接口：`GET /ui/market-data/stock-analysis/workbench`

## 业务与功能

| 验收项 | 权威口径 | 当前证据 | 状态 |
| --- | --- | --- | --- |
| 首屏先回答“能否继续复核、先看谁、卡在哪里” | `docs/stock_analysis_workbench_api_contract.md` | 页面 workbench contract、decision memo 与 queue 测试 | 通过 |
| 首屏只依赖一个聚合请求 | 同上 Frontend Consumption Rule | 5+5+5 浏览器样本：冷启动每轮 1 个 workbench，暖返回 0 个 | 通过 |
| 队列成员、顺序、数量和空态以 `first_screen.review_queue` 为唯一事实源 | 同上唯一事实源规则 | QueueModel 8 项测试及页面权威空队列、跨模块同代码、blocked 只读测试 | 通过 |
| `modules.main.result` 只按 `(source_module, stock_code)` 补证 | 同上 | 同源补证、跨源不串证、module state 不过滤测试 | 通过 |
| requested / resolved / fallback 日期不混用 | workbench date contract | 回退日期、刷新、sector series、drawer、Agent 上下文测试 | 通过 |
| `null`、0、missing、stale、fallback、deferred 可区分 | Acceptance Criteria | 空模块、空队列、零样本、陈旧、回退、deferred 与缺口测试 | 通过 |
| loading、HTTP error、成功但主模块缺失均可恢复 | 页面规则 | skeleton、恢复工作台、权限/传输/404/源表错误、retry 测试 | 通过 |
| 深度模块失败不破坏首屏 | workbench lazy module rule | signal confluence、sector series、backtest/optimization 错误隔离测试 | 通过 |
| 刷新先重算 Choice stock，再刷新队列；失败可审计重试 | 当前页面工作流 | refresh 顺序、fallback resolved date、失败重试测试 | 通过 |
| 行业筛选、候选详情、K 线复核、Agent 上下文形成页面闭环 | 当前页面工作流 | 页面交互测试 | 通过 |
| 观察用途，不出现买卖、下单、配置或执行批准 | governance contract | forbidden-copy、formal-use 双重许可、owner 状态测试 | 通过 |
| 正式用途保持关闭 | `GAP-STOCK-ANALYSIS-PAGE` | payload/meta 均需明确许可；后端 owner 状态测试 | 通过；owner 审批仍待外部完成 |

## 性能与加载

| 验收项 | 基线 | 当前证据 | 状态 |
| --- | ---: | --- | --- |
| 首屏传输量 | 4,053,664B | 3,375,859B，累计 -677,805B / -16.7% | 通过 |
| 首屏不加载完整 market-data 客户端 | 66KB 级客户端进入首屏 | 专属客户端 768B；网络与覆盖率均未出现完整客户端 | 通过 |
| 深度研究脚本和 CSS 按需加载 | 深度 CSS 在首屏 | 118.94KB CSS、深度 primitives 与组件位于 lazy boundary | 通过 |
| 首屏无深度诊断请求偷跑 | 曾自动请求 signal-confluence | 15/15 样本 deferred request = 0 | 通过 |
| 页面路由 JS | 227.95KB | 216.62KB（gzip 51.90KB） | 通过；仍有约 99KB 首屏未执行代码 |
| 移动限速首屏 | ready 22.32s / LCP 22.21s | 最近 5 轮中位数 ready 19.18s / LCP 19.10s | 通过但仍偏重 |
| 暖返回 | 121.96ms | 最近 5 轮中位数 56.01ms | 通过 |
| CLS | 未固定 | 桌面中位数 0.09、移动 0.04 | 通过但桌面接近 0.1 门槛 |
| 错误、控制台告警、横向溢出 | 未固定 | 5+5+5 样本全部为 0 | 通过 |

## 验证清单

- 前端组合回归：290/290。
- 额外 ApiClient 全路径回归：183/183。
- 后端 workbench API、首屏事实源、MCP 绑定、owner 状态：38/38。
- TypeScript、目标 ESLint、`vite build`：通过。
- `debt:audit`：仅工作区既有 `contracts.ts` 与 `pnl_service.py` 超基线；本轮未增长。

## 尚未最终关闭

1. 主页面块约 99KB、页面模型约 44KB 在首屏未执行；需审计深度研究计算与 JSX 是否可整体移出首屏块。
2. 全局 Ant Design/vendor 和 dashboard shell 是更大的跨页面热点；不得在股票页局部轮次中直接重构。
3. 需要一轮真实浏览器键盘焦点、深度研究展开/失败重试、抽屉关闭和三档响应式人工式自动验证。
4. workbench wrapper 尚无独立 golden sample，业务 owner 和正式用途审批仍未关闭；页面必须持续 fail closed。


## 最终收口更新（覆盖上方旧性能快照）

| 验收项 | 最终证据 | 状态 |
| --- | --- | --- |
| 首屏传输量 | 3,370,444B；相对 4,053,664B 累计 -683,220B / -16.85% | 通过 |
| 页面路由 JS | 207,192B（gzip 50.45KB）；相对拆分前 216,618B 减少 9,426B | 通过 |
| 深层选股概览按需加载 | 延迟块 6.90KB（gzip 1.91KB）；展开前 0 请求，键盘展开后加载 | 通过 |
| 桌面/移动响应式 | 1440×1000、390×844 均无横向溢出和控制台错误 | 通过 |
| 键盘闭环 | Enter 展开深度研究；行业权重股行 Enter 打开个股复核抽屉 | 通过 |
| 最终 5+5+5 性能样本 | 桌面 ready 528.95ms；暖返回 76.60ms；移动 ready 19,457.81ms | 通过 |
| 页面定向回归 | 页面/启动守卫/队列 236/236；新客户端 4/4 | 通过 |

上方“尚未最终关闭”第 1、3 项现已完成：已迁移一组可证明净收益的深层 JSX，且完成桌面/移动键盘与响应式浏览器验收。仍保留的外部边界只有：

1. 全局 Ant Design/vendor 与 dashboard shell 属于跨页面共享边界，本页轮次不直接重构。
2. workbench wrapper 的独立 golden sample、业务 owner 与正式用途审批仍由外部治理流程完成；页面继续 fail closed。
3. 仓库级 `npm run build` 被其他页面 `riskHomeAdapter.ts:626` 的未提交类型问题阻塞；本页 TypeScript 与 Vite 生产打包已通过。
