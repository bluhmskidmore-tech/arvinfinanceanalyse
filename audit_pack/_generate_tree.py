"""Generate markdown directory tree excluding heavy/sensitive dirs (audit helper only)."""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

EXCLUDE_DIRS = frozenset(
    {
        "node_modules",
        "venv",
        ".venv",
        "dist",
        "build",
        ".git",
        "__pycache__",
        ".next",
        "coverage",
        "logs",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "tmp-governance",
        "audit_pack",  # do not recurse into pack output
    }
)


def walk_md(root: Path, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if not root.is_dir():
        return [f"{prefix}{root.name}/ (missing)\n"]

    raw = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    entries: list[Path] = []
    for path in raw:
        name = path.name
        if path.is_dir() and name in EXCLUDE_DIRS:
            continue
        if path.is_file() and name.startswith(".env") and name != ".env.example":
            if path.parent == REPO:
                continue
        entries.append(path)

    for i, path in enumerate(entries):
        name = path.name
        connector = "└── " if i == len(entries) - 1 else "├── "
        if path.is_dir():
            lines.append(f"{prefix}{connector}{name}/\n")
            extension = "    " if i == len(entries) - 1 else "│   "
            sub = walk_md(path, prefix + extension)
            lines.extend(sub)
        else:
            lines.append(f"{prefix}{connector}{name}\n")
    return lines


def section_tree(rel: Path) -> str:
    target = REPO / rel
    hdr = f"### `{rel.as_posix()}/`\n\n```\n"
    if not target.exists():
        return hdr + "(目录不存在)\n```\n\n"
    body = "".join(walk_md(target))
    return hdr + body.rstrip() + "\n```\n\n"


def main() -> None:
    out = REPO / "audit_pack" / "01_PROJECT_TREE.md"
    parts: list[str] = []
    parts.append("# MOSS-V3 项目目录树（审计用）\n\n")
    parts.append("排除目录：`node_modules`, `venv`, `.venv`, `dist`, `build`, `.git`, `__pycache__`, `.next`, `coverage`, `logs`, `audit_pack`，及根目录下 `.env`（非示例）。\n\n")
    parts.append("## 根目录摘要\n\n")
    parts.append(section_tree(Path(".")))
    parts.append("## backend\n\n")
    parts.append(section_tree(Path("backend")))
    parts.append("## frontend/src\n\n")
    parts.append(section_tree(Path("frontend/src")))
    parts.append("## 主要配置文件（路径索引）\n\n")
    parts.extend(
        [
            "| 类别 | 路径 |\n|---|---|\n",
            "| 后端入口 | `backend/app/main.py` |\n",
            "| FastAPI 路由聚合 | `backend/app/api/__init__.py` |\n",
            "| 后端依赖 | `backend/pyproject.toml` |\n",
            "| Alembic | `backend/alembic.ini`, `backend/alembic/` |\n",
            "| 环境与设置 | `backend/app/governance/settings.py`, `config/.env.example`（若存在）|\n",
            "| 前端包与脚本 | `frontend/package.json` |\n",
            "| Vite / TS | `frontend/vite.config.ts`, `frontend/tsconfig.json` |\n",
            "| 前端路由 | `frontend/src/router/routes.tsx`, `frontend/src/router/*` |\n",
            "| 导航与就绪度 | `frontend/src/mocks/navigation.ts` |\n",
            "| 后端 ORM（Postgres/KPI） | `backend/app/models/` |\n",
            "| Pydantic Schema | `backend/app/schemas/` |\n",
            "| 核心业务服务 | `backend/app/services/` |\n",
            "| 正式金融计算 | `backend/app/core_finance/`（注意：**无** `backend/app/core/`，请以 `core_finance` 为准）|\n",
            "| 异步任务写入 | `backend/app/tasks/` |\n",
            "| 说明：`backend/app/db/`、`backend/app/utils/` 当前仓库未发现独立包目录 |\n",
        ]
    )
    parts.append("\n")

    out.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
