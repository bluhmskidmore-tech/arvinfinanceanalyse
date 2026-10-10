# 首页恢复、宏观来源修复与股票历史缺口

## 首页修复已上线

2026 年 9 月 16 日 10:08，首页报告日恢复功能已切换到本机 5888。真实接口和浏览器验证通过：请求 2026-08-28 时说明缺少正式损益；点击“查看最新可用报告”后清除日期筛选、保留其他查询参数，由后端返回 2026-08-31。已有有效快照时继续显示其实际日期和过期原因。

缺口来自源数据的日期覆盖。余额、持仓与债券分析各有 608 个日期，正式固收损益有 20 个月末日期。数据中心对 2026-08-28 的完整财务预检返回 `ready=false`，固收损益文件缺失；已有 `FI损益202608.xls` 的明确期间是 2026-08-01 至 2026-08-31。此次没有复制月末值、补造日损益或发起财务重算。

后端仅在确定请求日缺少数据、同时存在其他严格交集日期时返回结构化 503 说明。前端按错误代码区分报告日不可用与权限、网络错误，显示业务原因并提供显式恢复动作。移动端提示可完整换行，恢复按钮保持单行和 44px 点击高度。

主要生产改动位于 `backend/app/services/executive_service.py`、`backend/app/api/routes/executive.py` 及 `frontend/src/features/workbench/dashboard-home/`。日期交集、业务指标、金融计算和全局状态架构保持原有口径。相关契约补充在 `docs/page_contracts.md`。

## 验证证据

| 检查 | 结果 |
| --- | --- |
| 首页域及页面集成 Vitest | 40 个文件，396 项通过，0 失败 |
| 首页服务、端点、缓存及 E1 release pytest | 71 项通过 |
| 宏观抓取、周期来源配置与可用日期契约 pytest | 111 项通过 |
| TypeScript 类型检查 | 通过 |
| 前端 ESLint | 0 错误，1 项既有热更新警告 |
| 前端六项规范审计 | 全部通过 |
| 最终生产构建 | 306 个文件，构建保护检查通过 |
| 390px / 560px 浏览器 | 无横向溢出，恢复按钮为 140×44px |
| 真实 5888 / 7888 | 构建哈希匹配，健康检查通过，恢复交互通过 |

旧后端测试曾遗漏产品分类快速读取路径的隔离；已补齐测试替身并验证线程上下文转发，未放宽 DuckDB 保护。后端改动路由与端点测试 Ruff 通过；完整服务文件原有 38 项未使用导入告警，除这些既有 F401 外，本轮涉及文件检查通过。

运行回执位于 `.codex-tmp/frontend-remaining-20260916/`。最终构建目录为其中的 `accepted-build-final`，清单 SHA256 为 `9d26977a9db85f149ffbf4178ad432100ed90dfeafea7c8dd06b1c17a6fa4b0a`。切换回执记录 frontend PID 52368、API PID 46916、keeper PID 12508；worker 完整进程树保持原身份，maintenance 已退出，临时 5989/7988 已清理。回退目标是本轮切换前的 9 月 16 日已验收构建。

## 宏观抓取和信用时效问题已修复

现用 Tushare SDK 的宏观请求固定访问 `http://api.waditu.com/dataapi`，实测失败。`backend/app/tasks/macro_backfill.py` 已改用项目已有的 `https://api.tushare.pro` 地址，保留证书验证、超时、字段映射、请求窗口和来源顺序；没有修改全局 SDK。新增回归覆盖社融同比的上年窗口、GDP 原有字段、异常响应和连接释放。GitNexus 对受影响入口报告 LOW；索引提交与 HEAD 一致，但未识别分支调用，已用本地代码补足 `backfill_macro_series`、`_fetch_rows_for_plan`、`_fetch_by_source`、`_fetch_from_tushare` 的调用证据。

真实 HTTPS 验证返回八月 PMI。M2 与社融原始返回仍止于七月，因此又核验了[央行八月金融统计报告](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026091417020862747/index.html)：报告于 2026-09-14 17:00 发布，原始页面 `createDate` 为当日 17:02:09，社融存量同比 7.2%，M2 同比 7.5%。原始 HTML 的 SHA256 为 `2be3b50ac4c72068c9b17e28b184cb2186b3f6a6ffe606c2a5b58334bf642998`。现有解析器完成标题、哈希、口径和数值交叉校验后，已将这两项加入 `config/cycle_rotation_macro_official_releases.json`。

10:51 通过既有 `backfill_macro_series` 任务写入两条八月记录，执行窗口为 2026-08-01 至 2026-09-16，实际新增日期均为 2026-08-01（月度期间标记）。任务回执为 `backfill_macro_v1:20260916T025150Z`，`total_added=2`，落库值、单位、来源版本和真实 run_id 核对通过，迁移版本清单没有变化。没有重跑财务或股票历史链路。

另在 `config/cycle_rotation_macro_official_availability.json` 绑定原始报告、任务实际生成的 vendor_version 和发布日期之后的首个已观察市场日 2026-09-15。没有改写实际入库时间。回归和生产读取均验证：9 月 14 日仍拒绝使用，9 月 15 日起允许读取。真实 `/ui/market-data/livermore/signal-confluence?as_of_date=2026-09-15` 返回 HTTP 200、`quality_flag=ok`、`macro_authority_status=ready`；信用输入业务日为 2026-08-31、age 15、tier `fresh`，此前信用时效阻断已消除。

对应验证命令为 `.venv\Scripts\python.exe -m pytest tests/test_macro_backfill.py tests/test_cycle_rotation_macro_seed.py -q`（71 项通过）和 `.venv\Scripts\python.exe -m pytest tests/test_cycle_macro_input_contract.py -q`（40 项通过）。三个涉及的 Python 文件 Ruff 通过，新增用例保持非正式分析面的回归标记。

写入期间短暂停止 API 释放 DuckDB 锁，10:52 已恢复 API（PID 32908）并通过健康检查。前端 PID 52368、已验收构建与 worker 进程树保持原状，系统发布仍关闭。数据回执、可用日期绑定验证及真实 API 结果分别保存在本轮证据目录的 `credit-refresh-result.json`、`credit-availability-binding-validation.json`、`credit-confluence-live-api.json`；运行恢复见 `credit-refresh-runtime.json`。

## 股票历史缺口按用户决定跳过

当前系统发布开关维持关闭。现有 v1 发布包没有盘前来源资格，不能仅打开开关恢复候选。当天股票基础来源存在，Tushare 股票端点访问成功；本轮已补齐信用来源，回放窗口仍有历史缺口。

2026-04-13、2026-05-20、2026-07-08、2026-07-10 缺少真实的历史股票主题／概念归属。用户确认项目外也没有归档，并决定跳过，因此本轮停止历史补齐，不再重跑无法达到资格要求的 92 个缺口日期。

现有 `ready_empty` 契约允许可信来源下的零候选，仍要求宏观、回放和规则证据闭合。跳过上述日期不会消除来源缺口，也不会自动取得发布资格；股票候选与研究操作继续保持观察态，系统发布开关维持关闭。本轮没有进行股票业务写入或发布。
