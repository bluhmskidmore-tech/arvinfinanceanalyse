# Cursor Prompt: 股票分析工作台 P0

> 直接粘贴到 Cursor 的 chat 框执行。

---

你正在 `F:\MOSS-V3` 仓库工作。

## 任务目标

实现 P0 股票分析工作台。完整规格在：

```
docs/handoff/2026-05-06-stock-analysis-workbench-codex.md
```

**先读这个文件，严格按它执行，不要扩大范围。**

---

## 执行前必做

```bash
git status --short
```

仓库有大量无关脏文件（bond-analytics、ledger-pnl、macro-toolkit、qdb 等），**不要碰它们**。只改本任务列出的文件。

---

## 要改的文件（仅限这些）

**新建：**
- `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
- `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- `frontend/src/test/StockAnalysisPage.test.tsx`
- `frontend/src/test/StockAnalysisPageModel.test.ts`

**修改：**
- `frontend/src/mocks/navigation.ts`
- `frontend/src/router/routes.tsx`
- `frontend/src/test/WorkbenchShell.test.tsx`
- `frontend/src/test/RouteRegistry.test.tsx`

**不要动：**
- `frontend/src/api/client.ts`
- `frontend/src/api/marketDataClient.ts`
- `backend/app/**`
- `tests/**`
- 任何无关页面

---

## 任务顺序

按 handoff 文档的 Task 1 → 6 顺序执行，每个 task 完成后运行对应验证命令再继续。

**Task 1 验证：**
```bash
cd frontend && npm run test -- src/test/WorkbenchShell.test.tsx --pool=forks --poolOptions.forks.singleFork=true
```

**Task 2 验证：**
```bash
cd frontend && npm run test -- src/test/RouteRegistry.test.tsx --pool=forks --poolOptions.forks.singleFork=true
```

**Task 3 验证：**
```bash
cd frontend && npm run test -- src/test/StockAnalysisPageModel.test.ts --pool=forks --poolOptions.forks.singleFork=true
```

**Task 4 验证：**
```bash
cd frontend && npm run test -- src/test/StockAnalysisPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true
```

**Task 5-6 最终验证：**
```bash
cd frontend && npm run test -- src/test/StockAnalysisPageModel.test.ts src/test/StockAnalysisPage.test.tsx src/test/RouteRegistry.test.tsx src/test/WorkbenchShell.test.tsx --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
cd frontend && npm run debt:audit
```

**后端回归（运行存在的测试）：**
```bash
cd F:/MOSS-V3
python3 - <<'PY'
from pathlib import Path
for p in sorted(Path('tests').glob('*livermore*')): print(p)
for p in sorted(Path('tests').glob('*choice_stock*')): print(p)
PY
```
然后运行找到的测试文件：
```bash
uv run --project backend python -m pytest <找到的文件> -q
```

---

## 关键业务口径（不能偏）

- 候选股措辞只用：`观察` / `候选` / `复核` / `失效条件`
- 禁止出现：`买入建议` / `卖出建议` / `下单` / `调仓指令`
- 银行股专题字段（PB/ROE/NIM/不良率等）当前缺失，必须显示"待补"，不得 mock
- 基本面/估值证据未接入，反证卡里必须写明
- 页面必须有免责说明：仅供研究复核，不构成交易指令

---

## 完成后输出格式

```
Implemented P0 stock-analysis workbench.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result

Known risks / follow-up:
- ...
```
