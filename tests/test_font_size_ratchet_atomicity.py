from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path, baseline: dict | None) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(
        ROOT / "scripts/audit_font_size_floor.mjs",
        scripts / "audit_font_size_floor.mjs",
    )
    (tmp_path / "frontend/src").mkdir(parents=True)
    baseline_path = scripts / "audit_font_size_floor.baseline.json"
    if baseline is not None:
        baseline_path.write_text(json.dumps(baseline, indent=4) + "\n", encoding="utf-8")
    return baseline_path


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(tmp_path / "scripts/audit_font_size_floor.mjs"), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize("cross_namespace", [False, True])
def test_ratchet_rejects_growth_without_writing_other_reductions(
    tmp_path: Path, cross_namespace: bool,
) -> None:
    baseline_path = _fixture(
        tmp_path,
        {"css": {"frontend/src/paid.css": {"belowFloor": 1}}, "inline": {}},
    )
    (tmp_path / "frontend/src/paid.css").write_text(".paid { font-size: 12px; }", encoding="utf-8")
    if cross_namespace:
        (tmp_path / "frontend/src/new.tsx").write_text(
            "export const textStyle = { fontSize: 10 };", encoding="utf-8",
        )
    else:
        (tmp_path / "frontend/src/new.css").write_text(".new { font-size: 10px; }", encoding="utf-8")
    before = baseline_path.read_bytes()

    result = _run(tmp_path, "--ratchet")

    assert result.returncode == 1, result.stdout + result.stderr
    assert baseline_path.read_bytes() == before
    assert "Refused to raise" in result.stderr


def test_ratchet_lowers_only_after_all_namespaces_pass(tmp_path: Path) -> None:
    baseline_path = _fixture(
        tmp_path,
        {
            "css": {"frontend/src/a.css": {"belowFloor": 2}},
            "inline": {"frontend/src/b.tsx": {"belowFloor": 1}},
        },
    )
    (tmp_path / "frontend/src/a.css").write_text(".a { font-size: 10px; }", encoding="utf-8")
    (tmp_path / "frontend/src/b.tsx").write_text("const b = { fontSize: 12 };", encoding="utf-8")

    result = _run(tmp_path, "--ratchet")

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(baseline_path.read_text(encoding="utf-8")) == {
        "css": {"frontend/src/a.css": {"belowFloor": 1}}, "inline": {},
    }
    audit = _run(tmp_path)
    assert audit.returncode == 0, audit.stdout + audit.stderr


@pytest.mark.parametrize("has_debt", [False, True])
def test_ratchet_does_not_recreate_missing_baseline(tmp_path: Path, has_debt: bool) -> None:
    baseline_path = _fixture(tmp_path, None)
    if has_debt:
        (tmp_path / "frontend/src/a.css").write_text(".a { font-size: 10px; }", encoding="utf-8")

    result = _run(tmp_path, "--ratchet")

    assert result.returncode == 1, result.stdout + result.stderr
    assert not baseline_path.exists()


def test_ratchet_preserves_bytes_when_nothing_changed(tmp_path: Path) -> None:
    baseline_path = _fixture(tmp_path, {"css": {}, "inline": {}})
    before = baseline_path.read_bytes()

    result = _run(tmp_path, "--ratchet")

    assert result.returncode == 0, result.stdout + result.stderr
    assert baseline_path.read_bytes() == before


@pytest.mark.parametrize("invalid", ["bad", None, -1, 1.5, True, [], {}])
@pytest.mark.parametrize("args", [(), ("--ratchet",)])
def test_invalid_counter_fails_without_changing_baseline(
    tmp_path: Path, invalid: object, args: tuple[str, ...],
) -> None:
    baseline_path = _fixture(
        tmp_path, {"css": {"frontend/src/a.css": {"belowFloor": invalid}}, "inline": {}},
    )
    before = baseline_path.read_bytes()

    result = _run(tmp_path, *args)

    assert result.returncode == 1, result.stdout + result.stderr
    assert baseline_path.read_bytes() == before
    assert "must be a non-negative integer" in result.stderr
