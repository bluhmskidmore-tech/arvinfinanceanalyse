from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from backend.app.schemas.liability_knowledge import (
    LiabilityKnowledgeBriefPayload,
    LiabilityKnowledgeNote,
)
from backend.app.services.formal_result_runtime import build_result_envelope

LIABILITY_KNOWLEDGE_CACHE_VERSION = "cv_liability_knowledge_v1"
LIABILITY_KNOWLEDGE_RULE_VERSION = "rv_liability_knowledge_v1"
LIABILITY_KNOWLEDGE_EMPTY_SOURCE_VERSION = "sv_liability_knowledge_empty"

_LIABILITY_NOTE_FILENAMES = (
    "同业负债、流动性与金融市场业务传导链.md",
    "债券投资、久期与利率风险传导链.md",
    "金融市场条线经营分析标准提纲.md",
)


def liability_knowledge_brief_envelope() -> dict[str, object]:
    vault_path = _resolve_obsidian_vault_path()
    if vault_path is None:
        return _build_envelope(
            payload=LiabilityKnowledgeBriefPayload(
                page_id="liability-analytics",
                available=False,
                vault_path=None,
                status_note="obsidian-vault-not-found",
                notes=[],
            ),
            source_version=LIABILITY_KNOWLEDGE_EMPTY_SOURCE_VERSION,
            quality_flag="warning",
            evidence_rows=0,
        )

    notes: list[LiabilityKnowledgeNote] = []
    note_versions: list[str] = []
    missing_files: list[str] = []
    for filename in _LIABILITY_NOTE_FILENAMES:
        note_path = vault_path / filename
        if not note_path.exists():
            missing_files.append(filename)
            continue
        note = _load_note(note_path)
        notes.append(note)
        note_versions.append(f"{note_path.name}:{note_path.stat().st_mtime_ns}")

    status_bits = ["obsidian-local"]
    if missing_files:
        status_bits.append(f"missing={len(missing_files)}")
    source_version = _build_source_version(note_versions)
    return _build_envelope(
        payload=LiabilityKnowledgeBriefPayload(
            page_id="liability-analytics",
            available=bool(notes),
            vault_path=str(vault_path),
            status_note="; ".join(status_bits),
            notes=notes,
        ),
        source_version=source_version,
        quality_flag="ok" if notes else "warning",
        evidence_rows=len(notes),
    )


def _build_envelope(
    *,
    payload: LiabilityKnowledgeBriefPayload,
    source_version: str,
    quality_flag: str,
    evidence_rows: int,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_liability_knowledge_brief",
        result_kind="liability.page_knowledge",
        cache_version=LIABILITY_KNOWLEDGE_CACHE_VERSION,
        source_version=source_version,
        rule_version=LIABILITY_KNOWLEDGE_RULE_VERSION,
        quality_flag=quality_flag,
        evidence_rows=evidence_rows,
        filters_applied={"page_id": "liability-analytics"},
        result_payload=payload.model_dump(mode="json"),
    )


def _build_source_version(note_versions: list[str]) -> str:
    if not note_versions:
        return LIABILITY_KNOWLEDGE_EMPTY_SOURCE_VERSION
    digest = hashlib.sha1("|".join(note_versions).encode("utf-8")).hexdigest()[:12]
    return f"sv_liability_knowledge_{digest}"


def _load_note(note_path: Path) -> LiabilityKnowledgeNote:
    text = _read_note_text(note_path)
    title = _extract_title(text, fallback=note_path.stem)
    summary = _extract_summary(text)
    why_it_matters = _extract_why_it_matters(text) or summary
    questions = _extract_key_questions(text)
    return LiabilityKnowledgeNote(
        id=_slugify(note_path.stem),
        title=title,
        summary=summary,
        why_it_matters=why_it_matters,
        key_questions=questions,
        source_path=str(note_path),
    )


def _resolve_obsidian_vault_path() -> Path | None:
    explicit = str(os.getenv("MOSS_OBSIDIAN_VAULT_PATH", "")).strip()
    if explicit:
        return Path(explicit).expanduser()

    config_candidates: list[Path] = []
    appdata = str(os.getenv("APPDATA", "")).strip()
    if appdata:
        config_candidates.append(Path(appdata) / "Obsidian" / "obsidian.json")
    config_candidates.append(Path.home() / "AppData" / "Roaming" / "Obsidian" / "obsidian.json")
    config_candidates.append(Path.home() / ".config" / "Obsidian" / "obsidian.json")

    for candidate in config_candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        vaults = payload.get("vaults")
        if not isinstance(vaults, dict):
            continue
        ranked: list[tuple[int, int, str]] = []
        for entry in vaults.values():
            if not isinstance(entry, dict):
                continue
            path_value = str(entry.get("path") or "").strip()
            if not path_value:
                continue
            ranked.append(
                (
                    1 if bool(entry.get("open")) else 0,
                    int(entry.get("ts") or 0),
                    path_value,
                )
            )
        if ranked:
            ranked.sort(reverse=True)
            return Path(ranked[0][2]).expanduser()
    return None


def _read_note_text(note_path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return note_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return note_path.read_text(encoding="utf-8", errors="ignore")


def _extract_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _extract_summary(text: str) -> str:
    summary = _extract_section_body(text, "## 一句话结论")
    if summary:
        return summary
    quote = _extract_blockquote(text)
    if quote:
        return quote
    return _extract_first_paragraph(text)


def _extract_why_it_matters(text: str) -> str:
    quote = _extract_blockquote(text)
    if quote:
        return quote
    return _extract_first_paragraph(text)


def _extract_key_questions(text: str) -> list[str]:
    lines = text.splitlines()
    questions: list[str] = []
    in_question_block = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## ") and "先问" in stripped:
            in_question_block = True
            continue
        if in_question_block and stripped.startswith("## "):
            break
        if in_question_block and stripped.startswith("### "):
            question = re.sub(r"^\d+\.\s*", "", stripped[4:].strip())
            if question:
                questions.append(question)
        if len(questions) >= 3:
            break
    if questions:
        return questions

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("### "):
            question = re.sub(r"^\d+\.\s*", "", stripped[4:].strip())
            if question:
                questions.append(question)
        if len(questions) >= 3:
            break
    return questions


def _extract_section_body(text: str, heading: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue
        collected: list[str] = []
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if stripped.startswith("## "):
                break
            if not stripped:
                if collected:
                    break
                continue
            cleaned = stripped.lstrip("> ").strip()
            if cleaned:
                collected.append(cleaned)
        if collected:
            return _normalize_text(" ".join(collected))
    return ""


def _extract_blockquote(text: str) -> str:
    quotes: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            quotes.append(stripped.lstrip("> ").strip())
        elif quotes:
            break
    return _normalize_text(" ".join(quotes))


def _extract_first_paragraph(text: str) -> str:
    collected: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
        collected.append(stripped)
    return _normalize_text(" ".join(collected))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    slug = slug.strip("-")
    return slug or "note"
