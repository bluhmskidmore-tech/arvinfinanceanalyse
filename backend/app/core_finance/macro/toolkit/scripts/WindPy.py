import sys
from pathlib import Path

if not __package__:
    _REPO_ROOT = Path(__file__).resolve().parents[6]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

from backend.app.core_finance.macro.toolkit.WindPy import w

__all__ = ["w"]
