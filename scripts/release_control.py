from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.release_control import (  # noqa: E402
    ReleaseConflictError,
    ReleaseControlService,
    ReleaseGateBlockedError,
    ReleaseInputError,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_RUNTIME = 3


class CliInputError(ValueError):
    pass


class ReceiptArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliInputError(message)


def _build_service() -> ReleaseControlService:
    from backend.app.governance.settings import get_settings
    from backend.app.repositories.release_control_repo import ReleaseControlRepository

    settings = get_settings()
    repo = ReleaseControlRepository(sql_dsn=settings.postgres_dsn)
    return ReleaseControlService(repo=repo)


def _read_json(path: str | Path, *, expected: str = "object") -> Any:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CliInputError(
            "input file is missing, unreadable, or invalid JSON"
        ) from exc
    if expected == "object" and not isinstance(value, Mapping):
        raise CliInputError("input JSON must be an object")
    return value


def _receipt_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json", exclude_none=True)
    elif isinstance(value, Mapping):
        dumped = dict(value)
    else:
        raise RuntimeError("release control returned an unsupported receipt")
    if not isinstance(dumped, dict):
        raise RuntimeError("release control returned a non-object receipt")
    return dumped


def _success_receipt(value: Any) -> dict[str, Any]:
    receipt = _receipt_dict(value)
    receipt["exit_code"] = EXIT_SUCCESS
    return receipt


def _write_receipt_file(
    receipt_file: str | Path | None,
    receipt: Mapping[str, Any],
) -> bool:
    if receipt_file is None:
        return True
    try:
        Path(receipt_file).write_text(
            json.dumps(
                dict(receipt),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError):
        return False
    return True


def _attach_receipt_file_status(
    receipt: dict[str, Any],
    *,
    receipt_file: str | Path | None,
) -> dict[str, Any]:
    if _write_receipt_file(receipt_file, receipt):
        return receipt

    result = dict(receipt)
    existing_details = result.get("details")
    details = dict(existing_details) if isinstance(existing_details, Mapping) else {}
    details["receipt_file_status"] = "write_failed"
    result.update(
        {
            "action_applied": True,
            "error_code": "receipt_file_write_failed",
            "details": details,
            "exit_code": EXIT_RUNTIME,
        }
    )
    return result


def run_prepare(
    *,
    release_id: str,
    manifest_file: str | Path,
    freeze: bool = False,
    idempotency_key: str | None = None,
    service: ReleaseControlService | None = None,
) -> dict[str, Any]:
    document = _read_json(manifest_file)
    if "payload" in document:
        embedded_release_id = str(document.get("release_id") or release_id)
        if embedded_release_id != release_id:
            raise CliInputError("manifest release_id does not match --release-id")
        payload = document["payload"]
    else:
        payload = document
    if not isinstance(payload, Mapping):
        raise CliInputError("manifest payload must be an object")
    receipt = (service or _build_service()).prepare_release(
        release_id=release_id,
        payload=payload,
        freeze=freeze,
        idempotency_key=idempotency_key,
    )
    return _success_receipt(receipt)


def run_validate(
    *,
    release_id: str,
    validation_file: str | Path | None = None,
    idempotency_key: str | None = None,
    service: ReleaseControlService | None = None,
) -> dict[str, Any]:
    receipts = _read_json(validation_file) if validation_file else {}
    receipt = (service or _build_service()).record_validation(
        release_id,
        receipts,
        idempotency_key=idempotency_key,
    )
    return _success_receipt(receipt)


def run_approve_record(
    *,
    release_id: str,
    manifest_digest: str | None = None,
    approval_file: str | Path,
    idempotency_key: str | None = None,
    service: ReleaseControlService | None = None,
) -> dict[str, Any]:
    document = _read_json(approval_file)
    raw_authority_receipt = document.get("authority_receipt", document)
    if not isinstance(raw_authority_receipt, Mapping):
        raise CliInputError("approval file must contain an authority_receipt object")
    digest = str(
        manifest_digest or raw_authority_receipt.get("manifest_sha256") or ""
    ).strip()
    if not digest:
        raise CliInputError("manifest_digest is required for approval")
    receipt = (service or _build_service()).record_approval(
        release_id=release_id,
        manifest_digest=digest,
        authority_receipt=raw_authority_receipt,
        idempotency_key=idempotency_key,
    )
    return _success_receipt(receipt)


def _activation_document(
    plan_file: str | Path,
) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    document = _read_json(plan_file)
    raw_scopes = document.get("scopes")
    if not isinstance(raw_scopes, Sequence) or isinstance(
        raw_scopes,
        (str, bytes, bytearray),
    ):
        raise CliInputError("activation plan must contain a scopes array")
    if not all(isinstance(item, Mapping) for item in raw_scopes):
        raise CliInputError("every activation scope must be an object")
    return list(raw_scopes), dict(document)


def run_promote(
    *,
    release_id: str,
    plan_file: str | Path | None = None,
    scopes: Sequence[Mapping[str, Any]] | None = None,
    idempotency_key: str,
    target_environment: str | None = None,
    manifest_digest: str | None = None,
    receipt_file: str | Path | None = None,
    service: ReleaseControlService | None = None,
) -> dict[str, Any]:
    if plan_file is not None and scopes is not None:
        raise CliInputError("pass either plan_file or scopes, not both")
    if plan_file is not None:
        resolved_scopes, document = _activation_document(plan_file)
    elif scopes is not None:
        resolved_scopes, document = list(scopes), {}
    else:
        raise CliInputError("whole-bundle scopes are required")
    receipt = (service or _build_service()).promote_release_bundle(
        release_id=release_id,
        scopes=resolved_scopes,
        idempotency_key=idempotency_key,
        target_environment=(target_environment or document.get("target_environment")),
        manifest_digest=manifest_digest or document.get("manifest_digest"),
    )
    result = _success_receipt(receipt)
    return _attach_receipt_file_status(result, receipt_file=receipt_file)


def run_rollback(
    *,
    to_release_id: str,
    plan_file: str | Path | None = None,
    scopes: Sequence[Mapping[str, Any]] | None = None,
    idempotency_key: str,
    target_environment: str | None = None,
    manifest_digest: str | None = None,
    reason: str,
    mode: str,
    receipt_file: str | Path | None = None,
    service: ReleaseControlService | None = None,
) -> dict[str, Any]:
    if plan_file is not None and scopes is not None:
        raise CliInputError("pass either plan_file or scopes, not both")
    if plan_file is not None:
        resolved_scopes, document = _activation_document(plan_file)
    elif scopes is not None:
        resolved_scopes, document = list(scopes), {}
    else:
        raise CliInputError("whole-bundle scopes are required")
    receipt = (service or _build_service()).rollback_release_bundle(
        to_release_id=to_release_id,
        scopes=resolved_scopes,
        idempotency_key=idempotency_key,
        target_environment=(target_environment or document.get("target_environment")),
        manifest_digest=manifest_digest or document.get("manifest_digest"),
        reason=reason,
        mode=mode,
    )
    result = _success_receipt(receipt)
    return _attach_receipt_file_status(result, receipt_file=receipt_file)


def run_show(
    *,
    release_id: str,
    service: ReleaseControlService | None = None,
) -> dict[str, Any]:
    release = (service or _build_service()).show_release(release_id)
    return {
        "action": "show",
        "outcome": "applied",
        "release_id": release_id,
        "release": _receipt_dict(release),
        "exit_code": EXIT_SUCCESS,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = ReceiptArgumentParser(
        description="Internal whole-bundle release control CLI.",
    )
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=ReceiptArgumentParser,
    )

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--release-id", required=True)
    prepare.add_argument("--manifest-file", required=True)
    prepare.add_argument("--freeze", action="store_true", required=True)
    prepare.add_argument("--idempotency-key")

    validate = commands.add_parser("validate")
    validate.add_argument("--release-id", required=True)
    validate.add_argument("--validation-file", required=True)
    validate.add_argument("--idempotency-key")

    approve = commands.add_parser("approve-record")
    approve.add_argument("--release-id", required=True)
    approve.add_argument("--manifest-digest")
    approve.add_argument("--approval-file", required=True)
    approve.add_argument("--idempotency-key")

    promote = commands.add_parser("promote")
    promote.add_argument("--release-id", required=True)
    promote.add_argument("--plan-file", required=True)
    promote.add_argument("--idempotency-key", required=True)
    promote.add_argument("--target-environment")
    promote.add_argument("--manifest-digest")
    promote.add_argument("--receipt-file")

    rollback = commands.add_parser("rollback")
    rollback.add_argument("--to-release-id", required=True)
    rollback.add_argument("--plan-file", required=True)
    rollback.add_argument("--idempotency-key", required=True)
    rollback.add_argument("--target-environment")
    rollback.add_argument("--manifest-digest")
    rollback.add_argument("--reason", required=True)
    rollback.add_argument(
        "--mode",
        required=True,
        choices=("sealed_bundle_reactivate", "forward_rebuild"),
    )
    rollback.add_argument("--receipt-file")

    show = commands.add_parser("show")
    show.add_argument("--release-id", required=True)
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    values = vars(args).copy()
    command = values.pop("command")
    if command == "prepare":
        return run_prepare(**values)
    if command == "validate":
        return run_validate(**values)
    if command == "approve-record":
        return run_approve_record(**values)
    if command == "promote":
        plan_file = values.pop("plan_file")
        scopes, document = _activation_document(plan_file)
        call = {
            "release_id": values.pop("release_id"),
            "scopes": scopes,
            "idempotency_key": values.pop("idempotency_key"),
            "receipt_file": values.pop("receipt_file"),
        }
        target_environment = values.pop("target_environment") or document.get(
            "target_environment"
        )
        manifest_digest = values.pop("manifest_digest") or document.get(
            "manifest_digest"
        )
        if target_environment is not None:
            call["target_environment"] = target_environment
        if manifest_digest is not None:
            call["manifest_digest"] = manifest_digest
        return run_promote(**call)
    if command == "rollback":
        plan_file = values.pop("plan_file")
        scopes, document = _activation_document(plan_file)
        call = {
            "to_release_id": values.pop("to_release_id"),
            "reason": values.pop("reason"),
            "mode": values.pop("mode"),
            "scopes": scopes,
            "idempotency_key": values.pop("idempotency_key"),
            "receipt_file": values.pop("receipt_file"),
        }
        target_environment = values.pop("target_environment") or document.get(
            "target_environment"
        )
        manifest_digest = values.pop("manifest_digest") or document.get(
            "manifest_digest"
        )
        if target_environment is not None:
            call["target_environment"] = target_environment
        if manifest_digest is not None:
            call["manifest_digest"] = manifest_digest
        return run_rollback(**call)
    if command == "show":
        return run_show(**values)
    raise CliInputError("unknown release control command")


def _error_receipt(
    *,
    outcome: str,
    exit_code: int,
    error_code: str,
    reason_codes: Sequence[str] = (),
    approval_gate_receipt: Any | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "outcome": outcome,
        "error_code": error_code,
        "exit_code": exit_code,
    }
    if reason_codes:
        receipt["reason_codes"] = list(dict.fromkeys(reason_codes))
    if approval_gate_receipt is not None:
        receipt["approval_gate_receipt"] = _receipt_dict(approval_gate_receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(list(argv) if argv is not None else None)
        receipt = _dispatch(args)
    except (CliInputError, ReleaseInputError, ValueError) as exc:
        print(
            f"release_control: invalid input ({exc.__class__.__name__})",
            file=sys.stderr,
        )
        receipt = _error_receipt(
            outcome="invalid",
            exit_code=EXIT_INVALID,
            error_code="invalid_input",
        )
    except (ReleaseGateBlockedError, ReleaseConflictError) as exc:
        print(
            f"release_control: action blocked ({exc.__class__.__name__})",
            file=sys.stderr,
        )
        receipt = _error_receipt(
            outcome="conflict" if isinstance(exc, ReleaseConflictError) else "blocked",
            exit_code=EXIT_BLOCKED,
            error_code=(
                "release_conflict"
                if isinstance(exc, ReleaseConflictError)
                else "release_gate_blocked"
            ),
            reason_codes=(
                exc.reason_codes if isinstance(exc, ReleaseGateBlockedError) else ()
            ),
            approval_gate_receipt=(
                exc.approval_gate_receipt
                if isinstance(exc, ReleaseGateBlockedError)
                else None
            ),
        )
    except Exception:
        print("release_control: runtime error", file=sys.stderr)
        receipt = _error_receipt(
            outcome="error",
            exit_code=EXIT_RUNTIME,
            error_code="runtime_error",
        )

    if receipt.get("error_code") == "receipt_file_write_failed":
        print("release_control: receipt file write failed", file=sys.stderr)

    print(
        json.dumps(
            receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return int(receipt["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
