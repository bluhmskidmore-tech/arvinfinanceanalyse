# New Window Prompt - System Boundary Governance Continue

你在 `F:\MOSS-V3` 继续做系统边界治理。当前目标不是大重构，而是为了后续业务功能快速上线，先把边界、页面闭环、样本真值和验证入口治理清楚。

## 必读上下文

先只读这些文件，不要立刻改代码：

- `AGENTS.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
- `docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md`
- `docs/plans/2026-04-24-system-boundary-governance-execution-split.md`
- `docs/plans/2026-04-24-cursor-boundary-governance-prompts.md`
- `docs/page_contracts.md`
- `docs/golden_sample_plan.md`
- `docs/golden_sample_catalog.md`
- `tests/test_golden_samples_capture_ready.py`

## 当前已完成

- 系统边界治理操作模型已经落到 `docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md`。
- 后续任务拆分已经落到 `docs/plans/2026-04-24-system-boundary-governance-execution-split.md`。
- Cursor 并行 prompt 已经沉淀到 `docs/plans/2026-04-24-cursor-boundary-governance-prompts.md`。
- `PAGE-PROD-CAT-PNL-001` 已进入 `docs/page_contracts.md`，并绑定 `GS-PROD-CAT-PNL-A` 与 product-category truth contract。
- `docs/golden_sample_plan.md` 与 `docs/golden_sample_catalog.md` 已对齐当前 12 个 capture-ready 样本包。
- `GS-EXEC-OVERVIEW-A` 的 `response.json` 与 `assertions.md` 已修正到当前 executive metric contract：
  - `aum.label = "总资产规模"`
  - `aum.caliber_label = "本币资产口径"`
  - `yield/nim/dv01.caliber_label = null`
- 已验证：`python -m pytest -q tests/test_golden_samples_capture_ready.py` 通过，结果为 14 passed。

## 下一步主旨

核心主旨：任何新功能或页面上线前，都必须能回答三个问题。

1. 这个页面属于正式主链、候选能力、诊断工具，还是冻结/废弃面？
2. 页面展示的每个业务指标，能否追到 API response -> adapter/transformer -> store/state -> selector/computed -> component -> chart/table？
3. 当前 golden sample、page contract、metric dictionary、测试入口是否一致？

不要为了架构漂亮做平台层改造。优先做一个页面或一个样本闭环，改动小、证据足、可以快速上线。

## 建议执行顺序

### Prompt 3 - Metric Dictionary Sample Scope

只读开始，优先检查：

- `docs/metric_dictionary*`
- `docs/page_contracts.md`
- `docs/golden_sample_plan.md`
- `docs/golden_sample_catalog.md`
- `tests/golden_samples/**/response.json`
- `tests/golden_samples/**/assertions.md`

目标：

- 建立或补齐 capture-ready 样本与 metric dictionary 的绑定规则。
- 不臆造 `metric_id`。
- 如果指标只有页面 truth contract，没有字典级定义，明确标注为待绑定，不要假装已完成。
- 输出最小文档变更，不改业务代码。

验收：

- 能列出 12 个样本包中哪些 metric_id 已有字典真值，哪些只有页面/样本真值。
- `GS-PROD-CAT-PNL-A` 与 `PAGE-PROD-CAT-PNL-001` 的缺口必须显式记录。
- 跑 `python -m pytest -q tests/test_golden_samples_capture_ready.py`，确认仍然通过。

### Prompt 4 - Frontend Formal Recompute Audit

只读开始，优先检查正式主链页面：

- executive dashboard
- balance analysis
- attribution
- risk analysis
- product category pnl

目标：

- 找出前端是否有重复计算、硬编码 fallback、mock fallback、单位转换、日期回退、null/0 混淆。
- 每个发现必须带文件路径、函数/组件、指标名、风险等级、建议修复顺序。
- 不做大范围改造；先产出审计表。

验收：

- 输出一份最小审计文档到 `docs/plans/`。
- 审计必须按页面归类，并优先列出会影响业务结论的风险。

### Prompt 5 - First Page Closure Candidate

基于 Prompt 4 的结果，选一个最小、收益最高的页面或状态链闭环。

优先选择条件：

- 业务风险明确。
- 文件范围小。
- 可以通过 adapter/selector/component 或 state test 锁住。
- 不需要 backend/schema/global state 改造。

执行要求：

- 先补最小测试，再改实现。
- 严格追踪 API response -> adapter/transformer -> store/state -> selector/computed -> component -> chart/table。
- 修复后运行最窄相关测试，再运行 capture-ready 测试。

## 硬边界

- 不要主动改数据库 schema、auth、queue、scheduler、cache、global SDK wrapper、app-wide state architecture。
- 不要把候选页面提升为正式主链，除非 page contract、truth contract、golden sample、metric dictionary、测试入口都闭合。
- 不要 staging unrelated dirty files。
- 不要把 `docs/pnl/`、`tests/golden_samples/GS-PROD-CAT-PNL-A/` 或 frontend product-category 代码顺手塞进无关提交，除非当前 prompt 明确要求。
- 如果指标定义不明确，记录 ambiguity 和证据，不要猜。

## 默认验证命令

```powershell
python -m pytest -q tests/test_golden_samples_capture_ready.py
```

文档类变更还要用 `rg` 或 `Select-String` 检查目标关键字是否只出现在预期文件中。

## 推荐提交粒度

每次提交只做一种闭环：

- 一次 metric dictionary/sample binding 文档闭环；或
- 一次 frontend audit 文档闭环；或
- 一个页面/状态链的测试加修复闭环。

提交信息遵守 Lore Commit Protocol，说明约束、拒绝过的方案、已测和未测。
