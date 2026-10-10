# MOSS-V3 全量审计修复 PRD（2026-08-27）

状态：执行中。来源：2026-08-27 全量系统审计（13 域并行审计）。
执行模式：49 个实施子代理分 4 波（Wave 1-4）+ 主代理终审。同波任务文件互不相交，跨波依赖串行。

## 1. 背景与目标

2026-08-27 全量审计产出 13 份域报告，经交叉评估与业务口径裁定后，形成本轮修复范围。
目标：消除已确认的 P0/P1 缺陷与高价值 P2/P3 项，解除 CI 门禁阻断，全部变更带可验证证据。

## 2. 业务口径裁定（不修项）

| 项 | 裁定 | 理由 |
| --- | --- | --- |
| DV01/CS01 面值基数 | 不修 | 用户裁定：面值即监管口径，`DV01_BASIS="face_value_modified_duration"` 契约与锁定测试自洽 |
| regulatory_dv01 默认全量 | 不修 | 监管口径覆盖全部正式持仓，include-all 自洽 |
| KRD 桶级 DV01 聚合 | 不修计算 | 面值监管口径的一致延伸 |

## 3. 本轮不实施项（含理由）

| 项 | 理由 | 去向 |
| --- | --- | --- |
| config/.env 凭据轮换 | 需在 Choice/Tushare/Stitch 服务侧操作 | 用户操作项 |
| 生产身份链（网关/JWT） | 架构决策，涉及认证保护边界 | 用户决策项 |
| agent prompt 脱敏/加密 | 合规策略选择（保留期、密钥管理） | 用户决策项 |
| 2027 CFETS 假日表 | 国务院假日安排未发布，禁止编造 | 2026-11 后运维补登 |
| 现金流真实付息计划 | 需付息计划数据源支持 | 后续专项 |
| 动量缺数返回 None | fail-explicit 是正确设计，前值填充反而引入隐性口径 | 关闭 |
| crisis z-score 截断 | 改变危机评分数值口径 | 需业务确认 |
| varchar/date schema 统一 | 数据库 schema 保护边界 | 仅做规范文档（O06b） |
| OTEL 生产 readiness 降级 | 部署策略项 | 用户决策项 |
| 前端 @ 路径别名迁移 | 全量 import 迁移属无关重构 | 关闭 |
| vol target 杠杆参数化 | 非缺陷（默认不加杠杆是当前业务行为） | 关闭 |
| Agent 测试纳入默认 CI | 排除面策略变更 | 用户决策项 |

## 4. 全局约束（每个子代理必须遵守）

1. 最小改动：只改任务指定文件与直接关联测试，禁止顺手重构。
2. 编码红线：含中文文件禁止用 PowerShell 文本命令读写；用 Read/StrReplace/Write 工具或 Node fs。
3. 禁止 git 写操作（commit/stash/checkout/restore 等）。
4. 正式金融路径（backend/app/core_finance/）变更必须附影响说明与测试证据。
5. 变更后运行任务指定的窄域验证命令并报告结果；失败必须如实报告。
6. 不修改本 PRD 未授权的口径（如 DV01 基数、H/A/T 映射规则本体）。

## 5. 任务总表

模型缩写：SOL=gpt-5.6-sol-max（后端，用户指定档位）、SON=claude-sonnet-5-thinking-high、G3=gemini-3.1-pro、GF=gemini-3.7-flash-high、C2=composer-2.5-fast。

### Wave 1（文件互不相交，35 项并行）

| ID | 任务 | 主要文件 | 验收 | 模型 |
| --- | --- | --- | --- | --- |
| B01 | pnl_basis_bridge 假门禁修复：rounding_alignment 独立容差校验并 fail-loud；arithmetic_status 可表达未闭合；net closure 冗余性注释；补"输入不自洽"黄金测试 | backend/app/core_finance/pnl_basis_bridge.py、schemas/pnl_basis_bridge.py、services/pnl_basis_bridge_service.py、tests/test_pnl_basis_bridge_contract.py | 注入缺口的用例在修复前失败、修复后按预期拒绝；原有 2 用例通过 | SOL |
| B02 | pnl_attribution workbench float→Decimal 全程迁移，输出边界转 float | backend/app/core_finance/pnl_attribution/workbench.py + 对应测试 | 三因子闭合恒等式测试通过；现有调用方测试通过 | SOL |
| B03 | 宏观综合评分权重复核：先验证缺项时真实取值路径；确认缺陷才做动态归一 | backend/app/core_finance/macro/macro_portfolio_impact.py + 测试 | 复核结论+（如修）缺项场景测试 | SOL |
| B04 | 回测夏普年化复核：验证 returns 序列频率与 365 年化是否错配；确认错配才修 | backend/app/core_finance/portfolio_backtest.py + 测试 | 复核结论+（如修）年化口径测试 | SOL |
| B05 | 固收引擎：久期期数闰日阈值跳变修复（按真实付息节奏取整）+ 负收益率合法化（-f<ytm 允许，Dmod 公式修正）；更新 test_krd_golden 等锁定值并出影响报告 | backend/app/core_finance/bond_analytics/common.py、engine.py + tests | 闰日残端用例得到 20 期/约 8.5230 年；负 ytm 探针不再回退；固收套件通过 | SOL |
| B06 | source_preview_repo 六个写函数补 require_repository_task_write_scope + 守卫测试 | backend/app/repositories/source_preview_repo.py、tests | 作用域外调用抛 PermissionError 测试通过；source_preview 流程测试通过 | SOL |
| B07 | stock_adjustment actor 纳入 CANONICAL_TASK_MODULES（或去注册改纯函数，二选一给证据） | backend/app/tasks/worker_bootstrap.py、stock_adjustment_factor_daily_refresh.py | worker 模块清单测试/导入验证通过 | SOL |
| B08 | commit_report_date_purge 与 sync_zqtz_snapshot_market_value_cny_from_formal 补自带守卫；补 purge 提交后-插入前中断的故障注入测试 | backend/app/repositories/fact_load_gates.py、balance_analysis_repo.py、新测试 | 故障注入断言"该 report_date 零行+状态可识别"；守卫测试通过 | SOL |
| B09 | research calendar 上游抓取：有限次指数退避 + source status/warnings 区分空数据与抓取失败 | backend/app/services/research_calendar_upstream_fetch_service.py + 测试 | 失败注入用例返回失败状态而非空列表 | SOL |
| B10 | queued→cancelled 取消路径补 agent_audit 最小 payload（与 failed-run 审计同构） | backend/app/services/agent_run_service.py + 测试 | 取消排队 run 后 agent_audit 流有记录 | SOL |
| B11 | local_request_resolution follow-up 标记改整 token 匹配，降低会话自我误导 | backend/app/agent/runtime/local_request_resolution.py + 测试 | 误触发用例不再命中；意图路由测试通过 | SOL |
| B12 | action token secret：production 且未配置时启动告警（不改回退链行为） | backend/app/agent/runtime/action_token.py 或装配点 + 测试 | 告警触发测试通过 | SOL |
| B13 | macro/helpers.to_decimal_safe 委托共享 decimal_utils.to_decimal，文档化差异 | backend/app/core_finance/macro/helpers.py + 测试 | 行为等价测试通过（None→0 值不变，新增共享告警可接受） | SOL |
| B14 | accounting_basis 规则 docstring 与 _GATE_ENFORCED_RULES 实际状态对齐 | backend/app/core_finance/calibers/rules/accounting_basis.py | 文案与 backend/scripts/audit_caliber_violations.py 一致 | SOL |
| B15 | 错误响应治理：market_data_livermore 不泄漏 csv_path/异常文本，改稳定错误码+固定文案（日志保留细节） | backend/app/api/routes/market_data_livermore.py + 测试 | 404/503 响应不含内部路径 | SOL |
| B16 | API 启动迁移环境感知：development 保留自动迁移；非 development 默认跳过写并 fail-fast 校验 schema 版本 | backend/app/main.py、storage_bootstrap.py、duckdb_schema_bootstrap.py + 测试 | 两种环境行为测试通过 | SOL |
| B17 | Hermes/Dexter 审计写失败：独立失败计数+ERROR 级告警日志（保留可用性优先），代码注释说明与本地路径的不对称权衡 | backend/app/services/hermes_agent_service.py、dexter_agent_service.py + 测试 | 注入审计写失败时告警可观测、业务应答不变 | SOL |
| B18 | governance settings 枚举/范围校验：environment 等关键字段 Literal 化、未知值 fail-fast、数值字段正区间；先盘点现有合法取值防破坏 | backend/app/governance/settings.py + 测试 | 非法值拒绝、现有配置组合全部可启动 | SOL |
| F01 | LedgerPnl 表格：formatAnalysisValue 补 Number.isNaN 拦截 + 行 key 改业务复合键 | frontend/src/features/ledger-pnl/components/LedgerPnlWorkbookTables.tsx + 测试 | NaN 渲染为 —；key 无 index | SON |
| F02 | 全局格式化层：formatYi/formatPercent/formatRawAsNumeric 等统一 Number.isFinite 拦截；decimalRaw 弃用 parseFloat 改严格十进制正则；formatYi/formatWan 千分位与 formatYuanAmountAsYiPlain 对齐；更新受影响测试 | frontend/src/utils/format.ts、frontend/src/api/numeric.ts + 测试 | Infinity/"12abc" 显示 —；千分位一致；vitest 相关套件通过 | SON |
| F03 | bond-dashboard：bp 差值改安全舍入（不引新依赖）；饼图降级分支最大余额补差 | frontend/src/features/bond-dashboard/utils/format.ts、components/AssetStructurePie.tsx + 测试 | 半分位边界用例正确；降级饼图合计 100.00% | SON |
| F04 | Agent 契约可空性：value/data/spec 改 `| null`；AgentContractSync 增加 required/nullable 对照；demo 信封 evidence_strength=local_fallback、quality_flag=warning；demo 余额复算改固定 payload | frontend/src/api/contracts/agent.ts、agentClient.ts、balanceAnalysisClient.ts、test/AgentContractSync.test.ts | parity 测试含可空性断言全绿 | SON |
| F05 | StockAnalysisCandidateLedgerTable 去 Tailwind 残留，改 CSS module + designSystem token | frontend/src/features/stock-analysis/components/StockAnalysisCandidateLedgerTable.tsx + 新 .module.css | 无 tailwind 工具类残留；组件测试通过；视觉等价 | G3 |
| F06 | transport 核心载荷轻量字段断言（agent/pnl 信封）：外壳校验升级为关键字段存在性+类型检查，失败进契约错误态 | frontend/src/api/transport.ts、pnlClient.ts、agentClient.ts + 测试 | 缺字段 payload 触发契约错误而非静默 undefined | SON |
| T01 | dashboard/strategy_reports/team_performance 三路由补契约冒烟测试（200+结构断言） | tests/ 新增 | 三条路由测试通过 | G3 |
| T02 | buildHomeBondNewsModel 补单元测试 | frontend/.../adapters/buildHomeBondNewsModel.test.ts | 覆盖空/正常/异常输入 | C2 |
| T03 | 7 个依赖 date.today() 的测试冻结时间（monkeypatch/freezegun 已有依赖则用） | tests/test_market_home_warmup.py 等 7 文件 | 冻结后全部通过 | G3 |
| O01 | 三个定时任务安装脚本 Python 路径改 .venv 动态解析（参照 register_scheduled_tasks.ps1） | scripts/install_*_timer.ps1 ×3 | 语法校验+路径解析逻辑正确 | C2 |
| O02 | start_dev.cmd 去硬编码盘符，改 %~dp0 相对解析 | start_dev.cmd | 任意克隆路径可用 | C2 |
| O03 | .gitignore 补全：output/、.tmp-agent*/、unused/、missing-governance-dir/、.locks/、.hypothesis/、frontend/.tmp-audit-evidence/、frontend/tmp_shots/、**/.tmp_*；不删除任何现有文件 | .gitignore | git status 未跟踪噪音大幅下降且不误伤已跟踪文件 | C2 |
| O04 | scripts/archive 三个归档目录补 README 声明静态快照+失效导入清单 | scripts/archive/*/README.md | README 就位 | GF |
| O05 | AGENT_MVP_RUNBOOK 补：外部 CLI 只读语义信任边界与升级复核要求；JSONL 压缩任务升级为强制周期任务 | docs/AGENT_MVP_RUNBOOK.md | 文档就位 | GF |
| O06a | 余额域代码注释措辞：qdb_gl 量价归因"校验差异"改"恒等式自检（非独立对账）"；liability_compat 不对称口径注释；AAA 默认值收录进规则引用表 | backend/app/core_finance/qdb_gl_monthly_analysis.py、liability_analytics_compat.py、balance_analysis_workbook.py（注释/文案级） | 相关测试不回归 | G3 |
| O06b | calc_rules.md 追加：总账自检占位读者告知规则；跨正式表/快照表连接必须完整自然键+NULL-safe 规范；KRD 面值口径展示措辞说明；DV01 面值=监管口径裁定记录 | docs/calc_rules.md | 文档就位 | G3 |
| O08 | cube_query 路由头注释"需要认证"改为 RBAC 事实描述 | backend/app/api/routes/cube_query.py | 文案准确 | GF |

### Wave 2（依赖 W1 或与 W1 文件相交，9 项）

| ID | 任务 | 主要文件 | 验收 | 模型 |
| --- | --- | --- | --- | --- |
| B19 | 质量标记落库：coupon/ytm_input_status、duration_quality_flag 三列 additive 迁移+INSERT+读路径透出；风险汇总按质量剔除或披露 | backend/app/core_finance/bond_analytics/engine.py、repositories/bond_analytics_repo.py、duckdb 迁移 | 迁移幂等；标记端到端测试 | SOL |
| B20 | Numeric 精度：raw 保留 float 兼容，新增无损字符串字段（如 raw_text）承载 Decimal 原值；前端 decimalRaw 优先消费新字段；抽样核心金额端点验证 | backend/app/schemas/common_numeric.py + frontend/src/api/numeric.ts | 大额 Decimal 端到端不丢位；现有消费方不破坏 | SOL |
| B21 | balance_analysis 路由补严格 response model（extra 收紧） | backend/app/api/routes/balance_analysis.py、schemas | OpenAPI 该路由有具体 schema；契约测试通过 | SOL |
| B22 | adb_analysis 路由：批量派发循环下沉 service、detail 泄漏修复、数据源缺失映射 503、补 response model | backend/app/api/routes/adb_analysis.py、services 新/扩展文件 | 路由瘦身；ADB 测试套件通过 | SOL |
| B23 | macro_toolkit 路由：payload builder 下沉 service、补 response model | backend/app/api/routes/macro_toolkit.py、services | 路由瘦身；宏观工具箱测试通过 | SOL |
| B24 | RBAC 强化：ensure_user_allowed 接入 route_policy 等级校验（存量冲突先告警模式）；grant_scope 写前拒绝低角色高动作+审计留痕；write/refresh/execute 不走 30s 缓存 | backend/app/security/auth_context.py、route_policy.py、repositories/user_scope_repo.py + 测试 | 现有权限测试全绿+新校验测试 | SOL |
| B25 | agent_audit/agent_prompt 纳入 governance SQL authority（沿用 cache_build_run 表模式：建表迁移+SUPPORTED_SQL_STREAMS+回退兼容） | backend/app/repositories/governance_repo.py、schema_registry、tests | sql-authority 模式下两流落 SQL；JSONL 回退兼容测试 | SOL |
| F07 | balanceLedger/pnl 契约去过度可选化（对齐后端必返字段）；mocks/fixtures 补齐字段或独立类型 | frontend/src/api/contracts/balanceLedger.ts、pnl.ts、相关 mocks | typecheck 通过；相关 vitest 通过 | SON |
| O07 | 35 个文件 BOM 清理（Node fs 逐文件去 EF BB BF），跑 audit_encoding_integrity 验证 | 35 个带 BOM 文件（先扫描确认清单） | 扫描 0 BOM、0 U+FFFD；py/tsx 可解析 | C2 |

### Wave 3（依赖 W2，2 项）

| ID | 任务 | 主要文件 | 验收 | 模型 |
| --- | --- | --- | --- | --- |
| B26 | service→api 反依赖解耦：response_cache/perf_logging/builder registry 迁到平台层，入口显式注入 | backend/app/api/response_cache.py、perf_logging.py、涉及 services | 无 services 导入 backend.app.api；启动+缓存测试通过 | SOL |
| F08 | 契约同步测试扩展：balance/pnl/portfolio 与后端 schema 的字段级 parity 测试（含可空性），参照 AgentContractSync 模式 | frontend/src/test/ 新增 | parity 测试全绿并能捕获注入的漂移 | SON |
| T04 | skip/xfail 测试盘点：逐条记录理由与恢复条件，产出清单文档 | docs/plans/2026-08-27-skipped-tests-inventory.md | 清单完整 | GF |

### Wave 4（终态基线，2 项）

| ID | 任务 | 主要文件 | 验收 | 模型 |
| --- | --- | --- | --- | --- |
| T05 | 黄金样本核对更新：复跑 capture-ready 全套；漂移逐项归因（工作区既有 v4 升级 vs 本轮 B01/B02/B05 修复），确认预期后更新样本 JSON 并记录归因 | tests/golden_samples/、tests/test_golden_samples_capture_ready.py | 全套通过且每项漂移有归因记录 | SOL |
| T06 | OpenAPI 基线更新：baseline-update 后 baseline-check 通过；diff 逐条归因（既有变更 vs 本轮 B21-B23） | contracts/openapi/ | api_contract_check baseline-check 退出码 0 | SOL |

## 6. 终审（主代理）

1. git diff 全量审查对照本表逐项核销。
2. 后端：ruff/相关 pytest 套件；前端：typecheck + 相关 vitest。
3. 正式金融路径影响汇总（B01/B02/B05/B13/B19 涉及）。
4. 输出：变更文件列表、测试证据、残余风险、未完成项。
