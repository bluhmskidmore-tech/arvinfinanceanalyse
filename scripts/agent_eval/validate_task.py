from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent_eval.reward import evaluate_result
from scripts.agent_eval.spec import validate_result_spec, validate_task_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a MOSS agent task result.")
    parser.add_argument("--task", required=True, help="Path to the task JSON file.")
    parser.add_argument("--result", required=True, help="Path to the agent result JSON file.")
    parser.add_argument("--out", help="Optional path for the scorecard JSON.")
    args = parser.parse_args()

    try:
        task = validate_task_spec(_load_json(Path(args.task)))
        result = validate_result_spec(_load_json(Path(args.result)))
    except ValueError as error:
        print(f"Invalid agent eval input: {error}", file=sys.stderr)
        return 2

    scorecard = evaluate_result(task, result)

    payload = json.dumps(scorecard, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

    return 0 if scorecard["status"] == "pass" else 1


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
