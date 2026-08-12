# C1 依赖安装与 lock 一致化：uv sync --frozen 切换方案

- 登记日期：2026-08-12
- 状态：调查完成、方案已备。**本任务不改 ci.yml、不改 backend/pyproject.toml、不运行任何安装命令**（uv sync / pip install / npm install 零执行）。CI 片段与 pyproject 片段供对应负责人应用。
- 本任务唯一代码编辑：`frontend/package.json` 新增 `engines` 字段（见 §5）。

## 结论

1. **lock 权威性成立但未被 CI 执行**：`backend/uv.lock` 钉 `duckdb==1.5.2` 等全量精确版本，但 `.github/workflows/ci.yml` 在 `uv lock --check` 通过后用 `pip install -e "./backend[dev]"` 重新按范围解析安装——校验与安装解耦，CI 实际安装集随 PyPI 当日版本漂移，lock 只当"摆设校验"。
2. **`uv lock --check --project backend` 当前失败（exit 1，2026-08-12 实测）**：共享工作区中 `backend/pyproject.toml` 存在未提交改动（新增 `arch>=7.0,<8` 主依赖），`uv.lock` 未同步（lock 中无 arch 条目）。该 pyproject 改动合入前必须由其负责人执行 `uv lock` 并提交，否则现行 CI backend job 第一步即红，切换 `uv sync --frozen` 更无从谈起。
3. **本地共享 `.venv`（Python 3.14.2）与 uv.lock 漂移率 5/22 ≈ 23%**：duckdb 1.5.1（落后 lock 的 1.5.2）、fastapi 0.135.3（落后 0.136.0）、pydantic、pydantic-settings、pytest 五项不一致；另有 lock 外安装的 tushare 1.4.29、akshare 1.18.57、arch 7.2.0。
4. **vendor SDK（tushare/akshare/EmQuantAPI/WindPy）在 pyproject 与 uv.lock 中零声明，且代码中全部为函数内惰性 import，无模块级依赖**——API 启动与 CI 测试不需要真实 SDK。处置建议：tushare/akshare 进 optional extra `[vendor]`；WindPy/EmQuantAPI 非 PyPI 包，维持惰性 import + 本地 shim 现状（§3）。
5. **Python 版本三分裂**：CI 硬编码 3.11，本地共享 `.venv` 是 3.14.2，uv 独立解析实测用 3.13.12（无 `.python-version` 钉定）。需 owner 决策统一基线（§4）。

## 一、核实数据（2026-08-12 实测，全部只读命令）

### 1.1 uv.lock 元数据与关键版本

lock 头部：`version = 1`、`revision = 3`、`requires-python = ">=3.11"`，resolution-markers 按 `<3.12` / `3.12–3.13` / `>=3.14` 三层分段。

| 包 | uv.lock 钉定版本 |
| --- | --- |
| duckdb | **1.5.2**（确认，lock L331-332） |
| fastapi | 0.136.0 |
| pandas | 2.3.3 |
| dramatiq | 1.18.0 |
| numpy | 2.4.4 |
| scipy | 1.17.1（py<3.12）/ 1.18.0（py>=3.12），按 marker 双条目 |
| pydantic / pydantic-settings | 2.13.2 / 2.14.2 |
| pytest / pytest-xdist | 9.0.3 / 3.8.0 |
| sqlalchemy / uvicorn / redis / psycopg | 2.0.49 / 0.44.0 / 6.4.0 / 3.3.3 |

lock 中项目自身条目 `moss-agent-analytics-os-backend` 为 `source = { editable = "." }`（uv sync 会以 editable 方式装项目，与 `pip install -e` 等价）；`provides-extras = ["dev", "otel"]`，**无 arch、无任何 vendor SDK 条目**。

### 1.2 ci.yml 安装步骤现状（解耦点定位）

| job | 行号 | 现状 |
| --- | --- | --- |
| backend | L36-37 | `uv lock --check --project backend`（仅校验） |
| backend | L39-40 | `pip install -e "./backend[dev]"`（**安装不走 lock**） |
| backend | L43 / L46 | `python scripts/backend_release_suite.py`、`python -m pytest tests/...`（用 setup-python 全局环境） |
| backend-full-pytest | L64-65 | 仅 `pip install -e "./backend[dev]"`，**连 lock check 都没有** |
| api-contract | L164-165 | 同上，仅 pip install |
| （公共） | L27/L60/L160 | `python-version: "3.11"`；`cache: pip` 且 cache key 是 `backend/pyproject.toml`（key 不到真实安装集） |
| （公共） | L31-34 | setup-uv 钉 `0.11.32`（与本机实测一致） |

### 1.3 `uv lock --check --project backend` 实测结果（如实记录：失败）

```text
uv 0.11.32 (3010295ae 2026-07-23 x86_64-pc-windows-msvc)
Using CPython 3.13.12
Resolved 82 packages in 16.48s
error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.
exit code = 1
```

根因（git 只读证据）：`git status` 显示仅 `backend/pyproject.toml` 为 M（未提交），diff 为新增主依赖 `"arch>=7.0,<8"`（另有 pytest.ini_options 移除与 ruff S110/S112 新增，不影响解析）；`backend/uv.lock` 未改动且无 arch 条目。即：**HEAD 上二者本是一致的，失败由共享工作区中另一任务对 pyproject 的在途改动引入**。附带发现：`Using CPython 3.13.12` 说明本机 uv 在无钉定时用自选解释器解析（见 §4）。

### 1.4 共享 `.venv` 实际版本 vs uv.lock（漂移量化）

本机环境盘点：

| 环境 | Python | 说明 |
| --- | --- | --- |
| `F:\MOSS-V3\.venv`（共享测试环境） | **3.14.2**（pythoncore-3.14-64 手工 venv，`pyvenv.cfg` 实测） | 下表对比对象 |
| 系统 `Python311` | 3.11.9 | 另一套完整项目栈（见表后注） |
| CI | 3.11 + pip 当日解析 | 无本地对应物 |

`.venv` 对比 uv.lock（`importlib.metadata` 枚举，22 个 lock 内可比包）：

| 包 | uv.lock | `.venv` 实装 | 漂移 |
| --- | --- | --- | --- |
| duckdb | 1.5.2 | **1.5.1** | **落后一个 patch（存储引擎，最需关注）** |
| fastapi | 0.136.0 | **0.135.3** | 落后 |
| pydantic | 2.13.2 | **2.12.5** | 落后 |
| pydantic-settings | 2.14.2 | **2.13.1** | 落后 |
| pytest | 9.0.3 | **9.1.1** | 超前 |
| 其余 17 项（pandas、dramatiq、numpy、scipy(1.18.0 与 3.14 marker 层一致)、sqlalchemy、uvicorn、redis、psycopg、httpx、pytest-xdist、requests、beautifulsoup4、minio、openpyxl、xlrd、anyio、alembic） | — | — | 一致 |

漂移率 5/22 ≈ **23%**。lock 之外的实装：`arch 7.2.0`（pyproject 在途新增，lock 尚无）、`tushare 1.4.29`、`akshare 1.18.57`（均未声明）。

系统 Python 3.11 栈另有独立漂移（佐证"pip 解析随时间漂移"）：fastapi **0.136.3**、psycopg **3.3.4** 超前 lock，numpy **1.26.4** 落后 lock 一个大版本，且缺 pytest-xdist、arch；akshare 1.18.54 也装在系统层。三套环境三种版本组合，即当前"无 lock 强制"的真实代价。

### 1.5 vendor SDK import 面（运行时必需 vs 脚本可选）

结论先行：**全仓库无一处模块级 vendor import**；全部位于函数体/try 块内，SDK 缺失只影响对应摄取任务或研究脚本的执行时报错，不影响 API 启动、不影响 CI 测试收集。

运行时主链（`backend/app`，惰性 import，属"部署了对应摄取任务的 worker 才需要"）：

| SDK | 位置 |
| --- | --- |
| tushare | `app/repositories/tushare_adapter.py:72`；`app/services/tushare_news_ingest_service.py:65`（源码注释即写明 "lazy: optional dependency at runtime"） |
| akshare | `app/repositories/akshare_adapter.py:459,519`；`app/tasks/choice_macro.py:1766,1805,2034,2059`；`app/tasks/commodity_daily_ingest.py:491` |
| EmQuantAPI | `app/config/choice_runtime.py:60`（惰性 + `type: ignore`，Choice 终端捆绑 SDK） |

研究/脚本可选面：

- WindPy：仅出现在 `app/core_finance/macro/toolkit/scripts/`（merrill_clock_cn、crisis_score_cn、crowding_cn、credit_bond_data、bond_futures_data、bond_futures_signals、backtest_cn、debug_wind）。
- 独立脚本：`scripts/supplement_livermore_after_close_inputs.py:542`、`backend/scripts/backfill_cross_asset_macro_environment.py:330`（均 akshare，函数内）。
- 其余约 70 个 grep 命中文件均为字符串/表名/配置键引用（如 `tushare_daily`），非 import。

**本地 shim（关键上下文）**：`toolkit/WindPy.py` 是读系统 DuckDB 的 Wind API 模拟器（`_SystemChoiceTushareWind` + `_WindResult`）；`toolkit/scripts/WindPy.py`、`toolkit/scripts/akshare.py` 是同目录重导出 shim——toolkit 脚本以脚本方式运行时 `sys.path[0]` 即脚本目录，`import akshare` / `from WindPy import w` 解析到本地 shim 而非 PyPI/终端 SDK。真实 SDK 仅在真实终端模式下需要。仓库无任何 requirements*.txt 声明这些包。

### 1.6 frontend 工具链 node 要求

- `frontend/package-lock.json`：`lockfileVersion: 3`（npm 9+ 的默认锁格式；node 20/22 自带 npm 10）。
- `ci.yml` 四处 `node-version: "22"`（frontend / lint / api-contract 各 job）。
- vite 8.2.1（锁文件内 engines 实测）：`node ^20.19.0 || >=22.12.0`——这是 devDependencies 中最严的 node 下限。
- `frontend/package.json` 原先无 engines 字段。

## 二、uv sync --frozen 切换方案（供 ci.yml 负责人应用）

### 2.1 目标

"校验即安装"：三个 python job 全部从 `uv.lock` 冻结安装，CI 环境=lock=可复现；消除 pip 二次解析。

### 2.2 建议的 CI 片段（backend job，主方案）

```yaml
      - name: Set up uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          version: "0.11.32"
          enable-cache: true
          cache-dependency-glob: backend/uv.lock

      - name: Check backend uv.lock consistency
        run: uv lock --check --project backend

      - name: Sync backend environment from lockfile
        run: uv sync --frozen --project backend --extra dev --python 3.11

      - name: Run bounded backend release suite
        run: uv run --project backend -- python scripts/backend_release_suite.py

      - name: Run agent harness tests
        run: uv run --project backend -- python -m pytest -q tests/test_agent_eval_spec.py tests/test_agent_eval_reward.py tests/test_agent_eval_collect.py
```

要点：

- `uv sync --frozen`：严格按 lock 安装、不更新 lock、不重新解析；`--extra dev` 对应现 `[dev]`；项目自身按 lock 的 `editable = "."` 安装，与 `pip install -e` 行为等价。
- 保留独立 `uv lock --check` 步骤（失败信号与安装失败分离）；备选合并式 `uv sync --locked --project backend --extra dev`（校验+安装一步，少一个 step 但红灯归因混合）。
- venv 落在 `backend/.venv` 而非 setup-python 全局环境，**后续每个 python 调用必须加 `uv run --project backend --` 前缀**（`uv run` 不改变 cwd，从仓库根调 `scripts/*.py` 与 `python -m pytest` 语义不变）。
- setup-python 步骤的 `cache: pip` / `cache-dependency-path` 两行删除（pip 不再安装任何东西），缓存改由 setup-uv `enable-cache` 承担且 key 到 `uv.lock`（现状 pip cache key 是 pyproject.toml，本就 key 不到真实安装集）。setup-python 本体可保留用于提供 3.11，亦可省去、由 uv 托管下载（`--python 3.11` 已显式钉定版本，两种来源等价）。

### 2.3 ci.yml 待改行清单（本任务不执行）

| job | 现状行 | 改动 |
| --- | --- | --- |
| backend | L28-29 `cache: pip` | 删除，换 setup-uv enable-cache |
| backend | L39-40 pip install | 换 `uv sync --frozen --project backend --extra dev --python 3.11` |
| backend | L43、L46 `python ...` | 加 `uv run --project backend --` 前缀 |
| backend-full-pytest | L61-62 cache、L64-65 pip install、L68 pytest | 同上；**该 job 现无 lock check，切换后天然获得 lock 强制**（建议同时补 `uv lock --check` 或直接用 `--locked`；注意该 job 现亦无 setup-uv step，需一并添加） |
| api-contract | L161-162 cache、L164-165 pip install、L179 export-openapi | 同上（同样需补 setup-uv step） |

### 2.4 本地开发说明（Windows PowerShell；**共享工作区当下不要执行**）

```powershell
# 创建/同步 backend/.venv 为 lock 精确环境（与 CI 完全一致）
uv sync --project backend --extra dev --python 3.11

# 之后以 uv run 运行（不必手工激活 venv）
uv run --project backend -- python -m pytest tests -q
uv run --project backend -- python scripts/backend_release_suite.py

# 需要摄取任务的 vendor SDK 时（extra 落地后）
uv sync --project backend --extra dev --extra vendor --python 3.11
```

- 现存根 `F:\MOSS-V3\.venv` 是手工 venv（Python 3.14.2），uv 不管理它；uv 默认使用 `backend/.venv`。如坚持复用根 .venv 可设 `$env:UV_PROJECT_ENVIRONMENT`，**不建议**——其解释器 3.14 与 CI 3.11 不一致（scipy 分层解析已实证差异）。
- 过渡期两 venv 并存：IDE 解释器与任务计划/脚本指向需明确切换；根 .venv 退役时机是 owner 决策（可能被本仓库外的快捷方式/计划任务引用）。

### 2.5 切换前置条件、风险与回退

前置条件（顺序硬性）：

1. `backend/pyproject.toml` 负责人完成 arch 变更后执行 `uv lock --project backend` 并连带提交 `uv.lock`——否则 `--check` 持续红、`--frozen` 装不出 arch。
2. 若采纳 §3 vendor extra，同一次 `uv lock` 一并解析进 lock，避免两次 lock 变更。

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| lock 冻结使"pip 每日隐式升级"掩盖的问题显性化（如系统 3.11 环境 pip 已装 fastapi 0.136.3，lock 仍是 0.136.0） | 中 | 建立显式升级窗口：定期 `uv lock --upgrade` + 全量回归，升级从"随机漂移"变"受控变更" |
| 某个 CI 步骤漏加 `uv run` 前缀 → ModuleNotFoundError | 低 | 按 §2.3 清单逐行核对；先在分支干跑全部 job |
| Python 解释器不钉则 uv 自选（本机实测解析用 3.13.12），与 CI 3.11 不一致；scipy 等按 python 版本装出不同版本（1.17.1 vs 1.18.0） | 中 | CI 片段已显式 `--python 3.11`；根治靠 §4 决策 + `backend/.python-version` |
| 首次切换缓存冷启动、CI 变慢一次 | 低 | setup-uv enable-cache 之后命中 uv.lock key |
| `.venv`（duckdb 1.5.1）与 lock（1.5.2）并存期本地/CI 行为差异 | 中 | 本地按 §2.4 重建后消除；DuckDB 1.5.x 内部为同代存储格式，数据文件兼容风险低，但版本对齐前本地复现 CI 失败时先查此差异 |

回退：全部改动仅在 `ci.yml` 一个文件内，revert 即回到 `pip install -e` 路径；`uv.lock` / `pyproject.toml` 无需伴随回退，零数据风险。

## 三、vendor 依赖处置建议

分层处置（依据 §1.5 import 面证据）：

**1. tushare、akshare（PyPI 有包，摄取任务真实需要）→ optional extra `[vendor]`。**

`backend/pyproject.toml` 片段（供该文件负责人应用，**本任务不改该文件**）：

```toml
[project.optional-dependencies]
# ...现有 dev / otel 之后新增：
vendor = [
  "tushare>=1.4,<2",   # 本地实装 1.4.29（2026-08-12 实测）
  "akshare>=1.18,<2",  # 本地实装 1.18.57（.venv）/ 1.18.54（系统层）
]
```

配套动作：pyproject 变更后 `uv lock` 使 extra 进入 lock 解析；CI 不装 vendor（测试用例不触达真实 SDK 调用路径，惰性 import 保证收集阶段无 ImportError）；需要摄取任务的 worker 部署 `uv sync --frozen --extra dev --extra vendor`。收益：结束"环境里有没有 tushare 全凭手工装"的状态，同时不扩大 CI/常规开发安装面。

**2. WindPy、EmQuantAPI（Wind/Choice 终端捆绑分发，非 PyPI）→ 不进 extra，维持现状并文档化。**

- 不可声明的原因：PyPI 无对应包，`uv lock` 无法解析；强行声明会让所有安装路径全红。
- 现状可接受的原因：import 全部惰性；toolkit 研究脚本默认命中本地 shim（`toolkit/WindPy.py` 读系统 DuckDB），仅真实终端模式需要 SDK，而该模式只存在于装有 Wind/Choice 客户端的工作站。
- 可选进阶（owner 决策项，不推荐现在做）：私有 wheel 索引 + `[tool.uv.sources]` 指向，把终端 SDK 纳入 lock 体系。

**3. 不建议做的**：把 tushare/akshare 提为主依赖（CI/开发安装面白白扩大）；在代码层为 vendor 加模块级 import 守卫重构（现有惰性 import 已是正确形态）。

## 四、Python 版本建议（owner 决策项）

现状矩阵（全部实测）：

| 环境 | Python | 证据 |
| --- | --- | --- |
| CI 全部 python job | 3.11（硬编码） | ci.yml L27/L60/L160 |
| 本地共享 `.venv` | **3.14.2** | `pyvenv.cfg`（home = pythoncore-3.14-64） |
| 本地系统解释器 | 3.11.9 | `py -0p`（另有 3.14 为 py 默认） |
| uv 解析用解释器 | 3.13.12（uv 托管、无钉定时自选） | `uv lock --check` 输出 |
| pyproject | `requires-python = ">=3.11"` | pyproject L5 |
| uv.lock | 3.11 / 3.12–3.13 / 3.14+ 三层 markers（scipy 等按层取不同版本） | lock L4-8 |
| 生产运行时 | **未知——本次调查未触达部署产物，无证据** | — |

owner 决策项：

1. **钉定基线**：建议新增 `backend/.python-version` 内容 `3.11`（与 CI 一致、改动最小），或明确升级到 3.12/3.13 的路线（需一次全量回归，scipy 1.18 层等随之生效）。未钉定前，一切 `uv sync` 必须显式 `--python`。
2. **生产盘点前不动 CI 的 3.11**：CI 版本应跟随生产运行时；生产版本本次无证据，先盘点再谈升级。
3. **本地 3.14.2 的 `.venv` 与 CI 3.11 的差异**要么接受（明知解释器层差异）、要么重建对齐——建议对齐，时机与 §2.4 本地切换合并执行。

## 五、frontend/package.json engines（本任务唯一代码编辑）

- 编辑内容：engines 字段定为

```json
  "engines": {
    "node": "^20.19.0 || >=22.12.0"
  }
```

- 并发合并说明：编辑落笔时发现共享工作区已有在途改动写入 `"node": ">=22"`。该值会放行 node 22.0–22.11（低于 vite 8.2.1 的 22.12.0 下限），且排除工具链支持的 node 20.19+ LTS，故在授权范围内改写为上述精确表达式。
- 推断依据：vite 8.2.1 的 engines（锁文件实测，devDependencies 中最严下限）∩ CI node 22 ⇒ 该表达式对 CI（22.x 最新）与本地 node 20.19+ LTS 均放行，且不放宽任何工具链要求（注意 `>=20.19.0` 写法会错误放行 node 21，故保留 vite 原表达式）。
- 不钉 npm 的原因：`lockfileVersion: 3` 由 npm 9+ 生成，而 node 20.19+/22.12+ 捆绑 npm ≥10，node 约束已传递覆盖 npm 下限，再钉属冗余。
- 语义边界：npm 默认对 engines 仅告警不阻断；如需硬失败可另加 `frontend/.npmrc` 的 `engine-strict=true`（不在本次授权，登记为可选后续项）。

## 六、验证记录（2026-08-12）

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| lock 一致性 | `uv lock --check --project backend` | **exit 1（失败）**，根因为共享工作区在途 pyproject 改动（§1.3），如实记录 |
| package.json 语法 | `node -e "JSON.parse(require('fs').readFileSync('frontend/package.json'))"` | **通过**（exit 0，engines.node 读回 `^20.19.0 \|\| >=22.12.0`） |
| 安装类命令 | — | **零执行**（uv sync / pip install / npm install 均未运行） |
