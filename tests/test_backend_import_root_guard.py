"""Static guard: forbid ``app.``-rooted imports under ``backend/app/``.

防双导入根 / 模块双实例（P1，2026-08-12 修复后冻结）：

- 全仓后端代码统一使用绝对 ``backend.app.`` 前缀作为唯一导入根。
- venv 的 editable ``.pth`` 将 ``<repo>/backend`` 常驻 ``sys.path``，使
  ``app.`` 与 ``backend.app.`` 两个根同时可导入。同一源文件会被 Python
  加载为两份互相独立的模块实例，导致：
  - 跨根 ``isinstance`` / 异常捕获失效（两根各有一份同名类）；
  - 模块级注册表 split-brain（如 calibers 注册表两根各持一份 ``_RULES``）。
- 2026-08-12 已将 ``backend/app/core_finance/macro/`` 下 13 个文件共 26 处
  ``from app....`` 导入统一改为 ``from backend.app....``。本测试从零存量
  冻结该不变量：``backend/app/`` 下任何 ``.py`` 文件不得再出现以 ``app``
  为根的导入（含 ``from app.x import y`` / ``import app.x`` /
  ``from app import x`` / ``import app`` 变体）。
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN_ROOT = _REPO_ROOT / "backend" / "app"

# 逐行匹配以 `app` 为根的导入；`\b` 确保不误伤 application/apps 等名字，
# 覆盖 `from app.x import y`、`import app.x`、`from app import x`、`import app`。
_APP_ROOT_IMPORT = re.compile(r"^\s*(?:from|import)\s+app\b")

# 运行时断言消息使用英文：Windows 控制台（cp936）下 pytest 输出中文会乱码。
_GUIDANCE = (
    "app-rooted imports under backend/app/ resolve through the editable .pth dual "
    "import root and create duplicate module instances (cross-root isinstance/except "
    "fail; module-level registries split-brain). Use the absolute `backend.app.` "
    "prefix instead."
)


def test_backend_app_has_no_app_rooted_imports() -> None:
    assert _SCAN_ROOT.is_dir(), f"scan root missing: {_SCAN_ROOT}"

    files_scanned = 0
    offenders: list[str] = []
    for path in sorted(_SCAN_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        files_scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _APP_ROOT_IMPORT.match(line):
                rel = path.relative_to(_REPO_ROOT).as_posix()
                offenders.append(f"  {rel}:{lineno}: {line.strip()}")

    assert files_scanned > 0, f"no python files scanned under {_SCAN_ROOT}"
    assert not offenders, _GUIDANCE + "\n" + "\n".join(offenders)
