from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_macro_toolkit_freshness_timer.ps1"


def test_installer_writes_scheduled_receipt_flags() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "--run-once" in text
    assert "--run-kind scheduled" in text
    assert "macro_toolkit_freshness_refresh_receipt.json" in text
    assert "06:30" in text
    assert "post-enable" in text
    assert "schtasks /Create" in text
