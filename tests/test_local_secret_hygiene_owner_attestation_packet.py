from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.local_secret_hygiene_owner_attestation_packet import (
    DEFAULT_OUTPUT,
    build_packet,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "local_secret_hygiene_owner_attestation_packet.py"


def test_local_secret_hygiene_owner_attestation_packet_is_value_free() -> None:
    packet = build_packet()

    assert packet["packet_kind"] == "local_secret_hygiene_owner_attestation_packet"
    assert packet["source_snapshot_status"] == "local_ignored_untracked_findings"
    assert packet["owner_attestation_ready"] is True
    assert packet["closure_approved"] is False
    assert packet["secret_value_fields_present"] is False
    assert packet["detected_secret_names"] == [
        "MOSS_TUSHARE_TOKEN",
        "STITCH_API_KEY",
    ]
    assert packet["attestation_options"] == [
        "rotated",
        "removed",
        "accepted-local-only",
        "deferred",
    ]
    assert packet["required_attestation_fields"] == [
        "environment_owner",
        "security_owner",
        "decision",
        "decision_date",
        "external_evidence_reference",
        "clean_runner_or_acceptance_result",
    ]
    assert packet["current_blockers"] == [
        "ignored config/.env finding remains",
        "owner attestation not captured",
        "clean-runner or accepted-local-only result not captured",
    ]
    assert packet["evidence_scope"] == {
        "read_only": True,
        "reads_secret_values": False,
        "requests_secret_values": False,
        "captures_secret_values": False,
        "writes_or_rotates_secrets": False,
        "clears_secret_scan": False,
        "approves_deployment": False,
        "approves_local_secret_hygiene": False,
    }
    assert "secret_value" not in json.dumps(packet["attestation_template"])
    assert "read or paste config/.env values" in packet["prohibited_actions"]
    assert "does not read, request, capture, rotate, clear, or approve" in packet[
        "boundary"
    ]


def test_local_secret_hygiene_owner_attestation_packet_cli_writes_markdown(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "local-secret-owner-attestation.md"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["packet_kind"] == "local_secret_hygiene_owner_attestation_packet"
    assert payload["packet_path"] == str(output_path)
    assert payload["owner_attestation_ready"] is True
    assert payload["closure_approved"] is False
    assert payload["secret_value_fields_present"] is False
    assert payload["evidence_scope"]["captures_secret_values"] is False

    text = output_path.read_text(encoding="utf-8")
    assert text == render_markdown(build_packet())
    assert "Local Secret Hygiene Owner Attestation Packet" in text
    assert "`MOSS_TUSHARE_TOKEN`" in text
    assert "`STITCH_API_KEY`" in text
    assert "`secret_value_fields_present=false`" in text
    assert "Do not read or paste `config/.env` values." in text


def test_checked_in_local_secret_hygiene_owner_attestation_packet_matches_renderer() -> None:
    packet = build_packet()

    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_markdown(packet)
