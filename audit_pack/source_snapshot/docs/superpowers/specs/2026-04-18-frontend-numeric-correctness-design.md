# 前端计算层正确性升级设计书（路径 C · 全三层）

- 起草日期：2026-04-18
- 设计作者：Cursor Agent（Opus 4.7）+ 项目主理
- 交付周期：8-10 周，分 5 波 ≈ 32 个 composer 子任务
- 关联审计：`docs/frontend_audit_report.md`
- 状态：Design Draft，待主理 review 后进入 `writing-plans`

---

## 1. Goals & Non-goals

### 1.1 Goal

前端所有受治理（governed）数字字段在 8-10 周内达到：

- 原始值、单位、展示、正负、fallback、explicit_miss 六件事**端到端可审计**
- 同一指标跨卡 / 跨图 / 跨表**共享同一 raw number**
- 组件**不再**自己做单位换算、`Math.abs`、颜色反转、字符串拼接
- 首页不再出现 `mixed` 报告日；非"同一报告日快照"时必须显式提示用户
- 生产构建拒绝默认回落 mock，必须显式声明数据源

### 1.2 Non-goal

- 不做 demo 导航页复活、不做 agent surface
- 不动 KPI / 现金流预测 / Cube / FX / macro 等与审计报告边界无关的业务逻辑
- 不重构全局 store 架构（不引入 Redux/Zustand）
- 不动权限 / 认证 / 队列 / 缓存底座
- 不合并 `executive_analytical` 与 `formal_attribution` 两套口径（见 § 7）

### 1.3 完成判定（Definition of Done）

- 所有 governed 页面通过 `adapter.test` 的 5 场景（正常 / null / 负数 / fallback / explicit_miss）
- 所有 mock 输出可被对应 zod schema `.parse()` 通过
- 同一指标"卡片 = 图形 = 表格"的 raw number 一致性集成测试全绿
- Dashboard 在严格日默认模式下不再出现 `mixed` 标签
- `npm run build` 在未设置 `VITE_DATA_SOURCE=real` 时 fail fast

---

## 2. 分层架构

```
┌────────────────────────────────────────────────────────┐
│ Backend pydantic schemas                               │
│   Numeric / Money / ResultMeta (source_surface 强制)   │
└──────────────────────┬─────────────────────────────────┘
                       │
            ApiEnvelope<T> + ResultMeta
                       │
┌──────────────────────▼─────────────────────────────────┐
│ Frontend contracts.ts  (由 pydantic 生成 zod schema)   │
└──────────────────────┬─────────────────────────────────┘
                       │
          zod runtime parse (mock ↔ real 一致性)
                       │
┌──────────────────────▼─────────────────────────────────┐
│ Page-local adapter                                     │
│   - 单位 / null / 0 / fallback / sign 统一收束         │
│   - 输出 typed view-model（组件只读这个）              │
└──────────────────────┬─────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────┐
│ Page-local selector                                    │
│   - 跨组件共享同一 raw number                          │
│   - 声明"这张卡 / 这张图 / 这张表吃哪个字段"           │
└──────────────────────┬─────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────┐
│ Global formatter  (frontend/src/utils/format.ts)       │
│   - Numeric → display string 的唯一出口                │
└──────────────────────┬─────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────┐
│ Components (DataSection / Chart / Table / Card)        │
│   - 只读 selector view-model                           │
│   - 不做换算、不做 abs、不自己编色彩语义                │
└────────────────────────────────────────────────────────┘
```

### 2.1 关键约束

- 组件**只**读 selector 吐出来的 typed view-model
- 组件**不**读原始 contract、**不**自己算 `/1e8`、**不**自己 `Math.abs`
- formatter 是 Numeric → string 的**唯一出口**
- adapter 是 `null / 0 / fallback / sign / unit` 转换的**唯一入口**
- 组件颜色从 tone 枚举派生，**不得**在组件内局部 override

---

## 3. 通用 Numeric 类型（默认值 1C）

### 3.1 后端 Pydantic 定义

位于新文件 `backend/app/schemas/common_numeric.py`：

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel

NumericUnit = Literal["yuan", "pct", "bp", "ratio", "count", "dv01", "yi"]

class Numeric(BaseModel):
    raw: float | None          # 未换算的原始值，None = 真缺（非 0）
    unit: NumericUnit          # 原始 raw 的单位
    display: str               # 展示串（带正负号、单位、精度；null → "—"）
    precision: int             # display 用到的小数位
    sign_aware: bool           # True = 允许负值（正负颜色区分）；False = 绝对值语义
```

### 3.2 前端 TypeScript 定义

位于 `frontend/src/api/contracts.ts` 顶部：

```ts
export type NumericUnit = "yuan" | "pct" | "bp" | "ratio" | "count" | "dv01" | "yi";

export type Numeric = {
  raw: number | null;
  unit: NumericUnit;
  display: string;
  precision: number;
  sign_aware: boolean;
};
```

### 3.3 迁移映射（示例）

| 旧字段 | 新字段 | 备注 |
|---|---|---|
| `ExecutiveMetric.value: str` | `ExecutiveMetric.value: Numeric` | sign_aware 按 id 决定 |
| `ExecutiveMetric.delta: str` | `ExecutiveMetric.delta: Numeric \| null` | 无环比时 raw=null |
| `PnlAttributionPayload.total: str` | `Numeric` | sign_aware=true |
| `AttributionSegment { amount, display_amount }` | `AttributionSegment { amount: Numeric }` | 合并 |
| `RiskSignal.value: str` | `Numeric` | 大多 sign_aware=false |
| `BondPortfolioHeadlinesPayload.total_market_value: str` | `Numeric (unit="yuan")` | |
| `KRDBucket.krd: str` | `Numeric (unit="ratio")` | |
| `CarryRollDownItem.carry: number` + 单位散落 | `Numeric (unit="ratio" 或 "bp")` | 口径需确认 |

### 3.4 前端消费示例

组件层绝不 `toFixed` 或 `/1e8`：

```tsx
<span>{metric.value.display}</span>
<span style={{ color: toneFromNumeric(metric.value) }}>
  {metric.value.display}
</span>
```

adapter 层集中生成 display：

```ts
function buildNumeric(raw: number | null, opts: {...}): Numeric {
  const display = raw === null ? "—" : formatWithUnit(raw, opts);
  return { raw, display, unit: opts.unit, precision: opts.precision, sign_aware: opts.sign_aware };
}
```

---

## 4. Backend authoritative snapshot（默认值 3C）

### 4.1 新增端点

`GET /ui/home/snapshot`

**请求参数：**
- `report_date`（可选）：YYYY-MM-DD；不传 = 默认日
- `allow_partial`（可选）：布尔，默认 `false`

**默认模式（严格日）：**
- 后端从 balance / pnl / liability / bond 四个业务域各自的可用日列表中，取**交集**的最近一日作为 `report_date`
- 若交集为空，整个 snapshot 返回 `result_meta.quality_flag="error"`，`fallback_mode="none"`，`result` 为空壳
- `result_meta.fallback_mode` 恒为 `"none"`（因为严格日本身就是 authoritative 的）
- `result.source_surface = "executive_analytical"`

**宽松模式（`allow_partial=true`）：**
- 允许用户指定任意历史日
- 不可用业务域的字段在 `result` 中以 `Numeric{raw:null, display:"—"}` 返回
- 每个缺失业务域在 `result.domains_missing: string[]` 中列出
- `result_meta.quality_flag = "warning"`，`vendor_status` 按域状态聚合
- 前端 UI 必须显式提示"部分业务域数据缺失"

### 4.2 Response Payload

```python
class HomeSnapshotPayload(BaseModel):
    report_date: str
    mode: Literal["strict", "partial"]
    source_surface: Literal["executive_analytical"]
    overview: OverviewPayload                  # typed, 使用 Numeric
    attribution: PnlAttributionPayload         # typed, 使用 Numeric
    domains_missing: list[str]                 # strict 模式下永远是 []
    domains_effective_date: dict[str, str]     # 严格模式下全部 = report_date
```

### 4.3 前端改造

- `DashboardPage` 从"调 4 个 query"改成"调 1 个 snapshot"
- `mixed` 标签从 UI 中消失
- `allow_partial` 开关作为 header 工具条的一个显式切换按钮（默认关闭）

### 4.4 旧端点废弃策略

旧 `/ui/home/overview` / `/ui/home/summary` / `/ui/pnl/attribution` 保留 2 个 phase 观察期后下线，观察期内通过日志计数确认无外部消费方。

---

## 5. Frontend Adapter / Selector / Formatter 层

### 5.1 文件布局

每个受治理页面建立：

```
frontend/src/features/<page>/
  adapters/
    <page>Adapter.ts        # 入口：Numeric/ResultMeta → typed view-model
    <page>Adapter.test.ts   # 5 场景单元测试
  selectors/
    <page>Selectors.ts      # 跨组件共享 raw / 声明字段归属
    <page>Selectors.test.ts
  components/
    ...                     # 只读 view-model
```

全局：

```
frontend/src/utils/format.ts    # Numeric → string 唯一出口
frontend/src/utils/tone.ts      # Numeric → tone 枚举唯一出口
```

### 5.2 Adapter 职责边界

- 输入：`ApiEnvelope<T>` + user-level query 参数（report_date / compareType 等）
- 输出：`{ viewModel: T', meta: DataSectionState }`
- 必做：
  - Numeric.raw null→"—" 处理
  - 0 vs null 区分（0 是有效值，null 是真缺）
  - fallback / explicit_miss / vendor_unavailable 提升到 DataSectionState
  - sign 一致性：同一 payload 的所有相关 Numeric 必须 sign_aware 一致
- 禁止：
  - 调 fetch / 调其他 adapter
  - 业务计算（如算环比、算占比）—— 业务计算留在后端或 selector

### 5.3 Selector 职责边界

- 输入：adapter 输出的 view-model
- 输出：若干 sub-view-model，面向具体组件
- 必做：
  - 声明"卡片 X 用哪个字段、图形 Y 用哪个字段、表格 Z 用哪个字段"
  - 保证"卡片 X 和图形 Y 吃的是同一个 raw number 派生"
- 测试：每对跨组件字段关系有一条 `expect(cardValue.raw).toBe(chartValue.raw)` 断言

### 5.4 Formatter 职责边界

位于 `frontend/src/utils/format.ts`，对外暴露：

```ts
formatNumeric(n: Numeric): string                    // 已有 display 直接返回
formatRawAsNumeric(raw, unit, precision, signed): string  // 给 adapter 用
formatYi(raw: number | null, signed: boolean): string     // 亿特化
formatPercent(raw: number | null, signed: boolean): string
formatBp(raw: number | null, signed: boolean): string
```

组件层**不**从 format.ts import 任何函数；组件层只从 selector/adapter 拿已经 formatted 的 Numeric.display。

---

## 6. DataSection 状态组件族（升级 AsyncSection）

### 6.1 状态机

`AsyncSection` 扩展为 `DataSection`，状态从 3 → 7：

| 状态 | 含义 | 触发条件 |
|---|---|---|
| `loading` | 请求进行中 | `isLoading` |
| `error` | 网络/后端错误 | `isError` |
| `empty` | 接口返回但无业务数据 | `result.items.length===0` |
| `stale` | vendor_stale 但仍可消费 | `meta.vendor_status==="vendor_stale"` |
| `fallback` | 命中最新快照回退 | `meta.fallback_mode==="latest_snapshot"` |
| `vendor_unavailable` | 接口返回但业务域整域缺失 | `meta.vendor_status==="vendor_unavailable"` |
| `explicit_miss` | 用户指定日无数据（而非最新日） | `source_version` 标识 explicit_miss |

### 6.2 API 设计

```tsx
<DataSection
  title="经营总览"
  state={adapterOutput.meta}    // DataSectionState 枚举 + 附加信息
  onRetry={() => refetch()}
  fallbackOverride?={<CustomFallback />}  // 页面定制
>
  <OverviewCards {...selectorOutput} />
</DataSection>
```

### 6.3 UI 模板

每种状态独立 UI 模板，不混用：

- `loading` — 骨架屏
- `error` — 红色边框 + 重试按钮 + 错误文案
- `empty` — 灰色卡片 + "暂无数据" + 跳转建议
- `stale` — 黄色角标 + "数据延迟至 X 日" + 仍渲染主体
- `fallback` — 橙色角标 + "已回退至最近可用日 X" + 仍渲染主体
- `vendor_unavailable` — 灰色占位卡 + "该业务域数据暂不可用" + 不渲染主体
- `explicit_miss` — 橙色卡 + "指定日 X 无数据，尝试其他日期" + 不渲染主体

### 6.4 迁移

Dashboard 和 PnlAttributionView 现有的 inline meta strip 全部归并进 DataSection；以 `meta` prop 控制状态，组件内部消除 inline `if (quality_flag !== "ok") ...`。

---

## 7. 两套口径强制区分（默认值 2A）

### 7.1 Contract 层

`ResultMeta` 新增必填字段：

```python
class ResultMeta(BaseModel):
    ...
    source_surface: Literal[
        "executive_analytical",   # 首页经营拆解用的 ProductCategoryPnlRepository；/ui/home/snapshot 也归此
        "formal_attribution",     # 归因工作台用的 formal FI + bond analytics
        "formal_pnl",
        "formal_balance",
        "formal_liability",
        "bond_analytics",
        "risk_tensor",
    ]
```

后端所有 envelope 构造强制带上该字段；CI lint 拒绝漏填。

### 7.2 UI 层

- DataSection header 必须展示 `source_surface` 对应的中文标签
- `source_surface ∈ {executive_analytical}` 的 section 必须用 `eyebrow="经营拆解"`（非"归因"）
- `source_surface ∈ {formal_attribution, ...}` 的 section 必须用 `eyebrow="正式归因"`（非"经营"）

### 7.3 文案 lint 规则

在 frontend 新增 `scripts/check_surface_naming.mjs`：

- `frontend/src/features/executive-dashboard/**` 和 `frontend/src/features/workbench/pages/DashboardPage.tsx` 内容不得出现字符串 `"归因"`（允许 `"贡献拆解"`）
- `frontend/src/features/pnl-attribution/**` 内容不得出现字符串 `"经营贡献"`
- CI 运行此 lint，违反即 fail

---

## 8. 符号与颜色修复（P1-4 / P2-1）

### 8.1 色彩单一出口

新增 `frontend/src/utils/tone.ts`：

```ts
export type Tone = "positive" | "neutral" | "warning" | "negative";

export const TONE_COLOR: Record<Tone, string> = {
  positive: "#2f8f63",
  negative: "#c1554b",
  warning: "#b35a16",
  neutral: "#6d7f99",
};

export function toneFromNumeric(n: Numeric): Tone { ... }
export function toneForStatus(status: string): Tone { ... }
```

- 组件**不得**局部定义颜色 map
- `PnlAttributionSection.chartToneColor` 和 `accentMap` 两个局部 map 直接删除，所有色彩从 `tone.ts::TONE_COLOR` 唯一派生
- 现有其他页面的局部颜色 map（如有）纳入 M1/M3 的对应波次清理

### 8.2 图表改造

- `PnlAttributionSection`：环形图改 **bipolar waterfall**（0 基线上下双向），去掉 `Math.abs`；列表条改 bipolar bar（0 居中、左负右正）
- `PnLCompositionChart`：饼图改 **bipolar waterfall** 或 **双轴条形图**；如果必须保留饼图作次视图，必须显式标题 "（绝对值构成占比）"
- `AttributionWaterfallChart`：已是 waterfall，审查是否还有 `Math.abs`

### 8.3 sign_aware 验证

每个 Numeric 字段在 schema 层声明 `sign_aware: bool`：
- sign_aware=true 的字段：adapter 保留符号、组件按 tone 渲染
- sign_aware=false 的字段：adapter 允许 abs，但 display 必须明确标"(绝对值)"

---

## 9. Fail Fast & Mock/Real 对拍（P0-1 终结）

### 9.1 Fail Fast

`frontend/src/api/client.ts::parseEnvMode`：

```ts
const parseEnvMode = (): DataSourceMode => {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (envValue === "real") return "real";
  if (envValue === "mock") return "mock";
  if (import.meta.env.PROD) {
    throw new Error(
      "VITE_DATA_SOURCE must be explicitly set to 'real' or 'mock' in production build."
    );
  }
  // dev / test 模式允许默认 mock，但输出警告
  console.warn("[client] VITE_DATA_SOURCE 未设置，dev 模式回落 mock；生产构建请显式声明。");
  return "mock";
};
```

### 9.2 Mock ↔ Schema 对拍

流程：

1. 后端 pydantic schema 通过 `datamodel-code-generator` 或手写桥自动导出 zod schema 到 `frontend/src/api/generated/zod/`
2. `mockClient` 的每个方法在开发/测试模式下，返回前 `.parse()` 过一遍对应 zod schema
3. 任何 shape 不一致 → 运行时抛错，CI 捕获

### 9.3 CI 检查

- `scripts/check_mock_contract.mjs`：启动 vitest，调用所有 mock 方法，断言每个返回值通过 zod parse
- 后端 `tests/test_frontend_contract_sync.py`：对比 pydantic schema 字段集与 contracts.ts 导出类型的字段集（字段名级别），不允许漂移

---

## 10. Testing 策略

### 10.1 单元：每个 adapter 5 场景

- 正常：raw=正常值，display 正确，tone 正确
- null：raw=null，display="—"，tone="neutral"
- 负数：raw=负数，display 带负号，tone="negative"（sign_aware=true 时）
- fallback：meta.fallback_mode="latest_snapshot"，DataSectionState="fallback"
- explicit_miss：meta 标识 explicit miss，DataSectionState="explicit_miss"

### 10.2 契约

- **Mock ↔ schema runtime**：所有 `mockClient` 输出 zod parse 通过（见 § 9.2）
- **Schema ↔ schema**：后端 pydantic 字段集 = 前端 TS 字段集（见 § 9.3）

### 10.3 集成：跨组件一致性

以 Dashboard 的 `aum` 为例：

```ts
it("aum raw number 在 card / chart / table 三处一致", () => {
  const payload = buildMockOverview();
  const vm = dashboardAdapter(payload);
  const cardSel = selectOverviewCards(vm);
  const chartSel = selectOverviewChart(vm);
  const tableSel = selectOverviewTable(vm);

  expect(cardSel.aum.raw).toBe(chartSel.aum.raw);
  expect(cardSel.aum.raw).toBe(tableSel.aum.raw);
});
```

### 10.4 E2E：7 种状态快照

每个受治理页面对 DataSection 的 7 种状态各有一条 Playwright 快照测试。

### 10.5 已有测试的迁移

git status 中已有的新增测试文件：

- `tests/test_pnl_attribution_workbench_contract.py` — 纳入 M1 契约测试基线
- `frontend/src/test/AdvancedAttributionChart.test.tsx`
- `frontend/src/test/PnlCompositionChart.test.tsx`
- `frontend/src/test/TPLMarketChart.test.tsx`

上述测试在 M1 / M3 中按 Numeric 迁移节奏同步升级，不另起炉灶。

---

## 11. 里程碑 3-Phase

| Phase | 周数 | 覆盖范围 | DoD |
|---|---|---|---|
| **M1 · 最小必做层** | 3-4 周 | executive + pnl_attribution 两页全链路 typed<br>adapter/selector/formatter 层落地<br>DataSection 组件族上线<br>P1-4 / P2-1 颜色与符号修复<br>fail fast<br>mock↔schema 对拍 | 两页 5 场景单元测试全绿<br>跨组件一致性集成测试全绿<br>vitest + playwright CI 绿 |
| **M2 · Snapshot & 口径** | 1-2 周 | `/ui/home/snapshot` 上线<br>Dashboard 切到 snapshot<br>`source_surface` 强制字段 + lint 上线<br>文案与 eyebrow 分离 | Dashboard 默认不再出现 mixed<br>严格/宽松两种模式 E2E 测试通过<br>naming lint CI 绿 |
| **M3 · 全仓扩展层** | 3-4 周 | bond-analytics / KRD / BondDashboard / PnL bridge / cashflow / liability 的 typed 升级<br>对应前端 adapter<br>回归测试 | 所有 governed 页面 contract 无 string-as-number 残留<br>相关 contract 对拍测试全绿 |

每个 Phase 结束必须通过主理 review 才进入下一个 Phase。

---

## 12. Composer 子任务拆分（详表）

5 波，共 **32 个子任务**。每波内部可并行（波次内子任务之间无依赖），**波次之间串行**（后一波依赖前一波合并）。

### 波次 1 · 基础设施（5 子任务，并行）

| # | 子任务 | 依赖 |
|---|---|---|
| 1.1 | 后端 `backend/app/schemas/common_numeric.py` + 单测 | - |
| 1.2 | 前端 `contracts.ts` 增加 `Numeric` type + zod schema 生成脚本 | - |
| 1.3 | 全局 `frontend/src/utils/format.ts` 集中化 + `tone.ts` + 单测 | - |
| 1.4 | `DataSection` 组件族（7 状态）+ 组件测试 | - |
| 1.5 | mock↔schema 对拍脚本 + CI 集成 | 1.1 / 1.2 |

### 波次 2 · Executive 升级（8 子任务）

| # | 子任务 | 依赖 |
|---|---|---|
| 2.1 | `schemas/executive_dashboard.py` 升级 Numeric（OverviewPayload / ExecutiveMetric / PnlAttributionPayload / AttributionSegment / RiskSignal） | 波次 1 |
| 2.2 | `services/executive_service.py` 的 Numeric 构造（沿用 effective_report_dates 语义） | 2.1 |
| 2.3 | 前端 `features/executive-dashboard/adapters/executiveDashboardAdapter.ts` + 5 场景单测 | 2.1 |
| 2.4 | `features/executive-dashboard/selectors/` + 跨组件一致性测试 | 2.3 |
| 2.5 | `OverviewSection` 改造（只读 view-model，`Math.*` 清零） | 2.3 / 2.4 |
| 2.6 | `PnlAttributionSection` 改造：删除 `chartToneColor`，环形 → bipolar waterfall，列表 → bipolar bar | 2.3 / 2.4 / 1.3 |
| 2.7 | Dashboard mock 同步升级 + mock↔schema 对拍 | 2.1 |
| 2.8 | Dashboard E2E 快照测试（7 状态 + 报告日切换 + mock/real 切换） | 2.5 / 2.6 |

### 波次 3 · PnL Attribution 升级（6 子任务）

| # | 子任务 | 依赖 |
|---|---|---|
| 3.1 | `schemas/pnl_attribution.py` 升级 Numeric（VolumeRate / TPL / Composition / Advanced / Campisi） | 波次 1 |
| 3.2 | `services/pnl_attribution_service.py` 的 Numeric 构造 | 3.1 |
| 3.3 | 前端 `features/pnl-attribution/adapters/pnlAttributionAdapter.ts` + 单测 | 3.1 |
| 3.4 | 5 个图表组件改造：VolumeRateAnalysisChart / TPLMarketChart / PnLCompositionChart / AdvancedAttributionChart / CampisiAttributionPanel | 3.3 |
| 3.5 | PnLCompositionChart 饼图 → bipolar waterfall（或加"绝对值占比"副标题） | 3.4 |
| 3.6 | PnL 页 mock 同步 + E2E 快照测试 | 3.2 / 3.4 |

### 波次 4 · Snapshot & 口径（5 子任务）

| # | 子任务 | 依赖 |
|---|---|---|
| 4.1 | 后端 `GET /ui/home/snapshot` 端点 + 严格/宽松模式 + 单测 | 波次 2 |
| 4.2 | `ResultMeta.source_surface` 字段 + 后端所有 envelope 强制填充 + 后端 lint | 波次 2 / 波次 3 |
| 4.3 | `DashboardPage` 切到 snapshot 消费，删除 mixed 分支 | 4.1 |
| 4.4 | `scripts/check_surface_naming.mjs` + CI 集成 | 4.2 |
| 4.5 | fail-fast 生产构建（`parseEnvMode` 升级）+ 构建脚本测试 | 波次 1 |

### 波次 5 · 全仓扩展层（8 子任务）

| # | 子任务 | 依赖 |
|---|---|---|
| 5.1 | bond-analytics schemas + 前端 contracts + adapter（portfolio headlines / top holdings / credit spread migration / analysis） | 波次 1 |
| 5.2 | KRD / cashflow-projection schemas + 前端 contracts + adapter | 波次 1 |
| 5.3 | BondDashboard schemas + 前端 contracts + adapter | 波次 1 |
| 5.4 | PnL bridge schemas + 前端 contracts + adapter | 波次 1 |
| 5.5 | Liability（risk/buckets / yield-metrics / counterparty / monthly / adb）schemas + adapter | 波次 1 |
| 5.6 | Benchmark excess / Action attribution / Accounting audit 等 bond-analytics 附属 payload | 5.1 |
| 5.7 | 以上 6 子任务对应的组件改造与 mock 同步 | 5.1-5.6 |
| 5.8 | 全仓 contract runtime 对拍测试 + CI 回归基线 | 5.1-5.7 |

### 12.1 Composer 协作协议

- 每个子任务由独立 composer subagent 执行，产出：
  - 代码变更 diff
  - 对应单元测试
  - 自测报告（`npm run typecheck && npm run test && npm run build` 或 pytest 全绿）
- 每个波次合并前由 Cursor Agent 主理审阅：
  - 检查是否越界（改到本波以外的文件）
  - 检查是否漏测试
  - 检查是否符合 § 2 分层约束
- 波次内部并行，波次之间严格串行

---

## 13. 风险与回滚

### 13.1 主要风险

| 风险 | 可能性 | 影响 | 缓解 |
|---|---|---|---|
| snapshot 严格日的交集为空（历史日都不齐） | 中 | 用户默认日看不到东西 | 提供"最近交集日 + 切宽松模式"的引导文案；M2 上线前先统计历史交集可用日分布 |
| 全仓 typed 升级破坏未迁移的小页面 | 高 | 小页面白屏 | zod runtime parse 会抛错，CI 捕获；逐页 migration，不一次性切换 |
| ProductCategoryPnlRepository 和 formal FI 的单位不一致被 Numeric 显式化后暴露出来 | 中 | 历史展示数字发生"视觉变化"（实际是把 bug 暴露） | 发布前做一次 before/after 数字对拍，差异大的字段单独列 migration note |
| composer 子任务越界乱改 | 低 | 波次合并失败 | 每个 composer prompt 明确声明"仅允许修改 path list X"，审阅阶段 diff 过滤 |

### 13.2 回滚策略

每个波次合并进 main 前打 tag：`numeric-correctness-w1-done` 等。回滚到上一个 tag 即可。contract 层升级采用 additive-only 策略（新字段并存老字段）直到前端全部切换完毕，不删字段直到 Phase 结束。

---

## 14. 口径不明遗留问题（需主理持续 review）

承接审计报告 § "口径不明确、不能靠代码猜"：

1. ✅ Dashboard authoritative `report_date` → 由 `/ui/home/snapshot` 决定（默认严格日、允许宽松覆盖）
2. ✅ 经营贡献 vs 损益归因 两套口径 → 允许并存，通过 `source_surface` + naming lint 强制区分
3. 🟡 Overview 四卡混合业务域 → snapshot 模式下统一报告日；非 snapshot 残留端点仍混合，将在 M2 下线观察后删除
4. ✅ Executive 是否接受字符串 contract → 否，全面升级 Numeric

---

## 15. 附录

- 审计原文：`docs/frontend_audit_report.md`
- 本设计 delta（基于 2026-04-18 git working tree）验证过 11 条审计断言，其中 P1-1 / P1-2 / P1-3 今天已经修复/规避，其余为本设计覆盖范围
- composer prompt 模板将在 design doc 通过 review 后以 `docs/superpowers/plans/2026-04-18-frontend-numeric-correctness-plan.md` 和 `docs/superpowers/plans/composer/wave-<N>/<task-id>.md` 形式落地，由 `writing-plans` skill 生成
