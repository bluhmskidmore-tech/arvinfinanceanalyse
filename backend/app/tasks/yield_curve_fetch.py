"""A killable vendor-only process for bounded yield-curve preparation."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.schemas.yield_curve import YieldCurveSnapshot
from pydantic import TypeAdapter

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SNAPSHOT_ADAPTER = TypeAdapter(YieldCurveSnapshot)
_CLEANUP_TIMEOUT_SECONDS = 5.0


class CurveFetchTimeout(TimeoutError):
    """The shared preparation budget expired while obtaining a vendor curve."""


class CurveFetchProcessError(RuntimeError):
    """The process or response protocol failed before certifying vendor exhaustion."""


class CurveVendorWindowExhausted(RuntimeError):
    """Every vendor attempt in the requested backtrack window failed."""


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Terminate interpreter launchers and their children without unbounded waits."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_CLEANUP_TIMEOUT_SECONDS,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass
    # No stdout/stderr pipes are inherited by SDK grandchildren. Even if tree
    # termination fails, cleanup itself must not recreate an indefinite wait.
    if process.stdin is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
    try:
        process.wait(timeout=_CLEANUP_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _validate_snapshot(payload: object, *, curve_type: str, anchor_date: str, max_backtrack_days: int) -> YieldCurveSnapshot:
    try:
        snapshot = _SNAPSHOT_ADAPTER.validate_python(payload)
        snapshot_date = date.fromisoformat(snapshot.trade_date)
        anchor = date.fromisoformat(anchor_date)
        if snapshot.curve_type != curve_type:
            raise ValueError("Yield-curve vendor response has a different curve_type.")
        if snapshot.trade_date != snapshot_date.isoformat() or not anchor - timedelta(days=max_backtrack_days) <= snapshot_date <= anchor:
            raise ValueError("Yield-curve vendor response date is outside the allowed backtrack window.")
        if not snapshot.points or any(not value.strip() for value in (snapshot.vendor_name, snapshot.vendor_version, snapshot.source_version)):
            raise ValueError("Yield-curve vendor response is missing points or lineage.")
    except (ValueError, TypeError, AttributeError) as exc:
        raise CurveFetchProcessError(f"Invalid yield-curve vendor response: {exc}") from exc
    return snapshot


def fetch_curve_snapshot_with_timeout(
    *,
    curve_type: str,
    anchor_date: str,
    max_backtrack_days: int,
    timeout_seconds: float,
) -> YieldCurveSnapshot:
    anchor = date.fromisoformat(anchor_date)
    if not isinstance(max_backtrack_days, int) or isinstance(max_backtrack_days, bool) or max_backtrack_days < 0:
        raise ValueError("max_backtrack_days must be a non-negative integer.")
    if not math.isfinite(timeout_seconds):
        raise ValueError("timeout_seconds must be finite.")
    if timeout_seconds <= 0:
        raise CurveFetchTimeout("Yield-curve vendor preparation budget has expired.")
    request = {
        "curve_type": curve_type,
        "anchor_date": anchor.isoformat(),
        "max_backtrack_days": max_backtrack_days,
    }
    with TemporaryDirectory(prefix="moss-yield-curve-", ignore_cleanup_errors=True) as temporary_dir:
        result_path = Path(temporary_dir) / "result.json"
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "backend.app.tasks.yield_curve_fetch", "--result-path", str(result_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(_REPO_ROOT),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            raise CurveFetchProcessError("Could not start the yield-curve vendor process.") from exc
        try:
            process.communicate(input=json.dumps(request, ensure_ascii=False), timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            raise CurveFetchTimeout(
                f"Yield-curve vendor fetch timed out after {timeout_seconds:g}s "
                f"for {curve_type} on or before {anchor.isoformat()}."
            ) from exc
        except OSError as exc:
            _terminate_process_tree(process)
            raise CurveFetchProcessError("Yield-curve vendor process communication failed.") from exc
        except BaseException:
            _terminate_process_tree(process)
            raise
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CurveFetchProcessError("Yield-curve vendor process did not return a valid result file.") from exc
        if process.returncode != 0:
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict) and error.get("kind") == "vendor_window_exhausted" and process.returncode == 1:
                raise CurveVendorWindowExhausted(str(error.get("message") or "Yield-curve vendor window is exhausted."))
            raise CurveFetchProcessError(f"Yield-curve vendor process failed with exit code {process.returncode}.")
        return _validate_snapshot(
            payload, curve_type=curve_type, anchor_date=anchor.isoformat(), max_backtrack_days=max_backtrack_days,
        )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-path", required=True)
    result_path = Path(parser.parse_args().result_path)
    status = 1
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict) or set(request) != {"curve_type", "anchor_date", "max_backtrack_days"}:
            raise ValueError("Invalid yield-curve request fields.")
        if not isinstance(request["curve_type"], str) or not request["curve_type"].strip():
            raise ValueError("A curve_type is required.")
        if type(request["max_backtrack_days"]) is not int or request["max_backtrack_days"] < 0:
            raise ValueError("max_backtrack_days must be a non-negative integer.")
        date.fromisoformat(request["anchor_date"])
        from backend.app.repositories.akshare_adapter import VendorAdapter

        # Import the canonical class with the loop: running this file with -m
        # creates a distinct __main__ module from the task's imported module.
        from backend.app.tasks.yield_curve_materialize import (
            CurveVendorWindowExhausted as VendorWindowExhausted,
        )
        from backend.app.tasks.yield_curve_materialize import (
            _fetch_curve_snapshot_on_or_before,
        )

        adapter = VendorAdapter()
    except Exception as exc:  # noqa: BLE001 - Child bootstrap/import failures require a nonzero process_error receipt, never vendor fallback.
        payload = {"error": {"kind": "process_error", "type": type(exc).__name__, "message": str(exc)}}
    else:
        try:
            snapshot = _fetch_curve_snapshot_on_or_before(adapter=adapter, **request)
        except VendorWindowExhausted as exc:
            # Only completion of the existing full backtrack loop can authorize
            # the parent's established local-curve fallback.
            cause = exc.__cause__ or exc
            payload = {"error": {"kind": "vendor_window_exhausted", "type": type(cause).__name__, "message": str(exc)}}
        except Exception as exc:  # noqa: BLE001 -- serialize unexpected child failures without authorizing local-data fallback.
            payload = {"error": {"kind": "process_error", "type": type(exc).__name__, "message": str(exc)}}
        else:
            try:
                snapshot = _validate_snapshot(snapshot, **request)
            except CurveFetchProcessError as exc:
                payload = {"error": {"kind": "process_error", "type": type(exc).__name__, "message": str(exc)}}
            else:
                status = 0
                payload = _SNAPSHOT_ADAPTER.dump_python(snapshot, mode="json")
    # Native SDK stdout cannot corrupt this file. It is the only child write;
    # DuckDB, governance, and task publication stay in the parent process.
    with result_path.open("x", encoding="utf-8") as result_file:
        json.dump(payload, result_file, ensure_ascii=False)
    return status


if __name__ == "__main__":
    raise SystemExit(_main())
