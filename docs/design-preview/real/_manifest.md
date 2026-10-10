# 真实现状采集 Manifest（real/）

采集时间：2026-07-19 12:33–12:35（本地）
环境：后端 FastAPI @ 127.0.0.1:7888（Postgres 开发集群 @ 55432 + DuckDB `data/moss.duckdb`），前端 Vite @ 127.0.0.1:5888（代理 /ui、/api → 7888）
截图规格：1440×900 视口，Playwright Chromium 无头；未登录跳转（后端 dev 模式未触发 auth 护栏，未设置任何 MOSS_* 绕过变量）
采集方式：`real/_capture.cjs`（只读，不修改任何源码）；每页等待 12–18s 让异步数据加载完成；同步记录页面发出的全部 /ui、/api 请求与状态码

## API 抽查（curl 直打，走 vite 代理）

| 端点 | 状态 | 关键日期字段 | 备注 |
|---|---|---|---|
| `/ui/home/snapshot` | 200 | `report_date=2026-06-30`，`effective_report_dates={balance_sheet:2026-06-30, pnl:2026-06-30}` | `basis=analytical`，`quality_flag=ok`，`fallback_mode=none`，真实 JSON（债券资产规模 3,734.29 亿等） |
| `/api/bond-dashboard/home-summary?report_date=2026-06-30` | 200 | `resolved_report_date=2026-06-30`，`as_of_date=2026-06-30`，`date_basis=bond_dashboard_report_date` | `rule_version=rv_bond_analytics_formal_materialize_v1`，`quality_flag=ok`，`fallback_date=null` |
| `/ui/market-data/rates` | 200 | source_version 含 `sv_public_bond_zh_us_rate_20260710`、`sv_public_currency_boc_safe_20260710` 等（行情截至 2026-07-10） | `basis=formal`，`formal_use_allowed=true` |

## 页面登记

| # | 页面 | 截图 | 数据来源判定 | 判断依据 | 可见加载失败/异常区块 |
|---|---|---|---|---|---|
| 1 | `/` 经营日报首页（深色） | `real/home.png` / `real/home.txt` | **真实 API** | 页面请求 `/ui/home/snapshot`、`/api/bond-dashboard/*`、`/api/bond-analytics/*`、`/ui/news/*` 等 24 个数据接口全部 200；页面徽标"数据已更新 · 通过 · 报告日一致"，报告日 2026-06-30 | 无。"待复核"区显示"暂无复核入口/当前无待办"为正常空态；"保留缺口 暂不可用"为功能未接入声明（非加载失败） |
| 2 | `/portfolio` 组合首页（深色） | `real/portfolio.png` / `real/portfolio.txt` | **真实 API** | `/api/bond-dashboard/home-summary`、`/ui/balance-analysis/overview`、`/api/bond-dashboard/risk-indicators`、`/api/pnl-attribution/summary` 全部 200；源日期徽标：债券总览/风险指标/资产负债/损益归因均=2026-06-30，"同日闭合" | 页面自带"仅供分析：来源证据未达到决策级口径"警示条（业务口径声明，非加载失败）；无失败区块 |
| 3 | `/market-overview` 市场首页（深色） | `real/market.png` / `real/market.txt` | **真实 API** | `/ui/market-data/rates`、`/ui/macro/choice-series/latest`、`/ui/macro/toolkit/analysis`、`/ui/news/choice-events/latest` 全部 200；"已接入 最新行情日 2026-07-10 正式序列日 2026-07-10" | 无。事件状态区注明"choice-events 已返回 12418 条" |
| 4 | `/bond-analysis` 债券分析（深色） | `real/bond-analysis.png` / `real/bond-analysis.txt` | **真实 API** | `/api/bond-dashboard/bundle?sections=headline-kpis…`（聚合 12 个 section）、`/api/bond-analytics/return-decomposition`、`/api/bond-analytics/action-attribution` 全部 200；报告日 2026-06-30（日期下拉含 2026-05 起连续日期） | 无。10年国开/中美利差/DR007/美元人民币 快照位显示 `--`（该页该卡片未取数，属页面设计空位） |
| 5 | `/market-data` 市场数据（浅色页+深色首屏孤岛） | `real/market-data.png` / `real/market-data.txt` | **真实 API（含 1 个失败子接口）** | 16 个数据接口 200（rates、catalog、fx、livermore、bond-futures 等），数据日期 2026-07-10；**`/api/external-data/watermarks` 返回 403** | 宏观深度读面顶部黄条："宏观序列最新读面已返回数据。外部数据水位读取失败，无法判断输入年龄。"（对应 watermarks 403）；证据口径总览显示"未接入 2 / 代理数据 1" |
| 6 | `/operations-analysis` 经营分析（浅色） | `real/operations.png` / `real/operations.txt` | **真实 API（含 1 个失败子接口）** | `/ui/balance-analysis/overview`、`/ui/pnl/product-category`（monthly）等 200，报告月份 2026-06-30、产品行数 18、正式 FX 5/5；**`/ui/preview/source-foundation` 返回 503** | "源批次"卡片显示"不可用 / 当前查询失败，请在下方面板重试"（对应 503）；页面顶部固定"临时例外"横幅（PAGE-OPS-001 收口期路由保留声明） |
| 7 | `/reports` 报表中心（浅色） | `real/reports.png` / `real/reports.txt` | **部分真实 + 明显失败态** | `/health/live`、`/health` 200（Live ok / Health ok）；**`/ui/preview/source-foundation` 503、`/api/cube/dimensions/bond_analytics` 403** | 整页"读取失败"徽标 + "数据中心读链路失败，不使用前端补数"；数据源状态、自助查询、Cube 维度与度量三个区块均为"读取失败"红字；数据源计数 0、Cube 维度 0；报表中心显示"规划中"（未接入声明） |

## 补充说明

- 所有页面 console 错误仅来自上述 403/503 网络失败（reports 页另有 1 条 React 重复 key 警告：`读取失败：不使用前端补数` 列表项）。
- 各页 `*.txt` 内含：`document.body.innerText` 前 ~3000 字符、`body`/`html`/`main` 计算背景色与字体、页面 CSS 自定义属性快照、完整 API 请求清单（方法+状态码）。
- 首屏底色实测：全局 `body` 为暖浅灰 `rgb(244,243,240)`；深色页（home/portfolio/market-overview/bond-analysis）由页面容器自带深色 surface 覆盖；market-data 内容区浅色、顶部快讯条与左侧导航为深色孤岛。
- 全局 CSS 变量含 `--radius: 0.5rem`、`--background: oklch(0.9702 0 0)`、MOSS 品牌色阶 `--moss-color-primary-50…500`（蓝系）。
- 采集脚本 `_capture.cjs` 与原始记录 `_capture.json` 保留在本目录供复核。
