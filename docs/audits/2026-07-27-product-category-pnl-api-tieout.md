# 产品分类 PnL API 端到端核对

日期：2026-07-27

页面：

- `PAGE-PROD-CAT-001`
- `PAGE-PROD-CAT-PNL-001`（page-contract 别名）
- 前端主路由：`/product-category-pnl`
- 前端审计路由：`/product-category-pnl/audit`
- 后端前缀：`/ui/pnl/product-category`
- 路由分组：`formal_mainline`

## 1. 结论

本工作流共有 11 个已注册 FastAPI operation，包含 6 个 GET 和 5 个
POST。按业务角色拆分为：

| 类别 | 数量 | 说明 |
| --- | ---: | --- |
| Governed read | 3 | 日期、产品分类 PnL 明细/场景、月环比或同比归因 |
| Refresh control | 2 | 刷新触发与刷新状态轮询 |
| Manual-adjustment / audit | 6 | 创建、列表、CSV 导出、编辑、撤销、恢复 |

静态调用证据显示，这 11 个 operation 在产品分类 PnL 主页面和审计页面内
实现 11/11 消费，没有 feature-local 零消费接口。三个 governed read 还被
`/operations-analysis`、`/market-finance`、`/pnl-attribution` 和
`/team-performance` 等页面复用，因此任何响应契约或日期语义修改都不是
单页低风险改动。

当前结论是：

- 实现链路已接通，正式读模型、场景覆盖、刷新和调整审计均能追踪到代码及测试。
- 本地 readiness 采样确认
  `product_category_pnl_formal_read_model` 与
  `product_category_pnl_canonical_fact` 均存在，2/2 表有日期证据。
- 页面仍未治理关闭：`GS-PROD-CAT-PNL-A` 是
  `captured-awaiting-approval`，业务 owner 审批未捕获，
  `closure_approved=false`，10 个 closure 单元全部为 `PARTIAL`。
- readiness CLI 的样本范围兼容映射已修复，当前输出 `overall_status=static-pass`
  与 `golden_sample_boundary=pass`；这只表示静态契约证据已路由，不表示审批完成。
  真实的审批未完成状态仍由 approval artifact 与 owner checker 独立确认。
- 最新 direct governance record 仍停在 `2026-05-31`，而本地正式表日期已到
  `2026-06-30`；record 引用的 live-smoke 截图当前不存在。
- `formal_mainline` 是路由所有权/风险分组，不能替代 golden sample、
  owner approval 或 page closure。

## 2. 权威链路

```text
配对总账对账工作簿 + 日均工作簿
  -> backend/app/services/product_category_source_service.py
  -> backend/app/core_finance/product_category_pnl.py
  -> product_category_pnl_canonical_fact
  -> product_category_pnl_formal_read_model
  -> backend/app/repositories/product_category_pnl_repo.py
  -> backend/app/services/product_category_pnl_service.py
  -> backend/app/api/routes/product_category_pnl.py
  -> frontend/src/api/productCategoryClient.ts
  -> ProductCategoryPnlPage / ProductCategoryAdjustmentAuditPage
```

注册证据：

- `backend/app/api/routes/product_category_pnl.py:33`
- `backend/app/api/__init__.py:134`

页面与业务真值证据：

- `docs/page_contracts.md:1816`
- `docs/pnl/product-category-page-truth-contract.md`
- `docs/pnl/adr-product-category-truth-chain.md`

## 3. 11 个 operation 清单

| # | 类别 | Method / path | 输入 | 实际语义输出 | 核心调用链 | 权限 | 已确认前端消费者 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Governed read | `GET /dates` | 无业务参数 | formal envelope；`ProductCategoryDatesPayload` | `product_category_dates_envelope` -> repo `list_report_dates` / `latest_source_version` | `product_category_pnl/read` | 主页面、审计页面、operations-analysis、market-finance、pnl-attribution |
| 2 | Governed read | `GET ""` | 必填 `report_date`；`view`；可选 `scenario_rate_pct` | formal 或 scenario envelope；`ProductCategoryPnlPayload` | service -> unified analysis -> `ProductCategoryPnlAnalysisAdapter` -> formal repo；可选内存 scenario overlay | `product_category_pnl/read` | 主页面、operations-analysis、market-finance、pnl-attribution、team-performance |
| 3 | Governed read | `GET /attribution` | 必填 `report_date`；`compare=mom\|yoy` | formal envelope；`ProductCategoryAttributionPayload` | service -> 两次 monthly formal repo read -> attribution core | `product_category_pnl/read` | 主页面、pnl-attribution |
| 4 | Refresh control | `POST /refresh` | 可选 `Idempotency-Key` header | queued、idempotent replay 或 sync-fallback completed 的 operational payload | refresh service -> actor / sync fallback -> materialize task | `product_category_pnl/refresh` | 主页面、审计页面 |
| 5 | Refresh control | `GET /refresh-status` | 必填 `run_id` | 最新 cache-build run record + `trigger_mode` | service -> governance stream | `product_category_pnl/read` | 主页面、审计页面 |
| 6 | Adjustment write | `POST /manual-adjustments` | 完整 create DTO | 新建 adjustment event | service -> governance stream append | `product_category_pnl.adjustment/write` | 主页面、审计页面 |
| 7 | Audit read | `GET /manual-adjustments` | `report_date` + filter / dual sort / dual paging | current-state `adjustments` + event `events` | service -> governance stream -> reduce / filter / sort | `product_category_pnl/read` | 主页面、审计页面 |
| 8 | Audit export | `GET /manual-adjustments/export` | 与列表共享 filter / sort；分页不参与导出 | `text/csv`，current state + event timeline | service -> governance stream -> CSV builder | `product_category_pnl/read` | 审计页面 |
| 9 | Adjustment write | `POST /manual-adjustments/{adjustment_id}/revoke` | path ID | adjustment event；状态变为 `rejected` | service -> governance stream append | `product_category_pnl.adjustment/write` | 主页面、审计页面 |
| 10 | Adjustment write | `POST /manual-adjustments/{adjustment_id}/edit` | path ID + 完整 update DTO | adjustment event | service -> governance stream append | `product_category_pnl.adjustment/write` | 主页面、审计页面 |
| 11 | Adjustment write | `POST /manual-adjustments/{adjustment_id}/restore` | path ID | adjustment event；状态变为 `approved` | service -> governance stream append | `product_category_pnl.adjustment/write` | 主页面、审计页面 |

路由实现锚点：

- `backend/app/api/routes/product_category_pnl.py:36`
- `backend/app/api/routes/product_category_pnl.py:48`
- `backend/app/api/routes/product_category_pnl.py:75`
- `backend/app/api/routes/product_category_pnl.py:100`
- `backend/app/api/routes/product_category_pnl.py:125`
- `backend/app/api/routes/product_category_pnl.py:144`
- `backend/app/api/routes/product_category_pnl.py:157`
- `backend/app/api/routes/product_category_pnl.py:185`
- `backend/app/api/routes/product_category_pnl.py:214`
- `backend/app/api/routes/product_category_pnl.py:244`
- `backend/app/api/routes/product_category_pnl.py:265`

前端 client 映射：

- `frontend/src/api/productCategoryClient.ts:482`

## 4. Formal、scenario、归因与调整边界

### 4.1 Formal detail

- 唯一持久化读路径是
  `product_category_pnl_formal_read_model`。
- backend 支持 `monthly`、`qtd`、`ytd`、
  `year_to_report_month_end`。
- 主页面选择器只开放 `monthly` 与 `ytd`；扩大选择器前必须同步更新页面
  contract、closure checklist 和测试。
- 完整性检查使用
  `asset_total.business_net_income + liability_total.business_net_income`
  对账 `grand_total.business_net_income`，阈值为 0.01 yuan。
- partial YTD 或完整性破坏会把 `quality_flag` 提升为 `warning`。

### 4.2 Scenario

- 只有显式传入 `scenario_rate_pct` 才进入 scenario basis。
- Scenario 以 formal rows 为底，在内存覆盖 FTP 与相关净收入；不写持久化
  scenario 结果。
- Scenario 返回
  `basis=scenario`、`scenario_flag=true`、
  `formal_use_allowed=false`。
- Scenario 必须保持 formal baseline 的 `category_id` / tree identity。
- DDL 虽包含 scenario read-model 表，当前 materialize task 清空该表但不写入；
  不能把它解释为第二条持久化真值链。

### 4.3 Attribution

- 归因固定读取 current / prior 两个 `monthly` formal snapshot。
- `compare=mom` 使用前一自然月末；`compare=yoy` 使用上一年同月末。
- current 缺失返回 404。
- prior 缺失仍返回 200，但 payload 为 `state=incomplete`，
  `quality_flag=warning`。
- 完整归因返回时，页面展示金额和闭合误差，但当前未直接展示其
  `result_meta`；只有 incomplete 分支渲染 `DataQualityBanner`。

### 4.4 Manual adjustment

- Create / edit / revoke / restore 只追加治理事件，不会即时改变 formal read
  model。
- 只有 `approval_status=approved` 的调整会在下一次 materialization 进入
  formal。
- Edit 是完整 update DTO，不是 partial PATCH。
- Revoke 把状态设为 `rejected`；restore 把状态设为 `approved`。
- Create 默认 `approval_status=approved`，edit 也可直接写
  `approved`；当前没有独立 approve operation。

## 5. 指标、单位和日期

当前 active 指标：

- Headline：`MTR-PCP-001` 至 `MTR-PCP-003`
  - `asset_total.business_net_income`
  - `liability_total.business_net_income`
  - `grand_total.business_net_income`
- Detail：`MTR-PCP-004` 至 `MTR-PCP-012`
  - `rows[].cnx_scale`
  - `rows[].cny_scale`
  - `rows[].foreign_scale`
  - `rows[].cny_ftp`
  - `rows[].foreign_ftp`
  - `rows[].cny_net`
  - `rows[].foreign_net`
  - `rows[].business_net_income`
  - `rows[].weighted_yield`

契约边界：

- 金额由后端以 Decimal 字段返回，页面只做 `亿元` 展示转换；不得在前端
  重算正式总计。
- `weighted_yield` 是 percent，不能按金额缩放；null 必须保持显式空态。
- 行身份由 `category_id`、`side`、`view`、`report_date` 决定，这些是维度，
  不是新指标。
- `requested_report_date` 是 query `report_date`；
  `resolved_report_date` 是 payload `result.report_date`。
- 按已批准 decision 1B，本页面没有独立 outward `as_of_date`；不得用
  `report_date` 或 `generated_at` 伪造。

## 6. `result_meta` 覆盖

| Operation | 当前 meta 状态 |
| --- | --- |
| `/dates` | formal envelope，包含 trace/result kind/source/rule/cache 等基础 meta；未填 filters、tables、evidence rows 或 requested/resolved date |
| detail | formal/scenario envelope，source/rule 来自选中 snapshot；未填 filters、tables、evidence rows 或 requested/resolved date |
| `/attribution` | 三个 governed read 中最完整：包含 filters、formal table 和 evidence row count；source version 只代表 current rows |
| 其余 8 个 | operational / governance payload，不返回 `result_meta` |

只有 spread metric 使用显式 `{raw, display, unit: "percent"}`。其他金额和
attribution 数值没有 DTO 内 unit wrapper，单位含义仍依赖 metric contract 和
page truth contract。

## 7. 核对发现

### F1 — Gate：实现可用不等于治理关闭

独立 owner checker 给出的有效治理事实是：

- `GS-PROD-CAT-PNL-A` 为 `captured-awaiting-approval`；
- owner / approver / approved_at 均为 `TBD`；
- `business_owner_approval_captured=false`；
- `closure_approved=false`；
- closure 为 0 `CLOSED`、10 `PARTIAL`；
- 15 个 owner action item 中 0 个已签署。

这不是代码断链，但在审批完成前不得把该页面描述为已认证关闭。

### F2 — 已修复（P1）：readiness 样本范围词汇发生兼容断裂

`golden_sample_readiness()` 返回两个不同字段：

- `status`：样本范围，formal contract 固定返回 `formal_sample`；
- `approval_status`：从 approval artifact 聚合的真实审批状态。

静态 readiness 的 `golden_sample_boundary` 有意检查“样本是否属于正式契约
范围”，而不是检查人工作出的 approval artifact 决定。旧 helper 对正式样本使用
边界值 `approved`，新 helper 把同一范围语义改名为 `formal_sample`，但消费端仍
按旧值比较，导致正式样本被错误阻断。

修复在消费端保留两层语义：当页面允许正式使用且 scope 为 `formal_sample` 时，
只把静态边界兼容映射为 `approved`；artifact 的
`captured-awaiting-approval`、`artifact_approved=false` 和 owner pending 状态
继续独立呈现，未被提升为审批通过。修复后 CLI 为 `static-pass`，同时仍明确
`closure_approved=false`。

证据：

- `scripts/mcp/golden_approval.py:18`
- `scripts/codex_page_readiness.py:786`
- `scripts/codex_page_readiness.py:1537`

### F3 — P1：OpenAPI 成功响应没有语义 DTO

运行时 OpenAPI introspection 显示：

- 10 个 JSON operation 的 2xx schema 都只是
  `type=object, additionalProperties=true`；
- CSV operation 的成功 schema 未指定，而且 OpenAPI 显示
  `application/json`，与运行时 `text/csv` 不一致；
- 403 / 404 / 409 / 503 等已实现错误语义没有在 operation contract 中声明。

后端虽然已有多数 Pydantic payload model，但 route 没有把它们绑定为
`response_model`。这会削弱 SDK 生成、契约 diff 和消费者兼容性检查。

### F4 — P1：调整事件未进入 authenticated actor 与结果版本指纹

- Route 中的 authenticated user 没有传入 adjustment service；
- adjustment event 没有记录 authenticated actor / reason；
- `operator` 是 `ADD` / `DELTA` / `OVERRIDE` 计算操作符，不是操作者身份；
- source version 由工作簿文件名、size 和 `mtime_ns` 生成，manual adjustment
  stream 不参与 source-version 计算。

因此 approved adjustment 可在 rematerialize 后改变 formal 结果，而
`source_version` 仍可能不变。需要治理 owner 决定 actor、reason、审批和
result-version 指纹，而不是由代码自行猜测。

### F5 — P1：刷新与正式/场景组合可产生新旧数据混用

刷新完成后，主页面只 refetch：

- dates；
- baseline；
- adjustments；
- 已启用时的 scenario。

它没有 refetch attribution、management attribution、趋势/历史 snapshot 或
sensitivity 查询。若 materialization 改变这些结果，同一页面可同时展示新
baseline 与旧归因/趋势。

同时，页面的 displayed totals / rows 在场景启用时来自 scenario，但经营分析
surface 和 first-screen readiness band 继续接入 formal attribution。页面文字虽
声明归因不解释场景差异，数据仍在同一决策带内组合，容易被理解成一个统一正式
结果。

证据：

- `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx:4089`
- `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx:4880`
- `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx:5201`

### F6 — P1：正式可用判断与退化 raw notice 都未完整落实 meta contract

`buildProductCategoryDataHealth()` 只检查 `quality_flag`、`vendor_status` 和
`fallback_mode`；不检查 `basis`、`formal_use_allowed` 或
`scenario_flag`。因此一份非正式或禁止正式使用、但其余三项为正常值的 meta，
仍可显示“可用于经营判断”。

页面 truth contract 还要求 first-screen governance strip 在 fallback、vendor
stale/unavailable 或 quality 非 ok 时显示专用 status line，并引用 raw 字段值。
当前：

- 外层可见 health strip 只有通用说明；
- `fallback=<raw>`、`vendor=<raw>`、`quality=<raw>` 和专用 notice 位于默认
  未展开的 `<details>` 中；
- degraded test 使用 `toHaveTextContent` 检查折叠 DOM，不能证明用户默认看得到。

证据：

- `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts:5498`
- `docs/pnl/product-category-page-truth-contract.md:259`
- `frontend/src/features/product-category-pnl/pages/ProductCategoryGovernanceStrip.tsx:63`
- `frontend/src/test/ProductCategoryPnlPage.test.tsx:811`
- `frontend/src/test/ProductCategoryPnlPage.test.tsx:3615`

### F7 — 已修复（P1）：并行 pytest 进程共享临时根目录

漂移失败的根因不是产品分类业务代码或单进程 suite order，而是 pytest 配置把
所有进程的 basetemp 固定为 `.codex-tmp/pytest-basetemp`。并行审计时，不同
pytest 进程会互相删除或复用相同的 `tmp_path`，从而污染：

- product-category source workbook；
- DuckDB 文件；
- auth-scope SQLite 文件。

这解释了 `month_count=1`、随机 403 和失败位置漂移。修复移除了 pytest.ini
中的固定默认 `--basetemp`，并由 conftest 在所有平台提供仓库内的
`pytest-basetemp-<pid>` 默认目录；Windows 继续使用可读 ACL，调用者显式传入
`--basetemp` 时仍保持原行为。修复后 41 项 flow 测试与 70 项组合定向测试均
通过，两个同时启动的子进程得到不同根目录，显式 override 契约也通过。

### F8 — P1：直接证据落后于最新本地数据且 live-smoke 文件缺失

`data/governance/cache_manifest.jsonl:5399` 的 direct record：

- `report_date=2026-05-31`；
- `created_at=2026-06-04T14:51:48.300790Z`；
- 引用 `.codex-tmp/product-category-pnl-live-smoke.png`。

本地正式表日期采样已到 `2026-06-30`，而该截图文件当前不存在，本轮也未运行
live browser/API smoke。因此 direct record 可证明历史链路结构，不能证明当前
最新月份的页面执行或视觉状态。

### F9 — P2：Attribution 没有进入同等强度的 page/trace contract

Attribution route、service、schema、frontend 和测试均存在，但以下证据没有把
它列为 supporting API：

- `docs/page_contracts.md` 的 product-category endpoint 表；
- `docs/pnl/product-category-page-truth-contract.md` 的 supporting API 清单；
- `scripts/mcp/moss_project_mcp.py` 的 page trace bundle。

此外，虽然 complete 和 incomplete 分支都收到 attribution `result_meta`，
complete 分支没有渲染它；只有 incomplete 分支显示 `DataQualityBanner`。应先补
contract membership，再决定完整成功态的 meta 呈现要求。

### F10 — P2：主页面调整数量使用当前页长度

主页面摘要使用 `adjustments.length`，而审计页面使用 API 返回的
`adjustment_count`。当列表分页或截断时，主页面会把当前页长度当成总调整数，
导致数量少报。

证据：

- `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx:5566`
- `frontend/src/features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx:346`

### F11 — P2：日期、单位与异常映射不完全对称

- Detail / attribution 的 `report_date` 是裸 `str`，没有 YYYY-MM-DD
  schema/pattern；内部 calendar parse error 可能成为未映射异常；
- create / edit 对 report date 做真实日历校验，list / export 只有正则格式校验；
- read / refresh 会把 auth store `RuntimeError` 映射为 503，四个 adjustment
  write 只捕获 `PermissionError`；
- edit / revoke / restore 把 service 的任意 `ValueError` 映射为 404，范围比
  “unknown adjustment ID” 更宽；
- 多个 first-screen 日期标签使用 `selectedDate`，不是响应
  `result.report_date`；若将来出现日期解析/回退，两者可能不一致；
- 只有 spread metric 使用 `{raw, display, unit}`，其余金额/归因数值仍靠外部
  metric/page contract 解释单位。

### F12 — P2：既有 owner 决策仍未完成

`docs/pnl/product-category-pnl-owner-decision-packet.md` 已登记 5 个正式决策：

1. 长运行 refresh timeout / stale 文案；
2. 扩展 validation copy；
3. current-state 与 event timeline 双排序的产品理由；
4. CSV UTF-8 BOM 服务端规则；
5. 大型 CSV export 的限制、streaming 和 timeout。

这些属于 owner / backend API contract 决策，不应由本轮梳理擅自实现。

### F13 — P3：指标、日期与导航文案存在文档漂移

- `docs/metric_dictionary.md:404-428` 已激活 `MTR-PCP-001` 至
  `MTR-PCP-012`，后续覆盖说明仍写“只有三条 active、detail 待落地”；
- `docs/MCP_RUNBOOK.md:306` 与
  `scripts/mcp/moss_project_mcp.py:2664` 仍把缺少 standalone
  `as_of_date` 记为 gap，但 `docs/page_contracts.md:1854` 和 truth contract
  decision 1B 已明确这是有意的 no-field 决策；
- navigation 同时标记 `readiness=live`、`readinessLabel=临时开放`、
  `governanceStatus=temporary-exception`，含义未对齐。

相关文件已有用户未提交修改，本轮不覆盖；后续应做一次只改文案/工具描述的
定向对齐。

## 8. 验证记录

### 8.1 通过

```text
npm test -- \
  src/test/ProductCategoryPnlPage.test.tsx \
  src/test/ProductCategoryAdjustmentAuditPage.test.tsx \
  src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts \
  src/features/product-category-pnl/pages/productCategoryPnlPageModel.dateSemantics.test.ts \
  src/test/ApiClient.test.ts
```

结果：5 files passed，304 tests passed。

单独复跑两个后端失败用例：

```text
1 passed
1 passed
```

### 8.2 后端回归

```text
python -m pytest \
  tests/test_product_category_pnl_flow.py \
  tests/test_product_category_pnl_attribution.py \
  tests/test_product_category_mapping_contract.py \
  tests/test_write_route_auth_contract.py \
  -q -k "product_category" -p no:cacheprovider
```

结果：70 passed，47 deselected。

```text
python -m pytest \
  tests/test_product_category_pnl_flow.py \
  -q -x -p no:cacheprovider
```

结果：41 passed。参见 F7。

并发隔离对照：

```text
tests/test_pytest_temp_isolation.py
```

结果：3 passed，覆盖当前进程默认值、两个并发子进程目录不同以及显式
`--basetemp` override 保留。

### 8.3 Readiness

```text
python scripts/codex_page_readiness.py --page-slug product-category-pnl
```

命令以 0 退出，`overall_status=static-pass`，2/2 catalog/date sampling 与
direct governance record 检查通过，`golden_sample_boundary` 为 pass。输出同时
保留 `artifact_status=captured-awaiting-approval`、
`artifact_approved=false`、`business_owner_approval_captured=false` 与
`closure_approved=false`；静态通过不等于审批或页面关闭。

真实治理状态由下列独立 checker 确认：

```text
python scripts/check_product_category_pnl_business_owner_approval.py \
  --require-captured
```

结果：exit 1；approval pending、0/10 closure units closed、15/15 action items
unsigned。该 checker 的非零结果与 approval artifact 一致，不依赖 F2 的
readiness gate。

### 8.4 OpenAPI

对 `backend.app.main:app` 做只读 OpenAPI introspection，确认 11 个 operation
均已注册，并确认 F3 的 generic/unspecified 成功响应契约。

## 9. 建议执行顺序

1. 已完成 readiness scope 兼容映射和 pytest 进程级临时目录隔离；未触碰业务
   公式、认证框架或 API 行为。
2. 为 11 个 operation 建立显式 response / error contract，先覆盖三个共享
   governed read 和 CSV media type。
3. 修复刷新后的 query invalidation，并把场景 totals 与 formal attribution
   在决策带中明确分离。
4. 让 data-health gate 检查 `formal_use_allowed` / `basis`，把 degraded raw
   notice 移到默认可见位置，并补真正的可见性断言。
5. 把 attribution 补入 page contract、trace bundle 和 source-to-screen 表，
   对 complete 状态补齐 meta 要求；主页面调整摘要改用 `adjustment_count`。
6. 由治理 owner 决定 adjustment actor、reason、审批和版本指纹；决定前不改
   认证/权限框架。
7. 对 `2026-06-30` 重新捕获 direct API/browser evidence，再完成现有 5 个
   owner/API 决策、golden sample 审批与 business-owner sign-off，最后才把
   closure 从 `PARTIAL` 推进。

第 1 项小修复批次已完成。后续可在独立范围内推进第 2 至 5 项，并继续把
owner approval 与静态 readiness 分开管理。

## 10. 证据边界

- 本会话没有项目 MCP 工具面；使用仓库内 page trace/readiness 脚本、合同、
  代码、OpenAPI 和测试作为替代证据。
- Readiness 采样的是当前本地 DuckDB，不是生产数据库证明。
- 静态前端引用能证明仓库内消费者，不能证明没有网关外部消费者；缺少 access
  log 或 consumer registry 时，不作“外部零消费”断言。
- 未运行 live browser smoke；本轮没有改动 UI/API 行为。
- 本轮只修改 readiness 静态判定兼容层、pytest 临时目录隔离与审计证据；未修改
  数据库 schema、认证框架、计算公式、API 行为或页面实现。
