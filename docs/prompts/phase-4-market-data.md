# Phase 4: 市场数据页重构

> 前置依赖: Phase 0 已完成
> 主规格文档: `docs/moss-fixed-income-platform-spec.md` 第六节第 6 项
> Mockup: `.omx/mockups/market_data_hd.png`

## 目标

将现有 `MarketDataPage.tsx`（~1300 行）增量重构为 mockup 所示的高密度市场数据终端页。

## 现状

**现有文件**: `src/features/market-data/pages/MarketDataPage.tsx`
**已知问题**: 有明确的"该板块图表待接入"占位区块

**后端已有**:
- `/ui/preview/macro-foundation` — 宏观目录
- `/ui/market-data/fx/*` — FX 正式状态/分析
- `/ui/news/choice-events/latest` — 资讯事件
- AkShare 适配器（`repositories/akshare_adapter.py`）— 可能用于实时行情

## 实施要求

### 文件拆分结构
```
src/features/market-data/
├── pages/
│   └── MarketDataPage.tsx              # 精简为布局编排
├── components/
│   ├── MarketKpiRow.tsx                # 8 个市场 KPI
│   ├── RateQuoteTable.tsx             # 利率行情（国债/国开表格）
│   ├── YieldCurvePanel.tsx            # 收益率曲线（国债+国开）
│   ├── CreditSpreadTable.tsx          # 信用利差（中短票/城投）
│   ├── MoneyMarketTable.tsx           # 资金市场（R/DR/SHIBOR）
│   ├── BondFuturesTable.tsx           # 国债期货（T/TF/TS/TL）
│   ├── NcdMatrix.tsx                  # 同业存单矩阵（期限×评级）
│   ├── BondTradeDetail.tsx            # 债券成交明细
│   ├── CreditBondTradeDetail.tsx      # 信用债成交明细
│   └── NewsAndCalendar.tsx            # 资讯与日历
├── types/
│   └── marketViewModels.ts
└── mocks/
    └── marketDataMock.ts              # 全量 mock 数据
```

### Mockup 对照（高密度终端风格）

**顶部 KPI（8 张）**:
1. 10Y 国债 `1.94%` -1.2bp，历史分位 18%
2. 10Y 国开 `2.05%` -0.8bp，国利差 11bp
3. DR007 `1.82%` +2.1bp，资金价格回升
4. 1Y AAA 存单 `2.18%` -0.6bp，配置价值回升
5. AAA 3Y 利差 `45bp` -1.8bp，分位 10%
6. 5Y IRS `2.38%` -0.3bp
7. 10Y 美债 `4.10%` +5bp，外部约束增强
8. USD/CNY `7.1400` +0.0064，汇率偏稳

**利率行情** — Tab: 绿健 | 收益率 | IRS
- 表格: 品种(国债/国开) | 期限(1Y-10Y) | 利率% | 涨跌bp | 成交量 | 区间

**收益率曲线** — Tab: 国债 | 国开
- ECharts 折线图，多日期对比
- 下方注释

**信用利差** — Tab: 中短票 | 城投债
- 表格: 品种 | 评级 | 利差 | 期限(bp) | 历史分位 | 3M趋势 | 信号

**资金市场** — 紧凑表格
- R001, DR001, DR007, R007
- 利率, 涨跌bp, 成交量, 加权, 区间

**国债期货** — Tab: 银行间 | 主力合约
- T2409, TF2409, TS2409, TL2409
- 合约, 价格, 涨跌, 涨跌幅, 成交量, 持仓量

**同业存单** — Tab: 发行利率
- 矩阵: 期限(1M, 3M, 6M, 9M, 1Y) × 评级(AAA, AA+, AA)
- 使用 `HeatmapTable` 组件

**债券成交明细（主力合约）** — 实时滚动表格
- 时间, 债券简称, 期限, 价格, 收益率, 成交量, 方向(买入/卖出)
- 买入用红色，卖出用绿色

**信用债成交（可选展示）** — 表格
- 时间, 简称, 评级, 价格, 收益率

**资讯与日历** — Tab: 资讯 | 事件日历
- 时间, 标题, 影响
- 来自 `/ui/news/choice-events/latest`

### 关键约束

- 这是 **market terminal 风格**，信息密度最高
- 以高密度表格 + 曲线 + 明细为主
- 不要做成大块叙事页
- 维持浅色 MOSS 风格，不要做成黑底终端
- 数字更新频率可以较高（如果后端支持）
- 现有占位区块直接替换为真实组件

## Mock 数据

市场数据 mock 需要更大量的数据点。参考 mockup 中的具体数值生成完整 mock。

## 验证

```bash
npm run lint && npm run typecheck && npm run build
```

视觉对比 `market_data_hd.png`。重点验证信息密度——单屏应能看到大量数据。
