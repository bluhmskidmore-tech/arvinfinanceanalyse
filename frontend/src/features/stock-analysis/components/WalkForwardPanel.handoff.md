# WalkForwardPanel 接线交接说明

预制件：回测诊断区「样本外验证」面板(walk-forward)。本次交付只创建新文件、
不改动 `frontend/src/features/stock-analysis/` 下任何现有文件；接线由后续会话完成。

## 交付物

| 文件 | 作用 |
| --- | --- |
| `frontend/src/api/strategyReportsClient.ts` | 契约类型(全 optional)+ `fetchWalkForwardReport`(404 → null) |
| `frontend/src/features/stock-analysis/components/StockAnalysisWalkForwardPanel.tsx` | 自包含面板组件 |
| `frontend/src/features/stock-analysis/components/StockAnalysisWalkForwardPanel.css` | 样式(全部 `--dh-api-*` token,零新增色值) |
| `frontend/src/features/stock-analysis/components/StockAnalysisWalkForwardPanel.test.tsx` | vitest 组件测试 |

后端：`GET /api/strategy-reports/walk-forward`(路由 `backend/app/api/routes/strategy_reports.py`,
service `backend/app/services/strategy_report_service.py`,已在 `backend/app/api/__init__.py` 注册,
读取 `docs/strategy-reports/walk-forward-first-run.json` 做展示裁剪,报告缺失返回 404)。

## 挂载位置建议(回测诊断区)

`frontend/src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx` 的周期区回测诊断段：
组合回测块 `div.stock-analysis-page__cycle-proxy-backtest`
(`data-testid="stock-analysis-candidate-history-portfolio-backtest"`,约 L3751)与
代理回测块(约 L3860)之后、周期区收尾之前，作为该区第三块诊断面。
面板自带边框容器(`--dh-api-line`),放入现有栅格即可，无需额外包装。

## 预计接线 diff(2 行)

```tsx
// StockAnalysisPageImpl.tsx 头部 import 区：
import { StockAnalysisWalkForwardPanel } from "../components/StockAnalysisWalkForwardPanel";

// 周期区代理回测块之后：
<StockAnalysisWalkForwardPanel />
```

## 加载方式与降级语义

- 组件自包含加载：挂载后 `useEffect` 调 `fetchWalkForwardReport()`(同源相对路径,原生 fetch)。
  不依赖 `clientContext`/react-query，因此接线零配置；测试/mock 场景注入 `loadReport` prop。
- 整面隐藏(render `null`)的情形：端点 404(报告未生成)、请求失败(含 403)、
  payload 无任何策略行。加载中同样不占位，不会在页面上留空壳。
- 如需并入页面统一的数据层，可改为页面级 `useQuery` + 传 `loadReport`：
  `useQuery({ queryKey: ["strategy-reports","walk-forward"], queryFn: () => fetchWalkForwardReport(), staleTime: Infinity })`,
  再 `<StockAnalysisWalkForwardPanel loadReport={() => query.promise}/>` 或直接沿用自包含模式。

## 展示口径备忘

- 结论标签直接透传报告 `verdict`：`oos_supported`(样本外支持,绿)/`oos_weakened`(样本外衰减,琥珀)/
  `oos_inconclusive`(方向不定,琥珀)/`insufficient_windows`(样本不足,中性)。排序按此优先级。
- 「样本内」为全训练期单值口径(报告不含逐窗样本内序列)；「样本外中位」为逐窗
  `excess_vs_gate` 的中位数(service 端计算)。双条按行内绝对值最大者归一,条形中性色,
  正负色只落在数值文本(`--dh-api-green/red`)。
- rpt(risk-per-trade 预算参数)漂移：`switch_rate`/`mode_value` 来自报告 `drift` 节点,
  逐窗最优序列放行内 tooltip。
- 报告的两个 schedule(`primary_6t_2v_2s`/`compact_1t_1v_1s`)即验证 horizon 维度,
  以 tab 切换,默认展示第一个(primary)。

## 权限与联调注意

- 端点读权限 resource 为 `strategy_reports`(action `read`),经 `ensure_read_allowed` 走
  user-scope 库；联调环境需先 grant,否则 403 → 面板静默隐藏。
- 报告刷新方式：重跑 `scripts/run_walk_forward_validation.py` 覆盖
  `docs/strategy-reports/walk-forward-first-run.json`；service 可用环境变量
  `MOSS_WALK_FORWARD_REPORT_PATH` 覆盖路径(测试即用此机制)。
- 本次未改 `tests/conftest.py`、`backend/app/main.py`、
  `frontend/src/features/stock-analysis/` 现有文件与 livermore 路由/服务(并行会话占用)。
