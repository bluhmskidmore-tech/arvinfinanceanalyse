# WP-J · `choice_policy_rate_7d` 步骤撞 DuckDB 文件锁时不重试

- 泳道：L1 后端，第二批第 2 个（与 WP-I 无共同文件，可并行）
- 层：Python + pytest
- 难度：低
- 前置：无
- 意义：这是今天 13:31 那次日更里**唯一失败**的必需步骤，它一失败回执就 `failed`、首屏就"暂停判断"

## 现象

`data/logs/macro_toolkit_freshness_refresh_receipt.json`（2026-09-02 05:41:45Z）：其余四步 `success`，`choice_policy_rate_7d: failed`，错误原文：

```
{"M0041653": "IO Error: Cannot open file \"\\\\?\\F:\\MOSS-V3\\data\\moss.duckdb\": 另一个程序正在使用此文件，进程无法访问。"}
```

## 根因（两层）

1. `backend/app/tasks/macro_toolkit_freshness_refresh.py:293-301 _is_duckdb_writer_contention()` 只匹配 `already open / database is locked / could not set lock / conflicting lock / lock on file` 五个英文子串。Windows 上的文件共享冲突报的是 `IO Error: Cannot open file … 另一个程序正在使用此文件`（英文系统是 `being used by another process`），一个都不匹配 → `_call_with_duckdb_retry()`（`:304-323`，6 次 × 10 s）直接放弃。
2. 更前一层：`_refresh_choice_policy_rate_7d()`（`:693-719`）调用的 `backend/scripts/backfill_crisis_score_inputs.backfill_crisis_score_inputs()` **不抛异常**，而是把错误收进返回值的 `errors` 字典并给 `status: error`。所以即便子串匹配了，`_call_with_duckdb_retry` 也看不到异常，无从重试。

对照：`scripts/choice_stock_daily_refresh.py:262-270` 的同类重试对锁的判定更宽，且在异常路径上。

## 改动

`backend/app/tasks/macro_toolkit_freshness_refresh.py`：

1. `_is_duckdb_writer_contention()` 增加 `"cannot open file"`、`"being used by another process"`、`"另一个程序正在使用"` 三个子串；并接受 `duckdb.IOException`（`duckdb.Error` 的子类，现有 isinstance 判断已覆盖，确认即可）。
2. `_refresh_choice_policy_rate_7d()`：当 `payload["errors"]` 非空且任一错误文本满足 `_is_duckdb_writer_contention` 的**文本判定**时，抛出一个 `duckdb.IOException`（或自定义 `DuckDBWriterContention(duckdb.Error)`）把错误文本带上，让外层 `_call_with_duckdb_retry` 接管重试；非锁类错误维持现有返回值语义（`status: error`，不抛）。为此把文本判定从异常判定里拆成 `_looks_like_duckdb_writer_contention(text: str) -> bool` 供两处复用。
3. 6 次 × 10 s 的常量不改。

`tests/`：找到现有 freshness 任务测试（`rg -l "macro_toolkit_freshness_refresh" tests/`），新增：

- `_is_duckdb_writer_contention` 对中文 `另一个程序正在使用此文件` 与英文 `being used by another process` 的 `duckdb.IOException` 返回 True；对 `Catalog Error` 返回 False。
- monkeypatch `backfill_crisis_score_inputs` 前两次返回锁错误 `errors`、第三次成功 → 步骤最终 `success`，`attempt_count == 3`；`time.sleep` 打桩不真等。
- 非锁错误（如 `Binder Error`）→ 不重试、返回 `status: error`（现有行为）。

## 不得触碰

`backend/scripts/backfill_crisis_score_inputs.py`（写路径口径不动）；`REQUIRED_STEPS`；回执 schema；`scripts/scheduling/*`。

## 验收

```bash
python -m pytest tests -q -k "freshness_refresh or macro_toolkit_refresh"
python -m pytest tests/test_macro_toolkit_refresh_receipt_service.py -q
```

不要自行触发 `schtasks /run`；由人在没有 pytest 运行时触发（README §4.1）。

## 报告要求

根因（两层都写）、改动文件、验证结果、剩余风险（锁重试只是缓解：API 进程与任务对同一 DuckDB 文件的读写互斥是结构性的，6 × 10 s 覆盖不了长时间占用；若仍失败请把 `failure_message` 里的锁持有者线索——若能取到——写进回执）。对 `core_finance/` 的影响：无。
