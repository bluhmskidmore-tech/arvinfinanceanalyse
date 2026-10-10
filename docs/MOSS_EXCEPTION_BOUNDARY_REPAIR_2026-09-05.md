# 异常边界修复验收（2026-09-05）

本轮已处理工作区新增或改变的 20 处 BLE001 告警，其中 9 处收窄异常类型，11 处保留经负向测试验证的必要兜底。根代理完成 123 项联合回归。可独立提交的范围为研究日历五处旧捕获、20 项独立测试，以及仅删除对应五条记录的基线；其他修改已在工作区完成验证，但仍依赖前置未提交实现。

两位 Sol 分别实施治理和服务修复，另一位 Sol 独立审查代码，Astra 核对架构与提交依赖，根代理负责隔离验证和最终验收。复审曾发现接口及组件捕获被过度收窄，会破坏已有错误响应和组件隔离；该中间实现已纠正。

| 文件 | 收窄数量 | 保留并说明兜底数量 |
| --- | ---: | ---: |
| `backend/app/api/routes/adb_analysis.py` | 0 | 6 |
| `backend/app/governance/release_approval.py` | 0 | 2 |
| `backend/app/governance/release_control.py` | 3 | 0 |
| `backend/app/services/market_overview_service.py` | 0 | 2 |
| `backend/app/services/research_calendar_upstream_fetch_service.py` | 6 | 0 |
| `backend/app/services/stock_portfolio_construction_service.py` | 0 | 1 |

研究日历原来把程序缺陷和上游网络故障一起捕获，可能把异常转为空列表或跳过条目。现在列表请求仅捕获 `requests.RequestException`，详情处理捕获请求异常及数值解析的 `ValueError`；`RuntimeError`、`TypeError`、`AttributeError` 继续向外抛出。工作区原有的 `failed`、`partial` 和 warnings 披露保持，未把这套尚未提交的扩展混入独立提交。

发布控制只翻译仓储约定的 `ReleaseControlError`，已知错误的安全映射及异常原因保持，未知异常原样抛出，写入失败不能形成成功回执。审批验证器仍对任意适配器异常拒绝审批；ADB 保留统一、脱敏的错误响应；市场组件与股票影子风险失败仍给出可见降级。这 11 处保留的广捕获使用逐处说明的 `noqa`，不计作已经消除的广捕获。

验证保留了旧代码失败的证据。将独立新测试放到原提交代码上，得到 15 项失败、5 项通过；应用五处捕获修改后，新旧业务测试合计 25 项通过。隔离候选的 Ruff 门禁为 149/149，新增和移除均为零；Python 3.11 下门禁自身的 24 项测试通过。基线只删除该文件的五条旧身份，其余 149 条记录逐项完全相同。

工作区联合回归共 123 项通过，包含新增的 47 项边界测试及相关既有回归。Ruff 使用 Python 3.11 与 0.15.7 版本；业务回归使用项目根目录的解释器。门禁测试使用已安装 pytest 的独立 Python 3.11 环境。初次隔离校验缺少 pytest 或两个已提交的测试依赖，补齐验证环境后通过，未因此调整生产依赖或测试断言。

独立提交的四个文件为：

- `backend/app/services/research_calendar_upstream_fetch_service.py`
- `tests/test_research_calendar_exception_boundaries.py`
- `scripts/ruff_ble001_baseline.json`
- `docs/MOSS_EXCEPTION_BOUNDARY_REPAIR_2026-09-05.md`

其余修改暂不提交的原因是依赖尚未闭合。ADB 路由依赖尚未提交的 DTO 与路由改动；治理、市场概览和股票组合源文件本身也尚未进入 HEAD。研究日历新增的 MOF 详情隔离、重试和 `include_status` 披露与五处旧捕获拆开保留。不能用本轮异常测试通过，代替对这些整组特性的验收。

具体仓储异常基类引入了一项可接受的架构约束：替代 `ReleaseControlRepositoryProtocol` 实现若需要已有安全映射，必须使用同一异常基类。当前调用者和测试均使用真实仓储，未发现循环导入；这项约束已进入架构复核记录。修改前 GitNexus 判定三个研究日历函数为 HIGH，直接影响聚合、归档和抓取任务，其余本轮目标为 LOW。未变更计算公式、正式数据库、发布脚本或服务进程，也未扩展分析页面的正式使用资格。

完整命令、JUnit、冻结哈希、本轮独有补丁和逐文件依赖保存在 [本轮证据目录](F:/MOSS-V3/.codex-tmp/debt-exceptions-2026-09-05/)。关键回执包括 [联合回归](F:/MOSS-V3/.codex-tmp/debt-exceptions-2026-09-05/root-final-tests.json)、[隔离修复验证](F:/MOSS-V3/.codex-tmp/debt-exceptions-2026-09-05/candidate-positive-after.json)、[基线差异](F:/MOSS-V3/.codex-tmp/debt-exceptions-2026-09-05/candidate-baseline-delta.json)、[代码复审](F:/MOSS-V3/.codex-tmp/debt-exceptions-2026-09-05/review-code.md)及[架构复核](F:/MOSS-V3/.codex-tmp/debt-exceptions-2026-09-05/architecture/review.md)。最终 Git 提交号、其余暂存内容保护结果和工作区门禁结果另记入本轮最终回执。
