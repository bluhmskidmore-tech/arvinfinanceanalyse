# MOSS-V3 审计资料包说明

`audit_pack/` 保留架构说明、历史风险清单和审计提示词，不再保存一份会与主仓库漂移的源码副本。

## 包内文件

| 文件 | 用途 |
|------|------|
| `00_AUDIT_PACKAGE_README.md` | 本说明 |
| `01_PROJECT_TREE.md` | 裁剪后的历史目录树 |
| `02_PROJECT_OVERVIEW.md` | 技术栈与模块综述 |
| `03_BACKEND_API_MAP.md` | 后端路由与鉴权概要 |
| `04_FRONTEND_PAGE_API_MAP.md` | 工作台页面与前端 API 调用关系 |
| `05_DATABASE_MODEL_MAP.md` | Postgres ORM / Alembic / DuckDB 侧说明 |
| `06_FINANCIAL_LOGIC_AUDIT.md` | 金融计算关注点清单 |
| `07_RISK_AND_BUG_SCAN.md` | 静态风险与疑点汇总 |
| `08_RUN_AND_TEST.md` | 启动、环境与历史验证记录 |
| `09_WEB_PRO_ARCHITECTURE_AUDIT_PROMPT.md` | 架构审计提示词 |
| `TOP10_PRIORITIES.md` | 历史优先级清单 |
| `MANIFEST_FILES.txt` | 本目录的轻量文件清单 |
| `_generate_tree.py` | 生成目录树的辅助脚本 |

## 源码证据

需要源码证据时，使用明确提交生成制品，不要复制当前工作区：

```bash
python scripts/build_source_audit_artifact.py \
  --commit <完整的40位提交SHA>
```

默认输出到被 Git 忽略的
`.codex-artifacts/source-audit/<sha>/`，包含确定性 ZIP 和 manifest。manifest 记录
commit、tree、逐文件 SHA256 与 ZIP SHA256；dirty、untracked、运行数据、真实
`.env` 以及旧 `audit_pack/source_snapshot/` 均不会进入制品。

GitHub 的 `Source Audit Artifact` 手动工作流可用于临时交付，保留期为 30 天；
它不是长期审计存档。需要长期保留时，应把 ZIP 与 manifest 一起放入具有明确保留策略的对象库或 Release。

## 安全边界

真实密钥、数据库口令和外部 Token 不得进入审计包。环境字段只参考
`config/.env.example` 与 `frontend/.env.example`。
