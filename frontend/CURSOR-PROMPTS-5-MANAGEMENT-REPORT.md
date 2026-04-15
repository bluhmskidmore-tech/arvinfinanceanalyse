# Prompt 5：管理报告 ManagementReport

## 任务
在 V3 前端 `F:/MOSS-V3/frontend/` 补建「管理报告」页面，完全对齐 V1 的功能。

## V3 架构模式
同 Prompt 1。

---

## 一、TypeScript 类型定义（追加到 contracts.ts）

```typescript
/** 管理报告 */
export type ManagementReportPeriodType = "MONTH" | "QUARTER" | "YEAR";
export type ManagementReportStatus = "pending" | "generating" | "succeeded" | "failed";

export type ManualSection = {
  title: string;
  bullets: string[];
  notes: string;
};

export type ManagementReportCreateRequest = {
  report_date: string;
  period_type: ManagementReportPeriodType;
  owner_id: number;
  manual_sections: Record<string, ManualSection>;
};

export type ManagementReportCreateResponse = {
  report_id: string;
  status: ManagementReportStatus;
};

export type ManagementReportStatusResponse = {
  report_id: string;
  status: ManagementReportStatus;
  progress?: number | null;
  error?: string | null;
  updated_at?: string | null;
};

export type ManagementReportManualInputRequest = {
  report_date: string;
  period_type: ManagementReportPeriodType;
  owner_id: number;
  sections: Record<string, ManualSection>;
};

export type ManagementReportManualInputResponse = {
  report_date: string;
  period_type: ManagementReportPeriodType;
  owner_id: number;
  sections: Record<string, ManualSection>;
  exists: boolean;
  updated_at?: string | null;
};

export type ManagementReportMeta = {
  report_id?: string;
  report_type?: string;
  period_type?: ManagementReportPeriodType;
  period_label?: string;
  requested_report_date?: string;
  actual_report_date?: string;
  period_start_date?: string;
  period_end_date?: string;
  owner_id?: number;
  owner_name?: string;
  generated_at?: string;
};

export type ManagementReportConsistencyCheck = {
  status: string;           // "ok" | "warning" | "error"
  message: string;
  values: string[];
  affected_sources: string[];
};

export type ManagementReportSourceStatus = {
  status: string;           // "ok" | "warning" | "error" | "pending"
  required: boolean;
  data_date?: string | null;
  scope_basis?: string | null;
  scope_label?: string | null;
  period_basis?: string | null;
  period_label?: string | null;
  owner_scope_supported?: boolean;
  notes?: string | null;
};

export type ManagementReportDataQuality = {
  readiness: string;        // "green" | "yellow" | "red"
  completeness_score: number; // 0-100
  warnings: string[];
  source_status: Record<string, ManagementReportSourceStatus>;
  fallback_flags: Record<string, boolean>;
  manual_pending: boolean;
  consistency_checks?: Record<string, ManagementReportConsistencyCheck>;
  scope_mismatch?: boolean;
  period_mismatch?: boolean;
};

export type ManagementReportJson = {
  meta: ManagementReportMeta;
  data_quality: ManagementReportDataQuality;
  decision_summary?: unknown | null;
  automated: Record<string, unknown>;
  manual_sections: Record<string, ManualSection>;
  narrative: Record<string, unknown>;
};
```

---

## 二、API 调用清单

| 用途 | V1 URL | 方法 | 参数/Body | 返回类型 | client.ts 方法名 |
|------|--------|------|-----------|----------|-----------------|
| 创建报告 | `POST /api/management-report` | POST | `ManagementReportCreateRequest` | `ManagementReportCreateResponse` | `createManagementReport(req)` |
| 查询状态 | `GET /api/management-report/{reportId}` | GET | reportId | `ManagementReportStatusResponse` | `getManagementReportStatus(reportId)` |
| 获取JSON | `GET /api/management-report/{reportId}/json` | GET | reportId | `ManagementReportJson` | `getManagementReportJson(reportId)` |
| 获取HTML | `GET /api/management-report/{reportId}/html` | GET | reportId | `string`（HTML） | `getManagementReportHtml(reportId)` |
| 读取人工补录 | `GET /api/management-report/manual-input` | GET | `?report_date=&period_type=&owner_id=` | `ManagementReportManualInputResponse` | `getManagementManualInput(params)` |
| 保存人工补录 | `PUT /api/management-report/manual-input` | PUT | `ManagementReportManualInputRequest` | `ManagementReportManualInputResponse` | `saveManagementManualInput(req)` |
| 获取 Owner 列表 | `GET /api/kpi/owners` | GET | `?year=&is_active=true` | `{ owners: KpiOwner[] }` | 复用已有的 KPI owner 接口 |

---

## 三、核心业务逻辑

### 报告生成轮询（4 秒间隔）
```typescript
// 1. 用户点击"生成报告"按钮
// 2. POST /api/management-report 创建报告，获得 report_id
// 3. 每 4 秒轮询 GET /api/management-report/{report_id} 查询状态
// 4. status === "succeeded" 时停止轮询，加载 JSON 和 HTML
// 5. status === "failed" 时停止轮询，显示错误

const POLL_INTERVAL_MS = 4000;

const pollStatus = async (reportId: string) => {
  const resp = await getManagementReportStatus(reportId);
  if (resp.status === 'succeeded') {
    stopPolling();
    // 并行加载 JSON 和 HTML
    const [json, html] = await Promise.all([
      getManagementReportJson(reportId),
      getManagementReportHtml(reportId),
    ]);
    setReportJson(json);
    setHtmlPreview(html);
  } else if (resp.status === 'failed') {
    stopPolling();
    setError(resp.error || '报告生成失败');
  }
  // pending/generating 继续轮询
};
```

### 人工补录四个章节
```typescript
const SECTION_ORDER = ['audit_compliance', 'systems_projects', 'team_review', 'next_period_plan'];
const SECTION_TITLES = {
  audit_compliance: '审计合规与风控',
  systems_projects: '系统与项目进展',
  team_review: '团队复盘',
  next_period_plan: '下期重点计划',
};
// 每个章节有：title（可编辑）、bullets（多行文本，每行一条）、notes（备注文本）
```

### 数据源状态检查
```typescript
const SOURCE_ORDER = ['kpi', 'operations', 'portfolio', 'risk_return', 'manual_sections'];
const SOURCE_TITLES = {
  kpi: 'KPI',
  operations: '经营复盘',
  portfolio: '组合概览',
  risk_return: '风险收益',
  manual_sections: '人工补录',
};
// 每个数据源有：status（ok/warning/error/pending）、scope_label、period_label、owner_scope_supported、data_date、notes
```

### 数据质量评分
```typescript
// readiness: "green" | "yellow" | "red"
// completeness_score: 0-100
// consistency_checks: scope_alignment + period_alignment
// 状态颜色映射：
//   ok/green/succeeded → 绿色
//   warning/yellow/partial/pending/generating → 黄色
//   其他 → 红色
```

---

## 四、页面布局

单页面，无 Tab。

布局从上到下：

1. **控制栏**
   - 报告日期选择器（默认当前 reportDate）
   - 期间类型选择：月度 / 季度 / 年度（默认 MONTH）
   - Owner 选择器（从 KPI owners 接口获取）
   - "生成报告"按钮（生成中显示 Spin + 进度）
   - "保存人工补录"按钮

2. **人工补录区域**（4 个章节卡片，2×2 网格）
   - 每个章节：
     - 区块标题（input，可编辑）
     - Bullets（textarea，每行一条）
     - Notes（textarea）
   - 章节：审计合规与风控 | 系统与项目进展 | 团队复盘 | 下期重点计划

3. **口径与校验**（Card）
   - 4 列 KPI：Readiness 状态 | 完整度(%) | Scope 对齐 | Period 对齐
   - 2 列：Scope 对齐详情 | Period 对齐详情
     - 每个详情块：状态徽章 + 消息 + 当前值列表 + 受影响区块列表
   - 2 列：5 个数据源状态卡片
     - 每个卡片：标题 + 状态徽章 + scope_label + period_label + Owner过滤支持 + 数据日期 + 备注
   - 统一告警列表

4. **HTML 预览**（Card）
   - 标题：`HTML 预览`
   - "下载 HTML" 按钮 + "下载 JSON" 按钮
   - iframe 或 dangerouslySetInnerHTML 渲染 HTML 内容

---

## 五、交互逻辑

1. **生成报告流程**：
   - 点击"生成报告" → POST 创建 → 轮询状态（4s）→ 成功后加载 JSON+HTML
   - 生成中禁用按钮，显示 Spin
2. **保存人工补录**：
   - 点击"保存" → PUT manual-input → 成功提示
3. **Owner 切换**：
   - 切换后重新加载人工补录数据
4. **期间类型切换**：
   - 切换后重新加载人工补录数据
5. **HTML/JSON 下载**：
   - HTML：创建 Blob 下载
   - JSON：`JSON.stringify(reportJson, null, 2)` 下载

---

## 六、业务口径说明

1. 报告期间：MONTH=月度、QUARTER=季度、YEAR=年度
2. Owner：KPI 考核对象（投资经理），报告按 Owner 维度生成
3. 数据源：KPI（绩效指标）、经营复盘（经营数据）、组合概览（持仓数据）、风险收益（风险指标）、人工补录（手动输入）
4. Scope 对齐：检查各数据源的范围是否一致
5. Period 对齐：检查各数据源的期间是否一致
6. `只要混口径，就不会被当成绿色正式版`

---

## 七、路由和导航注册

routes.tsx:
```typescript
const ManagementReportPage = lazy(() => import("../features/management-report/pages/ManagementReportPage"));
if (section.path === "/management-report") {
  return { path: section.path.slice(1), element: routeElement(<ManagementReportPage />) };
}
```

navigation.ts:
```typescript
{
  key: "management-report",
  label: "管理报告",
  path: "/management-report",
  icon: "reports",
  description: "管理报告生成工作台：数据源检查、人工补录、HTML/JSON 导出",
  readiness: "live",
  readinessLabel: "Live",
  readinessNote: "已接管理报告生成链路。",
},
```
