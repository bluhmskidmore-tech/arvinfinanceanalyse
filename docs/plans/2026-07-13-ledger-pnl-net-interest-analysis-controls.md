# Ledger PnL Net Interest Analysis Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `/ledger-pnl` 的净息贡献项科目穿透可以直接回答“哪些科目影响最大、当前视图包含什么、证据在哪”，同时维持后端金额、勾稽和排序为唯一财务真值。

**Architecture:** 保留现有 component-detail API 与严格契约模型。模型只补充后端原序位和显示所需的原始字段，并提供不改变顺序的文本/状态筛选；独立页面局部导出模块把当前筛选行序列化为 CSV，原样保留 API Decimal 字符串和三期来源证据。抽屉负责交互状态、下载和复制定位，不计算金额、不合计、不重排。

**Tech Stack:** React 19, TypeScript, TanStack Query, Ant Design, Vitest, Testing Library, CSS

---

## 业务边界

- 本轮页面：`/ledger-pnl?report_date=2026-06-30` 的“净息贡献项科目穿透”抽屉。
- 主问题：哪些科目按后端贡献顺序影响该净息构成项，当前筛选结果和三期来源定位是什么。
- 后端真值：`rows` 已按“contributing 优先、贡献绝对值降序、科目代码”排列；前端只保序展示。
- 禁止：前端 Decimal 转数值、减法、乘法、合计、贡献重算、勾稽重算或重新排序。
- 治理边界继续显示：候选口径、`formal_use_allowed=false`、`certification_effect=none`、`driver_status=unclear`；导出不得暗示正式认证。
- 不触碰：微贷数据缺口、后端公式/API、数据库、权限、调度、缓存、全局状态与无关页面。

### Task 1: 锁定筛选与后端序位模型

**Files:**
- Modify: `frontend/src/features/ledger-pnl/models/candidateNetInterestComponentDetailModel.ts`
- Test: `frontend/src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts`

**Step 1: Write the failing test**

- 断言 available 行携带稳定的后端序位、原始 Decimal 字符串、规则权重和来源证据。
- 断言状态筛选与科目代码/名称搜索不改变后端相对顺序。
- 断言空查询、大小写和前后空格行为；筛选不得解析金额或排序。

**Step 2: Run test to verify it fails**

Run: `npm test -- --run src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts`

Expected: 新导出类型/筛选器或字段尚不存在而失败。

**Step 3: Write minimal implementation**

- 扩充行视图所需的原样字段，移除组件通过数组下标回查 payload 的耦合。
- 新增纯筛选函数：按 code/name 做文本匹配，按 `all | contributing | excluded_offset` 做状态筛选，使用 `Array.filter` 保序。
- 后端序位由 API 数组位置形成显示标签；不读取贡献字符串进行比较。

**Step 4: Run test to verify it passes**

Run: `npm test -- --run src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts`

Expected: PASS。

### Task 2: 生成可追溯的当前视图 CSV

**Files:**
- Create: `frontend/src/features/ledger-pnl/models/candidateNetInterestComponentDetailExport.ts`
- Create: `frontend/src/test/LedgerPnlCandidateNetInterestComponentDetailExport.test.ts`

**Step 1: Write the failing test**

- 断言文件名包含报告月与指标 ID 的安全片段。
- 断言 UTF-8 BOM、RFC 风格引号转义、当前筛选行数和后端行顺序。
- 断言金额列使用 API 原始 Decimal 字符串，来源列含三期 `file/sheet/cell/row/hash/lock`。
- 断言治理字段明确为候选、不可正式使用、无认证效力、原因待解释。

**Step 2: Run test to verify it fails**

Run: `npm test -- --run src/test/LedgerPnlCandidateNetInterestComponentDetailExport.test.ts`

Expected: 导出模块尚不存在而失败。

**Step 3: Write minimal implementation**

- 构造 `{ filename, content }`，所有金额均从 payload/row 原样写出。
- CSV 单元格统一转义，内容加入 BOM；下载创建并及时回收 object URL。
- 提供单条来源定位文本构造器，供 CSV 与复制按钮共用。

**Step 4: Run test to verify it passes**

Run: `npm test -- --run src/test/LedgerPnlCandidateNetInterestComponentDetailExport.test.ts`

Expected: PASS。

### Task 3: 在抽屉加入分析操作与空结果闭环

**Files:**
- Modify: `frontend/src/features/ledger-pnl/components/LedgerPnlNetInterestComponentDetailDrawer.tsx`
- Modify: `frontend/src/features/ledger-pnl/components/LedgerPnlNetInterestComponentDetailDrawer.css`
- Test: `frontend/src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx`

**Step 1: Write the failing test**

- 断言首屏说明“后端贡献影响顺序”，行显示稳定序位。
- 断言可按代码/名称搜索并按计入/抵销状态筛选，结果计数准确且相对顺序不变。
- 断言无匹配时出现显式空态和重置操作。
- 断言“导出当前视图”下载的行与筛选结果一致。
- 断言每期来源可复制，成功/失败有可访问反馈。
- 断言 loading/error/stale/not-evaluable/failed 原有 fail-closed 行为不回退。

**Step 2: Run test to verify it fails**

Run: `npm test -- --run src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx`

Expected: 新控件与交互尚不存在而失败。

**Step 3: Write minimal implementation**

- 使用页面局部 state 管理搜索词、状态筛选与复制反馈；切换 selection 时不展示旧结果。
- 操作条只在 available 状态出现；展示“当前 N / 共 M 条”和后端排序声明。
- 表格使用筛选后的行视图，贡献序位保留 API 原位置；抵销行明确不参与贡献排名。
- 导出当前筛选视图；无结果时禁用导出并提供重置。
- 来源块强化 `综本!单元格`，提供复制定位，不尝试从浏览器打开本地工作簿。

**Step 4: Run test to verify it passes**

Run: `npm test -- --run src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx`

Expected: PASS。

### Task 4: 独立审查与浏览器闭环

**Files:**
- Review only the files from Tasks 1–3 and this plan.

**Step 1: Spec review**

- 独立子代理逐条核对业务边界、TDD 验收点、状态闭环和导出字段。
- 发现偏差先修复，再复审。

**Step 2: Code-quality review**

- 独立子代理检查 Decimal 保真、索引耦合、CSV 注入/转义、URL 回收、可访问性和 CSS 债务。
- 发现问题先修复，再复审。

**Step 3: Run narrow validation**

Run:

```powershell
npm test -- --run src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts src/test/LedgerPnlCandidateNetInterestComponentDetailExport.test.ts src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx
npm run typecheck
npx eslint src/features/ledger-pnl/models/candidateNetInterestComponentDetailModel.ts src/features/ledger-pnl/models/candidateNetInterestComponentDetailExport.ts src/features/ledger-pnl/components/LedgerPnlNetInterestComponentDetailDrawer.tsx src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts src/test/LedgerPnlCandidateNetInterestComponentDetailExport.test.ts src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx
npm run debt:audit
npm run build
```

Expected: 全部通过，债务基线不增长。

**Step 4: Browser verification**

- 在 `http://localhost:5888/ledger-pnl?report_date=2026-06-30` 验证桌面与窄屏。
- 验证抽屉打开、搜索、两类筛选、空态重置、导出按钮、来源复制、关闭和控制台错误。
- 核对 API 响应→模型→筛选→表格/CSV 的同一行金额、单位、月份与来源。

**Step 5: Pre-commit scope check**

- 仅暂存本计划和 Tasks 1–3 文件。
- 运行 GitNexus `detect-changes`，确认仅影响净息穿透明细视图。
- 不纳入工作区其他既有改动。
