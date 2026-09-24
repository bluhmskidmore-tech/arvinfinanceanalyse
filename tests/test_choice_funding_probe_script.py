from __future__ import annotations

import json
from pathlib import Path

from scripts.choice_funding_probe import (
    build_choice_funding_probe_payload,
    build_choice_runtime_preflight,
    summarize_choice_probe_result,
    main,
)

READY_PREFLIGHT = {
    "status": "config_present",
    "choice_emquant_parent_configured": True,
    "choice_start_options_configured": True,
    "choice_request_options_configured": True,
    "emquant_importable": True,
    "starts_choice_session": False,
    "calls_choice_data_api": False,
    "write_performed": False,
    "detail": "ready",
}


class _ChoiceRuntimeSettings:
    def __init__(
        self,
        *,
        choice_emquant_parent: str = "",
        choice_start_options: str = "",
        choice_request_options: str = "",
    ) -> None:
        self.choice_emquant_parent = choice_emquant_parent
        self.choice_start_options = choice_start_options
        self.choice_request_options = choice_request_options


def test_choice_runtime_preflight_reports_missing_config_without_import_probe():
    import_calls: list[str] = []

    result = build_choice_runtime_preflight(
        settings=_ChoiceRuntimeSettings(),
        get_em_c_func=lambda: import_calls.append("called"),
    )

    assert result["status"] == "missing_config"
    assert result["choice_emquant_parent_configured"] is False
    assert result["choice_start_options_configured"] is False
    assert result["emquant_importable"] is False
    assert result["starts_choice_session"] is False
    assert result["calls_choice_data_api"] is False
    assert result["write_performed"] is False
    assert import_calls == []


def test_choice_runtime_preflight_reports_ready_when_config_and_import_are_present():
    configured_paths: list[str] = []

    result = build_choice_runtime_preflight(
        settings=_ChoiceRuntimeSettings(
            choice_emquant_parent="F:/EMQuantAPI_Python/python3",
            choice_start_options="UserName=demo,PassWord=demo,ForceLogin=1",
            choice_request_options="RECVtimeout=5",
        ),
        configure_emquant_parent_func=configured_paths.append,
        get_em_c_func=lambda: object(),
    )

    assert result["status"] == "config_present"
    assert result["choice_emquant_parent_configured"] is True
    assert result["choice_start_options_configured"] is True
    assert result["choice_request_options_configured"] is True
    assert result["emquant_importable"] is True
    assert configured_paths == ["F:/EMQuantAPI_Python/python3"]


def test_choice_funding_probe_dry_run_skips_runtime_preflight_by_default():
    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=30,
        execute=False,
    )

    assert payload["status"] == "dry_run"
    assert payload["preflight"]["status"] == "skipped"
    assert payload["preflight"]["starts_choice_session"] is False
    assert payload["preflight"]["calls_choice_data_api"] is False
    assert payload["preflight"]["write_performed"] is False


def test_choice_funding_probe_execute_blocks_when_runtime_preflight_is_missing_config():
    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=30,
        execute=True,
        runtime_preflight={
            "status": "missing_config",
            "choice_emquant_parent_configured": False,
            "choice_start_options_configured": False,
            "choice_request_options_configured": False,
            "emquant_importable": False,
            "starts_choice_session": False,
            "calls_choice_data_api": False,
            "write_performed": False,
            "detail": "missing test config",
        },
    )

    assert payload["status"] == "blocked"
    assert payload["execute"] is True
    assert payload["preflight"]["status"] == "missing_config"
    assert payload["completed_batches"] == 0
    assert payload["failed_batches"] == 0
    assert payload["probe_results"] == []
    assert payload["write_performed"] is False


def test_choice_funding_probe_dry_run_payload_uses_default_catalog():
    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=10,
        execute=False,
    )

    assert payload["status"] == "dry_run"
    assert payload["execute"] is False
    assert payload["opportunity_id"] == "choice_funding_conditions"
    assert payload["choice_api_function"] == "edb"
    assert payload["wrapper_status"] == "available"
    assert payload["total_candidates"] == 31
    assert payload["batch_count"] == 4
    assert payload["landing_targets"] == ["fact_choice_macro_daily", "choice_market_snapshot"]
    first_batch = payload["batches"][0]
    assert first_batch["batch_index"] == 1
    assert first_batch["codes"]
    assert first_batch["request_options"] == (
        "IsLatest=0,StartDate=2026-06-10,EndDate=2026-06-10,Ispandas=1,RECVtimeout=5"
    )


def test_choice_funding_probe_execute_summarizes_success_and_failure_without_writing():
    calls: list[tuple[list[str], str]] = []

    class FakeChoiceClient:
        def edb(self, codes, options=""):
            calls.append((list(codes), options))
            if "EMM01089841" in codes:
                raise RuntimeError("Choice entitlement denied")
            return {"ok": True}

    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=10,
        execute=True,
        choice_client=FakeChoiceClient(),
        runtime_preflight=READY_PREFLIGHT,
    )

    assert payload["status"] == "partial"
    assert payload["execute"] is True
    assert payload["completed_batches"] == 3
    assert payload["failed_batches"] == 1
    assert payload["write_performed"] is False
    assert len(payload["probe_results"]) == 4
    assert payload["probe_results"][0]["status"] == "completed"
    assert payload["probe_results"][1]["status"] == "failed"
    assert "Choice entitlement denied" in payload["probe_results"][1]["error_message"]
    assert len(calls) == 4


def test_choice_funding_probe_execute_treats_nonzero_error_code_as_failed():
    class FakeResult:
        ErrorCode = 10001012
        ErrorMsg = "permission denied"

    class FakeChoiceClient:
        def edb(self, codes, options=""):
            return FakeResult()

    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=30,
        execute=True,
        choice_client=FakeChoiceClient(),
        runtime_preflight=READY_PREFLIGHT,
    )

    assert payload["status"] == "failed"
    assert payload["completed_batches"] == 0
    assert payload["failed_batches"] == 2
    result = payload["probe_results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == 10001012
    assert result["error_message"] == "permission denied"
    assert result["result_type"] == "FakeResult"


def test_choice_funding_probe_execute_records_success_result_type():
    class FakeResult:
        ErrorCode = 0
        ErrorMsg = ""

    class FakeChoiceClient:
        def edb(self, codes, options=""):
            return FakeResult()

    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=30,
        execute=True,
        choice_client=FakeChoiceClient(),
        runtime_preflight=READY_PREFLIGHT,
    )

    assert payload["status"] == "completed"
    result = payload["probe_results"][0]
    assert result["status"] == "completed"
    assert result["error_code"] == 0
    assert result["error_message"] == ""
    assert result["result_type"] == "FakeResult"


def test_choice_funding_probe_execute_summarizes_emquant_rows_and_dates():
    class FakeResult:
        ErrorCode = 0
        ErrorMsg = ""
        Dates = ["2026-06-07", "2026-06-10"]
        Data = {
            "DR007": [[1.72, 1.75]],
            "SHIBOR_ON": [[1.31, None]],
        }

    class FakeChoiceClient:
        def edb(self, codes, options=""):
            return FakeResult()

    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=30,
        execute=True,
        choice_client=FakeChoiceClient(),
        runtime_preflight=READY_PREFLIGHT,
    )

    result = payload["probe_results"][0]
    assert result["row_count"] == 3
    assert result["date_min"] == "2026-06-07"
    assert result["date_max"] == "2026-06-10"


def test_summarize_choice_probe_result_counts_dataframe_rows_and_dates():
    class FakeSeries:
        def __init__(self, values):
            self._values = values

        def dropna(self):
            return self

        def astype(self, _kind):
            return self

        def tolist(self):
            return list(self._values)

    class FakeFrame:
        def __init__(self):
            self.columns = ["DATES", "RESULT"]

        def __len__(self):
            return 2

        def __getitem__(self, key):
            if key == "DATES":
                return FakeSeries(["2026/06/07", "2026/06/10"])
            raise KeyError(key)

    summary = summarize_choice_probe_result(FakeFrame())

    assert summary["row_count"] == 2
    assert summary["date_min"] == "2026-06-07"
    assert summary["date_max"] == "2026-06-10"


def test_summarize_choice_probe_result_includes_dataframe_series_details():
    class FakeIndex:
        def __init__(self, values):
            self._values = values

        def tolist(self):
            return list(self._values)

    class FakeILoc:
        def __init__(self, rows):
            self._rows = rows

        def __getitem__(self, index):
            return self._rows[index]

    class FakeRows:
        def __init__(self, rows):
            self._rows = rows
            self.iloc = FakeILoc(rows)

        def __len__(self):
            return len(self._rows)

    class FakeLoc:
        def __init__(self, rows_by_code):
            self._rows_by_code = rows_by_code

        def __getitem__(self, keys):
            return FakeRows(self._rows_by_code.get(keys[0], []))

    class FakeSeries:
        def __init__(self, values):
            self._values = values

        def dropna(self):
            return self

        def astype(self, _kind):
            return self

        def tolist(self):
            return list(self._values)

    class FakeFrame:
        def __init__(self):
            self.columns = ["DATES", "RESULT"]
            self.index = FakeIndex(["DR007", "DR007", "SHIBOR_ON"])
            self.loc = FakeLoc(
                {
                    "DR007": [
                        {"DATES": "2025/01/01", "RESULT": None},
                        {"DATES": "2026/06/10", "RESULT": 1.75},
                    ],
                    "SHIBOR_ON": [{"DATES": "2026/06/09", "RESULT": 1.384}],
                }
            )

        def __len__(self):
            return 3

        def __getitem__(self, key):
            if key == "DATES":
                return FakeSeries(["2025/01/01", "2026/06/10", "2026/06/09"])
            raise KeyError(key)

    summary = summarize_choice_probe_result(FakeFrame())

    assert summary["series_details"] == [
        {
            "code": "DR007",
            "latest_date": "2026-06-10",
            "latest_value": 1.75,
            "non_null_rows": 1,
            "observed_rows": 2,
        },
        {
            "code": "SHIBOR_ON",
            "latest_date": "2026-06-09",
            "latest_value": 1.384,
            "non_null_rows": 1,
            "observed_rows": 1,
        },
    ]


def test_choice_funding_probe_execute_can_limit_batches():
    calls: list[list[str]] = []

    class FakeResult:
        ErrorCode = 0
        ErrorMsg = ""

    class FakeChoiceClient:
        def edb(self, codes, options=""):
            calls.append(list(codes))
            return FakeResult()

    payload = build_choice_funding_probe_payload(
        as_of_date="2026-06-10",
        chunk_size=10,
        max_batches=1,
        execute=True,
        choice_client=FakeChoiceClient(),
        runtime_preflight=READY_PREFLIGHT,
    )

    assert payload["status"] == "completed"
    assert payload["batch_count"] == 1
    assert payload["total_candidates"] == 31
    assert payload["selected_batch_count"] == 1
    assert payload["available_batch_count"] == 4
    assert len(calls) == 1
    assert len(payload["probe_results"]) == 1


def test_choice_funding_probe_cli_emits_json_dry_run(capsys):
    exit_code = main(["--as-of-date", "2026-06-10", "--chunk-size", "15"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert payload["batch_count"] == 3
    assert payload["total_candidates"] == 31
    assert payload["preflight"]["status"] == "skipped"


def test_choice_funding_probe_cli_accepts_latest_probe_mode(capsys):
    exit_code = main(
        [
            "--as-of-date",
            "2026-06-10",
            "--chunk-size",
            "30",
            "--probe-mode",
            "latest",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["probe_mode"] == "latest"
    assert payload["batches"][0]["probe_mode"] == "latest"
    assert payload["batches"][0]["request_options"] == "IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5"


def test_choice_funding_probe_cli_can_include_runtime_preflight(capsys):
    exit_code = main(["--as-of-date", "2026-06-10", "--chunk-size", "30", "--preflight"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert payload["preflight"]["status"] in {"config_present", "missing_config"}
    assert payload["preflight"]["starts_choice_session"] is False
    assert payload["preflight"]["calls_choice_data_api"] is False
    assert payload["preflight"]["write_performed"] is False


def test_choice_funding_probe_cli_writes_output_path(tmp_path: Path, capsys):
    output_path = tmp_path / "funding-probe.json"

    exit_code = main(
        [
            "--as-of-date",
            "2026-06-10",
            "--chunk-size",
            "15",
            "--max-batches",
            "1",
            "--output-path",
            str(output_path),
        ]
    )

    assert exit_code == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert file_payload["batch_count"] == 1
    assert file_payload["available_batch_count"] == 3
    assert file_payload["selected_batch_count"] == 1


def test_choice_funding_probe_cli_rejects_bad_chunk_size(capsys):
    exit_code = main(["--as-of-date", "2026-06-10", "--chunk-size", "0"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "chunk_size must be positive" in captured.err


def test_choice_funding_probe_cli_accepts_custom_catalog(tmp_path: Path, capsys):
    catalog_path = tmp_path / "choice_macro_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test",
                "vendor_name": "choice",
                "generated_at": "2026-06-10T09:00:00+08:00",
                "generated_from": "test",
                "batches": [
                    {
                        "batch_id": "stable",
                        "fetch_mode": "date_slice",
                        "fetch_granularity": "batch",
                        "refresh_tier": "stable",
                        "policy_note": "test",
                        "request_options": {"IsLatest": 0},
                        "series": [
                            {
                                "series_id": "DR007",
                                "series_name": "DR007",
                                "vendor_series_code": "DR007",
                                "frequency": "daily",
                                "unit": "%",
                                "theme": "money_liquidity",
                                "is_core": True,
                                "tags": ["choice", "macro", "money"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--as-of-date",
            "2026-06-10",
            "--macro-catalog",
            str(catalog_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_candidates"] == 1
    assert payload["batches"][0]["codes"] == ["DR007"]
