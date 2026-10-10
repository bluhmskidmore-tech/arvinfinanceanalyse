from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_macro_toolkit_freshness_timer.ps1"

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def test_installer_rejects_choice_source_ip_that_is_not_bindable_on_host() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "System.Net.Sockets.Socket" in text
    assert ".Bind(" in text
    assert "is not assigned to this host" in text
