# MOSS-V3 技术债清偿 PRD

| 项 | 内容 |
| --- | --- |
| 文档版本 | v0.3（证据重锚版——废弃 v0.1/v0.2 中失实证据） |
| 日期 | 2026-08-11（深夜修订） |
| 证据基线 | `codex/V1` 分支当日代码（注意：工作区活跃，实现前每项必须重锚） |
| 状态 | 待 owner 签核——签核前不启动任何实现工作包 |

## 0. 证据勘误声明（必读）

v0.1/v0.2 所依据的第一轮审计报告含**大量虚构证据**：其引用的多个文件（`spreadAdapter.ts`、`dashboardViewModel.ts`、`useDashboardData.ts`、`liabilityContracts.ts`）与符号（`weightedDv01Sum`、`computeSegmentDelta`）在仓库 git 全历史中不存在；声称的 `requirements.txt`/`quality-gates.yml`/`双测试根漏跑`/`mypy 存量 87` 等均与事实不符。第一轮评审报告对这些证据的"实测确认"同样失实。

v0.3 的每一项标注证据等级：

- **[锚]** 主代理本人以工具直接验证（文件读取/grep/命令输出）。
- **[共识]** 第二轮 ≥2 份独立核实报告结论一致，且与锚点无矛盾。
- **[单源]** 仅一份第二轮报告提出。**实现前必须由实现者重新取证，取证不符即关闭该项。**

**硬性纪律（新增）**：每个 PR 的第一个提交必须是"证据重锚记录"（复核该项现状的命令与输出摘要，附在 PR 描述），证据不符则停止并回报，禁止"按文档改代码"。

主代理亲验锚点清单（2026-08-11）：

1. 7·20 审计 6 个 P0 全部关闭（`_curve_points` 接受 Mapping、四条 API 写路径 actor 化、前端 concentration.ts 已删）。
2. `pnl_bridge_service.py` 全文件无裸 `except Exception`；`_curve_points`（约 691–708）窄异常静默返 None、无 warning 披露。
3. 依赖权威 = `backend/pyproject.toml` + `backend/uv.lock`（存在）；根 `requirements.txt`、`backend/requirements.lock` 不存在。
4. CI 为 `.github/workflows/ci.yml`（无 quality-gates.yml、无 mypy step）。
5. 根 `pytest.ini` `testpaths = tests + backend/tests`（双根已合并）；`backend/pyproject.toml` 另有 `[tool.pytest.ini_options]`（rootdir 陷阱）与 `[tool.mypy]`。
6. `.gitignore:13` 已含 `.codex-tmp/`。
7. 视觉令牌审计当前失败点：`dashboardHomeOptionTwo.module.css` hex 1 > 基线 0；`tokens.css` 基线已被上调至 122（当晚早些时候曾以 106 为基线失败——基线在会话期间被并行工作上调）。
8. 脚本规模：`backend/scripts` 13 个 .py、`scripts/` 146 个 .py。
9. `adb_analysis_service.py:92` `_stable_factor`（MD5 系 0.85–1.15 因子）+ `:1338` `simulate_if_single_snapshot: bool = True` 默认开启。
10. core_finance/服务硬编码个人机器路径 4 处：`formal_financial_indicators.py:11`（Desktop xlsx）、`macro/dual_frequency_equity.py:167`、`macro/macro_etf_strategy.py:132`、`hermes_agent_service.py:731`（/home/hermes）。
11. 本地分支 248、工作树 83；7·20 后 242 个提交。
12. 巨型文件（debt:audit 工具输出）：`MacroToolkitPage.tsx` 7038/基线 11588、`productCategoryPnlPageModel.ts` ~5351、`pnl_service.py` ~4185、MCP 单体 ~12.6k、其配套测试 ~14.5k；`macro_toolkit.py` 路由非空 4062（总行 ~4409）；`contracts.ts` 已拆分（18/7519）。

---

## 1. 背景与目标

### 1.1 背景

7·20 全系统审计的 6 个 P0 已全部关闭 [锚]；7–8 月 242 个提交完成了大量 P1 整改（含本轮第二轮核实确认的：负债前端重算移除、CFFEX/Livermore 写路径 actor 化、balance workbook canonical 修正 `f9697fe4b`、macro 统计函数下沉 `core_finance/macro/helpers.py`、MACRO-P1-01/05/07、source_preview 内容指纹、双测试根合并、ruff B 族启用、ESLint any=error、contracts.ts 拆分）。

当前真实债务重心（经第二轮核实 + 锚点验证）：

1. **仍在产出可疑数字的点位**：ADB 仿真日均默认开启、前端补算经营指标残留面、静默吞错真实点位、正式链 float 残留。
2. **保障面与断言面错位**：PR CI 后端只跑 release suite（约 24 文件），全量 pytest 仅 main/schedule；mypy（存量约 1849 错）与后端 ruff 均不在 CI。
3. **可移植性与治理**：核心正式指标绑个人桌面路径、CI 安装不吃 uv.lock、schema 三套账、脚本与分支堆积。

### 1.2 目标（可度量）

| 编号 | 目标 | 度量 | 期限 |
| --- | --- | --- | --- |
| G1 | 已确认的可疑数字点位清零 | A 组各项按第 5 节验收通过（以复核确认为准入） | Sprint 1–3 |
| G2 | PR 门禁能拦截主链回归 | 分层门禁上线：PR 定向测试策略 + mypy/ruff 棘轮 job + 每日全量 | Sprint 2 末 |
| G3 | 构建环境可复现 | CI 与本地统一 `uv sync --frozen`（或等价），安装产物一致 | Sprint 2 末 |
| G4 | 债务只降不升 | `debt-baselines.json` 棘轮上线（行数/豁免/白名单多计数汇流） | Sprint 2 末 |
| G5 | 正式路径无个人机器依赖 | 4 处硬编码路径清除，正式指标门禁可移植 | Sprint 1 末 |
| G6 | 仓库状态面收敛 | 11 支全合并分支清理 + 236 支 ahead 分支分类裁决报告 + 11 个脏工作树处置记录 | Sprint 4 末 |

**北极星**：连续两个 Sprint 无新增"违反 R-01/R-02/R-03 治理原则"的缺陷，且 CI 具备拦截同类回归的断言。

### 1.3 非目标

1. 不做平台级重构（不重写巨型文件/不引入新框架/不新建队列缓存基础设施）。
2. 不自行裁决第 10 节 owner 闸门事项。
3. 不重开 7·20 已关单事项，也不重开本轮确认已修复的事项（第 12.1 节"已关单"列）。
4. 不 bulk delete 分支/工作树；含未提交改动的工作树先走处置决策。
5. 不动 Phase 03/04。
6. 覆盖率门禁不在本期。
7. mypy 严格面不扩大，仅以基线棘轮方式入 CI。

---

## 2. 干系人与指派规则

| 角色 | 职责 |
| --- | --- |
| 业务 owner | 闸门签核；影响报告确认（ADB 仿真、缺失语义、黄金值变化） |
| 技术负责人 | PR 评审、棘轮基线审批、分支保留清单确认 |
| 实现者 | 证据重锚 → 测试先行 → 最小改动；每 PR 登记实现者与复核者 |

无指派与无重锚记录的 PR 不进入评审。

---

## 3. 需求与解决方案

> 每项：现状[证据等级] → 方案 → 验收 → 估时。文件:行号为 2026-08-11 深夜证据，实现时按第 0 节纪律重锚。

### 3.A 数字正确性与正式口径

#### A1. ADB 单日窗口用 MD5 因子合成"日均"且默认开启

- **现状 [锚]**：`backend/app/services/adb_analysis_service.py:92` `_stable_factor`（MD5 派生 0.85–1.15 缩放），`:1338` `simulate_if_single_snapshot: bool = True`，`:1381-1387` 单快照窗口即用 `spot × factor` 合成日均进入对比结果。这不是观测口径，是合成数。
- **方案**：默认改 False；单快照窗口返回 null + `reason="insufficient_window"`；若业务确需保留仿真，必须 owner 签核并在 API meta 与前端首屏标注 `synthetic=true`（fail-visible）。先出一份真实数据影响报告（最近报告日有多少输出实际来自仿真路径）。
- **验收**：单快照 fixture 不产出数字结论；`simulated` 路径要么删除要么全链路披露；影响报告归档并经 owner 确认。
- **估时**：1 天（含影响报告）。

#### A2. core_finance 正式指标绑个人机器路径

- **现状 [锚]**：`formal_financial_indicators.py:11` `SOURCE_WORKBOOK = "C:/Users/arvin/Desktop/..."`；`dual_frequency_equity.py:167` 与 `macro_etf_strategy.py:132` provenance 写死 Desktop 路径；`hermes_agent_service.py:731` 写死 `/home/hermes/...`。正式指标样本门禁不可移植。
- **方案**：SOURCE_WORKBOOK 改为 settings/环境变量 + 仓库内契约 fixture（脱敏样本入 `tests/fixtures/` 或 `sample_data/`）；两处 provenance 字符串改为仓库相对引用或元数据字段；hermes python_path 配置化。不改任何计算数值。
- **验收**：`rg "Users/arvin|/home/hermes" backend/app` 为零；正式指标测试在无 Desktop 文件的机器可运行（或进受控跳过清单）。
- **估时**：1 天。

#### A3. 静默吞错/落零的真实点位

- **现状 [共识]**（第二轮 PnL 评审与后端审计交叉，v0.2 所指 governance_repo/JSONL 点位失实作废）：
  - `executive_service.py:426` 坏行 `continue`；`:3111-3117`、`:3132-3140` headline 失败静默 `return {}` / `return None`——首页缺数无披露。
  - `campisi_decision_grade.py:28-34` 与 `campisi_attribution_service.py:614-620` 的 `decimal_value` 任意异常落 `ZERO`——脏输入变 0。
  - `product_category_pnl_service.py:733-736` payload 校验失败 `pass` 后静默回退 canonical。
  - `macro_backfill.py:591` 宽捕获 [单源]；macro 刷新 normalize 白名单丢弃失败明细 [单源]。
  - **反向约束 [共识]**：`governance_repo` JSONL 读路径当前 fail-loud，**保持不动**——任何"skip-and-count"改造都是倒退。
- **方案**：逐点位 fail-visible 化——落零改为 null + quality_flag/warning；`return {}` 改为显式 degraded 状态；校验失败必须记录原因。每点位独立小改动 + 回归测试（含"未预期异常上抛"用例）。
- **验收**：注入脏输入 fixture → 输出为 null/degraded 且原因可见，不再是 0/空对象/静默回退；campisi 落零路径清零。
- **估时**：2 天。

#### A4. PnL 曲线解析静默 None 无披露

- **现状 [锚+共识]**：`pnl_bridge_service.py` `_curve_points`（约 691–708）对非法 tenor/rate 窄异常返 None，归零 fallback 正确但**原因不进 result_meta warnings**。（v0.1/v0.2 描述的"388-394 裸 except"从未存在。）
- **方案**：`_curve_points` 失败时返回失败原因（或在调用点判 None 补 `curve_snapshot_error: <摘要>` 进现有 warnings 通道）；归零行为不变。
- **验收**：坏 snapshot fixture → warnings 含原因；`tests/test_pnl_bridge_curve_effects.py`、`tests/test_pnl_bridge_with_curve.py` 全绿。
- **估时**：0.5 天。

#### A5. 正式链 float/Decimal 破口（重锚版）

- **现状 [共识]**（v0.2 的 risk_tensor.py:406 等点位失实作废）：真实破口样本——`campisi.py:219` 曲线插值 float 中转后 `Decimal(str(...))` 回转 [单源]；`risk_scenario_stress_service.py`（约 251 行的现文件）冲击路径 float [共识]；`pnl_attribution_service.py` 多处 float 汇总 [共识]；`liability_analytics_service.py:243-255` Decimal 算完 float 输出 [单源]；`Numeric.raw_scale="auto"` 对 (0,1] 的歧义（文档自承）[共识]。
- **方案**：第一步（0.5 天）出"正式链 float 扫描清单"——按 core_finance + formal service 路径全量扫描并逐处定性（真破口/展示层/日志），清单归档；第二步按清单逐处 Decimal 化（测试先行锁现值 + 自动差异对比脚本），`raw_scale="auto"` 的消除单列（涉及契约，联动闸门第 5 项单位治理）。静态守卫：行级 `# float-ok: <原因>` 白名单标记 + 扫描测试。
- **验收**：扫描清单归档；首批（campisi 插值 + scenario stress）Decimal 化合入且黄金对比通过；静态守卫上线。
- **估时**：0.5（清单）+ 2（首批）天。

#### A6. 前端补算经营/分析指标残留面

- **现状 [单源，第二轮前端审计]**（v0.1/v0.2 的 DV01 聚合/区段减法/环比除零均已证伪或已修复）：`productCategoryPnlPageModel.ts` TPL 所需收益率反推（约 4707-4718）与 1–6 月净营收 sum/avg；`crossAssetAnalytics.ts` 前端 Pearson 矩阵与股债 ERP（111-135、601-626）;`AverageBalanceView.tsx` YoY 与期末偏离度并驱动风险文案（128-136 等）；`zqtzAdbAvgRollup.ts` 父子类目 rollup；`yieldAnalysisAggregates.ts`（自注 P1 违规，未挂路由）；`LiabilityAnalyticsPage.tsx:418-438` 期限桶求和。
- **方案**：逐项重锚后二分处置——属正式/经营口径的下沉后端（服务层或 core_finance，按指标登记属性），属展示辅助的显式标注 informal 并登记；未挂路由的 `yieldAnalysis*` 评估删除或归档。每项独立 PR。
- **验收**：每项要么后端权威字段 + 前端仅格式化，要么 informal 标注 + 债务登记；重锚不符项关闭并记录。
- **估时**：重锚 0.5 天 + 每项 0.5–1 天（首批取 TPL 反推与 AverageBalanceView 两项）。

#### A7. BalanceMovement 残留 null→0 与 core 层缺失语义

- **现状 [共识]**（两份第二轮报告交叉；原 computeSegmentDelta 叙述作废）：区段 delta 已消费后端 `delta_amount` ✅；残留——`numericValue` 把非有限值打成 0 可产出"持平"方向、`moveDeltaToneClass(finiteMetric(...) ?? 0)` 对 null 用持平色阶；**更深一层：后端 movement core 把缺失桶初始化为 ZERO 且 `balance_change` 非 Optional，"缺失"在正式口径中不可检测**。
- **方案**：前端两处 null 语义修复（null → 无方向/无色阶/"—"）先行（不改口径）；core 层显式缺失语义是**正式口径变更**——出影响报告（哪些历史输出会从 0 变 null）并走 owner 闸门后实施。
- **验收**：前端注入 null fixture 无"持平"伪结论；core 层变更仅在闸门签核后进行，且有影响报告与黄金样本更新。
- **估时**：前端 0.5 天；core 层 1 天 + 闸门。

#### A8. dashboard-home mock 面披露与收敛

- **现状 [单源×2，细节有出入需重锚]**：`useDashboardHomeSupplementalHydration.ts` `useMockFallback = mode !== "real" || isLiveDataFallback`（后者当前为常量 false——real 失败不静默回落 ✅）；mock 视图链（`dashboardHomeView.ts`、`riskRadarFromRiskItems.ts`）与 mock 常量仍进生产 bundle；`OperationsAnalysisPage.tsx` 直接渲染静态 mock 列表（标"静态示例"）；披露仅"样例数据日"标签。
- **方案**：重锚确认 real 模式失败路径确不落 mock 后，收敛为三件事：mock 模式首屏加显著"演示数据"横幅；`OperationsAnalysisPage` 静态列表要么接真数据要么显式空态占位并登记；评估 mock 常量从生产 bundle 剥离（注意 `StartupPerformanceGuards` 等测试的字符串断言依赖，需同步）。
- **验收**：mock 模式首屏有横幅；生产 real 模式无 mock 数据可达路径（bundle 分析或路由级验证）；OperationsAnalysisPage 处置落地。
- **估时**：1 天。

#### A9. 宏观开放口径项

- **现状 [单源，宏观评审实测]**：MACRO-P1-02（GDP 现价当季值相邻差分，Q1 季节性拉低 growth）与 MACRO-P1-04（政策利率两日工具集无交集约束）仍完全开放；`yield_curve_shape.py` 残留一处全历史分位冒充 1y [单源]；MACRO-P1-01/05/07 已修复，不重开。
- **方案**：P1-02 改同比或四期差分（涉及口径，出对比报告）；P1-04 只算交集；yield_curve_shape 截取真实 1y 窗口。
- **验收**：三项各有构造性 fixture 断言（季节性消除/交集约束/窗口截取）。
- **估时**：1.5 天。

### 3.B 保障面

#### B0. PR 门禁分层（新，最高优先）

- **现状 [共识]**：PR CI 后端仅跑 `scripts/backend_release_suite.py`（约 24 个测试文件）+ agent harness；全量 pytest（约 663+13 文件）仅 main push / schedule。回归可在 PR 阶段无检测合入。
- **方案**：不追求 PR 全量（时长不可行）；建立分层：(1) PR 保留 release suite；(2) 新增"触达路径定向测试"约定——PR 描述必须列出并执行与改动文件对应的 targeted tests（review checklist 强制项，可先人工后脚本化 diff→测试映射）；(3) 每日 schedule 全量已有，补"全量失败自动开 issue/通知"闭环；(4) release suite 覆盖清单登记为文档，重要新模块合入时同步评估是否入 suite。
- **验收**：约定入 CONTRIBUTING/checklist；schedule 失败通知闭环可演示；release suite 清单文档化。
- **估时**：1 天。

#### B1. mypy 基线棘轮入 CI

- **现状 [共识+锚]**：CI 无 mypy；配置在 `backend/pyproject.toml [tool.mypy]`（非 strict、ignore_missing_imports）；存量约 **1849 错 / 220 文件**（需 `--explicit-package-bases`，否则双重包名只报 1 错即止）[单源实测，量级可信]。
- **方案**：命令修正为 `mypy backend/app --config-file backend/pyproject.toml --explicit-package-bases`；以基线文件豁免存量（错误计数入棘轮只降不升）；新增错误即红；分包推进严格化（先 `core_finance` 子集）列为后续独立项。
- **验收**：CI mypy job 上线；基线外注入类型错误的验证分支被拦截；基线计数入 `debt-baselines.json`。
- **估时**：1 天。

#### B2. pytest 双配置陷阱消除

- **现状 [锚]**：根 `pytest.ini` 双根已合并（v0.2 的 B2 目标已不存在）；`backend/pyproject.toml` 另有 `[tool.pytest.ini_options]`（`testpaths=["../tests","tests"]`）——从 backend/ 目录起跑时 rootdir 切换、markers 定义丢失（UnknownMarkWarning 风险）。
- **方案**：删除 backend/pyproject.toml 的 pytest 段或与根 pytest.ini 完全对齐（markers 同步）；文档注明"统一从仓库根运行"。
- **验收**：`pytest backend/tests`（从任一目录）与根运行 markers 行为一致，无 UnknownMarkWarning。
- **估时**：0.5 天。

#### B3. 真实资产依赖测试的受控化

- **现状 [共识]**：真实数据 skipif 为 **4 文件 / 12 个装饰器**（`skipif(not all(path.is_file()...))` 模式，ledger/pnl 工作簿类）+ 若干 `pytest.skip` 族（redis-server ×5、Windows symlink ×3、Postgres DSN、系统 DuckDB、ledger pack、202606 real xlsx）[共识]；`var_engine.py`、`risk_metrics.py`、`adb_interbank_labels.py` 零测试 [单源]。
- **方案**：建 `tests/ci_skip_registry.json` 受控清单（覆盖 skipif + skip 两类）——CI 统计实际 skip 与清单比对，未登记新增即红；工作簿类已有合成黄金链（net-interest 模式）者补合成常驻版；环境类（redis/postgres/symlink）留清单不硬造；三个零测试模块——`var_engine`/`risk_metrics` 休眠先确认生产调用面（无调用则标休眠冻结 + 接线前必须补测），`adb_interbank_labels` 补直测。
- **验收**：registry 上线且未登记 skip 导致红灯（验证分支实测）；零测试模块处置落地。
- **估时**：2 天。

#### B4. 金融断言强度（文件名与容差修正版）

- **现状 [共识]**：`tests/test_krd.py`（非 test_krd_dv01.py）DV01 期望值自引用（`expected = m["face_value"] * m["modified_duration"] / 10000` 用被测输出推导）+ KRD 桶仅 `>0` 弱断言；`tests/test_bond_duration.py`（非 *_golden.py）以范围/恒等式断言为主；Campisi 的 `selection = total − income − treasury − spread` 是恒真式（selection 本就按残差定义），防不住符号/单位/互换类错误 [共识]。
- **方案**：KRD/DV01 补独立手算黄金常数（手算过程注释在测试内）；bond duration 补 ≥5 只标准券精确对照，**容差与实现 `quantize(1e-4)` 对齐（取 5e-4 级，不写 1e-8）** [单源修正]；Campisi 补 treasury/spread 分项的独立手算黄金值（真实仓储 dict 形状 fixture），替代恒真式。
- **验收**：三组黄金测试合入全绿，自引用期望删除。
- **估时**：1.5 天。

#### B5. 后端静态检查入 CI（修正版）

- **现状 [共识+锚]**：ruff `B` 族**已启用**（配置 ignore E501/B008/B904）、ESLint flat config `no-explicit-any` **已是 error 且存量≈0**——v0.2 两条主打措施是无效工作项；真缺口：**后端 ruff 不在 CI**；`S110/S112` 未启用（存量 9 处）[共识]；`BLE001`（裸宽捕获）存量约 182 处 [单源]。
- **方案**：CI 增后端 ruff job（现有配置）；启用 S110/S112（9 处即时清理或 noqa 登记）；BLE001 以棘轮引入（存量豁免清单只降不升，A3 修复的文件顺带清对应 BLE001）；考虑解除 B904 ignore（异常链丢失与静默吞错同根因）并按棘轮推进。
- **验收**：CI 后端 lint job 上线；S110/S112 零未登记违规；BLE001 计数入棘轮。
- **估时**：1 天。

#### B6. 前端契约强转收敛（口径修正版）

- **现状 [单源实测]**：`as unknown as` 全仓 251 处（绝大多数在测试），**生产代码约 11 处**（api/client mock 拼装、homeSupplementalClient envelope、ledger-pnl models、echarts option 等）；liability 域生产代码 0 处（v0.2 的 41/17 作废）。
- **方案**：生产 11 处逐个消除（envelope 边界补轻量 assert）；测试计数入棘轮防增长；目标改为"生产 0 + 新增禁止"。
- **验收**：生产路径 `rg "as unknown as" --glob '!*test*' --glob '!**/mocks/**'` 为 0（或白名单登记）；棘轮上线。
- **估时**：1 天。

#### B7. core_finance 直测缺口（重锚版）

- **现状 [共识]**：v0.2 点名的 balance_sheet/bond_ytm/holdings 模块已不存在（作废）；确认成立的：`fx_rates` 行为断言寄居 `tests/test_caliber_rule_fx_mid_conversion.py`；var_engine/risk_metrics/adb_interbank_labels 零测试（并入 B3 处置）。
- **方案**：fx_rates 用例迁出为 `tests/test_fx_rates.py`（纯移动）；其余并入 B3。
- **验收**：迁移后全绿，calibers 文件不再含 fx 行为断言。
- **估时**：0.5 天。

### 3.C 依赖、数据与 schema

#### C1. 依赖安装与 lock 一致化（重写版）

- **现状 [锚+共识]**：权威 = `backend/pyproject.toml` + `backend/uv.lock`（duckdb 钉 1.5.2 [单源]）；CI `uv lock --check` 后却用 `pip install -e "./backend[dev]"` 安装——**lock 校验与实际安装解耦**，范围内版本漂移仍可能；`tushare`/`akshare`/`EmQuantAPI` 等运行时依赖未入 pyproject [单源]；frontend 无 engines/packageManager 约束 [单源]。
- **方案**：CI 与本地统一 `uv sync --frozen`（或 `uv pip install` 等价物）；vendor SDK 依赖显式声明（可选 extra `[vendor]`）或文档化豁免理由；frontend 补 engines；Python 版本闸门改为"3.11（CI 现值）vs 生产实测"。**放弃 v0.2 的 pip-tools 方案**（与既有 uv 体系冲突）。
- **验收**：CI 安装产物与 `uv.lock` 一致（安装后校验脚本）；vendor 依赖声明或豁免登记。
- **估时**：1 天。

#### C2. 输入指纹残留与 data_input 治理（重写版）

- **现状 [共识]**：source_preview 内容 SHA256 **已上线且有测试**（GOV-P1-04 对应部分关单，勿重复建设）；真实 mtime-only 残留三处：`pnl_source_service.py:516`、`qdb_gl_input_validation_service.py:559`、`product_category_source_service.py:179` [共识×2]；`data_input/` 约 1306 文件、`YYYY.MM.DD` 与 `YYYYMMDD` 双日期格式并存（约 183 vs 970）[单源]；`*_fixed/*_v2` 人工副本当前 0 匹配（v0.2 描述作废）。
- **方案**：三处服务指纹补内容哈希（复用 source_preview 已有实现模式，每处附缓存失效影响说明）；MANIFEST 落在**可跟踪路径**（`.gitignore` 例外 `!data_input/MANIFEST.json` 或 `docs/data/`），登记 vendor 目录权威文件集合与双日期格式的规范化决定；`scripts/verify_data_input_manifest.py` 为**新建交付物**。
- **验收**：三处同 mtime 内容变化 → 指纹变化（新增测试）；manifest + 校验脚本上线。
- **估时**：1.5 天。

#### C3. schema 三套账对齐（新）

- **现状 [单源，证据具体]**：SQL 文件号（01–39 缺 26）≠ 迁移版本号（`duckdb_migrations.register_all` v1–v39，注释自认 v30 曾被复用）≠ `manifest.json`（仅 32 项，漏 32/34/35/36/37/38 号切片）；`30/31_*.sql` 不在 register_all，仅靠 `adjusted_returns.py`/`matched_baseline.py` 懒 ensure；legacy `ensure_*_legacy_columns` 与 `vw_external_legacy_*` 并存。
- **方案**：重锚后做三向对齐：manifest 补全 → 30/31 纳入 register_all（或显式登记懒加载豁免及原因）→ 加一致性契约测试（SQL 目录/迁移注册/manifest 三方 diff 即红）。不改任何表结构。
- **验收**：一致性测试上线且全绿；缺号/复用历史在 manifest 注记。
- **估时**：1 天。

#### C4. 脚本 DuckDB 直连治理（数量级修正版）

- **现状 [共识]**：裸 `duckdb.connect(` 约 **43 文件 / 64 调用点**（scripts+backend/scripts；含 read_only=True 6 处、显式写 3 处、dry_run 写 3 处）[单源实测]；服务层直连约 19 文件 [单源]；正确封装为 `duckdb_repo.read_only_connection` 与 `task_write_guard.repository_task_write_scope`（v0.2 的 duckdb_conn.py 不存在）。
- **方案**：先上静态棘轮（白名单=现状 64 处，只降不升，新增即红——含 services 层）；迁移分批：显式写脚本 6 处优先 → 常驻读脚本 → 研究/一次性脚本随 C5 归档不迁。**估时上调、目标降级为"棘轮 + 首批 10 处"**，全量迁移滚动进行。
- **验收**：静态守卫上线；写路径 6 处全部走 task write scope 或显式豁免登记；首批 10 处迁移。
- **估时**：2 天。

#### C5. 脚本生命周期与一次件归档

- **现状 [锚+共识]**：`backend/scripts` 13 个 .py、`scripts/` 146 个 .py [锚]；治理战役产物堆积（`portfolio_home_*` ×26、`emit_*` ×14 同构、`backfill_*` ×9、修复/诊断族）[单源分类]；`Lifecycle:` 头注释 0 处。
- **方案**：盘点清单（名称/用途/最近 touch/分类）；一次性已完成迁 `scripts/archive/`（git mv）；`emit_*` 14 个同构脚本收敛为单入口 + 参数（低风险重复消除）；新脚本头注释规范 + review checklist；`scripts/**` 下 266 个 .pyc 清理。
- **验收**：盘点归档；archive PR 合入；emit 收敛后功能等价（对照一次输出）。
- **估时**：2 天。

### 3.D 卫生

#### D1. 忽略规则收尾（v0.2 该项主体已完成）

- **现状 [锚]**：`.codex-tmp/` 已在 .gitignore:13。残留：`tmp-*.json` 未忽略（根目录 `tmp-backtest-stock_candidate.json` 未跟踪漂浮）。
- **方案**：补 `tmp-*.json` 规则；确认后删除该漂浮文件。**估时 0.1 天。**

#### D2. 视觉令牌基线诚实化

- **现状 [锚]**：当前红灯是 `dashboardHomeOptionTwo.module.css` hex 1 > 基线 0；`tokens.css` 基线曾在本日被从 106 上调至 122（基线上调=债务合法化，未见 owner 记录）。
- **方案**：修当前 1 处红灯；把"基线上调需技术负责人签核"写入 debt:audit 使用规则；`tokens.css` 122→106 的降债列为独立决策项（闸门第 13 项）。
- **验收**：debt:audit 全绿；基线变更规则入文档。
- **估时**：0.5 天。

#### D3. 分支/工作树盘点（产能修正版）

- **现状 [锚+共识]**：248 分支 / 83 工作树 [锚]；全合并可删仅约 **11 支**，236 支 ahead（1–14 提交不等）[单源实测]；约 11 个工作树含未提交改动 [单源]。
- **方案**：前置脏工作树处置决策（11 个逐个判定）；11 支全合并清理；236 支 ahead 出分类裁决报告（按最后活动/主题分组，owner 批次裁决——这是决策工作不是清理工作）；G6 目标按此改写。
- **验收**：处置记录 + 盘点报告 + 首批清理归档；无保留清单外删除。
- **估时**：1.5 天 + owner 裁决周期。

#### D4. 死代码清理（点位修正版）

- **现状**：确认项 [锚/共识]——`_prepare_yield_curve_inputs_for_refresh`（bond_analytics_service.py ~1070，无生产调用；删除需同步测试 patch 字符串）；`24_cffex_member_rank.sql` 头注释漂移（指旧 service 直写路径）。修正项 [单源]——乱码死函数实际是 `_apply_mapping_field`（qdb service ~750-759，v0.2 行号 1848-1876 落在活跃代码上，作废）；前端注释块两轮报告矛盾（一说 180 行一说不明显）→ 降级为搭车检查。新增 [单源]——前端死资产：`bond-analysis-foundation/` ~40 文件仅测试引用、`YieldAnalysisPage.tsx` 未挂路由但含前端聚合、`@nextui-org/react` 与 `framer-motion` 零引用死依赖。
- **方案**：确认项直接清（删除检查三件套：rg 引用/`__all__`/测试 patch）；单源项重锚后清；死依赖删除（快赢，bundle 减重）；bond-analysis-foundation 归档或删除评估单列。
- **验收**：各项清理后对应测试全绿；`npm ls` 无死依赖。
- **估时**：1 天。

### 3.E 结构（触碰式清偿）

#### E1. balance workbook 声明残留小修正

- **现状 [共识]**：canonical 反转已于 7·20 修复（`f9697fe4b`，包版 builder 为纯委托壳）；残留：单体 `core_finance/balance_analysis_workbook.py` 头注释仍写"新代码应从 package import"（与现实相反）+ 2 个测试直测休眠副本。
- **方案**：改头注释一致化；测试改指权威入口。**估时 0.25 天。**

#### E2. 债务棘轮机制（debt-baselines.json）

- **现状 [共识]**：`audit_frontend_debt.mjs` 基线为硬编码 const、只拦上涨、无下调机制；基线可被随手上调（D2 实证）。
- **方案**：基线外置 `debt-baselines.json`（多计数汇流：文件行数、mypy 计数、BLE001 豁免、as-unknown-as、duckdb 直连白名单、视觉 hex）；下调走显式 `--ratchet` 人工 PR（防 CI 写仓库）；**基线上调必须技术负责人签核并注明原因**；MacroToolkitPage 基线 11588 → 当前实测+2%（约 7200），BalanceMovementAnalysisPage（当前 ~4416–4612，活跃增长中）入监控名单。
- **验收**：json 机制合入；任一计数上升即红（验证分支实测）；上调签核规则入文档。
- **估时**：1.5 天。

#### E3. 格式化器收敛（口径修正版）

- **现状 [单源实测]**：共享层为 `utils/format.ts` 单文件（含 legacy fmt* 双轨）；亿元类本地定义约 36 处/27 文件、pct 类约 23 处、日期类约 20 处；≥14 个 Page 已用共享层（全仓 Page 约 44）；产品类别页用 `"-"` 而非 `EM_DASH`。
- **方案**：语义决策一次定齐——真零 `0.00` 与 null `—` 必须不同形（R-01）、精度按指标类型、NaN/空串防护、导出路径用 raw 数值；`format.ts` 内 legacy 双轨合并；迁移按"触达页面顺带替换"+ 本地定义计数入棘轮。
- **验收**：语义单测合入；棘轮生效；`"-"` 违规修复。
- **估时**：1 天（机制与语义）。

#### E4. core_finance 反向依赖（清单重锚版）

- **现状 [单源，v0.2 清单全部作废]**：当前反向 import 主要在：`module_contracts.py:5`、`source_preview_parsers.py:15`、`macro/toolkit/WindPy.py:8`、`macro/toolkit/system_sources.py:155`、`crowding_cn.py:31-32`、`matched_baseline.py`/`adjusted_returns.py` 的 schema_registry 懒加载。
- **方案**：实现前重锚全清单；按"正式链优先、注入改造、每处独立 PR + GitNexus 影响分析"推进；schema 懒加载与 C3 联动处置。
- **验收**：每处完成后该模块反向 import 为零且行为等价。
- **估时**：重锚 0.5 天 + 每处 0.5–1 天。

#### E5. macro route 拆分（工作量重估版）

- **现状 [共识+锚]**：`macro_toolkit.py` 非空 4062/总 4409 行 [锚]；统计函数已迁 `core_finance/macro/helpers.py`（v0.2"迁 pearson"工作量作废）；剩：ThreadPoolExecutor 1 处只读 fan-out（:683 附近）、路由内策略/危机分数/capability 装配编排（`_capability_payload` ~1641、`_compute_crisis_score_capability` ~2662 等）[共识]。
- **方案**：按端点域渐进拆到 `macro_toolkit_service`/`macro_toolkit_analysis_service`（已存在的服务）；ThreadPoolExecutor 按数值标准处置（p95>2s 或连接等待→任务化，否则限并发+超时并披露）；验收表述统一为"请求进程编排符合并发/超时约束"（消除 v0.2 自相矛盾）。研究型纯函数去向已解决（helpers.py），**闸门第 12 项（analytics 层）撤销**。
- **验收**：每域 PR 后端点契约测试不变绿；route 行数棘轮递减。
- **估时**：每域 1–1.5 天。

#### E6. MCP 单体与巨型 service（挂账+守卫）

- **现状 [共识]**：`moss_project_mcp.py` ~12.1–12.6k 行承载四服务并被 ~19 个脚本 import 成"第二服务层"；后端 >1000 行模块约 44 个，最长函数 `_compute_executive_overview` 695 行 [单源]。
- **方案**：均挂账不动；上两道守卫——巨型文件入棘轮名单（E2）、"禁新增 service 层 duckdb 直连与 route 层编排"静态断言（C4 联动）；MCP 触发条件（单月 ≥3 次契约变更或新增服务）写入登记。
- **估时**：随 E2/C4 交付，无独立估时。

---

## 4. 里程碑与排期

| Sprint | 内容 | 出口标准 | 估时 |
| --- | --- | --- | --- |
| Sprint 1（W1–W2） | A1 ADB 仿真、A2 路径清除、A3 静默点位、A4 曲线披露、D1、D2、D4 快赢（死依赖） | G1 首批 + G5 达成；debt:audit 全绿 | 约 8 人天 |
| Sprint 2（W3–W4） | B0 门禁分层、B1 mypy 棘轮、B2 配置陷阱、B5 ruff 入 CI、C1 uv 一致化、E2 棘轮机制 | G2、G3、G4 达成 | 约 7 人天 |
| Sprint 3（W5–W6） | A5 float 清单+首批、A6 前端补算首批、A7 前端 null 修复、A8 mock 面、A9 宏观、B3、B4、C2 | 数字正确性收口；受控跳过上线 | 约 10 人天 |
| Sprint 4（W7–W8） | B6、B7、C3 schema、C4 首批、C5 归档、D3 盘点、E1、E3、E4 重锚+首处、决策包提交 | G6 达成；闸门决策包全部提交 | 约 9 人天 |
| 持续 | E4 逐处、E5 逐域、E6 挂账守卫 | 棘轮计数每 Sprint 下降 | — |

决策包制作估时单列：13 项 × 0.5 天 ≈ 6.5 人天，分布在 Sprint 2–4。

并行约束：A3 静默点位群（executive/campisi/product_category）单人串行；A1/A2 可并行；前端项与后端项可双线。

---

## 5. PR 切片（21 个）

| PR | 内容 | 项 |
| --- | --- | --- |
| PR-01 | ADB 仿真默认关闭 + 影响报告 | A1 |
| PR-02 | 个人机器路径清除 | A2 |
| PR-03 | 静默点位群 fail-visible（单人串行；顺带清对应 BLE001） | A3 |
| PR-04 | 曲线解析披露 | A4 |
| PR-05 | 卫生快赢：tmp 规则 + 视觉红灯 + 死依赖删除 | D1、D2、D4 部分 |
| PR-06 | 门禁分层约定 + schedule 失败闭环 | B0 |
| PR-07 | mypy 基线棘轮 job | B1 |
| PR-08 | pytest 双配置对齐 | B2 |
| PR-09 | 后端 ruff 入 CI + S110/S112 | B5 |
| PR-10 | uv sync --frozen 一致化 + vendor 依赖声明 | C1 |
| PR-11 | debt-baselines.json 棘轮 | E2 |
| PR-12 | float 扫描清单 + campisi/scenario 首批 Decimal 化 | A5 |
| PR-13 | 前端补算首批（TPL 反推 + AverageBalanceView） | A6 |
| PR-14 | BalanceMovement null 语义（前端部分） | A7 前端 |
| PR-15 | mock 面披露收敛 | A8 |
| PR-16 | 宏观三项 | A9 |
| PR-17 | ci_skip_registry + 零测试模块处置 | B3、B7 |
| PR-18 | 黄金断言三组（krd/duration/campisi 分项） | B4 |
| PR-19 | 三处 mtime 指纹 + manifest | C2 |
| PR-20 | schema 三套账对齐 + 一致性测试 | C3 |
| PR-21 | 脚本静态棘轮 + 写路径迁移 + emit 收敛 + 归档 | C4、C5 |

（D3 盘点、E1 小修正、A7 core 层闸门项、E4/E5 逐处/逐域为后续滚动 PR。）

回滚与观察期原则沿用 v0.2：对外语义变化保留旧字段一个 Sprint；数值可能变化的 PR（PR-01/12、A7 core 层）必须先有影响报告。

---

## 6. 验证矩阵（文件名修正版）

```powershell
# A 组
python -m pytest tests/test_pnl_bridge_curve_effects.py tests/test_pnl_bridge_with_curve.py tests/test_campisi_attribution_service.py -q
python -m pytest tests/ -k "adb" -q                    # A1 相关（实现时以实际文件名收窄）
python -m pytest tests/test_macro_toolkit_async_write_refresh.py -q   # 注意：-k "macro_toolkit_write_refresh" 命中为 0，勿用

# B 组
python -m mypy backend/app --config-file backend/pyproject.toml --explicit-package-bases   # 带基线比对
ruff check backend --select S110,S112
python -m pytest tests/test_krd.py tests/test_bond_duration.py -q     # 黄金补强后改为新增文件名
python -m pytest --collect-only -q | Select-String "backend/tests"    # 双根收集确认

# C 组
uv lock --check --project backend; uv sync --frozen --project backend  # (PR-10 后为 CI 等价命令)
python scripts/verify_data_input_manifest.py                            # (PR-19 交付后生效，新建脚本)

# 前端
Set-Location frontend
npm run typecheck; npm run debt:audit
npm run test -- BalanceMovementAnalysisPage AverageBalanceView productCategoryPnlPageModel

# 静态守卫（对应 PR 交付后生效）
python -m pytest tests/test_decimal_discipline_static.py tests/test_scripts_duckdb_guard_static.py -q
```

CI 对照：PR 默认后端门禁 = `scripts/backend_release_suite.py`（约 24 文件）；全量 pytest 在 main/schedule——B0 交付前，重要修复必须在 PR 内显式跑 targeted tests。

---

## 7. 风险登记

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| 证据再度漂移（工作区活跃 + 本轮已发生基线被并行上调） | 高 | 第 0 节重锚纪律硬门槛；每 PR 首提交为重锚记录 |
| A1 关闭仿真使历史对比页面数字变化 | 高 | 影响报告先行 + owner 签核 + 前端空态处理同步 |
| A7 core 层缺失语义属正式口径变更 | 高 | 闸门 + 影响报告 + 黄金样本更新，不与前端修复混 PR |
| A5 Decimal 化改变数值 | 中 | 锁现值 + 自动差异脚本 + 超展示精度须确认 |
| C1 uv 统一暴露 pip 时代隐性依赖差异 | 中 | 切换前后 `pip freeze`/uv 导出 diff 审查 |
| C2 指纹升级使对应缓存 stale | 中 | 每处附失效面说明，分批合入 |
| 单源项失实 | 中 | 重锚不符即关闭，不带病实现 |
| D3 误删/丢失未提交工作 | 中 | 11 个脏工作树前置处置；删除仅限全合并证明 |
| Sprint 1 静默点位群互相踩踏 | 中 | PR-03 单人串行 |
| 巨型文件持续增长（BalanceMovement 当日仍在涨） | 中 | E2 棘轮尽早合入（Sprint 2 而非更晚） |

---

## 8. owner 决策闸门（13 项）

沿用 7·20 的 9 项（HQLA 2B、日均分母、缺 maturity 桶、舍入 HALF_UP/EVEN、DV01 与情景口径、CFETS 假日、CNH 归并、结构性存款、期限缺口阈值），加：

10. Python 运行时版本（3.11 CI 现值 vs 生产实测）。
11. 负数金额呈现约定（E3 最终样式前置）。
12. ~~analytics 层设立~~（撤销——统计函数已迁 core_finance/macro/helpers.py，无需新层）。
13. **新增**：视觉令牌基线 122→106 降债决策 + ADB 仿真日均是否保留（保留则 synthetic 披露口径）+ BalanceMovement core 层缺失语义变更（三件独立签核，共用决策包模板）。

每项决策包：现状/替代/真实数据差异/影响面/是否重物化/签核与生效日期。制作排期见第 4 节。

---

## 9. 附录

### 9.1 台账对照（v0.3）

| 状态 | 项 |
| --- | --- |
| 已关单勿重开 | 7·20 六 P0；API-P1-05（lazy proxy）；MACRO-P1-01/05/07；GOV-P1-04（source_preview 部分）；BAL-P2-01 主体（f9697fe4b）；双测试根合并；ruff B 族；ESLint any=error；contracts.ts 拆分；负债前端重算（SYS-P0-06） |
| v0.2 失实作废 | 原 A1（weightedDv01Sum）、原 A3（dashboardViewModel ∞%）、原 A5 前端猜单位（spreadAdapter）、原 A7 裸 except、原 A8（governance_repo 读路径）、原 A9 两点位、原 B2 目标、原 C1（requirements 三清单）、原 C2 副本清单、原 E4 六处清单、闸门 12 |
| 本 PRD 活跃项 | A1–A9、B0–B7、C1–C5、D1–D4、E1–E6，映射 7·20 编号：A3→部分对应原静默治理原则 R-01、A5→FI-P2-10 域、A9→MACRO-P1-02/04、B4→TEST-P1-01/02、C2→GOV-P1-04 残留、E4→API-P1-03、E5→API-P1-01/02 |

### 9.2 证据索引

- 锚点：第 0 节 12 项（主代理工具输出，2026-08-11）。
- 第二轮核实与评估报告 9 份（后端/前端/测试 CI/基础设施核实 + PnL/固收/余额/宏观/共享域评审 + 总体质量）。
- 第一轮 4 份审计 + 10 份评审报告：**证据可信度不足，仅作线索不作依据**。
- 对照：`docs/plans/2026-07-20-full-system-audit-remediation-plan.md`、`.planning/STATE.md`。

### 9.3 v0.2 → v0.3 修订记录（摘要）

1. 新增第 0 节证据勘误声明与三级证据标注；每 PR 强制证据重锚。
2. A 组全部重写：删除 4 个失实项，新增 ADB 仿真（锚）、个人路径（锚）、静默点位真实清单（共识）、前端补算残留面（单源）、core 层缺失语义（共识）。
3. B 组修正：B0 门禁分层为最高优先新项；mypy 存量 87→1849；B2 改配置陷阱；B5 删除已完成措施改 S110/S112+BLE001；B6 口径 47→生产 11。
4. C 组重写：pip-tools 方案废弃改 uv sync --frozen；指纹残留改为三处服务；新增 schema 三套账（C3）；脚本计数 390→159、直连 21→64。
5. D 组修正：D1 已完成；D2 改为基线诚实化（基线曾被上调）；D3 清理产能 136→11；D4 点位修正。
6. E 组修正：E1 已修改小修正；E4 清单全换；E5 统计迁移已完成、工作量重估；闸门 12 撤销。
7. 验证矩阵文件名全部修正（test_krd.py、test_bond_duration.py、test_macro_toolkit_async_write_refresh.py、ci.yml、uv 命令）。
