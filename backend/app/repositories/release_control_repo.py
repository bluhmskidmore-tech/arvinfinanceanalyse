from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import Table, create_engine, event, insert, select, text, update
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

# isort: split
from backend.app.models.base import Base
from backend.app.models.release_control import (
    ReleaseAlias,
    ReleaseManifest,
)
from backend.app.models.release_control import (
    ReleaseEvent as ReleaseEventRow,
)
from backend.app.schemas.release_approval import ApprovalGateReceipt
from backend.app.schemas.release_control import (
    ReleaseEvent as ReleaseEventContract,
)
from backend.app.schemas.release_control import (
    ReleaseManifest as ReleaseManifestContract,
)

DEFAULT_TARGET_ENVIRONMENT = "development"
DEFAULT_MANIFEST_KIND = "release_bundle"
PHYSICAL_BUNDLE_SCOPE = ("physical_bundle", "duckdb-main")
_PHYSICAL_PATH_KEYS = frozenset({"duckdb_path", "database_path", "physical_path"})

_SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
_JSON_OBJECT = dict[str, Any]
_FaultInjector = Callable[[str, Mapping[str, Any]], None]
_SqlRow = Mapping[str, Any] | RowMapping


class ReleaseControlError(RuntimeError):
    """Base error for durable release-control operations."""


class ReleaseControlDataError(ReleaseControlError):
    """Persisted or supplied release-control data violates the repository contract."""


class ManifestNotFoundError(ReleaseControlError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"release manifest does not exist: {release_id}")


class ManifestConflictError(ReleaseControlError):
    def __init__(self, release_id: str, *, expected_digest: str, actual_digest: str | None) -> None:
        self.release_id = release_id
        self.expected_digest = expected_digest
        self.actual_digest = actual_digest
        detail = actual_digest or "content digest is already bound to another release"
        super().__init__(f"immutable manifest conflict for {release_id}: expected {expected_digest}, found {detail}")


class ManifestDigestMismatchError(ReleaseControlError):
    def __init__(self, release_id: str, *, expected_digest: str, actual_digest: str) -> None:
        self.release_id = release_id
        self.expected_digest = expected_digest
        self.actual_digest = actual_digest
        super().__init__(
            f"manifest digest mismatch for {release_id}: expected {expected_digest}, found {actual_digest}"
        )


class IdempotencyConflictError(ReleaseControlError):
    def __init__(
        self,
        action: str,
        idempotency_key: str,
        *,
        target_environment: str | None = None,
        release_id: str | None = None,
    ) -> None:
        self.action = action
        self.idempotency_key = idempotency_key
        self.target_environment = target_environment
        self.release_id = release_id
        scope = (
            f" for {target_environment}/{release_id}"
            if target_environment is not None and release_id is not None
            else ""
        )
        super().__init__(
            f"idempotency key {idempotency_key!r} for action {action!r}{scope} was already used by another request"
        )


class AliasRevisionConflictError(ReleaseControlError):
    def __init__(
        self,
        *,
        target_environment: str,
        scope_kind: str,
        scope_key: str,
        expected_revision: int,
        actual_revision: int | None,
    ) -> None:
        self.target_environment = target_environment
        self.scope_kind = scope_kind
        self.scope_key = scope_key
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        actual = "missing" if actual_revision is None else str(actual_revision)
        super().__init__(
            "release alias revision conflict for "
            f"{target_environment}/{scope_kind}/{scope_key}: expected {expected_revision}, found {actual}"
        )


class AliasTargetConflictError(ReleaseControlError):
    def __init__(self, *, target_environment: str, scope_kind: str, scope_key: str, release_id: str) -> None:
        self.target_environment = target_environment
        self.scope_kind = scope_kind
        self.scope_key = scope_key
        self.release_id = release_id
        super().__init__(f"release {release_id} is already current for {target_environment}/{scope_kind}/{scope_key}")


class WholeBundleScopeError(ReleaseControlError):
    """The requested aliases are not the complete scope plan declared by the manifest."""


class ReleaseStateConflictError(ReleaseControlError):
    def __init__(self, release_id: str, *, action: str, actual_state: str) -> None:
        self.release_id = release_id
        self.action = action
        self.actual_state = actual_state
        super().__init__(f"release {release_id} cannot execute {action} from state {actual_state}")


class _RecordMapping(Mapping[str, Any]):
    """Small immutable records with both attribute and Mapping access."""

    def to_dict(self) -> dict[str, Any]:
        return {field.name: deepcopy(getattr(self, field.name)) for field in fields(self)}  # type: ignore[arg-type]

    def __getitem__(self, key: str) -> Any:
        if key not in {field.name for field in fields(self)}:  # type: ignore[arg-type]
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(field.name for field in fields(self))  # type: ignore[arg-type]

    def __len__(self) -> int:
        return len(fields(self))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class StoredManifest(_RecordMapping):
    release_id: str
    state: str
    target_environment: str
    manifest_kind: str
    content_sha256: str
    payload: _JSON_OBJECT
    created_at: datetime

    @property
    def manifest_digest(self) -> str:
        return self.content_sha256


@dataclass(frozen=True, slots=True)
class StoredEvent(_RecordMapping):
    event_id: str
    release_id: str
    action: str
    from_state: str
    to_state: str
    manifest_sha256: str
    target_environment: str
    scope_kind: str | None
    scope_key: str | None
    idempotency_key: str | None
    request_sha256: str | None
    event_payload: _JSON_OBJECT
    receipt: _JSON_OBJECT | None
    occurred_at: datetime

    @property
    def payload(self) -> _JSON_OBJECT:
        return deepcopy(self.event_payload)


@dataclass(frozen=True, slots=True)
class StoredAlias(_RecordMapping):
    target_environment: str
    scope_kind: str
    scope_key: str
    current_release_id: str
    previous_release_id: str | None
    revision: int
    alias_payload: _JSON_OBJECT
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ActivationReceipt(_RecordMapping):
    action: str
    release_id: str
    manifest_digest: str
    target_environment: str
    idempotency_key: str
    request_sha256: str
    status: str
    operation_payload: _JSON_OBJECT
    approval_gate_receipt: _JSON_OBJECT | None
    scopes: tuple[_JSON_OBJECT, ...]
    events: tuple[_JSON_OBJECT, ...]

    @property
    def alias(self) -> StoredAlias:
        """Compatibility view for callers that submit exactly one scope."""

        if len(self.scopes) != 1:
            raise AttributeError("batch activation receipt has more than one alias")
        scope = self.scopes[0]
        return StoredAlias(
            target_environment=str(scope["target_environment"]),
            scope_kind=str(scope["scope_kind"]),
            scope_key=str(scope["scope_key"]),
            current_release_id=str(scope["current_release_id"]),
            previous_release_id=_optional_text(scope.get("previous_release_id")),
            revision=int(scope["revision"]),
            alias_payload=_json_object(scope.get("alias_payload", {}), field_name="alias_payload"),
            updated_at=_coerce_datetime(scope["updated_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "release_id": self.release_id,
            "manifest_digest": self.manifest_digest,
            "target_environment": self.target_environment,
            "idempotency_key": self.idempotency_key,
            "request_sha256": self.request_sha256,
            "status": self.status,
            "operation_payload": deepcopy(self.operation_payload),
            "approval_gate_receipt": (
                deepcopy(self.approval_gate_receipt) if self.approval_gate_receipt is not None else None
            ),
            "scopes": [deepcopy(scope) for scope in self.scopes],
            "events": [deepcopy(event) for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class _ScopeExpectation:
    scope_kind: str
    scope_key: str
    expected_revision: int
    alias_payload: _JSON_OBJECT

    @property
    def identity(self) -> tuple[str, str]:
        return (self.scope_kind, self.scope_key)

    def request_payload(self) -> _JSON_OBJECT:
        return {
            "scope_kind": self.scope_kind,
            "scope_key": self.scope_key,
            "expected_revision": self.expected_revision,
            "alias_payload": deepcopy(self.alias_payload),
        }


class ReleaseControlRepository:
    """SQL authority for immutable manifests, append-only events, and CAS aliases.

    PostgreSQL schemas are migration-owned. SQLite is supported only as a test
    authority and creates exactly the three release-control tables on startup.
    """

    def __init__(
        self,
        sql_dsn: str = "",
        *,
        engine: Engine | None = None,
        sql_engine: Engine | None = None,
        default_target_environment: str = DEFAULT_TARGET_ENVIRONMENT,
        fault_injector: _FaultInjector | None = None,
    ) -> None:
        if engine is not None and sql_engine is not None:
            raise ValueError("pass only one of engine or sql_engine")
        injected_engine = engine or sql_engine
        normalized_dsn = _normalize_sqlalchemy_dsn(sql_dsn)
        if injected_engine is not None and normalized_dsn:
            raise ValueError("pass either sql_dsn or an Engine, not both")
        if injected_engine is None and not normalized_dsn:
            raise ValueError("sql_dsn or an Engine is required")

        self.sql_dsn = normalized_dsn
        self.default_target_environment = _required_text(
            default_target_environment,
            field_name="default_target_environment",
        )
        self._fault_injector = fault_injector
        self._owns_engine = injected_engine is None
        if injected_engine is not None:
            self.engine = injected_engine
        elif normalized_dsn.startswith("postgresql+"):
            self.engine = create_engine(normalized_dsn, future=True, poolclass=NullPool)
        else:
            self.engine = create_engine(normalized_dsn, future=True)
        self._sql_engine = self.engine

        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
            with self.engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(
                self.engine,
                tables=[
                    cast(Table, ReleaseManifest.__table__),
                    cast(Table, ReleaseEventRow.__table__),
                    cast(Table, ReleaseAlias.__table__),
                ],
            )

    def close(self) -> None:
        if self._owns_engine:
            self.engine.dispose()

    def create_manifest(
        self,
        *,
        release_id: str,
        payload: Mapping[str, Any] | Any,
        state: str = "candidate",
        target_environment: str | None = None,
        manifest_kind: str = DEFAULT_MANIFEST_KIND,
        created_at: datetime | None = None,
    ) -> StoredManifest:
        release_id = _required_text(release_id, field_name="release_id")
        state = _required_text(state, field_name="state")
        try:
            contract = ReleaseManifestContract.model_validate({
                "release_id": release_id,
                "state": state,
                "payload": payload,
            })
        except ValidationError as exc:
            raise ReleaseControlDataError(f"invalid release manifest: {exc}") from exc
        normalized_payload = contract.payload.canonical_payload()
        payload_json = canonical_json(normalized_payload)
        digest = str(contract.content_sha256)
        environment = contract.target_environment
        if (
            target_environment is not None
            and _required_text(
                target_environment,
                field_name="target_environment",
            )
            != environment
        ):
            raise ReleaseControlDataError("target_environment must match the immutable manifest payload")
        manifest_kind = _required_text(manifest_kind, field_name="manifest_kind")
        created_at = _coerce_datetime(created_at or datetime.now(UTC))

        try:
            with self.engine.begin() as connection:
                existing = self._get_manifest_row(connection, release_id)
                if existing is not None:
                    return self._replay_or_raise_manifest(existing, digest)
                connection.execute(
                    insert(cast(Table, ReleaseManifest.__table__)).values(
                        release_id=release_id,
                        target_environment=environment,
                        manifest_kind=manifest_kind,
                        content_sha256=digest,
                        payload_json=payload_json,
                        created_at=created_at,
                    )
                )
        except IntegrityError:
            # A concurrent writer can win the release-id or content-digest key.
            # Re-read after rollback so an exact release-id replay still succeeds.
            with self.engine.connect() as connection:
                existing = self._get_manifest_row(connection, release_id)
            if existing is not None:
                return self._replay_or_raise_manifest(existing, digest)
            raise ManifestConflictError(
                release_id,
                expected_digest=digest,
                actual_digest=None,
            )

        return StoredManifest(
            release_id=release_id,
            state=state,
            target_environment=environment,
            manifest_kind=manifest_kind,
            content_sha256=digest,
            payload=deepcopy(normalized_payload),
            created_at=created_at,
        )

    def get_manifest(self, release_id: str) -> StoredManifest | None:
        release_id = _required_text(release_id, field_name="release_id")
        with self.engine.connect() as connection:
            row = self._get_manifest_row(connection, release_id)
            if row is None:
                return None
            state = self._current_release_state(connection, release_id)
            return self._manifest_from_row(row, state=state)

    def append_event(
        self,
        *,
        release_id: str,
        action: str,
        from_state: str | None = None,
        to_state: str | None = None,
        manifest_sha256: str | None = None,
        manifest_digest: str | None = None,
        target_environment: str | None = None,
        scope_kind: str | None = None,
        scope_key: str | None = None,
        event_payload: Mapping[str, Any] | Any | None = None,
        payload: Mapping[str, Any] | Any | None = None,
        idempotency_key: str | None = None,
        request_sha256: str | None = None,
        receipt: Mapping[str, Any] | Any | None = None,
        event_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> StoredEvent:
        release_id = _required_text(release_id, field_name="release_id")
        action = _required_text(action, field_name="action")
        if action not in {"prepare", "validate", "approve-record"}:
            raise ReleaseControlDataError("activation events must be written by activate_release, not append_event")
        if event_payload is not None and payload is not None:
            raise ValueError("pass only one of event_payload or payload")
        normalized_payload = _json_object(
            event_payload if event_payload is not None else payload or {},
            field_name="event_payload",
        )
        normalized_receipt = _json_object(receipt, field_name="receipt") if receipt is not None else None
        idempotency_key = _optional_text(idempotency_key)
        resolved_environment: str | None = None
        normalized_request_sha: str | None = None

        try:
            with self.engine.begin() as connection:
                manifest_row = self._require_manifest_row(connection, release_id)
                expected_digest = _normalize_sha256(
                    manifest_sha256 or manifest_digest or str(manifest_row["content_sha256"]),
                    field_name="manifest_sha256",
                )
                self._assert_manifest_digest(manifest_row, expected_digest)
                resolved_environment = _required_text(
                    target_environment or manifest_row["target_environment"],
                    field_name="target_environment",
                )
                manifest_environment = str(manifest_row["target_environment"])
                if resolved_environment != manifest_environment:
                    raise ReleaseControlDataError(
                        f"manifest environment is {manifest_environment!r}, not {resolved_environment!r}"
                    )
                self._lock_release_state(
                    connection,
                    target_environment=resolved_environment,
                    release_id=release_id,
                )
                normalized_request_sha = self._event_request_sha256(
                    request_sha256=request_sha256,
                    release_id=release_id,
                    action=action,
                    from_state=_optional_text(from_state),
                    to_state=_optional_text(to_state),
                    manifest_sha256=expected_digest,
                    target_environment=resolved_environment,
                    scope_kind=scope_kind,
                    scope_key=scope_key,
                    event_payload=normalized_payload,
                    receipt=normalized_receipt,
                    idempotency_key=idempotency_key,
                )
                if idempotency_key is not None:
                    self._lock_idempotency_key(
                        connection,
                        action=action,
                        target_environment=resolved_environment,
                        release_id=release_id,
                        idempotency_key=idempotency_key,
                    )
                    replay = self._find_idempotent_event(
                        connection,
                        action=action,
                        target_environment=resolved_environment,
                        release_id=release_id,
                        idempotency_key=idempotency_key,
                    )
                    if replay is not None:
                        self._assert_same_idempotent_event(
                            replay,
                            action=action,
                            idempotency_key=idempotency_key,
                            request_sha256=normalized_request_sha,
                            from_state=_optional_text(from_state),
                            to_state=_optional_text(to_state),
                            manifest_sha256=expected_digest,
                            scope_kind=_optional_text(scope_kind),
                            scope_key=_optional_text(scope_key),
                            event_payload=normalized_payload,
                            receipt=normalized_receipt,
                        )
                        return self._event_from_row(replay)

                contract = self._validate_event_contract(
                    release_id=release_id,
                    action=action,
                    from_state=_optional_text(from_state),
                    to_state=_optional_text(to_state),
                    manifest_sha256=expected_digest,
                    event_payload=normalized_payload,
                    idempotency_key=idempotency_key,
                )
                if action == "approve-record":
                    manifest_payload = _load_json_object(
                        manifest_row["payload_json"],
                        field_name="release_manifest.payload_json",
                    )
                    expected_registry_sha = _normalize_sha256(
                        manifest_payload.get("approval_registry_sha256"),
                        field_name="release manifest approval_registry_sha256",
                    )
                    authority_payload = _json_object(
                        contract.event_payload.get("authority_receipt"),
                        field_name="authority_receipt",
                    )
                    gate_payload = _json_object(
                        contract.event_payload.get("approval_gate_receipt"),
                        field_name="approval_gate_receipt",
                    )
                    if (
                        _normalize_sha256(
                            authority_payload.get("registry_sha256"),
                            field_name="authority receipt registry_sha256",
                        )
                        != expected_registry_sha
                        or _normalize_sha256(
                            gate_payload.get("registry_sha256"),
                            field_name="approval gate registry_sha256",
                        )
                        != expected_registry_sha
                    ):
                        raise ReleaseControlDataError("approval receipts do not bind the frozen manifest registry")
                current_state = self._current_release_state(connection, release_id)
                if action == "prepare" and not self._release_has_events(
                    connection,
                    release_id,
                ):
                    current_state = "draft"
                if contract.from_state != current_state:
                    raise ReleaseStateConflictError(
                        release_id,
                        action=action,
                        actual_state=current_state,
                    )
                return self._insert_event(
                    connection,
                    event_id=event_id or _new_event_id(),
                    release_id=release_id,
                    action=action,
                    from_state=str(contract.from_state),
                    to_state=str(contract.to_state),
                    manifest_sha256=expected_digest,
                    target_environment=resolved_environment,
                    scope_kind=_optional_text(scope_kind),
                    scope_key=_optional_text(scope_key),
                    idempotency_key=idempotency_key,
                    request_sha256=normalized_request_sha if idempotency_key else _optional_sha256(request_sha256),
                    event_payload=normalized_payload,
                    receipt=normalized_receipt,
                    occurred_at=_coerce_datetime(occurred_at or datetime.now(UTC)),
                )
        except IntegrityError:
            if idempotency_key is None or resolved_environment is None or normalized_request_sha is None:
                raise
            with self.engine.connect() as connection:
                replay = self._find_idempotent_event(
                    connection,
                    action=action,
                    target_environment=resolved_environment,
                    release_id=release_id,
                    idempotency_key=idempotency_key,
                )
            if replay is None:
                raise
            self._assert_same_idempotent_event(
                replay,
                action=action,
                idempotency_key=idempotency_key,
                request_sha256=normalized_request_sha,
                from_state=_optional_text(from_state),
                to_state=_optional_text(to_state),
                manifest_sha256=expected_digest,
                scope_kind=_optional_text(scope_kind),
                scope_key=_optional_text(scope_key),
                event_payload=normalized_payload,
                receipt=normalized_receipt,
            )
            return self._event_from_row(replay)

    def list_events(
        self,
        *,
        release_id: str | None = None,
        action: str | None = None,
        target_environment: str | None = None,
        scope_kind: str | None = None,
        scope_key: str | None = None,
    ) -> list[StoredEvent]:
        statement = select(ReleaseEventRow.__table__)
        if release_id is not None:
            statement = statement.where(
                ReleaseEventRow.__table__.c.release_id == _required_text(release_id, field_name="release_id")
            )
        if action is not None:
            statement = statement.where(
                ReleaseEventRow.__table__.c.action == _required_text(action, field_name="action")
            )
        if target_environment is not None:
            statement = statement.where(
                ReleaseEventRow.__table__.c.target_environment
                == _required_text(target_environment, field_name="target_environment")
            )
        if scope_kind is not None:
            statement = statement.where(
                ReleaseEventRow.__table__.c.scope_kind == _required_text(scope_kind, field_name="scope_kind")
            )
        if scope_key is not None:
            statement = statement.where(
                ReleaseEventRow.__table__.c.scope_key == _required_text(scope_key, field_name="scope_key")
            )
        statement = statement.order_by(ReleaseEventRow.__table__.c.row_id.asc())
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._event_from_row(row) for row in rows]

    def get_alias(
        self,
        scope_kind: str,
        scope_key: str,
        *,
        target_environment: str | None = None,
    ) -> StoredAlias | None:
        environment = _required_text(
            target_environment or self.default_target_environment,
            field_name="target_environment",
        )
        with self.engine.connect() as connection:
            row = self._get_alias_row(
                connection,
                target_environment=environment,
                scope_kind=_required_text(scope_kind, field_name="scope_kind"),
                scope_key=_required_text(scope_key, field_name="scope_key"),
            )
        return self._alias_from_row(row) if row is not None else None

    def list_aliases(self, *, target_environment: str | None = None) -> list[StoredAlias]:
        statement = select(ReleaseAlias.__table__)
        if target_environment is not None:
            statement = statement.where(
                ReleaseAlias.__table__.c.target_environment
                == _required_text(target_environment, field_name="target_environment")
            )
        statement = statement.order_by(
            ReleaseAlias.__table__.c.target_environment.asc(),
            ReleaseAlias.__table__.c.scope_kind.asc(),
            ReleaseAlias.__table__.c.scope_key.asc(),
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._alias_from_row(row) for row in rows]

    def activate_release(
        self,
        *,
        action: str,
        target_environment: str,
        release_id: str,
        manifest_digest: str,
        scope_expectations: Sequence[Mapping[str, Any] | Any],
        idempotency_key: str,
        request_sha256: str | None = None,
        target_transition: str = "current",
        replacement_transition: str | None = None,
        operation_payload: Mapping[str, Any] | Any | None = None,
        event_payload: Mapping[str, Any] | Any | None = None,
        activation_context: Mapping[str, Any] | Any | None = None,
        approval_gate_receipt: Mapping[str, Any] | ApprovalGateReceipt | None = None,
        fault_injector: _FaultInjector | None = None,
    ) -> ActivationReceipt:
        """Atomically activate every alias in a manifest scope plan.

        Missing aliases may only be initialized with ``expected_revision=0``.
        Existing aliases use a revision predicate. All alias writes, replacement
        events, and the idempotent command receipt share one ``Engine.begin``.
        """

        action = _required_text(action, field_name="action")
        if action not in {"promote", "rollback"}:
            raise ReleaseControlDataError("action must be promote or rollback")
        environment = _required_text(target_environment, field_name="target_environment")
        release_id = _required_text(release_id, field_name="release_id")
        manifest_digest = _normalize_sha256(manifest_digest, field_name="manifest_digest")
        idempotency_key = _required_text(idempotency_key, field_name="idempotency_key")
        target_transition = _required_text(target_transition, field_name="target_transition")
        replacement_transition = _required_text(
            replacement_transition or ("deprecated" if action == "promote" else "rolled_back"),
            field_name="replacement_transition",
        )
        expected_replacement_transition = "deprecated" if action == "promote" else "rolled_back"
        if replacement_transition != expected_replacement_transition or target_transition != "current":
            raise ReleaseControlDataError(
                f"{action} requires replacement_transition={expected_replacement_transition!r} "
                "and target_transition='current'"
            )
        supplied_operation_payloads = [
            value for value in (operation_payload, event_payload, activation_context) if value is not None
        ]
        if len(supplied_operation_payloads) > 1:
            raise ValueError("pass only one of operation_payload, event_payload, or activation_context")
        normalized_operation_payload = _json_object(
            supplied_operation_payloads[0] if supplied_operation_payloads else {},
            field_name="operation_payload",
        )
        normalized_approval_gate_receipt: _JSON_OBJECT | None = None
        if approval_gate_receipt is not None:
            try:
                parsed_approval_gate = ApprovalGateReceipt.model_validate(approval_gate_receipt)
            except ValidationError:
                raise ReleaseControlDataError("approval_gate_receipt must be a canonical gate receipt") from None
            if parsed_approval_gate.status != "passed":
                raise ReleaseControlDataError("approval_gate_receipt must record a passed gate")
            normalized_approval_gate_receipt = parsed_approval_gate.model_dump(mode="json")
        expectations = self._normalize_scope_expectations(scope_expectations)
        request_payload = {
            "action": action,
            "target_environment": environment,
            "release_id": release_id,
            "manifest_digest": manifest_digest,
            "target_transition": target_transition,
            "replacement_transition": replacement_transition,
            "operation_payload": deepcopy(normalized_operation_payload),
            "scope_expectations": [item.request_payload() for item in expectations],
        }
        computed_request_sha = canonical_sha256(request_payload)
        normalized_request_sha = (
            _normalize_sha256(request_sha256, field_name="request_sha256")
            if request_sha256 is not None
            else computed_request_sha
        )
        injector = fault_injector or self._fault_injector
        primary_event_action = "promote" if action == "promote" else "reactivate"

        try:
            with self.engine.begin() as connection:
                self._lock_target_environment(connection, environment)
                self._lock_release_state(
                    connection,
                    target_environment=environment,
                    release_id=release_id,
                )
                self._lock_idempotency_key(
                    connection,
                    action=primary_event_action,
                    target_environment=environment,
                    release_id=release_id,
                    idempotency_key=idempotency_key,
                )
                replay = self._find_idempotent_event(
                    connection,
                    action=primary_event_action,
                    target_environment=environment,
                    release_id=release_id,
                    idempotency_key=idempotency_key,
                )
                if replay is not None:
                    self._assert_activation_replay(
                        replay,
                        action=action,
                        idempotency_key=idempotency_key,
                        request_sha256=normalized_request_sha,
                        request_payload=request_payload,
                    )
                    return self._activation_receipt_from_event(replay)

                manifest_row = self._require_manifest_row(connection, release_id)
                self._assert_manifest_digest(manifest_row, manifest_digest)
                manifest_environment = str(manifest_row["target_environment"])
                if manifest_environment != environment:
                    raise ReleaseControlDataError(
                        f"manifest environment is {manifest_environment!r}, not {environment!r}"
                    )
                manifest_payload = _load_json_object(
                    manifest_row["payload_json"],
                    field_name="release_manifest.payload_json",
                )
                if normalized_approval_gate_receipt is not None:
                    if (
                        normalized_approval_gate_receipt["release_id"] != release_id
                        or normalized_approval_gate_receipt["manifest_sha256"] != manifest_digest
                        or normalized_approval_gate_receipt["registry_sha256"]
                        != _normalize_sha256(
                            manifest_payload.get("approval_registry_sha256"),
                            field_name="release manifest approval_registry_sha256",
                        )
                    ):
                        raise ReleaseControlDataError("approval_gate_receipt does not bind the activation manifest")
                self._assert_complete_scope_plan(manifest_payload, expectations)
                self._assert_live_scope_closure(
                    connection,
                    target_environment=environment,
                    expectations=expectations,
                )
                target_from_state = self._current_release_state(connection, release_id)
                allowed_target_states = (
                    {"approved"} if action == "promote" else {"approved", "deprecated", "rolled_back"}
                )
                if target_from_state not in allowed_target_states:
                    raise ReleaseStateConflictError(
                        release_id,
                        action=action,
                        actual_state=target_from_state,
                    )

                activated_at = datetime.now(UTC)
                scope_receipts: list[_JSON_OBJECT] = []
                replaced_scopes: dict[str, list[_JSON_OBJECT]] = {}
                for index, expectation in enumerate(expectations):
                    alias_row = self._get_alias_row(
                        connection,
                        target_environment=environment,
                        scope_kind=expectation.scope_kind,
                        scope_key=expectation.scope_key,
                        for_update=True,
                    )
                    if alias_row is None:
                        if expectation.expected_revision != 0:
                            raise AliasRevisionConflictError(
                                target_environment=environment,
                                scope_kind=expectation.scope_kind,
                                scope_key=expectation.scope_key,
                                expected_revision=expectation.expected_revision,
                                actual_revision=None,
                            )
                        previous_release_id = None
                        next_revision = 1
                        connection.execute(
                            insert(cast(Table, ReleaseAlias.__table__)).values(
                                target_environment=environment,
                                scope_kind=expectation.scope_kind,
                                scope_key=expectation.scope_key,
                                current_release_id=release_id,
                                previous_release_id=None,
                                revision=next_revision,
                                alias_payload_json=canonical_json(expectation.alias_payload),
                                updated_at=activated_at,
                            )
                        )
                    else:
                        actual_revision = int(alias_row["revision"])
                        if actual_revision != expectation.expected_revision:
                            raise AliasRevisionConflictError(
                                target_environment=environment,
                                scope_kind=expectation.scope_kind,
                                scope_key=expectation.scope_key,
                                expected_revision=expectation.expected_revision,
                                actual_revision=actual_revision,
                            )
                        previous_release_id = str(alias_row["current_release_id"])
                        if previous_release_id == release_id:
                            raise AliasTargetConflictError(
                                target_environment=environment,
                                scope_kind=expectation.scope_kind,
                                scope_key=expectation.scope_key,
                                release_id=release_id,
                            )
                        next_revision = actual_revision + 1
                        result = connection.execute(
                            update(cast(Table, ReleaseAlias.__table__))
                            .where(
                                ReleaseAlias.__table__.c.target_environment == environment,
                                ReleaseAlias.__table__.c.scope_kind == expectation.scope_kind,
                                ReleaseAlias.__table__.c.scope_key == expectation.scope_key,
                                ReleaseAlias.__table__.c.revision == expectation.expected_revision,
                            )
                            .values(
                                current_release_id=release_id,
                                previous_release_id=previous_release_id,
                                revision=next_revision,
                                alias_payload_json=canonical_json(expectation.alias_payload),
                                updated_at=activated_at,
                            )
                        )
                        if result.rowcount != 1:
                            raise AliasRevisionConflictError(
                                target_environment=environment,
                                scope_kind=expectation.scope_kind,
                                scope_key=expectation.scope_key,
                                expected_revision=expectation.expected_revision,
                                actual_revision=None,
                            )

                    scope_receipt = {
                        "target_environment": environment,
                        "scope_kind": expectation.scope_kind,
                        "scope_key": expectation.scope_key,
                        "previous_release_id": previous_release_id,
                        "current_release_id": release_id,
                        "previous_revision": expectation.expected_revision,
                        "revision": next_revision,
                        "alias_payload": deepcopy(expectation.alias_payload),
                        "updated_at": activated_at.isoformat(),
                    }
                    scope_receipts.append(scope_receipt)
                    if previous_release_id is not None:
                        replaced_scopes.setdefault(previous_release_id, []).append(
                            {
                                "scope_kind": expectation.scope_kind,
                                "scope_key": expectation.scope_key,
                                "revision": next_revision,
                            }
                        )
                    _invoke_fault(
                        injector,
                        "after_alias_cas",
                        {"index": index, "scope": deepcopy(scope_receipt)},
                    )

                _invoke_fault(
                    injector,
                    "before_events",
                    {"scopes": deepcopy(scope_receipts)},
                )
                outgoing_action = "supersede" if action == "promote" else "rollback"
                target_action = primary_event_action
                replacement_events: list[dict[str, Any]] = []
                for replaced_release_id, replaced_scope_list in sorted(replaced_scopes.items()):
                    self._lock_release_state(
                        connection,
                        target_environment=environment,
                        release_id=replaced_release_id,
                    )
                    replaced_manifest = self._require_manifest_row(connection, replaced_release_id)
                    replaced_from_state = self._current_release_state(
                        connection,
                        replaced_release_id,
                    )
                    if replaced_from_state != "current":
                        raise ReleaseStateConflictError(
                            replaced_release_id,
                            action=outgoing_action,
                            actual_state=replaced_from_state,
                        )
                    replacement_events.append(
                        {
                            "event_id": _new_event_id(),
                            "release_id": replaced_release_id,
                            "action": outgoing_action,
                            "from_state": replaced_from_state,
                            "to_state": replacement_transition,
                            "manifest_sha256": str(replaced_manifest["content_sha256"]),
                            "scopes": deepcopy(replaced_scope_list),
                        }
                    )

                target_event = {
                    "event_id": _new_event_id(),
                    "release_id": release_id,
                    "action": target_action,
                    "from_state": target_from_state,
                    "to_state": target_transition,
                }
                ordered_event_specs = [*replacement_events]
                ordered_event_specs.append(target_event)
                event_receipts = [
                    {
                        "event_id": str(item["event_id"]),
                        "release_id": str(item["release_id"]),
                        "action": str(item["action"]),
                        "from_state": str(item["from_state"]),
                        "to_state": str(item["to_state"]),
                    }
                    for item in ordered_event_specs
                ]
                receipt_payload = {
                    "action": action,
                    "release_id": release_id,
                    "manifest_digest": manifest_digest,
                    "target_environment": environment,
                    "idempotency_key": idempotency_key,
                    "request_sha256": normalized_request_sha,
                    "status": target_transition,
                    "operation_payload": deepcopy(normalized_operation_payload),
                    "approval_gate_receipt": deepcopy(normalized_approval_gate_receipt),
                    "scopes": deepcopy(scope_receipts),
                    "events": deepcopy(event_receipts),
                }
                _invoke_fault(
                    injector,
                    "before_receipt_event",
                    {"receipt": deepcopy(receipt_payload)},
                )

                for replacement_event in replacement_events:
                    replacement_payload = {
                        "activated_release_id": release_id,
                        "activation_action": action,
                        "operation_payload": deepcopy(normalized_operation_payload),
                        "scopes": deepcopy(replacement_event["scopes"]),
                    }
                    self._validate_event_contract(
                        release_id=str(replacement_event["release_id"]),
                        action=str(replacement_event["action"]),
                        from_state=str(replacement_event["from_state"]),
                        to_state=str(replacement_event["to_state"]),
                        manifest_sha256=str(replacement_event["manifest_sha256"]),
                        event_payload=replacement_payload,
                        idempotency_key=None,
                    )
                    stored_replacement = self._insert_event(
                        connection,
                        event_id=str(replacement_event["event_id"]),
                        release_id=str(replacement_event["release_id"]),
                        action=str(replacement_event["action"]),
                        from_state=str(replacement_event["from_state"]),
                        to_state=str(replacement_event["to_state"]),
                        manifest_sha256=str(replacement_event["manifest_sha256"]),
                        target_environment=environment,
                        scope_kind=None,
                        scope_key=None,
                        idempotency_key=None,
                        request_sha256=None,
                        event_payload=replacement_payload,
                        receipt=None,
                        occurred_at=activated_at,
                    )
                    _invoke_fault(
                        injector,
                        "after_replacement_event",
                        {"event": _event_receipt(stored_replacement)},
                    )

                target_payload = {
                    "request": deepcopy(request_payload),
                    "computed_request_sha256": computed_request_sha,
                    "operation_payload": deepcopy(normalized_operation_payload),
                }
                if normalized_approval_gate_receipt is not None:
                    target_payload["approval_gate_receipt"] = deepcopy(normalized_approval_gate_receipt)
                self._validate_event_contract(
                    release_id=release_id,
                    action=target_action,
                    from_state=target_from_state,
                    to_state=target_transition,
                    manifest_sha256=manifest_digest,
                    event_payload=target_payload,
                    idempotency_key=idempotency_key,
                )
                self._insert_event(
                    connection,
                    event_id=str(target_event["event_id"]),
                    release_id=release_id,
                    action=target_action,
                    from_state=target_from_state,
                    to_state=target_transition,
                    manifest_sha256=manifest_digest,
                    target_environment=environment,
                    scope_kind=None,
                    scope_key=None,
                    idempotency_key=idempotency_key,
                    request_sha256=normalized_request_sha,
                    event_payload=target_payload,
                    receipt=receipt_payload,
                    occurred_at=activated_at,
                )
        except IntegrityError:
            # A concurrent request may have committed the same idempotency key.
            # The failed transaction has rolled all alias writes back at this point.
            with self.engine.connect() as connection:
                replay = self._find_idempotent_event(
                    connection,
                    action=primary_event_action,
                    target_environment=environment,
                    release_id=release_id,
                    idempotency_key=idempotency_key,
                )
                if replay is None:
                    self._raise_alias_integrity_conflict(
                        connection,
                        target_environment=environment,
                        expectations=expectations,
                    )
                    raise
            self._assert_activation_replay(
                replay,
                action=action,
                idempotency_key=idempotency_key,
                request_sha256=normalized_request_sha,
                request_payload=request_payload,
            )
            return self._activation_receipt_from_event(replay)

        return _activation_receipt(receipt_payload)

    def promote_release_batch(self, **kwargs: Any) -> ActivationReceipt:
        return self.activate_release(action="promote", **kwargs)

    def rollback_release_batch(self, **kwargs: Any) -> ActivationReceipt:
        return self.activate_release(action="rollback", **kwargs)

    def promote_release_bundle(
        self,
        *,
        release_id: str,
        scopes: Sequence[Mapping[str, Any] | Any] | None = None,
        scope_expectations: Sequence[Mapping[str, Any] | Any] | None = None,
        idempotency_key: str,
        target_environment: str | None = None,
        manifest_digest: str | None = None,
        request_sha256: str | None = None,
        operation_payload: Mapping[str, Any] | Any | None = None,
        fault_injector: _FaultInjector | None = None,
    ) -> ActivationReceipt:
        return self._activate_manifest_bundle(
            action="promote",
            release_id=release_id,
            scopes=scopes,
            scope_expectations=scope_expectations,
            idempotency_key=idempotency_key,
            target_environment=target_environment,
            manifest_digest=manifest_digest,
            request_sha256=request_sha256,
            operation_payload=operation_payload,
            fault_injector=fault_injector,
        )

    def rollback_release_bundle(
        self,
        *,
        release_id: str,
        scopes: Sequence[Mapping[str, Any] | Any] | None = None,
        scope_expectations: Sequence[Mapping[str, Any] | Any] | None = None,
        idempotency_key: str,
        target_environment: str | None = None,
        manifest_digest: str | None = None,
        request_sha256: str | None = None,
        operation_payload: Mapping[str, Any] | Any | None = None,
        fault_injector: _FaultInjector | None = None,
    ) -> ActivationReceipt:
        return self._activate_manifest_bundle(
            action="rollback",
            release_id=release_id,
            scopes=scopes,
            scope_expectations=scope_expectations,
            idempotency_key=idempotency_key,
            target_environment=target_environment,
            manifest_digest=manifest_digest,
            request_sha256=request_sha256,
            operation_payload=operation_payload,
            fault_injector=fault_injector,
        )

    def _activate_manifest_bundle(
        self,
        *,
        action: str,
        release_id: str,
        scopes: Sequence[Mapping[str, Any] | Any] | None,
        scope_expectations: Sequence[Mapping[str, Any] | Any] | None,
        idempotency_key: str,
        target_environment: str | None,
        manifest_digest: str | None,
        request_sha256: str | None,
        operation_payload: Mapping[str, Any] | Any | None,
        fault_injector: _FaultInjector | None,
    ) -> ActivationReceipt:
        if scopes is not None and scope_expectations is not None:
            raise ValueError("pass only one of scopes or scope_expectations")
        expectations = scope_expectations if scope_expectations is not None else scopes
        if expectations is None:
            raise WholeBundleScopeError("scope expectations are required")
        manifest = self.get_manifest(release_id)
        if manifest is None:
            raise ManifestNotFoundError(release_id)
        return self.activate_release(
            action=action,
            target_environment=target_environment or manifest.target_environment,
            release_id=release_id,
            manifest_digest=manifest_digest or manifest.content_sha256,
            scope_expectations=expectations,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            operation_payload=operation_payload,
            fault_injector=fault_injector,
        )

    def _normalize_scope_expectations(
        self,
        expectations: Sequence[Mapping[str, Any] | Any],
    ) -> tuple[_ScopeExpectation, ...]:
        if not expectations:
            raise WholeBundleScopeError("scope_expectations must contain the complete release scope plan")
        normalized: list[_ScopeExpectation] = []
        identities: set[tuple[str, str]] = set()
        for raw in expectations:
            item = _mapping_or_model(raw, field_name="scope_expectation")
            scope_kind = _required_text(
                item.get("scope_kind") or item.get("kind"),
                field_name="scope_expectation.scope_kind",
            )
            scope_key = _required_text(
                item.get("scope_key") or item.get("key"),
                field_name="scope_expectation.scope_key",
            )
            identity = (scope_kind, scope_key)
            if identity in identities:
                raise WholeBundleScopeError(f"duplicate scope expectation: {scope_kind}/{scope_key}")
            identities.add(identity)
            alias_payload = _json_object(
                item.get("alias_payload") or {},
                field_name="scope_expectation.alias_payload",
            )
            self._validate_alias_payload(scope_kind, alias_payload)
            normalized.append(
                _ScopeExpectation(
                    scope_kind=scope_kind,
                    scope_key=scope_key,
                    expected_revision=_nonnegative_int(
                        item.get("expected_revision"),
                        field_name="scope_expectation.expected_revision",
                    ),
                    alias_payload=alias_payload,
                )
            )
        normalized.sort(key=lambda item: (_scope_sort_order(item.scope_kind), item.scope_key))
        return tuple(normalized)

    def _assert_complete_scope_plan(
        self,
        manifest_payload: Mapping[str, Any],
        expectations: Sequence[_ScopeExpectation],
    ) -> None:
        declared_bindings = _manifest_scope_bindings(manifest_payload)
        declared = set(declared_bindings)
        supplied = {item.identity for item in expectations}
        if declared and supplied != declared:
            missing = sorted(declared - supplied)
            unexpected = sorted(supplied - declared)
            raise WholeBundleScopeError(
                f"activation does not match the immutable manifest scope plan; missing={missing}, unexpected={unexpected}"
            )
        for item in expectations:
            if declared and item.alias_payload != declared_bindings[item.identity]:
                raise WholeBundleScopeError(
                    "activation alias payload differs from the immutable manifest for "
                    f"{item.scope_kind}/{item.scope_key}"
                )
        required_physical = PHYSICAL_BUNDLE_SCOPE in declared or not declared
        if required_physical and PHYSICAL_BUNDLE_SCOPE not in supplied:
            raise WholeBundleScopeError(
                "whole-bundle activation requires physical_bundle/duckdb-main in scope_expectations"
            )

    def _assert_live_scope_closure(
        self,
        connection: Connection,
        *,
        target_environment: str,
        expectations: Sequence[_ScopeExpectation],
    ) -> None:
        statement = select(
            ReleaseAlias.__table__.c.scope_kind,
            ReleaseAlias.__table__.c.scope_key,
        ).where(ReleaseAlias.__table__.c.target_environment == target_environment)
        if connection.dialect.name != "sqlite":
            statement = statement.with_for_update()
        rows = connection.execute(statement).all()
        live_identities = {(str(row[0]), str(row[1])) for row in rows}
        supplied_identities = {expectation.identity for expectation in expectations}
        omitted_live_scopes = sorted(live_identities - supplied_identities)
        if omitted_live_scopes:
            raise WholeBundleScopeError(
                f"activation manifest omits scopes already controlled in the target environment: {omitted_live_scopes}"
            )

    def _validate_alias_payload(self, scope_kind: str, alias_payload: Mapping[str, Any]) -> None:
        if scope_kind == "logical_lane" and _contains_physical_path_key(alias_payload):
            raise ReleaseControlDataError("logical_lane alias_payload cannot contain a physical database path")

    def _get_manifest_row(self, connection: Connection, release_id: str) -> _SqlRow | None:
        return (
            connection.execute(
                select(ReleaseManifest.__table__).where(ReleaseManifest.__table__.c.release_id == release_id)
            )
            .mappings()
            .first()
        )

    def _require_manifest_row(self, connection: Connection, release_id: str) -> _SqlRow:
        row = self._get_manifest_row(connection, release_id)
        if row is None:
            raise ManifestNotFoundError(release_id)
        return row

    def _replay_or_raise_manifest(
        self,
        row: _SqlRow,
        requested_digest: str,
    ) -> StoredManifest:
        stored_digest = str(row["content_sha256"])
        if stored_digest != requested_digest:
            raise ManifestConflictError(
                str(row["release_id"]),
                expected_digest=requested_digest,
                actual_digest=stored_digest,
            )
        return self._manifest_from_row(row, state="candidate")

    def _manifest_from_row(self, row: _SqlRow, *, state: str) -> StoredManifest:
        return StoredManifest(
            release_id=str(row["release_id"]),
            state=state,
            target_environment=str(row["target_environment"]),
            manifest_kind=str(row["manifest_kind"]),
            content_sha256=str(row["content_sha256"]),
            payload=_load_json_object(row["payload_json"], field_name="release_manifest.payload_json"),
            created_at=_coerce_datetime(row["created_at"]),
        )

    def _assert_manifest_digest(self, row: _SqlRow, expected_digest: str) -> None:
        actual_digest = str(row["content_sha256"])
        if actual_digest != expected_digest:
            raise ManifestDigestMismatchError(
                str(row["release_id"]),
                expected_digest=expected_digest,
                actual_digest=actual_digest,
            )

    def _current_release_state(self, connection: Connection, release_id: str) -> str:
        row = connection.execute(
            select(ReleaseEventRow.__table__.c.to_state)
            .where(ReleaseEventRow.__table__.c.release_id == release_id)
            .order_by(ReleaseEventRow.__table__.c.row_id.desc())
            .limit(1)
        ).first()
        return str(row[0]) if row is not None else "candidate"

    def _release_has_events(self, connection: Connection, release_id: str) -> bool:
        return (
            connection.execute(
                select(ReleaseEventRow.__table__.c.row_id)
                .where(ReleaseEventRow.__table__.c.release_id == release_id)
                .limit(1)
            ).first()
            is not None
        )

    def _insert_event(
        self,
        connection: Connection,
        *,
        event_id: str,
        release_id: str,
        action: str,
        from_state: str,
        to_state: str,
        manifest_sha256: str,
        target_environment: str,
        scope_kind: str | None,
        scope_key: str | None,
        idempotency_key: str | None,
        request_sha256: str | None,
        event_payload: Mapping[str, Any],
        receipt: Mapping[str, Any] | None,
        occurred_at: datetime,
    ) -> StoredEvent:
        payload_copy, payload_json = _canonical_json_object(event_payload, field_name="event_payload")
        receipt_copy: _JSON_OBJECT | None
        receipt_json: str | None
        if receipt is None:
            receipt_copy = None
            receipt_json = None
        else:
            receipt_copy, receipt_json = _canonical_json_object(receipt, field_name="receipt")
        values = {
            "event_id": _required_text(event_id, field_name="event_id"),
            "release_id": _required_text(release_id, field_name="release_id"),
            "action": _required_text(action, field_name="action"),
            "from_state": _required_text(from_state, field_name="from_state"),
            "to_state": _required_text(to_state, field_name="to_state"),
            "manifest_sha256": _normalize_sha256(manifest_sha256, field_name="manifest_sha256"),
            "target_environment": _required_text(
                target_environment,
                field_name="target_environment",
            ),
            "scope_kind": _optional_text(scope_kind),
            "scope_key": _optional_text(scope_key),
            "idempotency_key": _optional_text(idempotency_key),
            "request_sha256": _optional_sha256(request_sha256),
            "event_payload_json": payload_json,
            "receipt_json": receipt_json,
            "occurred_at": _coerce_datetime(occurred_at),
        }
        connection.execute(insert(cast(Table, ReleaseEventRow.__table__)).values(**values))
        return StoredEvent(
            event_id=str(values["event_id"]),
            release_id=str(values["release_id"]),
            action=str(values["action"]),
            from_state=str(values["from_state"]),
            to_state=str(values["to_state"]),
            manifest_sha256=str(values["manifest_sha256"]),
            target_environment=str(values["target_environment"]),
            scope_kind=_optional_text(values["scope_kind"]),
            scope_key=_optional_text(values["scope_key"]),
            idempotency_key=_optional_text(values["idempotency_key"]),
            request_sha256=_optional_sha256(values["request_sha256"]),
            event_payload=payload_copy,
            receipt=receipt_copy,
            occurred_at=_coerce_datetime(values["occurred_at"]),
        )

    def _find_idempotent_event(
        self,
        connection: Connection,
        *,
        action: str,
        target_environment: str,
        release_id: str,
        idempotency_key: str,
    ) -> _SqlRow | None:
        return (
            connection.execute(
                select(ReleaseEventRow.__table__).where(
                    ReleaseEventRow.__table__.c.action == action,
                    ReleaseEventRow.__table__.c.target_environment == target_environment,
                    ReleaseEventRow.__table__.c.release_id == release_id,
                    ReleaseEventRow.__table__.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .first()
        )

    def _assert_same_idempotent_request(
        self,
        row: _SqlRow,
        *,
        action: str,
        idempotency_key: str,
        request_sha256: str,
    ) -> None:
        if str(row.get("request_sha256") or "") != request_sha256:
            raise IdempotencyConflictError(
                action,
                idempotency_key,
                target_environment=str(row["target_environment"]),
                release_id=str(row["release_id"]),
            )

    def _assert_same_idempotent_event(
        self,
        row: _SqlRow,
        *,
        action: str,
        idempotency_key: str,
        request_sha256: str,
        from_state: str | None,
        to_state: str | None,
        manifest_sha256: str,
        scope_kind: str | None,
        scope_key: str | None,
        event_payload: Mapping[str, Any],
        receipt: Mapping[str, Any] | None,
    ) -> None:
        self._assert_same_idempotent_request(
            row,
            action=action,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
        )
        stored_payload = _load_json_object(
            row["event_payload_json"],
            field_name="release_event.event_payload_json",
        )
        stored_receipt = _optional_json_object(
            row.get("receipt_json"),
            field_name="release_event.receipt_json",
        )
        same_request = (
            str(row["from_state"]) == str(from_state or "")
            and str(row["to_state"]) == str(to_state or "")
            and str(row["manifest_sha256"]) == manifest_sha256
            and _optional_text(row.get("scope_kind")) == scope_kind
            and _optional_text(row.get("scope_key")) == scope_key
            and stored_payload == event_payload
            and stored_receipt == receipt
        )
        if not same_request:
            raise IdempotencyConflictError(
                action,
                idempotency_key,
                target_environment=str(row["target_environment"]),
                release_id=str(row["release_id"]),
            )

    def _validate_event_contract(
        self,
        *,
        release_id: str,
        action: str,
        from_state: str | None,
        to_state: str | None,
        manifest_sha256: str,
        event_payload: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> ReleaseEventContract:
        try:
            return ReleaseEventContract.model_validate({
                "release_id": release_id,
                "action": action,
                "from_state": from_state,
                "to_state": to_state,
                "manifest_digest": manifest_sha256,
                "event_payload": deepcopy(dict(event_payload)),
                "idempotency_key": idempotency_key,
            })
        except ValidationError as exc:
            raise ReleaseControlDataError(f"invalid release event: {exc}") from exc

    def _assert_activation_replay(
        self,
        row: _SqlRow,
        *,
        action: str,
        idempotency_key: str,
        request_sha256: str,
        request_payload: Mapping[str, Any],
    ) -> None:
        self._assert_same_idempotent_request(
            row,
            action=action,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
        )
        stored_payload = _load_json_object(
            row["event_payload_json"],
            field_name="release_event.event_payload_json",
        )
        if stored_payload.get("request") != request_payload:
            raise IdempotencyConflictError(
                action,
                idempotency_key,
                target_environment=str(row["target_environment"]),
                release_id=str(row["release_id"]),
            )

    def _activation_receipt_from_event(self, row: _SqlRow) -> ActivationReceipt:
        receipt = _optional_json_object(row["receipt_json"], field_name="release_event.receipt_json")
        if receipt is None:
            raise ReleaseControlDataError("idempotent activation event has no receipt")
        return _activation_receipt(receipt)

    def _event_request_sha256(
        self,
        *,
        request_sha256: str | None,
        release_id: str,
        action: str,
        from_state: str | None,
        to_state: str | None,
        manifest_sha256: str,
        target_environment: str,
        scope_kind: str | None,
        scope_key: str | None,
        event_payload: Mapping[str, Any],
        receipt: Mapping[str, Any] | None,
        idempotency_key: str | None,
    ) -> str:
        if request_sha256 is not None:
            return _normalize_sha256(request_sha256, field_name="request_sha256")
        return canonical_sha256(
            {
                "release_id": release_id,
                "action": action,
                "from_state": from_state,
                "to_state": to_state,
                "manifest_sha256": manifest_sha256,
                "target_environment": target_environment,
                "scope_kind": _optional_text(scope_kind),
                "scope_key": _optional_text(scope_key),
                "event_payload": deepcopy(dict(event_payload)),
                "receipt": deepcopy(dict(receipt)) if receipt is not None else None,
                "idempotency_key": idempotency_key,
            }
        )

    def _event_from_row(self, row: _SqlRow) -> StoredEvent:
        return StoredEvent(
            event_id=str(row["event_id"]),
            release_id=str(row["release_id"]),
            action=str(row["action"]),
            from_state=str(row["from_state"]),
            to_state=str(row["to_state"]),
            manifest_sha256=str(row["manifest_sha256"]),
            target_environment=str(row["target_environment"]),
            scope_kind=_optional_text(row.get("scope_kind")),
            scope_key=_optional_text(row.get("scope_key")),
            idempotency_key=_optional_text(row.get("idempotency_key")),
            request_sha256=_optional_text(row.get("request_sha256")),
            event_payload=_load_json_object(
                row["event_payload_json"],
                field_name="release_event.event_payload_json",
            ),
            receipt=_optional_json_object(
                row.get("receipt_json"),
                field_name="release_event.receipt_json",
            ),
            occurred_at=_coerce_datetime(row["occurred_at"]),
        )

    def _get_alias_row(
        self,
        connection: Connection,
        *,
        target_environment: str,
        scope_kind: str,
        scope_key: str,
        for_update: bool = False,
    ) -> _SqlRow | None:
        statement = select(ReleaseAlias.__table__).where(
            ReleaseAlias.__table__.c.target_environment == target_environment,
            ReleaseAlias.__table__.c.scope_kind == scope_kind,
            ReleaseAlias.__table__.c.scope_key == scope_key,
        )
        if for_update and connection.dialect.name != "sqlite":
            statement = statement.with_for_update()
        return connection.execute(statement).mappings().first()

    def _alias_from_row(self, row: _SqlRow) -> StoredAlias:
        return StoredAlias(
            target_environment=str(row["target_environment"]),
            scope_kind=str(row["scope_kind"]),
            scope_key=str(row["scope_key"]),
            current_release_id=str(row["current_release_id"]),
            previous_release_id=_optional_text(row.get("previous_release_id")),
            revision=int(row["revision"]),
            alias_payload=_load_json_object(
                row["alias_payload_json"],
                field_name="release_alias.alias_payload_json",
            ),
            updated_at=_coerce_datetime(row["updated_at"]),
        )

    def _lock_idempotency_key(
        self,
        connection: Connection,
        *,
        action: str,
        target_environment: str,
        release_id: str,
        idempotency_key: str,
    ) -> None:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {
                    "lock_key": (
                        f"release-control-idempotency:{action}:{target_environment}:{release_id}:{idempotency_key}"
                    )
                },
            )

    def _lock_target_environment(
        self,
        connection: Connection,
        target_environment: str,
    ) -> None:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"release-control-environment:{target_environment}"},
            )

    def _lock_release_state(
        self,
        connection: Connection,
        *,
        target_environment: str,
        release_id: str,
    ) -> None:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": (f"release-control-state:{target_environment}:{release_id}")},
            )

    def _raise_alias_integrity_conflict(
        self,
        connection: Connection,
        *,
        target_environment: str,
        expectations: Sequence[_ScopeExpectation],
    ) -> None:
        for expectation in expectations:
            row = self._get_alias_row(
                connection,
                target_environment=target_environment,
                scope_kind=expectation.scope_kind,
                scope_key=expectation.scope_key,
            )
            if row is None:
                continue
            actual_revision = int(row["revision"])
            if expectation.expected_revision == 0 or actual_revision != expectation.expected_revision:
                raise AliasRevisionConflictError(
                    target_environment=target_environment,
                    scope_kind=expectation.scope_kind,
                    scope_key=expectation.scope_key,
                    expected_revision=expectation.expected_revision,
                    actual_revision=actual_revision,
                )


def canonical_json(value: Any) -> str:
    normalized = _json_value(value, field_name="value")
    try:
        return json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ReleaseControlDataError(f"value must be canonical JSON: {exc}")


def canonical_sha256(value: Any) -> str:
    return _sha256_text(canonical_json(value))


def compute_activation_request_sha256(
    *,
    action: str,
    target_environment: str,
    release_id: str,
    manifest_digest: str,
    scope_expectations: Sequence[Mapping[str, Any] | Any],
    target_transition: str = "current",
    replacement_transition: str | None = None,
    operation_payload: Mapping[str, Any] | Any | None = None,
) -> str:
    action = _required_text(action, field_name="action")
    replacement_transition = replacement_transition or ("deprecated" if action == "promote" else "rolled_back")
    temporary = object.__new__(ReleaseControlRepository)
    normalized = ReleaseControlRepository._normalize_scope_expectations(temporary, scope_expectations)
    return canonical_sha256(
        {
            "action": action,
            "target_environment": _required_text(
                target_environment,
                field_name="target_environment",
            ),
            "release_id": _required_text(release_id, field_name="release_id"),
            "manifest_digest": _normalize_sha256(manifest_digest, field_name="manifest_digest"),
            "target_transition": _required_text(target_transition, field_name="target_transition"),
            "replacement_transition": _required_text(
                replacement_transition,
                field_name="replacement_transition",
            ),
            "operation_payload": _json_object(
                operation_payload or {},
                field_name="operation_payload",
            ),
            "scope_expectations": [item.request_payload() for item in normalized],
        }
    )


def _activation_receipt(value: Mapping[str, Any] | Any) -> ActivationReceipt:
    receipt = _json_object(value, field_name="activation_receipt")
    raw_scopes = receipt.get("scopes")
    raw_events = receipt.get("events")
    if not isinstance(raw_scopes, list) or not isinstance(raw_events, list):
        raise ReleaseControlDataError("activation receipt scopes and events must be JSON arrays")
    return ActivationReceipt(
        action=_required_text(receipt.get("action"), field_name="activation_receipt.action"),
        release_id=_required_text(
            receipt.get("release_id"),
            field_name="activation_receipt.release_id",
        ),
        manifest_digest=_normalize_sha256(
            receipt.get("manifest_digest"),
            field_name="activation_receipt.manifest_digest",
        ),
        target_environment=_required_text(
            receipt.get("target_environment"),
            field_name="activation_receipt.target_environment",
        ),
        idempotency_key=_required_text(
            receipt.get("idempotency_key"),
            field_name="activation_receipt.idempotency_key",
        ),
        request_sha256=_normalize_sha256(
            receipt.get("request_sha256"),
            field_name="activation_receipt.request_sha256",
        ),
        status=_required_text(receipt.get("status"), field_name="activation_receipt.status"),
        operation_payload=_json_object(
            receipt.get("operation_payload") or {},
            field_name="activation_receipt.operation_payload",
        ),
        approval_gate_receipt=(
            _json_object(
                receipt.get("approval_gate_receipt"),
                field_name="activation_receipt.approval_gate_receipt",
            )
            if receipt.get("approval_gate_receipt") is not None
            else None
        ),
        scopes=tuple(_json_object(item, field_name="activation_receipt.scope") for item in raw_scopes),
        events=tuple(_json_object(item, field_name="activation_receipt.event") for item in raw_events),
    )


def _event_receipt(event: StoredEvent) -> _JSON_OBJECT:
    return {
        "event_id": event.event_id,
        "release_id": event.release_id,
        "action": event.action,
        "from_state": event.from_state,
        "to_state": event.to_state,
    }


def _manifest_scope_identities(payload: Mapping[str, Any]) -> set[tuple[str, str]]:
    return set(_manifest_scope_bindings(payload))


def _manifest_scope_bindings(
    payload: Mapping[str, Any],
) -> dict[tuple[str, str], _JSON_OBJECT]:
    raw_scopes = payload.get("lanes") or payload.get("scopes") or payload.get("scope_bindings") or []
    if not isinstance(raw_scopes, list):
        raise ReleaseControlDataError("manifest scope plan must be a JSON array")
    bindings: dict[tuple[str, str], _JSON_OBJECT] = {}
    for raw in raw_scopes:
        if not isinstance(raw, Mapping):
            raise ReleaseControlDataError("manifest scope plan entries must be JSON objects")
        scope_kind = _optional_text(raw.get("scope_kind") or raw.get("kind"))
        scope_key = _optional_text(raw.get("scope_key") or raw.get("key"))
        if scope_kind is None or scope_key is None:
            continue
        identity = (scope_kind, scope_key)
        if identity in bindings:
            raise ReleaseControlDataError(f"manifest repeats scope {scope_kind}/{scope_key}")
        bindings[identity] = _json_object(
            raw.get("alias_payload") or {},
            field_name=f"manifest scope {scope_kind}/{scope_key} alias_payload",
        )
    return bindings


def _scope_sort_order(scope_kind: str) -> int:
    return 0 if scope_kind == "physical_bundle" else 1


def _contains_physical_path_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _PHYSICAL_PATH_KEYS or _contains_physical_path_key(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_physical_path_key(item) for item in value)
    return False


def _normalize_sqlalchemy_dsn(dsn: str) -> str:
    normalized = str(dsn or "").strip()
    if normalized.startswith("postgresql+psycopg://"):
        return normalized
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized[len("postgresql://") :]
    return normalized


def _canonical_json_object(value: Any, *, field_name: str) -> tuple[_JSON_OBJECT, str]:
    normalized = _json_object(value, field_name=field_name)
    serialized = canonical_json(normalized)
    return json.loads(serialized), serialized


def _json_object(value: Any, *, field_name: str) -> _JSON_OBJECT:
    normalized = _mapping_or_model(value, field_name=field_name)
    serialized = canonical_json(dict(normalized))
    loaded = json.loads(serialized)
    if not isinstance(loaded, dict):
        raise ReleaseControlDataError(f"{field_name} must be a JSON object")
    return loaded


def _json_value(value: Any, *, field_name: str) -> Any:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump(mode="json")
    return deepcopy(value)


def _mapping_or_model(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump(mode="json")
    if not isinstance(value, Mapping):
        raise ReleaseControlDataError(f"{field_name} must be a mapping or Pydantic model")
    return deepcopy(dict(value))


def _load_json_object(value: Any, *, field_name: str) -> _JSON_OBJECT:
    try:
        loaded = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise ReleaseControlDataError(f"{field_name} is not valid JSON: {exc}")
    if not isinstance(loaded, dict):
        raise ReleaseControlDataError(f"{field_name} must contain a JSON object")
    return deepcopy(loaded)


def _optional_json_object(value: Any, *, field_name: str) -> _JSON_OBJECT | None:
    if value is None:
        return None
    return _load_json_object(value, field_name=field_name)


def _required_text(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ReleaseControlDataError(f"{field_name} is required")
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _nonnegative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ReleaseControlDataError(f"{field_name} must be a nonnegative integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ReleaseControlDataError(f"{field_name} must be a nonnegative integer")
    if normalized < 0 or str(value).strip() != str(normalized):
        raise ReleaseControlDataError(f"{field_name} must be a nonnegative integer")
    return normalized


def _normalize_sha256(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip().upper()
    if not _SHA256_RE.fullmatch(normalized):
        raise ReleaseControlDataError(f"{field_name} must be a 64-character hexadecimal SHA-256")
    return normalized


def _optional_sha256(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return _normalize_sha256(value, field_name="request_sha256")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = str(value or "").strip()
    if not normalized:
        raise ReleaseControlDataError("datetime value is required")
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        raise ReleaseControlDataError(f"invalid datetime value: {normalized}")


def _new_event_id() -> str:
    return f"release-event-{uuid.uuid4()}"


def _invoke_fault(
    injector: _FaultInjector | None,
    stage: str,
    context: Mapping[str, Any],
) -> None:
    if injector is not None:
        injector(stage, deepcopy(dict(context)))


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
