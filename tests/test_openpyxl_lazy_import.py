from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_package_import_does_not_load_openpyxl() -> None:
    """Cold-import backend.app.api must not pay openpyxl (~1s) until workbook I/O runs."""
    code = (
        "import sys; "
        "import backend.app.api; "
        "loaded = sorted(m for m in sys.modules if m == 'openpyxl' or m.startswith('openpyxl.')); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_target_modules_import_without_loading_openpyxl() -> None:
    code = (
        "import sys\n"
        "import backend.app.services.balance_analysis_workbook_service\n"
        "import backend.app.core_finance.qdb_gl_monthly_analysis\n"
        "import backend.app.services.pnl_source_service\n"
        "import backend.app.core_finance.source_preview_parsers\n"
        "import backend.app.services.ledger_import_service\n"
        "import backend.app.services.ledger_analytics_service\n"
        "import backend.app.services.qdb_gl_input_validation_service\n"
        "import backend.app.services.product_category_source_service\n"
        "loaded = sorted(\n"
        "    module_name\n"
        "    for module_name in sys.modules\n"
        "    if module_name == 'openpyxl' or module_name.startswith('openpyxl.')\n"
        ")\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr
