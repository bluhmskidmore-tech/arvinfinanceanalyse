"""Run one bounded, read-only stock-supplier access check.

This diagnostic never reads or writes business databases, caches, governance
streams, or workflow receipts. Its output is deliberately too small to be used
as evidence that the pretrade workflow is ready.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_OPERATIONS = frozenset({"trade_cal", "daily_basic"})
_TICKER_PATTERN = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")
_OUTPUT_FIELDS = ("state", "date", "count", "elapsed", "error_class")


class _RedirectRejected(RuntimeError):
    """The fixed supplier endpoint attempted an HTTP redirect."""


class _RepeatedHttpExchange(RuntimeError):
    """The bounded diagnostic attempted more than one HTTP exchange."""


class _InvalidSupplierPayload(RuntimeError):
    """The supplier returned an envelope that cannot be validated."""


class _ValidatedResponse:
    def __init__(self, response: object) -> None:
        self._response = response

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    def json(self) -> Mapping[str, object]:
        payload = self._response.json()
        if not isinstance(payload, Mapping):
            raise _InvalidSupplierPayload("supplier payload must be an object")
        code = payload.get("code")
        if isinstance(code, bool) or not isinstance(code, int):
            raise _InvalidSupplierPayload("supplier code must be an integer")
        if code != 0:
            return payload
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise _InvalidSupplierPayload("successful supplier payload needs data")
        fields = data.get("fields")
        items = data.get("items")
        if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
            raise _InvalidSupplierPayload("supplier fields must be text list")
        if not isinstance(items, list):
            raise _InvalidSupplierPayload("supplier items must be a list")
        if any(
            not isinstance(item, (list, tuple)) or len(item) != len(fields)
            for item in items
        ):
            raise _InvalidSupplierPayload("supplier row width does not match fields")
        return payload


@dataclass(frozen=True, slots=True)
class _CheckInput:
    operation: str
    as_of_date: str
    compact_date: str
    vendor_source_ip: str
    ticker: str | None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        add_help=False,
        allow_abbrev=False,
        exit_on_error=False,
    )
    parser.add_argument("--operation", default="trade_cal")
    parser.add_argument("--as-of-date")
    parser.add_argument("--vendor-source-ip")
    parser.add_argument("--ticker")
    return parser


def _parse_input(argv: Sequence[str] | None) -> _CheckInput | None:
    args, unknown = _parser().parse_known_args(argv)
    if unknown:
        return None
    operation = str(args.operation or "").strip()
    if operation not in _OPERATIONS:
        return None

    raw_date = str(args.as_of_date or "").strip()
    try:
        from datetime import date

        parsed_date = date.fromisoformat(raw_date)
    except ValueError:
        return None
    if raw_date != parsed_date.isoformat():
        return None

    raw_ip = str(args.vendor_source_ip or "").strip()
    if not raw_ip or raw_ip.lower() == "auto":
        return None
    try:
        parsed_ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return None
    if not isinstance(parsed_ip, ipaddress.IPv4Address) or str(parsed_ip) != raw_ip:
        return None
    if parsed_ip.is_loopback or parsed_ip.is_link_local or parsed_ip.is_multicast or parsed_ip.is_unspecified:
        return None

    ticker = str(args.ticker or "").strip() or None
    if operation == "daily_basic":
        if ticker is None or _TICKER_PATTERN.fullmatch(ticker) is None:
            return None
    elif ticker is not None:
        return None

    return _CheckInput(
        operation=operation,
        as_of_date=raw_date,
        compact_date=raw_date.replace("-", ""),
        vendor_source_ip=raw_ip,
        ticker=ticker,
    )


def _result(
    *,
    state: str,
    date_value: str | None,
    count: int | None,
    started_at: float,
    error_class: str | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "state": state,
        "date": date_value,
        "count": count,
        "elapsed": max(0, int(round((time.perf_counter() - started_at) * 1000))),
        "error_class": error_class,
    }
    assert tuple(result) == _OUTPUT_FIELDS
    return result


@contextmanager
def _single_http_exchange() -> Iterator[None]:
    """Disable redirects and ensure the existing client issues one POST at most."""
    import requests

    original_post = requests.post
    call_count = 0

    def bounded_post(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise _RepeatedHttpExchange("supplier access check permits one HTTP exchange")
        kwargs["allow_redirects"] = False
        kwargs["verify"] = True
        response = original_post(*args, **kwargs)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and 300 <= status_code < 400:
            raise _RedirectRejected("supplier endpoint redirect rejected")
        return _ValidatedResponse(response)

    requests.post = bounded_post
    try:
        yield
    finally:
        requests.post = original_post


def _records(frame: object, expected_columns: tuple[str, str]) -> tuple[str, list[dict[str, object]]]:
    try:
        columns = tuple(str(column) for column in frame.columns)
        rows = frame.to_dict(orient="records")
    except (AttributeError, TypeError, ValueError):
        return "invalid_schema", []
    if columns != expected_columns or not isinstance(rows, list):
        return "invalid_schema", []
    if any(not isinstance(row, dict) for row in rows):
        return "invalid_schema", []
    return "valid", rows


def _validate_trade_calendar(frame: object, inputs: _CheckInput) -> tuple[str, int | None]:
    schema_state, rows = _records(frame, ("cal_date", "is_open"))
    if schema_state != "valid":
        return schema_state, None
    if not rows:
        return "empty", 0
    identities = [(row.get("cal_date"), row.get("is_open")) for row in rows]
    if any(identity in identities[:index] for index, identity in enumerate(identities)):
        return "duplicate_rows", None
    if len(rows) != 1:
        return "excess_rows", None
    row = rows[0]
    returned_date = row.get("cal_date")
    if returned_date is None:
        return "invalid_date", None
    if not isinstance(returned_date, str):
        return "invalid_schema", None
    if returned_date != inputs.compact_date:
        return "invalid_date", None
    is_open = row.get("is_open")
    if type(is_open) not in (str, int) or is_open not in ("0", "1", 0, 1):
        return "invalid_schema", None
    return "matched", 1


def _validate_daily_basic(frame: object, inputs: _CheckInput) -> tuple[str, int | None]:
    schema_state, rows = _records(frame, ("ts_code", "trade_date"))
    if schema_state != "valid":
        return schema_state, None
    if not rows:
        return "empty", 0
    identities = [(row.get("ts_code"), row.get("trade_date")) for row in rows]
    if any(identity in identities[:index] for index, identity in enumerate(identities)):
        return "duplicate_rows", None
    if len(rows) != 1:
        return "excess_rows", None
    row = rows[0]
    returned_date = row.get("trade_date")
    returned_ticker = row.get("ts_code")
    if returned_date is None:
        return "invalid_date", None
    if not isinstance(returned_date, str) or not isinstance(returned_ticker, str):
        return "invalid_schema", None
    if returned_date != inputs.compact_date:
        return "invalid_date", None
    if returned_ticker != inputs.ticker:
        return "invalid_identity", None
    return "matched", 1


def _contains_cause(exc: BaseException, expected_type: type[BaseException]) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, expected_type):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _failure_state(exc: Exception) -> tuple[str, str]:
    import requests

    if isinstance(exc, (requests.Timeout, requests.ConnectionError, requests.exceptions.SSLError)):
        if _contains_cause(exc, socket.gaierror):
            return "transport_failure", "DNSFailure"
        return "transport_failure", type(exc).__name__
    if isinstance(exc, (requests.exceptions.JSONDecodeError, _InvalidSupplierPayload)):
        return "invalid_schema", type(exc).__name__.lstrip("_")
    if isinstance(exc, (_RedirectRejected, _RepeatedHttpExchange, requests.HTTPError, RuntimeError)):
        return "supplier_failure", type(exc).__name__.lstrip("_")
    return "unknown_failure", type(exc).__name__


def _run_check(inputs: _CheckInput, started_at: float) -> dict[str, object]:
    from backend.app.governance.settings import get_settings
    from backend.app.tasks.choice_stock_materialize import (
        _TushareRestApi,
        resolve_tushare_token_with_settings_fallback,
    )
    from scripts.choice_stock_daily_refresh import (
        _vendor_source_network,
        resolve_vendor_source_ip,
    )

    try:
        resolved_source_ip = resolve_vendor_source_ip(inputs.vendor_source_ip)
    except (OSError, ValueError) as exc:
        return _result(
            state="binding_error",
            date_value=inputs.as_of_date,
            count=None,
            started_at=started_at,
            error_class=type(exc).__name__,
        )

    try:
        token = resolve_tushare_token_with_settings_fallback(get_settings())
    except Exception as exc:  # configuration errors must remain redacted
        return _result(
            state="credential_error",
            date_value=inputs.as_of_date,
            count=None,
            started_at=started_at,
            error_class=type(exc).__name__,
        )
    if not token:
        return _result(
            state="credential_error",
            date_value=inputs.as_of_date,
            count=None,
            started_at=started_at,
            error_class="MissingCredential",
        )

    client = _TushareRestApi(str(token))
    network_entered = False
    try:
        with _vendor_source_network(resolved_source_ip):
            network_entered = True
            with _single_http_exchange():
                if inputs.operation == "trade_cal":
                    frame: Any = client.query(
                        "trade_cal",
                        exchange="SSE",
                        start_date=inputs.compact_date,
                        end_date=inputs.compact_date,
                        fields="cal_date,is_open",
                    )
                    state, count = _validate_trade_calendar(frame, inputs)
                else:
                    assert inputs.ticker is not None
                    frame = client.query(
                        "daily_basic",
                        ts_code=inputs.ticker,
                        trade_date=inputs.compact_date,
                        fields="ts_code,trade_date",
                    )
                    state, count = _validate_daily_basic(frame, inputs)
    except Exception as exc:
        if not network_entered and isinstance(exc, (OSError, ValueError)):
            return _result(
                state="binding_error",
                date_value=inputs.as_of_date,
                count=None,
                started_at=started_at,
                error_class=type(exc).__name__,
            )
        state, error_class = _failure_state(exc)
        return _result(
            state=state,
            date_value=inputs.as_of_date,
            count=None,
            started_at=started_at,
            error_class=error_class,
        )

    return _result(
        state=state,
        date_value=inputs.as_of_date,
        count=count,
        started_at=started_at,
        error_class=None if state in {"matched", "empty"} else state,
    )


def main(argv: Sequence[str] | None = None) -> int:
    started_at = time.perf_counter()
    try:
        inputs = _parse_input(argv)
    except Exception as exc:
        output = _result(
            state="input_error",
            date_value=None,
            count=None,
            started_at=started_at,
            error_class=type(exc).__name__,
        )
    else:
        if inputs is None:
            output = _result(
                state="input_error",
                date_value=None,
                count=None,
                started_at=started_at,
                error_class="InvalidArguments",
            )
        else:
            try:
                output = _run_check(inputs, started_at)
            except Exception as exc:
                output = _result(
                    state="unknown_failure",
                    date_value=inputs.as_of_date,
                    count=None,
                    started_at=started_at,
                    error_class=type(exc).__name__,
                )
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0 if output["state"] in {"matched", "empty"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
