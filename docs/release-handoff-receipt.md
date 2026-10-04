# 源码、候选包与运行入口交接回执

`scripts/release_handoff_receipt.py` 将源码、已记录的测试、候选包、运行登记和实际 HTTP 响应分别核对，输出一份 JSON。它不执行测试、不构建、不启动服务，也不修改运行登记或创建运行控制锁。结果描述本次检查时可观察到的版本关系，不代表业务对账、发布审批或后端运行验收。

## 使用方式

从仓库根目录执行，输入文件可保存在仓库外。`--selection` 是准备交接的候选配置，沿用运行控制器已有字段；实际登记固定读取 `tmp-governance/runtime-clean/control/frontend.json`。默认检查 `http://127.0.0.1:5888/`，只有明确检查其他本机入口时才传 `--base-url`。

```powershell
backend\.venv\Scripts\python.exe -B scripts/release_handoff_receipt.py --source-manifest C:/evidence/source-manifest.json --test-receipt C:/evidence/test-receipt.json --build-receipt C:/evidence/build-receipt.json --selection C:/evidence/candidate-selection.json
```

`--test-receipt` 和 `--build-receipt` 可省略。缺少这些输入时仍检查源码、候选、登记和 HTTP，并将缺少的关联标为 `unknown`。旧测试日志不能因为日期相近、HEAD 相同或退出码为零，就补写成与当前源码绑定的证据。命令只向标准输出写 JSON；全部层通过时退出码为 0，其余情况为 1，参数错误由命令行解析器报告。示例中的 `-B` 禁止 Python 导入时写入字节码缓存；作为库调用时，字节码缓存由调用进程的 Python 设置控制。

## 输入证据

源码清单兼容既有的文件列表，每项包含仓库相对路径 `path` 和小写 SHA-256 `sha256`。额外的 `bytes` 字段不参与核对。这种输入的覆盖范围是 `listed_files_only`：检查列出的文件是否变化或缺失，不证明仓库内没有新增文件。

如果需要发现新增文件，使用带 `roots` 的对象。程序会递归检查这些明确指定目录内的文件集，任何未列出的文件都会导致失败；清单中位于这些目录之外的文件仍逐项检查。范围只限声明的目录和文件，不自动扩大为全仓。

```json
{
  "roots": ["frontend/src"],
  "files": [
    {"path": "frontend/src/main.tsx", "sha256": "该文件的64位小写SHA256"}
  ]
}
```

上例仅说明结构；真实清单必须列全 `frontend/src` 内的文件。不要把数据、依赖、构建输出或缓存目录纳入源码范围。路径不得逃出仓库或穿过符号链接、目录联接。历史文件列表可保留其中已声明的临时辅助文件，这不等于允许递归扫描临时目录；目录闭集模式会拒绝依赖、数据、构建与缓存目录，枚举失败也必须报错。

测试回执保存实际执行命令、退出码和本次记录的结果，并用 `source_manifest_sha256` 指向受测清单的**原始文件字节**哈希。应在测试执行时保留源码前后身份，确认稳定后才记录关联；本工具不重新执行或独立认证这些声明。

```json
{
  "source_manifest_sha256": "受测源码清单的64位SHA256",
  "command": ["python", "-m", "pytest", "tests/test_example.py", "-q"],
  "exit_code": 0,
  "results": [{"name": "tests/test_example.py", "status": "passed"}]
}
```

零退出码只说明这里记录的检查结果。空结果、缺少执行信息、失败或跳过结果不能算这一层通过。测试范围由 `command` 和 `results` 明示，程序不会把局部测试提升为全量测试或业务验收。后端套件选择继续以 `scripts/backend_release_suite.py` 为准；此工具不复制套件列表、不修改 CI 选择器。

构建来源回执包含 `source_manifest_sha256` 和 `build_manifest_sha256`。前者指构建时记录的源码清单，后者指候选文件清单，两者都使用原始文件字节哈希。它是已记录的构建关联，不是本工具重新构建得到的证明；缺少同期证据时应省略，不能根据现有包倒填。

候选配置沿用以下结构。候选文件清单、完整文件集及每个文件哈希由现有 `dev_runtime_control.verify_build` 校验，不另写一套验包规则。

```json
{
  "mode": "accepted",
  "data_source": "real",
  "build_root": ".codex-tmp/example/dist",
  "manifest_path": ".codex-tmp/example/manifest.json",
  "manifest_sha256": "候选清单的64位小写SHA256"
}
```

## 如何读取结果

顶层 `scope=declared_inputs_only` 和 `evidence_authority=supplied_records_not_independently_attested` 表明这里只核对声明范围及提供的记录。`status=passed` 表示这些层的检查通过，不表示外部记录经过独立认证，也不改变 `business_acceptance=not assessed`。

`layers.source` 报告清单覆盖方式、预期清单哈希、现场文件指纹和差异。`layers.tests` 报告声明的测试结果及其源码关联，`layers.candidate` 报告候选完整性，`layers.build_binding` 报告构建来源关联。`layers.registration` 比较候选与当前登记；登记不同也继续执行 HTTP 检查，让两类问题分别可见。

HTTP 检查复用 `frontend_plan` 提供的探针，对比候选的 `index.html` 和入口模块响应哈希；普通 200 响应不足以通过。它只证明这些入口响应，不证明所有懒加载资源、真实 API、后端版本或报告日指标。没有直接调用旧 `probe_frontend`，因为旧函数会创建运行控制锁；这里仅复用无写入的验包和探针规划逻辑。

检查结束前会重新核对源码、候选、登记和关联回执，拒绝检查期间观察到的变化。这是前后检查，不是加锁的原子快照，无法排除瞬间修改又恢复。`identity_sha256` 用于比较同一输入和观测身份，不是签名、发布令牌或永久有效的验收编号。再次修改源码、构建或登记后，应重新生成回执。
