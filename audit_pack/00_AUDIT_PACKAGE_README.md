# MOSS-V3 审计资料包说明

本文档目录由自动化扫描生成，供上传至 ChatGPT 或其他审计工具做一次系统级排查。**未改动业务源代码**。

## 包内文件

| 文件 | 用途 |
|------|------|
| `00_AUDIT_PACKAGE_README.md` | 本说明 |
| `01_PROJECT_TREE.md` | 裁剪后的目录树（根 / backend / frontend/src）|
| `02_PROJECT_OVERVIEW.md` | 技术栈与模块综述 |
| `03_BACKEND_API_MAP.md` | 后端路由与鉴权概要 |
| `04_FRONTEND_PAGE_API_MAP.md` | 工作台页面与前端 API 调用关系 |
| `05_DATABASE_MODEL_MAP.md` | Postgres ORM / Alembic / DuckDB 侧说明 |
| `06_FINANCIAL_LOGIC_AUDIT.md` | 金融计算关注点清单 |
| `07_RISK_AND_BUG_SCAN.md` | 静态风险与疑点汇总 |
| `08_RUN_AND_TEST.md` | 启动方式、环境与最近验证命令输出 |
| `source_snapshot/` | 关键源码与配置快照（**无** node_modules / venv；`.env` 仅脱敏副本见 `source_snapshot/redacted_env/`）|
| `_generate_tree.py` | 生成目录树用辅助脚本 |

## 使用建议

1. 先阅读 `02` + `08` 建立上下文，再按需深入 `03`–`07`。
2. 与代码对照时直接使用 `source_snapshot/`，路径与仓库内一致。
3. 真实密钥、数据库口令、外部 Token **不在包内**；脱敏变量见 `redacted_env`。

## 压缩包产物

仓库根目录会生成：`moss_v3_audit_pack.zip`（内容与 `audit_pack/` 等价）。可同时复制一份到桌面，见会话输出。
