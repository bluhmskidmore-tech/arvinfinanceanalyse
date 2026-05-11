from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.services import macro_adversarial_signal_service


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8-sig")


def test_load_macro_adversarial_signal_payload_prefers_final_signal_and_blocks_on_third_layer(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "final_signal.csv",
        """
品种,日期,最终信号,仓位比例,置信度,信号说明,第三层_通过
T,2026-05-11,空仓,0,3,第三层拦截：拥挤冲突,False
TF,2026-05-11,多,0.75,3,拥挤度OK,True
""",
    )
    _write_csv(
        tmp_path / "crowding_latest.csv",
        """
品种,日期,C分位数,拥挤度信号,说明
T,2026-05-11,0.91,警惕多头,多头拥挤
TF,2026-05-11,0.35,中性,拥挤度中性
""",
    )

    payload, meta = macro_adversarial_signal_service.load_macro_adversarial_signal_payload(tmp_path)

    assert payload["status"] == "ok"
    assert payload["mode"] == "final_signal"
    assert payload["risk_gate"] == "block"
    assert payload["position_scale"] == 0.75
    assert payload["diagnostics"] == []
    assert [item["symbol"] for item in payload["items"]] == ["T", "TF"]
    blocked = payload["items"][0]
    assert blocked["risk_gate"] == "block"
    assert blocked["position_scale"] == 0.0
    assert blocked["signal"] == "空仓"

    assert meta["source_version"] == "macro_toolkit.final_signal.csv"
    assert meta["vendor_version"] == "macro_toolkit.local_csv"
    assert meta["quality_flag"] == "ok"
    assert meta["vendor_status"] == "ok"
    assert meta["fallback_mode"] == "none"
    assert meta["evidence_rows"] == 2


def test_load_macro_adversarial_signal_payload_falls_back_to_crowding_snapshot_and_flags_non_finite(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "crowding_latest.csv",
        """
鍝佺,鏃ユ湡,C鍒嗕綅鏁?,鎷ユ尋搴︿俊鍙?,璇存槑
TL,2026-05-11,NaN,璀︽儠澶氬ご,澶氬ご鎷ユ尋
""",
    )

    payload, meta = macro_adversarial_signal_service.load_macro_adversarial_signal_payload(tmp_path)

    assert payload["status"] == "degraded"
    assert payload["mode"] == "crowding_latest"
    assert payload["risk_gate"] == "degraded"
    assert payload["position_scale"] == 0.0
    assert payload["items"][0]["symbol"] == "TL"
    assert payload["items"][0]["crowding_percentile"] is None
    assert any("non-finite" in item for item in payload["diagnostics"])

    assert meta["source_version"] == "macro_toolkit.crowding_latest.csv"
    assert meta["quality_flag"] == "warning"
    assert meta["vendor_status"] == "vendor_stale"
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["evidence_rows"] == 1


def test_load_macro_adversarial_signal_payload_returns_missing_when_no_csv_exists(tmp_path: Path) -> None:
    payload, meta = macro_adversarial_signal_service.load_macro_adversarial_signal_payload(tmp_path)

    assert payload["status"] == "missing"
    assert payload["mode"] == "missing"
    assert payload["risk_gate"] == "missing"
    assert payload["position_scale"] == 0.0
    assert payload["items"] == []
    assert payload["diagnostics"] == ["final_signal.csv missing", "crowding_latest.csv missing"]

    assert meta["source_version"] == "macro_toolkit.adversarial_signal.missing"
    assert meta["quality_flag"] == "error"
    assert meta["vendor_status"] == "vendor_unavailable"
    assert meta["fallback_mode"] == "none"
    assert meta["evidence_rows"] == 0


def test_macro_toolkit_adversarial_signal_endpoint_emits_expected_result_meta(monkeypatch) -> None:
    monkeypatch.setattr(
        macro_toolkit_route,
        "OUTPUT_DIR",
        Path("F:/fake-macro-output"),
    )
    monkeypatch.setattr(
        macro_toolkit_route.macro_adversarial_signal_service,
        "load_macro_adversarial_signal_payload",
        lambda output_dir=None: (
            {
                "status": "degraded",
                "mode": "crowding_latest",
                "risk_gate": "degraded",
                "position_scale": 0.0,
                "items": [],
                "diagnostics": ["crowding-only snapshot"],
            },
            {
                "source_version": "macro_toolkit.crowding_latest.csv",
                "vendor_version": "macro_toolkit.local_csv",
                "tables_used": ["macro_toolkit_output.crowding_latest.csv"],
                "evidence_rows": 0,
                "quality_flag": "warning",
                "vendor_status": "vendor_stale",
                "fallback_mode": "latest_snapshot",
                "as_of_date": "2026-05-11",
            },
        ),
    )

    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/adversarial-signal")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "degraded"
    assert payload["result_meta"]["result_kind"] == "macro_toolkit.adversarial_signal"
    assert payload["result_meta"]["rule_version"] == "rv_macro_adversarial_signal_v1"
    assert payload["result_meta"]["source_version"] == "macro_toolkit.crowding_latest.csv"
    assert payload["result_meta"]["vendor_version"] == "macro_toolkit.local_csv"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["tables_used"] == ["macro_toolkit_output.crowding_latest.csv"]
