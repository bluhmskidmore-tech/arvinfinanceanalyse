# Phase 6: 跨资产驱动页重构

> 前置依赖: Phase 0 + Phase 3 已完成
> 主规格文档: `docs/moss-fixed-income-platform-spec.md` 第六节第 4 项
> Mockup: `.omx/mockups/cross_asset_drivers_hd.png`

## 目标

将现有 `CrossAssetPage.tsx`（~608 行）增量重构为 mockup 所示的跨资产驱动分析页。

## 现状

**现有文件**: `src/features/cross-asset/pages/CrossAssetPage.tsx`

**后端已有**:
- `/api/macro-bond-linkage/analysis` — 宏观-债券联动分析
- `/ui/preview/macro-foundation` — 宏观序列目录
- AkShare 适配器可能提供跨资产行情

## 实施要求

### 文件拆分结构
```
src/features/cross-asset/
├── pages/
│   └── CrossAssetPage.tsx              # 增强为完整跨资产页
├── components/
│   ├── CrossAssetKpiRow.tsx            # 8 个跨资产 KPI
│   ├── MarketJudgment.tsx             # 市场判断
│   ├── DriverDecomposition.tsx        # 驱动拆解
│   ├── ValuationHeatmap.tsx           # 估值/分位热图
│   ├── CrossAssetTrendChart.tsx       # 跨资产走势（20日基准=100）
│   ├── MarketCandidateActions.tsx     # 市场候选动作
│   ├── EventSupplyCalendar.tsx        # 事件与供给日历
│   └── WatchList.tsx                  # 观察名单
├── types/
│   └── crossAssetViewModels.ts
└── mocks/
    └── crossAssetMock.ts
```

### Mockup 对照

**顶部 KPI（8+ 张）**:
1. 10Y 国债 `1.94%` -1.1bp，债市反映
2. 10Y 美债 `4.10%` +5bp，外部约束增强
3. 中美国债利差 `-210bp`，利差倒挂手
4. DR007 `1.82%` +2.1bp，资金价格偏松
5. 沪深300 `3924.5` +1.8%，风险偏好回升
6. 布油 `82.3` +4.8%，通胀预期比升
7. 铜 `8500` +3.2%，工业品回暖
8. USD/CNY `7.1400` +0.0064，汇率偏稳

**市场判断** (`MarketJudgment`):
- 一段判断文字
- 关键词标签: 主导因子/流动性, 次要因子/海外约束, 风险判断/中段优于长端

**驱动拆解** (`DriverDecomposition`):
- 5 个驱动因子卡片:
  1. 流动性 — 偏多 — "DR007仍处低位, NCD压力暂未显性化"
  2. 海外约束 — 偏空 — "10Y美债上行, 中美利差倒挂扩大"
  3. 增长预期 — 中性偏弱 — "A股与黑色回暖, 长端下行阻力增加"
  4. 通胀扰动 — 中性 — "原油连续上行, 仍停留预期层面"
  5. 影响债券定价 → 影响程度标注
- 每个因子有方向图标和颜色

**估值/分位热图** (`ValuationHeatmap`):
- 使用 `HeatmapTable`:
  - 10Y 国债 `1.94%` 分位 18%
  - 5Y 国开-国债 `12bp` 分位 72% — 偏高宜
  - AAA 3Y `45bp` 分位 10% — 偏拥挤
  - 1Y AAA 存单 `28bp` 分位 81% — 可配
  - 中美国债利差
- 颜色: 低分位=红(拥挤), 中=灰(中性), 高=绿(可配)

**跨资产走势（近20日，统一基准=100）** (`CrossAssetTrendChart`):
- ECharts 折线图，多条线:
  - 10Y 国债, 10Y 美债, 沪深300, 布油, DR007, 铜
- X 轴: 近 20 个交易日
- Y 轴: 统一基准 = 100（首日标准化）
- 注释: "近20日国债与油价持续上行，A股与工业品同步回暖..."

**跨资产传导链** — 简洁步骤:
1. 先看顶部 KPI
2. 再看驱动拆解
3. 结合估值/分位热图
4. 结论: "当前债市..."

**市场候选动作** (`MarketCandidateActions`):
- 关注 5Y 国债 — 中段中期率优于长端
- 观察 1Y AAA 存单 — 等待供给落地
- 暂不追 10Y 长端 — 海外约束...
- 信用仅做票息 — 利差偏拥挤
- 每项有: 触发条件, 备注

**事件与供给日历** (`EventSupplyCalendar`):
- 表格: 日期 | 事件 | 影响评估 | 级别(高/中)
- 国债招标, 同业存单到期, 美国非农, CPI数据

**观察名单** (`WatchList`):
- 表格: 品种 | 当前 | 分位 | 信号
- 5Y 国开, 1Y AAA 存单, AA+ 3Y 城投
- 信号: 等待供给落地 / 偏拥挤观望 / 不宜追涨

**页面输出**:
- 环境标签
- 方向判断
- 主要风险
- 关注窗口

### 关键约束

- 这一页看**外部变量如何推动债券定价**
- 不能和 Bond Analysis 重复（Bond Analysis 看债市内部）
- 跨资产走势图必须统一基准（首日=100）
- 数据主要来自 `/api/macro-bond-linkage/analysis` + mock
- 如果后端 macro-bond-linkage 数据不够，mock 补齐

## 验证

```bash
npm run lint && npm run typecheck && npm run build
```

视觉对比 `cross_asset_drivers_hd.png`。
