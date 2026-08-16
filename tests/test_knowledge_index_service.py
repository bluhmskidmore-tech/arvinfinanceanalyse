from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services import knowledge_index_service as service


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MOSS_OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_ontology(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service,
        "_known_entity_ids",
        lambda: frozenset({"MTR-PNL-001", "CONCEPT-formal_pnl", "PAGE-BALANCE-001"}),
    )


def write_note(
    vault: Path,
    name: str,
    frontmatter: str,
    body: str = "正文第一段。",
) -> Path:
    path = vault / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n# {Path(name).stem}\n\n{body}", encoding="utf-8")
    return path


def test_vault_missing_returns_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOSS_OBSIDIAN_VAULT_PATH", str(tmp_path / "missing"))

    payload = service.load_knowledge_index()

    assert payload.available is False
    assert payload.status_note == "obsidian-vault-not-found"
    assert payload.notes == []


def test_note_with_known_bindings_indexed(vault: Path, fake_ontology: None) -> None:
    write_note(
        vault,
        "formal-pnl.md",
        "moss_entities:\n  - MTR-PNL-001\n  - CONCEPT-formal_pnl\nmoss_binding_status: narrative",
        body="> 正式损益先看报告日和会计归属矩阵。",
    )

    payload = service.load_knowledge_index()

    assert payload.available is True
    assert payload.unknown_bindings == {}
    assert len(payload.notes) == 1
    assert payload.notes[0].entities == ["MTR-PNL-001", "CONCEPT-formal_pnl"]
    assert payload.notes[0].warnings == []
    assert payload.notes[0].summary == "正式损益先看报告日和会计归属矩阵。"


def test_inline_list_frontmatter_parses(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "inline.md", "moss_entities: [MTR-PNL-001, PAGE-BALANCE-001]")

    payload = service.load_knowledge_index()

    assert payload.notes[0].entities == ["MTR-PNL-001", "PAGE-BALANCE-001"]


def test_unknown_entity_flagged_not_dropped(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "unknown.md", "moss_entities:\n  - MTR-NOPE-999")

    payload = service.load_knowledge_index()

    assert len(payload.notes) == 1
    assert payload.notes[0].entities == ["MTR-NOPE-999"]
    assert payload.notes[0].warnings == ["unknown-entity:MTR-NOPE-999"]
    assert payload.unknown_bindings == {"unknown": ["MTR-NOPE-999"]}


def test_note_without_frontmatter_skipped(vault: Path, fake_ontology: None) -> None:
    (vault / "plain.md").write_text("# Plain\n\nNo binding.", encoding="utf-8")

    payload = service.load_knowledge_index()

    assert payload.available is False
    assert payload.notes == []


def test_unbound_note_does_not_consume_readable_note_id(vault: Path, fake_ontology: None) -> None:
    (vault / "foo").mkdir(parents=True, exist_ok=True)
    (vault / "foo" / "alpha!.md").write_text("# Plain\n\nNo binding.", encoding="utf-8")
    write_note(vault, "foo/alpha.md", "moss_entities: [MTR-ALPHA-999]")

    payload = service.load_knowledge_index()

    assert len(payload.notes) == 1
    assert payload.notes[0].note_id == "foo__alpha"
    assert "-" not in payload.notes[0].note_id
    assert payload.unknown_bindings == {"foo__alpha": ["MTR-ALPHA-999"]}


def test_code_block_warning(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "code.md", "moss_entities: [MTR-PNL-001]", body="```python\nx = 1\n```")

    payload = service.load_knowledge_index()

    assert "contains-code-block" in payload.notes[0].warnings


def test_ontology_unavailable_degrades(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_known_entity_ids", lambda: None)
    write_note(vault, "offline.md", "moss_entities: [MTR-PNL-001]")

    payload = service.load_knowledge_index()

    assert payload.notes[0].warnings == ["ontology-index-unavailable"]
    assert payload.unknown_bindings == {}


def test_entity_notes_envelope_shape(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "formal.md", "moss_entities: [MTR-PNL-001]")

    envelope = service.entity_notes_envelope("MTR-PNL-001")

    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["result_kind"] == "knowledge.entity_notes"
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["evidence_rows"] == 1
    assert envelope["result"]["entity_id"] == "MTR-PNL-001"
    assert envelope["result"]["available"] is True


def test_summaries_for_entities_format_and_degrade(
    vault: Path,
    fake_ontology: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_note(vault, "formal.md", "moss_entities: [MTR-PNL-001]", body="业务摘要。")

    summaries = service.knowledge_summaries_for_entities(["MTR-PNL-001"])

    assert summaries == [
        "[MTR-PNL-001] formal: 业务摘要。 (source: formal.md, status: narrative)"
    ]

    monkeypatch.setenv("MOSS_OBSIDIAN_VAULT_PATH", str(tmp_path / "missing"))
    assert service.knowledge_summaries_for_entities(["MTR-PNL-001"]) == []


def test_summaries_for_entities_sorted_before_slice(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "z-last.md", "moss_entities: [MTR-PNL-001]", body="Zulu summary.")
    write_note(vault, "a-first.md", "moss_entities: [MTR-PNL-001]", body="Alpha summary.")
    write_note(vault, "m-middle.md", "moss_entities: [MTR-PNL-001]", body="Middle summary.")

    summaries = service.knowledge_summaries_for_entities(
        ["MTR-PNL-001"],
        max_notes_per_entity=2,
    )

    assert summaries == [
        "[MTR-PNL-001] a-first: Alpha summary. (source: a-first.md, status: narrative)",
        "[MTR-PNL-001] m-middle: Middle summary. (source: m-middle.md, status: narrative)",
    ]


def test_summaries_omit_value_bearing_narrative(vault: Path, fake_ontology: None) -> None:
    write_note(
        vault,
        "valuation.md",
        "moss_entities: [MTR-PNL-001]",
        body="Current valuation is 12.4x and ROE is 18%.",
    )

    assert service.knowledge_summaries_for_entities(["MTR-PNL-001"]) == []


def test_summaries_degrade_when_ontology_is_unavailable(
    vault: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "_known_entity_ids", lambda: None)
    write_note(vault, "offline.md", "moss_entities: [MTR-PNL-001]", body="Narrative only.")

    assert service.knowledge_summaries_for_entities(["MTR-PNL-001"]) == []


def test_binding_status_candidate_and_invalid(vault: Path, fake_ontology: None) -> None:
    write_note(
        vault,
        "candidate.md",
        "moss_entities: [MTR-PNL-001]\nmoss_binding_status: candidate",
    )
    write_note(
        vault,
        "invalid.md",
        "moss_entities: [PAGE-BALANCE-001]\nmoss_binding_status: approved",
    )

    payload = service.load_knowledge_index()
    by_id = {note.note_id: note for note in payload.notes}

    assert by_id["candidate"].binding_status == "candidate"
    assert by_id["invalid"].binding_status == "narrative"


def test_top_level_paths_keep_readable_note_ids(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "alpha.md", "moss_entities: [MTR-TOP-999]")

    payload = service.load_knowledge_index()

    assert [note.note_id for note in payload.notes] == ["alpha"]
    assert payload.unknown_bindings == {"alpha": ["MTR-TOP-999"]}


def test_duplicate_filenames_in_separate_folders_get_distinct_note_ids(
    vault: Path, fake_ontology: None
) -> None:
    write_note(vault, "foo/alpha.md", "moss_entities: [MTR-FOO-999]")
    write_note(vault, "bar/alpha.md", "moss_entities: [MTR-BAR-999]")

    payload = service.load_knowledge_index()
    by_id = {note.note_id: note for note in payload.notes}

    assert set(by_id) == {"bar__alpha", "foo__alpha"}
    assert by_id["bar__alpha"].entities == ["MTR-BAR-999"]
    assert by_id["foo__alpha"].entities == ["MTR-FOO-999"]
    assert payload.unknown_bindings == {
        "bar__alpha": ["MTR-BAR-999"],
        "foo__alpha": ["MTR-FOO-999"],
    }


def test_flat_and_nested_paths_keep_distinct_note_ids_and_unknown_bindings(
    vault: Path, fake_ontology: None
) -> None:
    write_note(vault, "foo-alpha.md", "moss_entities: [MTR-FLAT-999]")
    write_note(vault, "foo/alpha.md", "moss_entities: [MTR-NESTED-999]")

    payload = service.load_knowledge_index()
    by_id = {note.note_id: note for note in payload.notes}

    assert set(by_id) == {"foo-alpha", "foo__alpha"}
    assert by_id["foo-alpha"].entities == ["MTR-FLAT-999"]
    assert by_id["foo__alpha"].entities == ["MTR-NESTED-999"]
    assert payload.unknown_bindings == {
        "foo-alpha": ["MTR-FLAT-999"],
        "foo__alpha": ["MTR-NESTED-999"],
    }


def test_punctuation_normalized_nested_siblings_get_distinct_note_ids(
    vault: Path, fake_ontology: None
) -> None:
    write_note(vault, "foo/alpha.md", "moss_entities: [MTR-ALPHA-999]")
    write_note(vault, "foo/alpha!.md", "moss_entities: [MTR-ALPHA-BANG-999]")

    payload = service.load_knowledge_index()
    by_source = {
        Path(note.source_path).relative_to(vault).as_posix(): note.note_id for note in payload.notes
    }
    hashed_note_id = by_source["foo/alpha!.md"]
    suffix = hashed_note_id.removeprefix("foo__alpha-")

    assert len(set(by_source.values())) == 2
    assert by_source["foo/alpha.md"] == "foo__alpha"
    assert hashed_note_id.startswith("foo__alpha-")
    assert len(suffix) == 8
    assert all(char in "0123456789abcdef" for char in suffix)
    assert payload.unknown_bindings == {
        "foo__alpha": ["MTR-ALPHA-999"],
        hashed_note_id: ["MTR-ALPHA-BANG-999"],
    }
    assert {note.entities[0] for note in payload.notes} == {"MTR-ALPHA-999", "MTR-ALPHA-BANG-999"}


def test_punctuation_normalized_note_id_stays_stable_across_rescans(
    vault: Path, fake_ontology: None
) -> None:
    write_note(vault, "foo/alpha!.md", "moss_entities: [MTR-ALPHA-BANG-999]")

    first_payload = service.load_knowledge_index()

    assert len(first_payload.notes) == 1
    first_note_id = first_payload.notes[0].note_id
    suffix = first_note_id.removeprefix("foo__alpha-")

    assert first_note_id.startswith("foo__alpha-")
    assert len(suffix) == 8
    assert all(char in "0123456789abcdef" for char in suffix)
    assert first_payload.unknown_bindings == {first_note_id: ["MTR-ALPHA-BANG-999"]}

    write_note(vault, "foo/alpha.md", "moss_entities: [MTR-ALPHA-999]")

    second_payload = service.load_knowledge_index()
    by_source = {
        Path(note.source_path).relative_to(vault).as_posix(): note.note_id for note in second_payload.notes
    }

    assert by_source["foo/alpha!.md"] == first_note_id
    assert by_source["foo/alpha.md"] == "foo__alpha"
    assert second_payload.unknown_bindings == {
        "foo__alpha": ["MTR-ALPHA-999"],
        first_note_id: ["MTR-ALPHA-BANG-999"],
    }


def test_skip_dirs_are_excluded_from_scan(vault: Path, fake_ontology: None) -> None:
    write_note(vault, "kept.md", "moss_entities: [MTR-PNL-001]")
    write_note(vault, "nested/kept-too.md", "moss_entities: [PAGE-BALANCE-001]")
    write_note(vault, ".obsidian/ignored.md", "moss_entities: [MTR-PNL-001]")
    write_note(vault, ".trash/ignored.md", "moss_entities: [MTR-PNL-001]")
    write_note(vault, "templates/ignored.md", "moss_entities: [MTR-PNL-001]")

    payload = service.load_knowledge_index()

    assert [note.note_id for note in payload.notes] == ["kept", "nested__kept-too"]
    assert payload.status_note == "obsidian-local"


def test_scan_truncation_stops_after_sorted_scan_cap(
    vault: Path, fake_ontology: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "_MAX_SCAN_FILES", 2)
    write_note(vault, "c-third.md", "moss_entities: [MTR-PNL-001]")
    write_note(vault, "a-first.md", "moss_entities: [MTR-PNL-001]")
    write_note(vault, "b-second.md", "moss_entities: [MTR-PNL-001]")

    payload = service.load_knowledge_index()

    assert [note.note_id for note in payload.notes] == ["a-first", "b-second"]
    assert payload.status_note == "obsidian-local; scan-truncated"
