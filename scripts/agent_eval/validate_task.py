from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent_eval.collect import collect_measured_result
from scripts.agent_eval.reward import evaluate_result
from scripts.agent_eval.spec import validate_measured_result, validate_result_spec, validate_task_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a MOSS agent task result.")
    parser.add_argument("--task", required=True, help="Path to the task JSON file.")
    parser.add_argument("--result", help="Path to an existing result JSON file.")
    parser.add_argument(
        "--measure",
        action="store_true",
        help="Observe the repository and produce the result instead of reading one.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root used when measuring.")
    parser.add_argument("--base-ref", help="Git ref to diff against when measuring changed files.")
    parser.add_argument(
        "--task-digest",
        help="sha256 of the task file captured before the agent ran; proves the rules were not rewritten.",
    )
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="Reject a result that was not produced by the measurement collector.",
    )
    parser.add_argument("--out", help="Optional path for the scorecard JSON.")
    parser.add_argument("--result-out", help="Optional path to write the measured result JSON.")
    args = parser.parse_args()

    if args.measure == bool(args.result):
        print("Provide exactly one of --measure or --result.", file=sys.stderr)
        return 2

    try:
        task = validate_task_spec(_load_json(Path(args.task)))
        if args.measure:
            result = collect_measured_result(
                task,
                repo_root=args.repo_root,
                base_ref=args.base_ref,
                task_path=args.task,
                expected_task_digest=args.task_digest,
            )
        else:
            result = _load_json(Path(args.result))

        if args.measure or args.require_measured:
            validate_measured_result(result)
        else:
            validate_result_spec(result)
    except ValueError as error:
        print(f"Invalid agent eval input: {error}", file=sys.stderr)
        return 2

    if args.result_out:
        _write_json(Path(args.result_out), result)

    scorecard = evaluate_result(task, result)
    scorecard["measured"] = "measurement" in result
    _report_unprobed_gates(result)

    payload = json.dumps(scorecard, ensure_ascii=False, indent=2)
    if args.out:
        _write_json(Path(args.out), scorecard)
    else:
        print(payload)

    return 0 if scorecard["status"] == "pass" else 1


def _report_unprobed_gates(result: dict[str, Any]) -> None:
    measurement = result.get("measurement")
    if not isinstance(measurement, dict):
        return
    unprobed = measurement.get("unprobed_gates") or []
    if unprobed:
        print(
            "Gates scored as failed because no probe is declared: " + ", ".join(str(gate) for gate in unprobed),
            file=sys.stderr,
        )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
