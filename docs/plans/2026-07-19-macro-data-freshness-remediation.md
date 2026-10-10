# 宏观数据新鲜度修复 Runbook（2026-07-19）

- 关联审计：`docs/strategy_contracts/macro_strategy_p0_evidence_2026-07-19.md`、`.codex-tmp/macro_p0_evidence_audit.json`
- 性质：数据侧诊断 + 有条件补数。**未修改任何 backend 代码或 schema**；所有写入均走 `backend/app/tasks/` 既有任务链路（含 `cffex_member_rank_service -> tasks/cffex_member_rank` 的既有写路径）。
- 数据库：`data/moss.duckdb`（governance settings 的 `duckdb_path`）。
- 凭证前提（本轮已核实，仅报告存在性）：`config/.env` 中 `MOSS_CHOICE_USERNAME` / `MOSS_CHOICE_PASSWORD` / `MOSS_TUSHARE_TOKEN` 均存在；`tushare`、`EmQuantAPI`、`akshare` SDK 均可导入，Choice 账号可登录。
- 全局根因：仓库内**不存在任何调度器**（`backend/app/tasks/` 无 cron / periodic 定义，dramatiq actor 只能被 API 或手动触发）。所有"滞后"本质上都是"最后一次手动触发之后没有人再跑"。

---

## 1. `fact_commodity_futures_daily` / `fact_cffex_member_rank_daily` 滞后 23 天

### 根因

- **调度没跑**，非凭证或接口问题。两表最后落库 2026-06-26；Tushare token 一直存在，本轮实际跑通。
- 商品期货刷新入口：CLI `python -m backend.app.tasks.commodity_daily_ingest`（等价 API：`POST /macro-toolkit` 商品刷新，走 dramatiq `run_commodity_daily_ingest_task`）。幂等性：按 (product_code, trade_date) 先删后插；锁 `lock:duckdb:commodity-daily-ingest`。
- CFFEX 席位刷新入口：API `POST /macro-toolkit/cffex-member-rank/refresh`（service `materialize_cffex_member_rank` -> task `persist_cffex_member_rank_rows`）。**每次调用只取一个交易日**（默认最新日），补历史缺口需按交易日循环调用。幂等性：按 (trade_date, contract, source_vendor) 先删后插。

### 本轮已执行（2026-07-19）

商品期货（分两批以控制单次运行时长，全部 tushare 源成功）：

```powershell
python -m backend.app.tasks.commodity_daily_ingest --start-date 2026-06-20 --end-date 2026-07-19 --products TS,TF,T,TL,NHCI,NHII
python -m backend.app.tasks.commodity_daily_ingest --start-date 2026-06-20 --end-date 2026-07-19 --products RB,HC,I,JM,J,CU,AL,ZN,SC,TA,MA,M,P,AU,AG
```

CFFEX 席位（内联循环调用既有 service，每个交易日一次；sources 用 `tushare` 以避免依赖 Choice 终端在线）：

```powershell
python -c "
import sys, time
sys.path.insert(0, r'F:\MOSS-V3')
from datetime import date, timedelta
import duckdb
from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank
start, end = date(2026,6,29), date(2026,7,17)   # 按需调整窗口
cur = start
while cur <= end:
    if cur.weekday() < 5:
        for attempt in range(6):
            try:
                p = materialize_cffex_member_rank(trade_date=cur.isoformat(), sources=('tushare',))
                print(cur.isoformat(), p['row_count']); break
            except duckdb.IOException:
                time.sleep(10)   # DuckDB 单写者，其他写进程占用时重试
    cur += timedelta(days=1)
"
```

### 前后对比证据

| 表 | 执行前 | 执行后 |
| --- | --- | --- |
| `fact_commodity_futures_daily` | 11043 行，max=2026-06-26 | 11408 行，max=**2026-07-17** |
| `fact_cffex_member_rank_daily` | 15731 行，max=2026-06-26 | 18114 行，max=**2026-07-17** |

（2026-07-18/19 为周末，2026-07-17 即最新交易日，滞后清零。）

### 验证 SQL（只读）

```sql
select count(*), max(trade_date) from fact_commodity_futures_daily;
select count(*), max(trade_date) from fact_cffex_member_rank_daily;
-- 席位数据按日覆盖检查
select trade_date, count(distinct contract) contracts, count(*) rows
from fact_cffex_member_rank_daily
where trade_date >= '2026-06-26' group by 1 order by 1;
```

### 待办（负责人待定）

- [x] Scheduler entry: `refresh_macro_toolkit_freshness` actor / CLI (`scripts/macro_toolkit_freshness_refresh.py`); local Windows timer `MOSS-MacroToolkitFreshness` (host-local 06:30 ≈ Asia/Shanghai 18:30)。v3 顺序编排已包含商品、public headlines、Choice 7 天逆回购政策利率、NCD.SHIBOR 五期限与 CFFEX；NCD 窗口刷新保留已回补历史，政策利率拒答时 fail closed。
- [ ] CFFEX 席位当前仅 tushare 源回补；Choice 源（`fut_transaction_rankings`）需要 Choice 终端在线，是否双源并存由 owner 决定。
- [ ] 注意 DuckDB 单写者约束：调度时段避开 dev worker / 其他写任务（本轮出现两次瞬时写锁冲突，重试即过）。

---

## 2. `fact_choice_macro_daily`：EMM* 单行快照、NCD.SHIBOR 仅 9 行

### 根因（设计使然 + 部分 vendor 权限缺失）

- 目录 `config/choice_macro_catalog.json`（2026-07-20.choice-macro.v3）分层：
  - `stable_daily`（62 序列，`refresh_tier=stable`，`fetch_mode=date_slice`）：正常逐日累积；新增已验证可读的 `EMM00088132` 7 天逆回购中标利率。
  - `fallback_latest_single`（48 序列）与 `choice_funding_shibor_latest`（7 序列）：`refresh_tier=fallback`，`fetch_mode=latest`——**设计上就是单点快照**，每次刷新只拿最新值；历史只有靠每天刷新自然累积（而刷新又没有调度）。policy_note 明示原因：这些序列在本地 Choice 账号上 same-day date_slice 返回 no data。
  - `isolated_vendor_pending`（12 序列）：默认刷新完全跳过。
- NCD.SHIBOR.* 曾仅 9 行的直接原因：`refresh_tushare_ncd_shibor_proxy`（`backend/app/tasks/choice_macro.py`）的 `NCD_SHIBOR_LOOKBACK_DAYS=10`，且当时每次运行**先 delete 全部行再插入 10 天窗口**。该删除语义已修为仅覆盖本次抓取窗口，632 行/期限的回补历史会保留；2026-07-20 起 daily freshness 编排也会顺序调用该刷新，避免历史再次停滞。
- `M0041653` 曾只命中截至 2026-04-30 的 legacy 快照；2026-07-20 复测 Choice `EMM00088132` date-slice 已可返回真实历史。旧 crisis 回补在 vendor 拒答时自动 carry-forward 的路径已移除，避免把旧政策利率伪装为新日期。
- 历史回补的既有链路是 `backend/app/tasks/macro_backfill.py`（`backfill_macro_series`，目标=行数 < 10 的稀疏序列，源优先级 choice_edb / tushare_macro，逐行去重插入、幂等，锁 `lock:duckdb:macro-series-backfill`）。

### 本轮已执行（2026-07-19）

NCD.SHIBOR 历史回补（tushare shibor，秒级完成）：

```powershell
python -m backend.app.tasks.macro_backfill --series-names NCD.SHIBOR.1M NCD.SHIBOR.3M NCD.SHIBOR.6M NCD.SHIBOR.9M NCD.SHIBOR.1Y --sources tushare_macro --start-date 2024-01-01 --end-date 2026-07-19
```

EMM* 历史回补（Choice EDB，109 个稀疏 EMM 序列分 8 批跑；`backfill_macro_series` 遇单序列失败会整批 `blocked`，故对失败批次逐序列重试）：

```powershell
# 先看计划（只读）
python -m backend.app.tasks.macro_backfill --dry-run
# 再按 series 分批执行，例：
python -m backend.app.tasks.macro_backfill --series-names EMM00072301 EMM01474570 ... --sources choice_edb --start-date 2024-01-01 --end-date 2026-07-19
```

7 天逆回购政策利率补记（2026-07-20，真实 Choice EDB 行，不使用 carry-forward）：

```powershell
python backend/scripts/backfill_crisis_score_inputs.py --duckdb-path data/moss.duckdb --start-date 2024-01-01 --end-date 2026-07-20 --aliases M0041653
```

### 前后对比证据

| 指标 | 执行前 | 执行后 |
| --- | --- | --- |
| EMM* 仅 1 行的序列 | 104 / 106 | **14 / 111** |
| EMM* 行数 <10 的序列 | 104 | 19 |
| NCD.SHIBOR.* 每序列行数 | 9（2026-06-30 起） | **632（2024-01-02 至 2026-07-17）** |
| `EMM00088132` 7 天逆回购 | 0（运行时仅 legacy 至 2026-04-30） | **616（2024-01-02 至 2026-07-20，1.40%～1.80%）** |
| `fact_choice_macro_daily` 总行数 | 4628 | ≥47655（含后续政策利率 616 行；并发刷新后继续增长，max=2026-07-20） |

本轮共回补 EMM 序列 39296 行（95 个序列成功）+ SHIBOR 3115 行。

**仍无法回补的 14 个序列**（Choice EDB 对本账号返回 no data，与目录 policy_note 一致，属 vendor 权限/接口不支持）：

- 中债地方政府债到期收益率 6M/1Y/2Y/3Y/4Y/5Y/6Y/7Y/8Y（EMM00166438、EMM00166440–447）
- 活期存款利率（EMM00166216）、短期贷款利率:6个月(EMM00166239)、中长期贷款利率:1至3年(EMM00166241)
- 固定利率国债发行利率:9个月（EMM00167219）、逆回购利率:63天:月（EMM01089843）

另有 5 个低频序列回补后行数仍 <10（EMM00000015 中国GDP现价、EMM00072858 CPI不变价、EMM01954681 人均存款、EMM01089841 逆回购14天、EMM01244358），属年频/事件频序列，行数少是正常的。

### 验证 SQL（只读）

```sql
select series_id, count(*) c, min(trade_date), max(trade_date)
from fact_choice_macro_daily
where series_id like 'NCD.SHIBOR%' group by 1 order by 1;

select count(*) filter (where c = 1) one_row, count(*) total
from (select series_id, count(*) c from fact_choice_macro_daily
      where series_id like 'EMM%' group by 1);
```

### 待办（负责人待定）

- [x] ~~**高风险**：`refresh_tushare_ncd_shibor_proxy` 与 `refresh_public_cross_asset_headlines` 采用"删全量、插窗口"语义，下次运行会把本轮回补的 NCD.SHIBOR 历史再次清空。~~ **已于 2026-07-19 修复**：两个任务对 `fact_choice_macro_daily` 的删除改为按每序列本次抓取窗口起点的窗口删除（`_delete_fact_rows_in_fetched_window`），窗口外历史保留；快照/目录表保持整序列删除语义。回归测试 `tests/test_macro_refresh_preserves_history.py`。注意：窗口外的错误历史值不再被刷新覆盖，如需纠正须重跑 `macro_backfill`。
- [ ] 14 个 Choice EDB 拒答序列：向 Choice 确认账号 EDB 权限 / 指标代码有效性；确认前它们只能维持"最新值展示"，不可用于任何历史窗口信号（与 P0 审计结论一致）。
- [ ] `fallback_latest_single` 批次若要持续累积历史，需要建立日频 `refresh_choice_macro_snapshot` 调度（每天 latest 快照自然堆积），owner 待定。
- [ ] EMM 回补数据 `unit` 多为 unknown（EDB 返回不带单位），用于计算前需逐序列核对单位口径。

---

## 3. `std_external_macro_daily` 最新 2026-06-30，"滞后 19 天"

### 根因（频率节奏，非管道故障）

- 该表为月频/季频宏观标准层。max(trade_date)=2026-06-30 是 **NBS GDP 2026Q2 季度点**；tushare 月度序列（CPI/PPI/M2）max=2026-06-01，即 6 月值（6 月 CPI 约 7 月上旬发布，`trade_date` 记月初）。**7 月月度值尚未发布，当前数据已是最新可得**。
- 管道本身健康：库内 `ingest_batch_id` 证据显示最近一次成功 ingest 为 2026-07-17（`tushare-macro-refresh-*` 与 `nbs-gdp-20260717T*`）；本轮重跑再次成功。
- 刷新入口：`backend.app.tasks.tushare_macro_ingest.run_tushare_macro_ingest_once`（dramatiq actor `refresh_tushare_macro`）；编排入口 `backend.app.tasks.home_macro_release_refresh.refresh_home_macro_release_sources`（一次覆盖 Tushare 四序列 + NBS GDP + PMI 回补）。幂等性：`insert or replace` 按 (series_id, trade_date)。

### 本轮已执行（2026-07-19）

```powershell
python -c "import sys; sys.path.insert(0, r'F:\MOSS-V3'); from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once; import json; print(json.dumps(run_tushare_macro_ingest_once()['status']))"
```

结果：`status=success`，4 序列全部成功（cn_cpi 510 / cn_gdp 176 / cn_ppi 375 / cn_money 371 行 upsert），失败 0。执行后 max(trade_date) 仍为 2026-06-30 —— 这**验证了"无更新可拉"的结论**，而非任务失败。

### 验证 SQL（只读）

```sql
select series_id, count(*), max(trade_date), max(created_at)
from std_external_macro_daily group by 1 order by 1;
```

### 待办（负责人待定）

- [ ] stale SLA 应按频率定义（月频 45 天 / 季频 100 天，`home_macro_release_refresh._FRESH_DAYS` 已有先例），避免再用"距今日历天数"误报月频表 stale；owner 冻结口径。
- [ ] 建立 `refresh_home_macro_release_sources` 的周频（或每月 10-20 日发布窗口内日频）调度，owner 待定。
- [ ] 表内另有 4 个 legacy/crisis-score 序列停在 2026-04-30（`tushare.yc_cb.1001.CB.5Y`、`legacy.*`、`NHCI.NH`），由 `backend/scripts/backfill_crisis_score_inputs.py` 维护，本轮未动，需 owner 决定是否续跑。

---

## 附：残余风险汇总

1. **无调度器**是三类问题的共同根因，本轮补数只是一次性拉平；不建调度必然复发。
2. ~~NCD.SHIBOR / public headline 刷新任务的"删全量重建"语义与历史回补冲突~~（已于 2026-07-19 修复为窗口删除，见 §2 待办第 1 条）。
3. DuckDB 单写者：补数与 dev worker / API 触发的写任务并发时会出现 `IO Error: File is already open`，重试可过，但调度设计需串行化。
4. 全表仍无 PIT（release_at/vintage）列，本轮回补不改变 P0 审计"历史时点复现 fail-closed"的结论。
5. 商品期货 akshare 兜底源本轮未使用（tushare 全部成功），akshare 路径的可用性未验证。
