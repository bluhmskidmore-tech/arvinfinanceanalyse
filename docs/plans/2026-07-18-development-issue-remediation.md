# Development Issue Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用最小、可回滚的改动修复已证实的开发缺陷，恢复后端合同回归、三个浏览器回归、结果元数据一致性，以及 GitNexus/Hermes 运行时可靠性。

**Architecture:** 按页面或工作流分批处理，测试先行，每个问题一个原子提交。共享 formal result runtime 已经具备所需字段，本计划不修改共享 runtime，也不引入数据库、认证、调度器或全局状态架构变更；日期和 fallback 语义仅在各调用方合同确认后补齐。

**Tech Stack:** Python 3、FastAPI、DuckDB、pytest、React 18、TypeScript、Vitest、Playwright、CSS design tokens、JSON-RPC/MCP subprocess transport。

---

Status label: supporting

本计划是实施辅助材料，不覆盖 AGENTS.md、docs/DOCUMENT_AUTHORITY.md 或当前有效入口文件。

## 范围

纳入：

- balance-movement dates 合同测试夹具
- Product Category PnL 对比度
- bond-analysis 到 bond-trading-desk 下钻
- monthly operating analysis real/mock 浏览器契约
- balance、PnL bridge、yield curve 的日期与 fallback 元数据
- balance mock 非法金额的 fail-fast 行为
- GitNexus MCP 多帧读取
- Hermes bridge 配置变化后的受控重启
- 与上述改动直接相关的文档和 registry 漂移

不纳入：

- 数据新鲜度回补、风险数据修复、凭据轮换
- 数据库 schema、认证框架、调度器、缓存基座
- frontend/src/api/client.ts 扩张
- 全站视觉重构、存量硬编码颜色清理
- 未经合同确认的业务指标或日期推断

## 实施前提

1. 在最新目标分支的新 worktree 中执行，不在当前脏工作树上直接修复。
2. 记录起始 HEAD 和 git status。
3. 修改任何现有函数、类或方法前，先对精确符号运行 GitNexus upstream impact。
4. 如果 GitNexus MCP/CLI 不可用，只可执行测试夹具和纯 CSS 等不涉及共享符号的任务；共享/业务调用方任务暂停并记录限制。
5. 每个任务完成后运行 gitnexus_detect_changes；确认只影响预期符号和流程后再提交。

## 批次与预估

| 批次 | 内容 | 预估 |
|---|---|---:|
| A | 回归测试恢复：fixture、对比度、monthly smoke、bond drill | 1–1.5 天 |
| B | 页面本地合同：balance/PnL/yield meta、balance mock | 1.5–2 天，受合同确认影响 |
| C | Agent 运行时：GitNexus framing、Hermes lifecycle | 1.5–2 天 |
| D | registry/docs、全量验证、交付证据 | 0.5 天 |

单人净开发约 4–6 天。批次 A 可立即开始；批次 B 的 PnL/yield 部分有合同闸门；批次 C 可与批次 A 并行，但每个文件保持独立所有权。

### Task 0: 建立可重复基线

**Files:**

- Read: AGENTS.md
- Read: docs/agent_codebase_map.md
- Read: frontend/CLAUDE.md
- Read: backend/app/AGENTS.md

**Step 1: 建立干净 worktree**

从目标基线创建独立分支，建议名称：

~~~text
codex/development-audit-remediation
~~~

**Step 2: 记录已知失败**

Run:

~~~powershell
pytest tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result --maxfail=1 -q
~~~

Expected: balance-movement-analysis/dates 参数实例失败，返回 503。

Run from frontend:

~~~powershell
npx playwright test -c playwright.config.mjs tests/playwright/a11y-visual-smoke.spec.mjs --grep "product-category-pnl"
npx playwright test -c playwright.config.mjs tests/playwright/bond-trading-desk-drill.spec.mjs
npx playwright test -c playwright.config.mjs tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs
~~~

Expected: 三项分别复现对比度、下钻链接和 real-mode 标签失败。

**Step 3: 不提交**

此任务只生成基线记录。

### Task 1: 修复 balance-movement dates 合同测试夹具

**Tier:** 测试本地，不修改生产逻辑。

**Files:**

- Modify: tests/test_result_meta_on_all_ui_endpoints.py:181
- Test: tests/test_result_meta_on_all_ui_endpoints.py
- Test: tests/test_accounting_asset_movement_api.py

**Step 1: 先运行现有失败测试**

使用 Task 0 的精确 pytest 命令，确认失败来自不存在的只读 DuckDB 文件。

**Step 2: 添加最小空库夹具**

在现有 balance-analysis seed helper 旁添加：

~~~python
def _seed_balance_movement_dates_contract_surface(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.close()
~~~

在 balance-movement path 分支中，先调用 seed，再授予 read scope：

~~~python
if path == "/ui/balance-movement-analysis/dates":
    _seed_balance_movement_dates_contract_surface(tmp_path)
    _grant_balance_movement_read_scope(tmp_path, monkeypatch)
~~~

不要修改 repository 的 read_only=True，也不要把“数据库文件不存在”在生产代码中吞成空数据。

**Step 3: 验证**

Run:

~~~powershell
pytest tests/test_result_meta_on_all_ui_endpoints.py -q
pytest tests/test_accounting_asset_movement_api.py -q
~~~

Expected: 全部通过；空库仍返回 200 + 空 dates envelope。

**Step 4: Commit**

~~~text
test(balance-movement): seed empty duckdb for dates contract
~~~

### Task 2: 修复 Product Category PnL 对比度

**Tier:** Tier 1 visual-only。

**Files:**

- Modify: frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css:5352
- Test: frontend/tests/playwright/a11y-visual-smoke.spec.mjs

**Step 1: 复现 axe 失败**

确认 selector product-category-formal-readiness__driver-row > strong.is-negative 的对比度为 4.49:1。

**Step 2: 使用已有 token 做最小修改**

~~~css
.product-category-formal-readiness__driver-row > strong.is-negative {
  color: var(--moss-color-danger-700);
}
~~~

不修改全局 danger token，不调整正负值业务语义。

**Step 3: 验证**

Run from frontend:

~~~powershell
npx playwright test -c playwright.config.mjs tests/playwright/a11y-visual-smoke.spec.mjs --grep "product-category-pnl"
npm run lint
npm run debt:audit
~~~

Expected: axe critical/serious violations为空；lint 无新增 warning；debt baseline 不增长。

**Step 4: Commit**

~~~text
fix(product-category-pnl): raise negative value contrast
~~~

### Task 3: 修复 Monthly Operating Analysis 的 real/mock 测试错配

**Tier:** 测试基础设施，不改页面业务含义。

**Files:**

- Modify: frontend/tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs:3
- Modify: tests/test_frontend_playwright_smoke_scaffold.py
- Reference: frontend/playwright.config.mjs:6
- Reference: frontend/tests/playwright/product-category-pnl-desktop-states.spec.mjs:7

**Root cause:** Playwright runner 在 VITE_DATA_SOURCE 未设置时把 spec 判为 real，但它访问的主 webServer 默认以 mock 启动；真正的 real client server 是 state port。

**Step 1: 增加 scaffold 失败断言**

在 Python scaffold test 中要求 monthly spec 使用 MOSS_PLAYWRIGHT_STATE_BASE_URL 和 MOSS_PLAYWRIGHT_STATE_PORT。

**Step 2: 复用现有 real-state URL 模式**

~~~javascript
const REAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? "http://127.0.0.1:" + (process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889")
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
~~~

probe REAL_STATE_BASE_URL，并使用绝对 URL 打开页面：

~~~javascript
const targetUrl = new URL(
  "/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=202603",
  REAL_STATE_BASE_URL,
);
await page.goto(targetUrl.toString(), { waitUntil: "domcontentloaded" });
~~~

移除仅依赖 runner 端 dataSource 的错误 real 判定；保留真实 API route mocks。

**Step 3: 验证**

Run:

~~~powershell
pytest tests/test_frontend_playwright_smoke_scaffold.py -q
npx playwright test -c playwright.config.mjs tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs
~~~

Expected: 页面显示“正式接口链路”，且 dates/manual-adjustments route 均被调用。

**Step 4: Commit**

~~~text
test(product-category-pnl): run monthly audit smoke on real state server
~~~

### Task 4: 关闭 bond-analysis 下钻回归

**Tier:** 先测试诊断；只有证据指向页面数据链时才升级到 Tier 2。

**Files:**

- Modify: frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx
- Modify if browser-only: frontend/tests/playwright/bond-trading-desk-drill.spec.mjs
- Modify only if unit test fails: frontend/src/api/bondAnalyticsClient.ts:1068
- Modify only if unit test fails: frontend/src/mocks/bondTradingDeskDrillFixtures.ts
- Modify only if unit test fails: frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx:1353

**Step 1: 添加组件路径回归测试**

~~~typescript
it("renders the mock trading-desk link inside the raw holdings grid", async () => {
  renderCockpit(createApiClient({ mode: "mock" }));

  const grid = await screen.findByTestId("bond-analysis-holdings-raw-grid");
  const link = await within(grid).findByTestId("bond-trading-desk-link-230210.IB");

  expect(link).toHaveAttribute(
    "href",
    expect.stringContaining("/bond-trading-desk?bond_code=230210.IB"),
  );
});
~~~

**Step 2: 运行测试并执行决策**

Run:

~~~powershell
npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx
~~~

- 如果失败：沿 createApiClient(mock) → getBondAnalyticsTopHoldings → topHoldings → HoldingRows 修复第一个断点。
- 如果通过：组件和 mock fixture 合同正确，只修 Playwright server/mode/日期选择，不改生产组件。

不得为了让测试通过而把 230210.IB 硬编码进组件。

**Step 3: 增强浏览器断言**

在找链接之前，先断言 holdings evidence strip 显示 1 条；这样失败能区分“数据没进入组件”和“链接没渲染”。

**Step 4: 验证**

Run:

~~~powershell
npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx
npx playwright test -c playwright.config.mjs tests/playwright/bond-trading-desk-drill.spec.mjs
npm run typecheck
npm run debt:audit
~~~

Expected: mock holding 出现在 raw grid，href 保留 bond_code 和 report_date，下钻页可见。

**Step 5: Commit**

~~~text
fix(bond-analysis): restore trading-desk drill contract
~~~

### Task 5: 补齐 Balance Analysis 日期元数据

**Tier:** Tier 2 caller-local。

**Files:**

- Modify: backend/app/services/balance_analysis_service.py:447
- Test: tests/test_balance_analysis_api.py
- Test: tests/test_balance_analysis_service.py
- Do not modify: backend/app/services/formal_result_runtime.py

**Step 1: 运行 impact 和合同证据检查**

对 balance_analysis_overview_envelope 及被修改调用方运行 upstream impact。通过 metric-contract/lineage evidence 确认 date_basis 字符串；不要自行创造新口径。

**Step 2: 写失败测试**

测试必须断言：

- requested_report_date 等于请求日期
- resolved_report_date 和 as_of_date 等于 payload.report_date
- fallback_date 为 null
- date_basis 等于已确认合同值

**Step 3: 仅在调用方传参**

~~~python
env = build_formal_result_envelope_from_lineage(
    # existing lineage arguments
    requested_report_date=report_date,
    resolved_report_date=str(overview["report_date"]),
    as_of_date=str(overview["report_date"]),
    date_basis=CONFIRMED_BALANCE_DATE_BASIS,
    fallback_date=None,
    result_payload=payload.model_dump(mode="json"),
)
~~~

CONFIRMED_BALANCE_DATE_BASIS 必须由现有合同确认后替换，不在实现时猜测。

**Step 4: 验证并提交**

~~~powershell
pytest tests/test_balance_analysis_service.py tests/test_balance_analysis_api.py -q
~~~

Commit:

~~~text
fix(balance-analysis): expose report date provenance
~~~

### Task 6: 分别统一 PnL bridge 与 Yield Curve fallback 元数据

**Tier:** 两个独立 Tier 2 提交；不得合并为共享 runtime 改动。

**Files:**

- Modify: backend/app/services/pnl_bridge_service.py:213
- Test: tests/test_pnl_api_contract.py
- Modify: backend/app/services/yield_curve_term_structure_service.py:159
- Test: tests/test_yield_curve_term_structure_api.py
- Do not modify: backend/app/services/formal_result_runtime.py
- Do not modify: backend/app/schemas/result_meta.py

**Contract decision gate:**

在写实现前形成并批准以下矩阵：

| Surface | requested | resolved | as_of | fallback_date | fallback quality |
|---|---|---|---|---|---|
| PnL bridge | 业务报告日 | 待确认 | 待确认 | 多曲线时待确认 | stale / warning 待确认 |
| Yield curve | 请求日 | 单曲线或共同解析日 | 待确认 | 多曲线时待确认 | 当前为 stale |

如果多个 curve_type 解析到不同 fallback 日期，不允许把其中任意一个日期冒充统一 resolved/fallback_date。合同未确认时，本任务 BLOCK，但不阻塞其他任务。

**Step 1: 分别写失败测试**

- PnL 测试覆盖 no fallback、latest snapshot、vendor unavailable。
- Yield 测试覆盖 exact date、单一 fallback、多曲线不同 fallback。
- 测试同时断言 quality_flag、vendor_status、fallback_mode 与日期字段。

**Step 2: 在各自 builder 中补齐**

只使用服务已经计算出的 requested/resolved/fallback evidence。PnL 的 quality_flag 不再仅由 summary 覆盖 fallback 严重度；具体合并规则以批准矩阵为准。

**Step 3: 分别验证、分别提交**

~~~powershell
pytest tests/test_pnl_api_contract.py -q -k "pnl_bridge"
pytest tests/test_yield_curve_term_structure_api.py -q
~~~

Commits:

~~~text
fix(pnl-bridge): align fallback quality and date provenance
fix(yield-curve): expose resolved fallback dates
~~~

### Task 7: 让 balance mock 非法金额 fail fast

**Tier:** Tier 2 mock/client-local。

**Files:**

- Modify: frontend/src/api/balanceAnalysisClient.ts:201
- Test: frontend/src/test/ApiClient.test.ts
- Do not modify: frontend/src/api/client.ts

**Step 1: 写解析器失败测试**

将 parser 作为 domain-module export 直接测试：

~~~typescript
expect(parseBalanceAmount("12.50")).toBe(12.5);
expect(() => parseBalanceAmount("N/A")).toThrow("Invalid mock balance amount");
expect(() => parseBalanceAmount("12oops")).toThrow("Invalid mock balance amount");
~~~

**Step 2: 实现严格解析**

~~~typescript
export function parseBalanceAmount(
  raw: BalanceAnalysisTableRow[BalanceAnalysisAmountField],
): number {
  const parsed = Number(String(raw));
  if (!Number.isFinite(parsed)) {
    throw new Error("Invalid mock balance amount: " + String(raw));
  }
  return parsed;
}
~~~

该行为只约束开发 mock，不改变真实 API 的 null/invalid 展示合同。

**Step 3: 验证**

~~~powershell
npm run test -- src/test/ApiClient.test.ts
npm run typecheck
npm run debt:audit
~~~

Expected: 正常 mock 汇总不变，非法值不再静默归零。

**Step 4: Commit**

~~~text
fix(balance-analysis): fail fast on invalid mock amounts
~~~

### Task 8: 修复 GitNexus MCP 多帧读取

**Tier:** Tier 3 shared agent plumbing。

**Files:**

- Modify: backend/app/services/gitnexus_mcp_client.py:34
- Create: tests/test_gitnexus_mcp_client.py

**Step 1: Impact gate**

对 GitNexusMcpClient、_GitNexusMcpSession._request、_GitNexusMcpSession._read_message 运行 upstream impact。若为 HIGH/CRITICAL，先发出影响警告再继续。

**Step 2: 写三个失败测试**

1. 一个 read chunk 同时包含 notification + matching response。
2. response body 后紧跟下一完整 frame，第二次读取不得丢失。
3. notification 无 id 时 _request 必须跳过；真正错误 id 仍应报错。

**Step 3: 持久化接收 buffer**

在 session 初始化时添加：

~~~python
self._read_buffer = bytearray()
~~~

_read_message 每次只消费一个完整 frame，并把余下字节留在 _read_buffer；_request 循环读取，跳过没有 id 的 notification，直到取得 matching request id。

不得用一次 read 后丢弃 rest，也不得无限跳过带错误 id 的 response。

**Step 4: 验证**

~~~powershell
pytest tests/test_gitnexus_mcp_client.py -q
pytest tests/test_agent_intent_routing.py -q
~~~

Expected: 多帧和 notification 测试通过，既有 GitNexus agent 路径无回归。

**Step 5: Commit**

~~~text
fix(agent): preserve and route gitnexus mcp frames
~~~

### Task 9: 让 Hermes bridge 受配置签名约束

**Tier:** Tier 3 shared agent runtime。

**Files:**

- Modify: backend/app/services/hermes_agent_service.py:27
- Test: tests/test_hermes_agent_service.py

**Step 1: Impact gate**

对 _ensure_hermes_bridge、warm_hermes_bridge_if_configured、run_hermes_agent 运行 upstream impact。

**Step 2: 写失败测试**

- 相同配置 + 健康 managed process：不重启。
- managed process 存活但 URL/model/toolsets/max_turns 改变：终止旧进程并启动新进程。
- 外部健康 bridge、没有本进程所有权：不得终止外部服务。
- 旧进程退出：清空保存的配置签名。

**Step 3: 添加不可变配置签名**

建议使用 frozen dataclass，字段仅包含启动行为所依赖的配置：

~~~python
@dataclass(frozen=True)
class HermesBridgeConfig:
    command: str
    wsl_distro: str
    hermes_home: str
    bridge_url: str
    model: str
    toolsets: str
    max_turns: int
~~~

新增 _HERMES_BRIDGE_CONFIG。只对本模块创建并持有的 process 执行 terminate/wait/kill；配置相同且健康时直接复用。

**Step 4: 验证**

~~~powershell
pytest tests/test_hermes_agent_service.py -q
pytest tests/test_agent_runs_api.py -q
~~~

Expected: lifecycle 测试通过，没有真实启动 WSL/Hermes。

**Step 5: Commit**

~~~text
fix(agent): restart managed hermes bridge on config changes
~~~

### Task 10: 修正文档与 route registry 自描述

**Tier:** 文档 + 小型 registry 元数据；不改变路由行为。

**Files:**

- Modify: docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md:35
- Modify: backend/app/api/__init__.py:116
- Test: tests/test_backend_api_module_boundary.py or closest existing registry contract test

**Step 1: Impact gate**

修改 backend route registry 前运行精确 symbol impact。

**Step 2: 写 registry contract test**

断言 liability analytics 属于 analytical compatibility，不属于 formal mainline；cube query 保持 controlled/support 语义。

**Step 3: 同步文档**

将 risk-overview 从 placeholder 描述更新为当前 live risk tensor/cashflow 页面，同时明确它不等于被排除的 /ui/risk/overview executive endpoint。

**Step 4: 验证并提交**

~~~powershell
pytest tests -q -k "api_module and registry"
~~~

Commit:

~~~text
docs(boundary): align live risk and liability registry status
~~~

### Task 11: 最终验证与交付

**Step 1: 后端最窄回归**

~~~powershell
pytest tests/test_result_meta_on_all_ui_endpoints.py -q
pytest tests/test_balance_analysis_service.py tests/test_balance_analysis_api.py -q
pytest tests/test_pnl_api_contract.py -q -k "pnl_bridge"
pytest tests/test_yield_curve_term_structure_api.py -q
pytest tests/test_gitnexus_mcp_client.py tests/test_hermes_agent_service.py tests/test_agent_runs_api.py -q
~~~

**Step 2: 前端最窄回归**

Run from frontend:

~~~powershell
npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx src/test/ProductCategoryAdjustmentAuditPage.test.tsx src/test/ProductCategoryPnlPage.test.tsx src/test/ApiClient.test.ts
npx playwright test -c playwright.config.mjs tests/playwright/bond-trading-desk-drill.spec.mjs tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs
npx playwright test -c playwright.config.mjs tests/playwright/a11y-visual-smoke.spec.mjs --grep "product-category-pnl"
npm run lint
npm run typecheck
npm run debt:audit
npm run build
~~~

**Step 3: 扩大验证**

仅在最窄回归通过后执行：

~~~powershell
python scripts/backend_release_suite.py --mcp-profile full
~~~

以及 frontend 全量：

~~~powershell
npm run test
~~~

**Step 4: 影响与工作树检查**

- 运行 gitnexus_detect_changes。
- 检查 git diff --stat 和 git status --short。
- 确认没有数据库、认证、scheduler、client.ts 或无关页面改动。
- 将每个提交的测试结果记录在交付说明中。

## 发布门槛

必须全部满足：

1. 已知 4 个稳定回归全部关闭：backend envelope、contrast、bond drill、monthly real mode。
2. result_meta caller-only 变更有合同/血缘证据；不存在共享 runtime 自动推断。
3. PnL/yield 多 fallback 日期若未确认，相关任务保持未合并，不用猜测值填充。
4. GitNexus/Hermes 新测试覆盖多帧、notification、配置变化、外部进程所有权。
5. frontend lint/typecheck/debt/build 通过。
6. gitnexus_detect_changes 仅显示预期流程。

## 回滚策略

- 每个任务一个提交，可独立 revert。
- UI 修复不与 backend/agent 修复混合。
- Balance、PnL、Yield 三个 meta 任务分别提交。
- GitNexus 与 Hermes 分别提交。
- 如果共享边界影响升级为 HIGH/CRITICAL，停止合并并重新评审，不扩大修改范围。
