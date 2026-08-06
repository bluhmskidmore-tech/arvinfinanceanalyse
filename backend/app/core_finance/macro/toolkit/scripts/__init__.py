"""Migrated macro toolkit scripts.

Scripts in this package are executed through
``app.core_finance.macro.toolkit.run_toolkit_script`` so their legacy
``paths`` imports keep working.

When the scripts are imported as a package from tests, insert the toolkit root
on ``sys.path`` so top-level compatibility imports like ``import akshare``
resolve to the local shim in ``backend.app.core_finance.macro.toolkit`` rather
than requiring the external AkShare package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
if str(_TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOLKIT_ROOT))
