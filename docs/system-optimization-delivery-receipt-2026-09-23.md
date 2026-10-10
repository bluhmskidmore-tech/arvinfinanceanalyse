# 系统优化交付回执（2026-09-23）

本轮已有六项改动合入远端 `codex/V1`，当前提交为 `1c9f297a`。整分支 CI 揭示的 mock 客户端预载竞态已由 [PR #45](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/45) 修复；该 PR 的完整 CI 与合并提交的 [push CI 35816384652](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/actions/runs/35816384652) 均通过。本机 `:5888` 页面和 `:7888` API 未切换，因此“远端代码已合并”不等于“运行实例已更新”。

| 范围 | PR | 合并提交 | 结果 |
| --- | --- | --- | --- |
| 修复依赖锁中的已知漏洞版本 | [#42](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/42) | `07fd8600` | PR CI 全部通过，OSV 零发现 |
| 产品类别损益响应契约 | [#39](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/39) | `ebe29706` | 七个端点的契约及 PR CI 通过 |
| 稳定前端基准测试 | [#44](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/44) | `22d6089a` | 四处后台模拟加载竞态消除，PR CI 通过 |
| 曲线与损益桥测试选择器 | [#43](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/43) | `7ca7d213` | 专属 PR 门禁约 21 秒，PR CI 通过 |
| 余额变动远端读取 | [#41](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/41) | `3649d33f` | 读取失败状态、字段校验和取消超时，PR CI 通过 |
| Mock 客户端按需载入 | [#45](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/45) | `1c9f297a` | 消除闲置客户端的异步导入竞态，PR CI 全部通过 |

整分支首次 push CI 的前端断言全部通过，但三处未使用的 mock 客户端在测试环境关闭后继续导入模块，导致异步错误；同一提交的另一条 CI 通过，确认是竞态。PR #45 把 mock 导入延后到首次方法调用，保留同步可枚举的方法面；改前反例失败，改后通过。该改动暴露出 PnL 路由测试提前检查最终文字的问题，现已等待最终状态且保留原断言。定向客户端测试 65 项、PnL 路由 16 项、宏观工具页 107 项均通过；真实模式生产构建、类型检查、lint、债务审计、PR 完整 CI 与合并提交 push CI 均通过。`Backend Full Pytest` 和 `Agent Eval Replay` 在该 CI 中按选择器跳过，不计作已执行。

共享客户端的 GitNexus 上游分析基于与改动起点一致的 `3649d33f` 索引完成，`createApiClient` 被标为 CRITICAL 影响面，直接调用方及相关测试已核对。提交前 `detect-changes` 多次因本机全局索引注册表被并行任务改写而无法定位该工作树；改用当前源码、差异、定向回归与独立审查核对，未把图谱变更检测写成已通过。

余额改动针对响应体读取可能悬挂、失败或仅有缓存时仍显示确定报告日的问题。五份定向测试共 136 项通过；远端完整前后端测试、类型、lint、OSV 和无障碍检查通过。共享 GET 传输的响应体超时会影响其他调用方，已有传输层回归，但尚未在本机真实 API 与浏览器中验收。

选择器只移入远端基线已有的曲线引擎与损益桥映射，关联三份黄金测试；本地黄金测试 75 项通过。完整 102 项映射引用了远端尚不存在的源文件和测试，不能直接复制。新轻量工作流已在真实 `codex/V1` PR 事件中触发并通过；本轮 PR 没有修改曲线源文件，因此实际运行未选中黄金测试，不把“门禁触发通过”写成“生产曲线变更已回归”。

严格 Mypy 门禁仍在[草稿 PR #40](https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/pull/40)。远端已审阅依赖下，1,591 条历史诊断逐条匹配、零新增，PR CI 已通过；但本地尚未同步的 `a97f0f3a` 快照有 315 条未豁免诊断。它们未写入历史基线，在本地代码归属与诊断处理前不合并该门禁。

数据中心失败阶段界面只在隔离暂存树验证。远端目标分支缺少相应数据更新 route、service、repo、task 及其他依赖，单独移入界面会形成不可用入口，因此没有提交 PR，也没有上线。

本机运行版本复核时，`:5888` 指向已验收的 `.codex-tmp/frontend-builds/campisi-inputs-real-20260923-v4/dist`，309 个文件的清单哈希为 `6bbfd733ffe8d9e26d8f1dabc2771e2b652afae57700cdb411b2c82de4a31e11`；`frontend-plan` 和 HTTP `frontend-probe` 均通过。该清单没有源码提交号，实际客户端资产仍含创建 mock 客户端时立即导入模块的旧逻辑，故本轮 PR #45 未进入当前页面构建。

`:7888` 从 `F:\MOSS-V3` 的大量未提交源码启动，`/health/ready` 为 200，但不能证明运行了远端提交。当前 OpenAPI 已包含七个产品类别损益响应契约；余额读取的字段校验及依赖安全版本尚未齐备，当前虚拟环境仍为 AnyIO 4.13.0、Soup Sieve 2.8.3。远端 `1c9f297a` 与本机 `a97f0f3a` 共同祖先为 `fd702542`，本机独有 110 个提交，远端独有六项合并改动；19 个远端改动文件与本机已跟踪脏文件重叠。直接重建远端前端或覆盖本机后端会有功能回退风险，单纯重启后端仍会加载本机旧源码。现有脚本还将后端数据路径绑定在 `F:\MOSS-V3`，没有独立后端版本切换和回退入口。

因此本轮没有切换 `:5888` 或 `:7888`。下一步应在隔离目录保留本机源码及未提交文件的快照，只移入已核实缺失的余额字段校验、mock 按需载入和依赖版本，完成定向测试、构建及与当前 Campisi 页面逐项对比；前端通过清单验收后可用维护流程选择新构建。后端还需明确相同数据路径、源码身份和回退方式，才能在维护状态下切换并核对真实接口与业务对账。
