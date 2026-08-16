from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.schemas.knowledge_index import (
    EntityNotesPayload,
    KnowledgeIndexPayload,
    KnowledgeNoteBinding,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.obsidian_vault import read_note_text, resolve_obsidian_vault_path

KNOWLEDGE_INDEX_RULE_VERSION = "rv_knowledge_index_v1"
KNOWLEDGE_INDEX_CACHE_VERSION = "cv_knowledge_index_v1"
KNOWLEDGE_INDEX_EMPTY_SOURCE_VERSION = "sv_knowledge_index_empty"

_MAX_SCAN_FILES = 500
_SUMMARY_MAX_CHARS = 500
_SKIP_DIR_NAMES = {".obsidian", ".trash", "templates"}


@dataclass(frozen=True)
class _PendingNoteRecord:
    note_path: Path
    text: str
    entities: list[str]
    binding_status: str
    note_id: str


def load_knowledge_index() -> KnowledgeIndexPayload:
    vault_path = resolve_obsidian_vault_path()
    if vault_path is None or not vault_path.exists():
        return KnowledgeIndexPayload(
            available=False,
            vault_path=None,
            status_note="obsidian-vault-not-found",
        )

    known_entity_ids = _known_entity_ids()
    notes: list[KnowledgeNoteBinding] = []
    unknown_bindings: dict[str, list[str]] = {}
    pending_records: list[_PendingNoteRecord] = []
    status_bits = ["obsidian-local"]

    scanned = 0
    for note_path in _iter_markdown_notes(vault_path):
        if scanned >= _MAX_SCAN_FILES:
            status_bits.append("scan-truncated")
            break
        scanned += 1
        text = read_note_text(note_path)
        entities, binding_status = _parse_frontmatter(text)
        if not entities:
            continue
        pending_records.append(
            _PendingNoteRecord(
                note_path=note_path,
                text=text,
                entities=entities,
                binding_status=binding_status,
                note_id=_note_id_for_path(note_path, vault_path),
            )
        )

    for record in pending_records:
        note_id = record.note_id
        warnings: list[str] = []
        if "```" in record.text:
            warnings.append("contains-code-block")
        if known_entity_ids is None:
            warnings.append("ontology-index-unavailable")
        else:
            unknown = [
                entity_id for entity_id in record.entities if entity_id not in known_entity_ids
            ]
            if unknown:
                unknown_bindings[note_id] = unknown
                warnings.extend(f"unknown-entity:{entity_id}" for entity_id in unknown)

        notes.append(
            KnowledgeNoteBinding(
                note_id=note_id,
                title=_extract_title(record.text, fallback=record.note_path.stem),
                summary=_extract_summary(record.text),
                source_path=str(record.note_path),
                entities=record.entities,
                binding_status=record.binding_status,
                warnings=warnings,
            )
        )

    return KnowledgeIndexPayload(
        available=bool(notes),
        vault_path=str(vault_path),
        status_note="; ".join(status_bits),
        notes=notes,
        unknown_bindings=unknown_bindings,
    )


def entity_notes_envelope(entity_id: str) -> dict[str, object]:
    index = load_knowledge_index()
    notes = [note for note in index.notes if entity_id in note.entities]
    payload = EntityNotesPayload(
        entity_id=entity_id,
        available=bool(notes),
        vault_path=index.vault_path,
        status_note=index.status_note,
        notes=notes,
    )
    note_versions = [
        f"{note.source_path}:{Path(note.source_path).stat().st_mtime_ns}"
        for note in notes
        if Path(note.source_path).exists()
    ]
    warnings = [warning for note in notes for warning in note.warnings]
    quality_flag = "ok" if notes and not warnings else "warning"
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_knowledge_entity_{_slugify(entity_id)}",
        result_kind="knowledge.entity_notes",
        cache_version=KNOWLEDGE_INDEX_CACHE_VERSION,
        source_version=_build_source_version(note_versions),
        rule_version=KNOWLEDGE_INDEX_RULE_VERSION,
        quality_flag=quality_flag,
        evidence_rows=len(notes),
        filters_applied={"entity_id": entity_id},
        result_payload=payload.model_dump(mode="json"),
    )


def knowledge_summaries_for_entities(
    entity_ids: list[str],
    *,
    max_notes_per_entity: int = 2,
    max_summary_chars: int = 200,
) -> list[str]:
    try:
        index = load_knowledge_index()
    except Exception:
        return []
    if not index.available:
        return []
    if any("ontology-index-unavailable" in note.warnings for note in index.notes):
        return []

    summaries: list[str] = []
    for entity_id in entity_ids:
        matched = sorted(
            (
                note
                for note in index.notes
                if entity_id in note.entities and not _contains_numeric_value(note.summary)
            ),
            key=_note_sort_key,
        )[:max_notes_per_entity]
        for note in matched:
            summary = _truncate(note.summary, max_summary_chars)
            source = Path(note.source_path).name
            summaries.append(
                f"[{entity_id}] {note.title}: {summary} "
                f"(source: {source}, status: {note.binding_status})"
            )
    return summaries


def knowledge_vault_available() -> bool:
    try:
        vault_path = resolve_obsidian_vault_path()
    except Exception:
        return False
    return vault_path is not None and vault_path.is_dir()


def _known_entity_ids() -> frozenset[str] | None:
    try:
        from backend.app.ontology.loader import load_ontology_index

        return load_ontology_index().entity_ids()
    except Exception:
        return None


def _iter_markdown_notes(vault_path: Path):
    for root, dir_names, file_names in os.walk(vault_path):
        dir_names[:] = sorted(
            (dir_name for dir_name in dir_names if dir_name not in _SKIP_DIR_NAMES),
            key=lambda value: (value.casefold(), value),
        )
        for file_name in sorted(file_names, key=lambda value: (value.casefold(), value)):
            if not file_name.endswith(".md"):
                continue
            yield Path(root) / file_name


def _parse_frontmatter(text: str) -> tuple[list[str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], "narrative"

    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return [], "narrative"

    entities: list[str] = []
    binding_status = "narrative"
    frontmatter = lines[1:end_index]
    in_entities = False
    for raw_line in frontmatter:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("moss_entities:"):
            in_entities = True
            value = stripped.split(":", 1)[1].strip()
            if value.startswith("[") and value.endswith("]"):
                entities.extend(_split_inline_list(value[1:-1]))
            continue
        if stripped.startswith("moss_binding_status:"):
            in_entities = False
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            binding_status = value if value in {"narrative", "candidate"} else "narrative"
            continue
        if in_entities and stripped.startswith("-"):
            value = stripped[1:].strip().strip("\"'")
            if value:
                entities.append(value)
            continue
        if not raw_line.startswith((" ", "\t", "-")):
            in_entities = False

    return _unique(entities), binding_status


def _split_inline_list(value: str) -> list[str]:
    return [item.strip().strip("\"'") for item in value.split(",") if item.strip()]


def _extract_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _extract_summary(text: str) -> str:
    quote = _extract_blockquote(text)
    if quote:
        return _truncate(quote, _SUMMARY_MAX_CHARS)
    for paragraph in re.split(r"\n\s*\n", text):
        stripped = paragraph.strip()
        if not stripped or stripped.startswith("---") or stripped.startswith("#"):
            continue
        return _truncate(re.sub(r"\s+", " ", stripped), _SUMMARY_MAX_CHARS)
    return ""


def _extract_blockquote(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            return stripped.lstrip("> ").strip()
    return ""


def _build_source_version(note_versions: list[str]) -> str:
    if not note_versions:
        return KNOWLEDGE_INDEX_EMPTY_SOURCE_VERSION
    digest = hashlib.sha1("|".join(sorted(note_versions)).encode("utf-8")).hexdigest()[:12]
    return f"sv_knowledge_{digest}"


def _note_sort_key(note: KnowledgeNoteBinding) -> tuple[str, str]:
    path_key = Path(note.source_path).as_posix()
    return (path_key.casefold(), note.note_id)


def _note_id_for_path(note_path: Path, vault_path: Path) -> str:
    relative_parts = note_path.relative_to(vault_path).with_suffix("").parts
    base_note_id = "__".join(_slugify(part) for part in relative_parts)
    if all(part == _slugify(part) for part in relative_parts):
        return base_note_id
    return _hashed_note_id(base_note_id, note_path, vault_path)


def _hashed_note_id(
    base_id: str,
    note_path: Path,
    vault_path: Path,
) -> str:
    relative_path = note_path.relative_to(vault_path).as_posix()
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]
    return f"{base_id}-{digest}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return slug or "note"


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _contains_numeric_value(value: str) -> bool:
    return any(character.isdigit() for character in str(value or ""))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
