from __future__ import annotations

"""
Contract source:
- `docs/metric_dictionary.md`
- `tests/golden_samples/<sample_id>/response.json`

Whitelist:
- `EXEMPT_UNBOUND_SAMPLE_IDS` records any future candidate / blocked sample ids
  that are mentioned elsewhere in governance docs but are not yet part of the
  metric dictionary's capture-ready sample binding.
- The current repository uses section `12.4 Capture-ready sample_scope binding`
  as today's `bound_sample_id` equivalent; when a dedicated `bound_sample_id`
  column lands, this test should switch to that primary source automatically.

Follow-up plan:
- Keep candidate samples out of the bound set until their package directory
  exists and they are promoted into the metric dictionary binding.
- Remove whitelist entries once the sample becomes bound and capture-ready.
"""

import re
from pathlib import Path

import pytest

from tests.helpers import ROOT

METRIC_DICTIONARY_PATH = ROOT / "docs" / "metric_dictionary.md"
GOLDEN_ROOT = ROOT / "tests" / "golden_samples"

EXEMPT_UNBOUND_SAMPLE_IDS: dict[str, str] = {}

SAMPLE_ID_RE = re.compile(r"\bGS-[A-Z0-9-]+\b")


def _extract_bound_sample_ids() -> set[str]:
    text = METRIC_DICTIONARY_PATH.read_text(encoding="utf-8")

    if "bound_sample_id" in text:
        sample_ids: set[str] = set()
        in_bound_table = False
        for line in text.splitlines():
            if "bound_sample_id" in line:
                in_bound_table = True
                continue
            if in_bound_table and not line.lstrip().startswith("|"):
                break
            if in_bound_table:
                sample_ids.update(SAMPLE_ID_RE.findall(line))
        if sample_ids:
            return sample_ids

    section_header = "### 12.4 Capture-ready `sample_scope` 绑定"
    next_header = "### 12.5"
    if section_header not in text or next_header not in text:
        pytest.fail(
            "Unable to locate the metric-dictionary capture-ready sample binding section. "
            "Expected either `bound_sample_id` entries or section `12.4 Capture-ready sample_scope binding`."
        )

    section_text = text.split(section_header, maxsplit=1)[1].split(next_header, maxsplit=1)[0]
    sample_ids: set[str] = set()
    for line in section_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        sample_ids.update(SAMPLE_ID_RE.findall(line))
    return sample_ids


def test_metric_dictionary_bound_samples_have_on_disk_response_payloads():
    bound_sample_ids = _extract_bound_sample_ids()

    if not bound_sample_ids:
        pytest.fail(
            "Metric dictionary bound-sample extraction returned zero sample ids. "
            "Expected capture-ready sample bindings to be present."
        )

    stale_whitelist = sorted(sample_id for sample_id in EXEMPT_UNBOUND_SAMPLE_IDS if sample_id in bound_sample_ids)
    missing_directories: list[str] = []
    missing_responses: list[str] = []

    for sample_id in sorted(bound_sample_ids):
        sample_dir = GOLDEN_ROOT / sample_id
        if not sample_dir.is_dir():
            missing_directories.append(sample_id)
            continue
        if not (sample_dir / "response.json").is_file():
            missing_responses.append(sample_id)

    if stale_whitelist or missing_directories or missing_responses:
        lines = ["Metric dictionary -> golden sample completeness gap report:"]

        if missing_directories:
            lines.append(f"missing_sample_directories={len(missing_directories)}")
            lines.extend(
                f"- {sample_id}: missing directory `{Path('tests/golden_samples') / sample_id}`."
                for sample_id in missing_directories
            )

        if missing_responses:
            lines.append(f"missing_response_json={len(missing_responses)}")
            lines.extend(
                f"- {sample_id}: directory exists but `response.json` is missing."
                for sample_id in missing_responses
            )

        if stale_whitelist:
            lines.append(f"stale_whitelist={len(stale_whitelist)}")
            lines.extend(
                f"- {sample_id}: now appears in the bound sample set; remove it from `EXEMPT_UNBOUND_SAMPLE_IDS`."
                for sample_id in stale_whitelist
            )

        pytest.fail("\n".join(lines))
