"""CI 受控跳过清单守卫（纯静态文本扫描，不 import、不执行被扫描的测试）。

扫描范围：tests/ 与 backend/tests/ 下全部 *.py（递归），排除本守卫文件自身。

依赖型跳过模式（与 tests/ci_skip_registry.json 的 kinds 保持一致）：
- skipif        -> 行内出现 "pytest.mark.skipif"（条件跳过标记，含装饰器与
                   pytest.param(..., marks=pytest.mark.skipif(...)) 参数化条件跳过）
- skip_call     -> 行内出现 "pytest.skip("（运行时跳过调用）
- importorskip  -> 行内出现 "importorskip"（依赖包缺失跳过，含 pytest. 前缀与裸用法）

排除规则（保守取向：宁可多报要求登记，不静默漏报）：
1. 本文件自身与 registry JSON 不参与扫描（两者必然包含上述模式字面量）。
2. lstrip 后以 "#" 开头的纯注释行不计数；行内尾注释不剔除（多报方向，可接受）。
3. 无条件业务性标记 pytest.mark.skip（不带 if，常见于 pytest.param(...,
   marks=pytest.mark.skip) 的业务占位）不属于依赖型模式，按规则放行：
   它不匹配上述任一模式串（"pytest.mark.skipif" 与 "pytest.skip(" 均不是其子串）。
   TODO: 当前仓库不存在该用法；若未来引入且被误报（例如新的书写变体），
   请在 registry 中以 category="other" 登记并注明业务属性，而不是修改扫描规则。
4. 字符串/文档字符串中出现的模式会被计入（多报方向）；当前仓库无此情况。

比对规则：
- 未登记文件出现任一依赖型模式 -> FAIL（新增依赖型跳过必须先登记）。
- 已登记文件某 kind 的计数超过登记值 -> FAIL（同文件新增未登记跳过）。
- 计数低于登记值或登记文件已无匹配 -> 不失败，仅发 UserWarning 提醒同步清理
  registry（避免并行工作区中他人移除跳过时本守卫误伤）。
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
REGISTRY_PATH = SELF_PATH.parent / "ci_skip_registry.json"

SCAN_ROOTS = ("tests", "backend/tests")

PATTERNS: dict[str, str] = {
    "skipif": "pytest.mark.skipif",
    "skip_call": "pytest.skip(",
    "importorskip": "importorskip",
}

ALLOWED_CATEGORIES = {"real-data", "redis", "postgres", "symlink", "system-db", "other"}
ALLOWED_RECOMMENDATIONS = {"synthesize", "keep-controlled"}


def _load_registry() -> dict:
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _count_patterns_in_text(text: str) -> dict[str, int]:
    counts = {kind: 0 for kind in PATTERNS}
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for kind, pattern in PATTERNS.items():
            counts[kind] += stripped.count(pattern)
    return {kind: value for kind, value in counts.items() if value}


def _scan_tree() -> dict[str, dict[str, int]]:
    results: dict[str, dict[str, int]] = {}
    for root in SCAN_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            resolved = path.resolve()
            if resolved == SELF_PATH:
                continue
            counts = _count_patterns_in_text(
                resolved.read_text(encoding="utf-8", errors="replace")
            )
            if counts:
                results[resolved.relative_to(REPO_ROOT).as_posix()] = counts
    return results


def test_registry_schema_is_valid() -> None:
    registry = _load_registry()

    assert registry["schema_version"] == "ci-skip-registry-v1"
    assert list(registry["scan_roots"]) == list(SCAN_ROOTS)
    assert set(registry["kinds"]) == set(PATTERNS)
    assert set(registry["categories"]) == ALLOWED_CATEGORIES

    seen_files: set[str] = set()
    for entry in registry["entries"]:
        file_path = entry["file"]
        assert file_path not in seen_files, f"duplicate registry entry: {file_path}"
        seen_files.add(file_path)
        assert file_path.startswith(("tests/", "backend/tests/")), file_path

        expected_counts = entry["expected_counts"]
        assert expected_counts, f"{file_path}: expected_counts must not be empty"
        for kind, value in expected_counts.items():
            assert kind in PATTERNS, f"{file_path}: unknown kind {kind!r}"
            assert int(value) > 0, f"{file_path}: {kind} count must be positive"

        occurrence_totals: dict[str, int] = {}
        for occurrence in entry["occurrences"]:
            assert occurrence["kind"] in PATTERNS, file_path
            assert occurrence["category"] in ALLOWED_CATEGORIES, file_path
            assert occurrence["recommendation"] in ALLOWED_RECOMMENDATIONS, file_path
            assert isinstance(occurrence["depends_on"], list) and occurrence["depends_on"], file_path
            assert isinstance(occurrence["has_synthetic_alternative"], bool), file_path
            assert isinstance(occurrence["reason"], str) and occurrence["reason"].strip(), file_path
            occurrence_totals[occurrence["kind"]] = (
                occurrence_totals.get(occurrence["kind"], 0) + int(occurrence["count"])
            )
        assert occurrence_totals == {
            kind: int(value) for kind, value in expected_counts.items()
        }, f"{file_path}: occurrences do not reconcile with expected_counts"


def test_no_unregistered_dependency_skips() -> None:
    registry = _load_registry()
    registered: dict[str, dict[str, int]] = {
        entry["file"]: {kind: int(value) for kind, value in entry["expected_counts"].items()}
        for entry in registry["entries"]
    }
    actual = _scan_tree()

    violations: list[str] = []
    stale: list[str] = []

    for file_path, kinds in sorted(actual.items()):
        expected = registered.get(file_path)
        if expected is None:
            violations.append(
                f"{file_path}: unregistered dependency skip pattern(s) {kinds}"
            )
            continue
        for kind, count in kinds.items():
            allowed = expected.get(kind, 0)
            if count > allowed:
                violations.append(
                    f"{file_path}: {kind} occurrences {count} exceed registered {allowed}"
                )
            elif count < allowed:
                stale.append(
                    f"{file_path}: {kind} occurrences {count} below registered {allowed}"
                )

    for file_path, expected in sorted(registered.items()):
        observed = actual.get(file_path, {})
        for kind, allowed in expected.items():
            if observed.get(kind, 0) == 0 and allowed > 0:
                stale.append(
                    f"{file_path}: registered {kind} x{allowed} no longer found"
                )

    if stale:
        warnings.warn(
            "ci_skip_registry.json is stale (skips were removed or files deleted); "
            "please prune these entries: " + "; ".join(sorted(set(stale))),
            UserWarning,
            stacklevel=1,
        )

    assert not violations, (
        "New environment/data dependent skips must be registered in "
        "tests/ci_skip_registry.json before landing (file, kind counts, category, "
        "depends_on, synthetic alternative):\n" + "\n".join(violations)
    )


def test_pattern_counter_matches_expected_semantics() -> None:
    sample = "\n".join(
        [
            "import pytest",
            "# pytest.skip( inside a pure comment line is ignored",
            "@pytest.mark.skipif(not FLAG, reason='env gated')",
            "def test_a():",
            "    pytest.skip('runtime dependency missing')",
            "    duckdb = pytest.importorskip('duckdb')",
            "params = pytest.param(1, marks=pytest.mark.skip)",
        ]
    )

    counts = _count_patterns_in_text(sample)

    assert counts == {"skipif": 1, "skip_call": 1, "importorskip": 1}
