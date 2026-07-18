"""Read-only preview of the newest official NBS quarterly GDP release."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.app.repositories.nbs_gdp_release_adapter import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    NbsGdpReleaseAdapter,
    NbsGdpReleaseError,
)


def preview_nbs_gdp_release(
    *,
    reference_date: date,
    adapter: Any | None = None,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    """Fetch and parse official evidence without opening persistence services."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    release_adapter = adapter or NbsGdpReleaseAdapter(config_path=config_path)
    document = release_adapter.discover_and_fetch(reference_date=reference_date)
    observations = [
        {
            "report_period": str(row["trade_date"]),
            "value": row["value"],
        }
        for row in document.observations
    ]
    return {
        "status": "success",
        "reference_date": reference_date.isoformat(),
        "release_url": document.release_url,
        "fetched_at": document.fetched_at.isoformat(),
        "content_sha256": hashlib.sha256(document.html_bytes).hexdigest(),
        "series_id": str(config["series_id"]),
        "rule_version": str(config["rule_version"]),
        "observations": observations,
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Ignore official releases after this ISO date (default: today).",
    )
    args = parser.parse_args()
    try:
        result = preview_nbs_gdp_release(reference_date=args.reference_date)
    except NbsGdpReleaseError as exc:
        result = {
            "status": "blocked",
            "reference_date": args.reference_date.isoformat(),
            "error": f"{type(exc).__name__}: {exc}",
            "writes_performed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
