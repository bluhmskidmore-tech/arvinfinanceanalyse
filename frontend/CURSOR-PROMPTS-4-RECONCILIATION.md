# Prompt 4：全局对账 Reconciliation

## 任务
在 V3 前端 `F:/MOSS-V3/frontend/` 补建「全局对账」页面，完全对齐 V1 的计算口径和功能。

## V3 架构模式
同 Prompt 1。

---

## 一、TypeScript 类型定义（追加到 contracts.ts）

```typescript
/** 全局对账 */
export type ReconciliationDiffItem = {
  name: string;           // 对比项名称，如 "总资产(Position vs Ledger)"
  left: number;           // 左侧金额（元）
  right: number;          // 右侧金额（元）
  diff: number;           // 差异（元）= left - right
  breached: boolean;      // 是否超阈值
  note: string;           // 备注说明
};

export type ReconciliationAssetsComponent = {
  name: string;           // 如 "债券投资", "同业资产"
  amount: number;         // 元
  note?: string | null;
};

export type ReconciliationCoverageItem = {
  source: string;         // 数据源名称，如 "position_bonds", "ledger_daily_pnl"
  latest_report_date: string | null;
  count_rows: number | null;
};

export type ReconciliationSnapshotResponse = {
  report_date: string;
  ledger_currency: string;          // "CNX" | "CNY"
  threshold_yi: number;             // 阈值（亿元）

  // Position 口径
  position_total_assets: number;    // 元
  position_bond_assets: number;
  position_interbank_assets: number;
  assets_components: ReconciliationAssetsComponent[];

  // Ledger 口径（总账表）
  ledger_total_assets: number;
  ledger_total_liabilities: number;
  ledger_net_assets: number;
  ledger_monthly_pnl_total: number;     // 月度损益（514/516/517）
  ledger_monthly_pnl_all?: number | null; // 月度损益（全量 5*）

  // PnLRecord 口径（外部报表导入）
  pnl_records_total_pnl: number;

  // ProductCategoryPnL 口径
  product_category_view?: string | null;
  product_category_grand_cash_pnl?: number | null;
  product_category_grand_ftp?: number | null;
  product_category_grand_business_net_income?: number | null;

  // 差异对比
  diffs: ReconciliationDiffItem[];

  // 数据覆盖情况
  coverage: ReconciliationCoverageItem[];

  // 元数据
  generated_at: string;
  warnings: string[];
};
```

---

## 二、API 调用清单

| 用途 | V1 URL | 参数 | 返回类型 | client.ts 方法名 |
|------|--------|------|----------|-----------------|
| 对账快照 | `GET /api/meta/reconciliation` | `?report_date=&ledger_currency=CNX&threshold_yi=0.01&force_refresh=false` | `ReconciliationSnapshotResponse` | `getReconciliationSnapshot(reportDate, ledgerCurrency, thresholdYi, forceRefresh)` |

---

## 三、核心计算逻辑

### 金额格式化
```typescript
const formatMoney = (v: number | null | undefined) => {
  if (v === null || v === undefined) return '—';
  return `${(v / 100000000).toFixed(4)} 亿元`;  // 对账精度到4位小数
};
```

### 差异状态判断
```typescript
// breached = true 时：行背景红色 bg-red-50，差异金额红色字体
// breached = false 时：正常显示
const getStatusBadge = (breached: boolean) => {
  if (breached) return <Badge color="red">超阈值</Badge>;
  return <Badge color="green">正常</Badge>;
};
```

---

## 四、页面布局

单页面，无 Tab。数据加载：`GET /api/meta/reconciliation?report_date=&ledger_currency=&threshold_yi=&force_refresh=`

布局从上到下：

1. **页面标题 + 控制栏**
   - 标题：`全局对账`
   - 控制栏（一行）：
     - 账本货币选择：`CNX`（默认）/ `CNY`
     - 阈值输入：默认 `0.01`（亿元）
     - 强制刷新按钮

2. **Position 口径快照**（Card）
   - 标题：`Position 口径（持仓汇总）`
   - 3 列 KPI：总资产 | 债券资产 | 同业资产
   - 下方表格：资产构成明细
     - 列：名称 | 金额（亿元）| 备注

3. **Ledger 口径快照**（Card）
   - 标题：`Ledger 口径（总账表，币种: {ledger_currency}）`
   - 3 列 KPI：总资产 | 总负债 | 净资产
   - 2 列 KPI：月度损益（514/516/517）| 月度损益（全量 5*）

4. **PnLRecord 口径**（Card）
   - 标题：`PnLRecord 口径（外部报表导入）`
   - 1 个 KPI：总损益

5. **ProductCategoryPnL 口径**（Card，条件渲染）
   - 标题：`ProductCategoryPnL 口径（产品类别损益，{view} 视图）`
   - 3 列 KPI：现金损益合计(CNX) | FTP 合计 | 营业净收入
   - 仅当 `product_category_grand_cash_pnl` 存在时显示

6. **差异对比表**（核心表格）
   - 标题：`差异对比（阈值: {threshold_yi} 亿元）`
   - 列：对比项 | 左侧（亿元）| 右侧（亿元）| 差异（亿元）| 状态 | 备注
   - `breached === true` 的行：红色背景 + 红色差异金额 + "超阈值"徽章
   - `breached === false` 的行：正常 + "正常"绿色徽章

7. **数据覆盖情况**（Card）
   - 标题：`数据覆盖情况`
   - 列：数据源 | 最新报告日期 | 记录数

---

## 五、交互逻辑

1. **账本货币切换**：`CNX`（默认）/ `CNY`，切换后重新请求
2. **阈值设置**：输入框，默认 `0.01`（亿元），修改后重新请求
3. **强制刷新**：按钮，点击后 `force_refresh=true` 重新请求
4. 所有参数变化都触发重新查询

---

## 六、业务口径说明

1. Position 口径 = 持仓汇总（position_bonds + position_interbank）
2. Ledger 口径 = 总账表（按 ledger_currency 币种）
3. PnLRecord 口径 = 外部报表导入的损益
4. ProductCategoryPnL 口径 = 产品类别损益
5. 差异对比：跨口径比对，如 Position 总资产 vs Ledger 总资产
6. 阈值：差异绝对值超过阈值（亿元）时标记为 breached
7. 月度损益（514/516/517）= 利息收入+公允价值变动+投资收益三个科目
8. 月度损益（全量 5*）= 所有 5 开头科目

---

## 七、路由和导航注册

routes.tsx:
```typescript
const ReconciliationPage = lazy(() => import("../features/reconciliation/pages/ReconciliationPage"));
if (section.path === "/reconciliation") {
  return { path: section.path.slice(1), element: routeElement(<ReconciliationPage />) };
}
```

navigation.ts:
```typescript
{
  key: "reconciliation",
  label: "全局对账",
  path: "/reconciliation",
  icon: "settings",
  description: "多口径数据对账与差异分析",
  readiness: "live",
  readinessLabel: "Live",
  readinessNote: "已接对账快照读链路。",
},
```
