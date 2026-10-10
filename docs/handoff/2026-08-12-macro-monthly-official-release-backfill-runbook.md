# 宏观月度官方数据补录手册（2026-07 及以后）

日期：2026-08-12。来源：七月宏观数据登记任务的侦察结论（本机 NBS/PBC 域名 TLS 定向阻断，未能执行，零登记零写入）。

## 背景与机制

美林时钟（`merrill_clock_cn`）依赖月度宏观序列，7 月数据缺口使模型停在 2026-06。系统的官方发布防伪链路在 `backend/app/tasks/macro_backfill.py`：

1. **登记**：人工审核后在 `config/cycle_rotation_macro_official_releases.json` 的 `releases` 数组新增条目（发布 URL、artifact URL、发布时间、**artifact 全文 SHA256**、解析约束）。
2. **校验**（摄取时强制）：域名白名单（NBS 仅 `stats.gov.cn`、PBC 仅 `pbc.gov.cn`）、运行时重抓 artifact 验哈希、结构校验（NBS xls：sheet=`制造业`、表头 `PMI`；PBC HTML：`<title>` 与 `release_title` 精确相等、标题/正文数值交叉相等）、单位/频率/日期窗检查。任一不过整批 blocked，不写库。
3. **摄取**：`python -m backend.app.tasks.macro_backfill`，持锁单事务，只插不存在的 `(series_id, trade_date)`，血缘写 `vendor_version`/`run_id`。机制不落盘 artifact（manifest 只存 URL+哈希，在线重抓）。

**官方通道仅覆盖三个序列**：制造业 PMI（M0017126，NBS）、社融存量同比（M5525763，PBC）、M2 同比（M0001385，PBC）。CPI/PPI/M1/工业增加值不在此机制内，只能走 tushare/Choice（需 vendor 网络恢复）。

## 发布日历（2026-07 数据）

| 数据 | 发布方 | 发布日 | 通道 |
|---|---|---|---|
| 制造业 PMI | NBS | 已发布（2026-07-31） | 官方防伪通道，网络恢复后可立即补 |
| CPI / PPI 同比 | NBS | 已发布（2026-08-09） | 仅 tushare/Choice |
| M2 / 社融 | PBC | 预计 2026-08-13（「2026年7月金融统计数据报告」） | 官方防伪通道 |
| 工业增加值 | NBS | 预计 2026-08-15 | 仅 tushare/Choice |

## 防伪红线

- 一切数值必须来自本机实际抓取的官方 artifact；SHA256 对真实字节计算。
- 拿不到 artifact（断网/未发布/解析可疑）就放弃该序列，禁止编造、估算、引用第三方转译。
- 合理性检查基准（2026-06 值）：PMI 50.3、M2 同比 8.0%、社融存量同比 7.4%。PMI 超出 [40,60] 或环比变动 >2 视为可疑。

## 操作步骤（PowerShell，仓库根目录）

```powershell
# 0) 环境
$env:PYTHONIOENCODING='utf-8'

# 1) 连通性探测（200 再继续）
.venv\Scripts\python.exe -c "import requests; print(requests.get('https://www.stats.gov.cn/sj/zxfb/', headers={'User-Agent':'MOSS macro backfill/1.0'}, timeout=20).status_code)"

# 2) 定位发布页
# PMI: https://www.stats.gov.cn/sj/zxfbhjd/ 找「2026年7月中国采购经理指数运行情况」
#   发布页形如 .../202607/t202607XX_XXXXXXX.html，页内 xls 附件形如 .../202607/P0202607XXXXXXXXXXXX.xls
# M2/社融: https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html 找「2026年7月金融统计数据报告」

# 3) 抓 artifact 并算 SHA256（必须对本机抓到的字节计算）
.venv\Scripts\python.exe -c "import requests,hashlib; b=requests.get('<artifact_url>', headers={'User-Agent':'MOSS macro backfill/1.0'}, timeout=20).content; print(len(b), hashlib.sha256(b).hexdigest())"

# 4) 人工解析数值并做合理性检查（见防伪红线基准）
# PMI xls：sheet「制造业」表头「PMI」列 2026-07 行
# PBC HTML：标题段与正文段数值必须一致

# 5) 编辑 config/cycle_rotation_macro_official_releases.json，按既有格式追加条目：
# PMI（1 条）：source=nbs_pmi_release, series_id=M0017126, series_name=制造业PMI,
#   release_url/artifact_url=<实际>, published_at=2026-07-31T09:30:00+08:00（以发布页为准）,
#   artifact_sha256=<步骤3>, latest_period=2026-07-01,
#   covered_period_start/end=<按 xls 实际>, sheet_name=制造业, value_header=PMI,
#   source_unit=%, target_unit=index, value_transform=identity_percentage_points_to_index_points
# M2/社融（2 条，同一 URL 与哈希）：source=pbc_financial_statistics_release,
#   series_id=M5525763（社会融资规模存量:同比）/ M0001385（M2:同比）,
#   release_url=artifact_url=<发布页>, published_at/available_at=<页面时间+08:00>,
#   artifact_sha256=<哈希>, release_title=2026年7月金融统计数据报告, report_month=2026-07,
#   source_unit=%, target_unit=%, value_transform=identity_percentage_points,
#   field_mappings={"M5525763":"社会融资规模存量:同比","M0001385":"广义货币M2:同比"}
# 可同步递增 manifest_version。

# 6) 无写预览（必须 status=preview_ready 且数值与步骤 4 一致）
.venv\Scripts\python.exe -m backend.app.tasks.macro_backfill --fetch-preview --series-names 制造业PMI 社会融资规模存量:同比 M2:同比 --start-date 2026-07-01 --sources nbs_pmi_release pbc_financial_statistics_release
# --start-date 限窗很重要：避免重抓 4/5/6 月页面（官网改版会使旧条目哈希失配导致整批 blocked）

# 7) 正式摄取（去掉 --fetch-preview；期望 status=completed、total_added=3）
# 若 PBC 未发布，先只补 PMI：--series-names 制造业PMI --sources nbs_pmi_release

# 8) DuckDB 只读验证（期望 max(trade_date)=2026-07-01）
.venv\Scripts\python.exe -c "import duckdb; c=duckdb.connect('data/moss.duckdb', read_only=True); print(c.execute(\"select series_id, max(trade_date) from fact_choice_macro_daily where series_id in ('M0017126','M5525763','M0001385') group by 1\").fetchall())"

# 9) 重跑美林时钟（期望「当前宏观状态 (2026-07)」）
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from backend.app.core_finance.macro.toolkit.runner import run_toolkit_script; r=run_toolkit_script('merrill_clock_cn')"

# 10) 回归
.venv\Scripts\python.exe -m pytest tests/test_macro_model_merrill.py -q
```

## 备注

- 时钟推进机理：日期轴是各序列并集，只要 PMI（或 M2/社融）出现 2026-07-01 行即推进到 2026-07；CPI/PPI 缺 7 月不阻塞（动量滚动窗口用 5/6 月值，摊薄通胀动量时效性，属已知行为）。
- Livermore 周期门的 sidecar `config/cycle_rotation_macro_official_availability.json` 不会自动同步，7 月行会回退到 run_id 可用性门（fail-closed）；需要该链路认可时另行按其协议更新。
- 页面 readiness 对月度产物的判定容差见 `macro_model_readiness`（2026-08-12 起月度产物按月度容差判定 current）。
