# MOSS 修复效果复验记录

后续修复已完成正式数据发布，实际风险接口现有 577 个可用日期、0 个受阻日期，详情及历史读取均通过，见 [正式发布记录](/F:/MOSS-V3/docs/MOSS_GLOBAL_REPAIR_PUBLICATION_2026-09-05.md)。以下保留发布前发现版本不一致和前端未启动时的复验原始证据。

本次复验确认：修复版本的计算、页面和隔离历史数据通过检查，但现有运行环境的风险接口尚不可用，不能通过正式运行验收。后端已经要求 v8 规则，正式库仍保留 v7，577 个日期全部被版本检查拦截。需要完成正式数据重算发布，使数据与服务要求一致。

2026-09-05 实测 `127.0.0.1:7888/health` 返回 200；风险日期接口返回 200，但可用日期为 0、受阻日期为 577。读取 `2026-07-31` 风险详情返回 503。日期接口明确说明：期望 `rv_risk_tensor_formal_materialize_v8`，实际为 `rv_risk_tensor_formal_materialize_v7`，需要重新物化。证据见 [运行接口结果](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/running-risk-detail.json)。这也修正了此前“运行服务尚未切换”的笼统表述：至少风险接口已经执行 v8 校验，正式数据没有同步。

前端常用端口 5888 本次没有服务监听。为验证页面对真实后端状态的处理，本次使用已验收的 real 模式构建，将上述运行后端的 GET 响应原样转入临时本地浏览器；页面明确显示“风险报告日已被新鲜度校验拦截”，没有用零值替代。此检查没有部署前端，临时服务结束后关闭。见 [运行状态页面截图](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/running-risk-blocked.png) 与 [浏览器回执](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/running-browser.json)。

计算和界面回归采用最终修复代码，并纳入后续新增用例，结果如下。各类检查存在重叠，不累加成独立用例总数。

| 检查 | 本轮结果 | 证据 |
| --- | --- | --- |
| 后端相关回归 | 565 通过，2 个既有样例缺失跳过 | [JUnit](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/root-backend.xml) |
| 前端相关回归 | 17 个文件、234 项通过 | [日志](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/root-frontend.log) |
| Playwright 导航及几何规格 | 15 项通过 | [日志](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/root-browser.log) |
| 页面可访问性与溢出 | 7 桌面、4 手机，均无违规及溢出 | [浏览器结果](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/browser/browser-results.json) |
| 首页标题与日期 | 390／768／1440 宽度无交叠，可键盘聚焦 | [边界框](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/after-geometry.json) |
| 隔离库历史逐字段对账 | 577 日期全部通过，v7 残留 0 | [对账结果](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/history-verification.json) |
| 候选服务及页面金额 | 三日期服务读取通过，页面显示 v8 与 -89.22 亿元 | [页面回执](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/browser-receipt.json) |

本轮再次确认，持仓和风险页面首次进入分别保持 7 次和 4 次接口请求，实际加载 JavaScript 较修复前减少 118,436 和 111,264 字节；切换同业页后返回债券页，没有重复请求或加载完整聚合客户端。对照使用同一组合成接口响应，仅用于验证加载与交互，不代表生产响应时间承诺。见 [构建加载对照](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/build-comparison.json)。

上述页面可访问性检查使用显式 mock 模式；候选金额核对使用隔离库实际服务响应；运行状态检查使用现有 7888 后端响应。这三种证据分别记录，没有用样例页面通过替代正式运行验收。源码及 271 个构建文件的哈希均与上一轮验收一致，见 [输入身份核验](F:/MOSS-V3/.codex-tmp/global-reverify-2026-09-05/input-identity.json)。

本轮仅增加验证脚本和结果记录，没有修改业务源码、正式数据库或治理记录，也没有重启现有后端。剩余动作是按 [修复验收报告中的发布安排](F:/MOSS-V3/docs/MOSS_GLOBAL_AUDIT_REPAIR_ACCEPTANCE_2026-09-05.md) 重新确认当前输入，备份正式库及治理记录，通过任务层发布 577 个日期，再检查运行接口与页面恢复。不能直接用整个候选库覆盖正式库，也不能通过放宽版本检查来隐藏这次阻断。
