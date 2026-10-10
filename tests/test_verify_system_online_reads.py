from __future__ import annotations

import json

import pytest

from scripts import verify_system_online_reads as probe


def test_business_fingerprint_preserves_null_quality_and_generation():
    payload = {
        "generation": "system-1", "amount": None, "quality": "stale",
        "computed_at": "now", "rows": [{"generated_at": "now", "amount": "1.00"}],
    }
    assert probe._canonical_business(payload) == {
        "generation": "system-1", "amount": None, "quality": "stale",
        "rows": [{"amount": "1.00"}],
    }
    assert "computed_at" in payload


def test_one_interaction_pins_all_followup_reads(monkeypatch):
    calls = []

    def fake_probe(base_url, domain, path, generation):
        calls.append((domain, generation))
        return {"domain": domain, "generation": "system-r0"}

    monkeypatch.setattr(probe, "_probe", fake_probe)
    rows = probe._interaction("http://127.0.0.1:7888", "2026-08-31", 7)
    assert calls == [
        ("home", None), ("balance", "system-r0"), ("bond", "system-r0"),
        ("risk", "system-r0"), ("pnl", "system-r0"),
    ]
    assert {row["interaction"] for row in rows} == {7}


@pytest.mark.parametrize("kind", ["missing", "mismatch", "changed"])
def test_cli_rejects_generation_or_consistency_failure(monkeypatch, tmp_path, kind):
    output = tmp_path / "audit.json"
    monkeypatch.setattr("sys.argv", [
        "probe", "--report-date", "2026-08-31", "--clients", "1",
        "--rounds", "2", "--phase", "during-label-only", "--require-generation",
        "--output", str(output),
    ])

    def fake_interaction(base_url, report_date, interaction, include_update_status=False):
        return [{
            "domain": "home", "interaction": interaction,
            "http_status": 200, "envelope_valid": True,
            "generation": None if kind == "missing" else "system-r0",
            "requested_generation": "system-r1" if kind == "mismatch" else None,
            "business_report_date": report_date,
            "business_sha256": str(interaction) if kind == "changed" else "stable",
            "elapsed_ms": 1,
        }]

    monkeypatch.setattr(probe, "_interaction", fake_interaction)
    assert probe.main() == 1
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["failures"]
    assert evidence["writer_overlap_proven"] is False


def test_cli_rejects_nonlocal_target_before_http(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", [
        "probe", "--base-url", "https://example.com", "--report-date", "2026-08-31",
        "--phase", "test", "--output", str(tmp_path / "audit.json"),
    ])
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2


def _comparable_payloads():
    report_date = "2026-08-31"
    return {
        "home": {
            "report_date": report_date,
            "domains_missing": [],
            "domains_effective_date": {"balance_sheet": report_date, "pnl": report_date},
            "overview": {"metrics": [
                {"id": "aum", "label": "总资产规模", "value": {"raw": 100, "unit": "yuan"}},
                {"id": "dv01", "value": {"raw": 12, "unit": "dv01"}},
            ]},
        },
        "balance": {
            "report_date": report_date, "currency_basis": "CNY", "position_scope": "all",
            **{
                f"{side}total_{field}_amount": amount
                for side, amount in (("", "130"), ("asset_", "100"), ("liability_", "30"))
                for field in ("market_value", "amortized_cost", "accrued_interest")
            },
        },
        "bond": {"report_date": report_date, "total_dv01": "12", "total_market_value": "80", "bond_count": 2},
        "risk": {
            "report_date": report_date, "portfolio_dv01": {"raw": 12, "unit": "dv01"},
            "total_market_value": {"raw": 80, "unit": "yuan"}, "bond_count": 2,
        },
    }


def test_same_source_tieout_checks_eight_mappings_without_exporting_amounts():
    checks = probe._business_tieout(_comparable_payloads(), "2026-08-31")
    assert len(checks) == 8
    assert all(check["status"] == "passed" for check in checks)
    assert all(set(check) == {"check", "status", "absolute_tolerance"} for check in checks)


@pytest.mark.parametrize("mismatch", ["unit", "date", "scope", "null", "value"])
def test_tieout_does_not_hide_incomparable_or_different_values(mismatch):
    payloads = _comparable_payloads()
    if mismatch == "unit":
        payloads["risk"]["total_market_value"]["unit"] = "wan_yuan"
    elif mismatch == "date":
        payloads["risk"]["report_date"] = "2026-08-30"
    elif mismatch == "scope":
        payloads["balance"]["currency_basis"] = "USD"
    elif mismatch == "null":
        payloads["risk"]["total_market_value"]["raw"] = None
    else:
        payloads["risk"]["total_market_value"]["raw"] = 81
    checks = probe._business_tieout(payloads, "2026-08-31")
    assert any(check["status"] != "passed" for check in checks)


def test_interaction_discards_captured_business_values_after_tieout(monkeypatch):
    payloads = _comparable_payloads()

    def fake_probe(base_url, domain, path, generation, captured_business=None):
        if captured_business is not None:
            captured_business[domain] = payloads.get(domain, {})
        return {"domain": domain, "generation": "system-r0"}

    monkeypatch.setattr(probe, "_probe", fake_probe)
    rows = probe._interaction("http://127.0.0.1:7888", "2026-08-31", 1, business_tieout=True)
    assert len(rows[0]["business_tieout"]) == 8
    assert "asset_total_market_value_amount" not in json.dumps(rows)
    assert "captured_business" not in json.dumps(rows)
