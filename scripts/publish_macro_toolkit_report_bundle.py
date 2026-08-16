from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "macro_toolkit" / "output" / "bond_macro_report_bundle"
MAX_ASSET_BYTES = 50_000_000


@dataclass(frozen=True)
class AssetSpec:
    artifact_id: str
    filename: str
    label: str
    kind: str
    media_type: str


ASSET_SPECS = (
    AssetSpec("full-report", "report.pdf", "完整报告", "report", "application/pdf"),
    AssetSpec("one-page-pdf", "onepager.pdf", "一页摘要 PDF", "brief", "application/pdf"),
    AssetSpec("one-page-preview", "onepager.png", "一页摘要预览", "preview", "image/png"),
    AssetSpec("speaker-notes", "speaker_notes.md", "汇报讲稿", "notes", "text/markdown"),
    AssetSpec("red-team-findings", "redteam_findings.md", "红队复核结论", "review", "text/markdown"),
    AssetSpec("readme", "README.md", "资产包说明", "readme", "text/markdown"),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="发布只读宏观报告资产包。")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--title", default="2026 中国宏观与利率策略")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--curve-date", required=True)
    parser.add_argument("--account-report-date", required=True)
    parser.add_argument("--validation-passed", type=int, required=True)
    parser.add_argument("--validation-failed", type=int, required=True)
    return parser


def _validated_date(parser: argparse.ArgumentParser, field: str, value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        parser.error(f"{field} must be an ISO date: {value}")
    return value


def _preflight_assets(parser: argparse.ArgumentParser, source_dir: Path) -> list[tuple[AssetSpec, bytes]]:
    if not source_dir.exists() or not source_dir.is_dir() or source_dir.is_symlink():
        parser.error(f"source directory is unavailable or unsafe: {source_dir}")
    resolved_source = source_dir.resolve(strict=True)
    assets: list[tuple[AssetSpec, bytes]] = []
    for spec in ASSET_SPECS:
        path = source_dir / spec.filename
        if not path.exists() or not path.is_file() or path.is_symlink():
            parser.error(f"required report asset is missing or unsafe: {spec.filename}")
        resolved_path = path.resolve(strict=True)
        if resolved_path.parent != resolved_source:
            parser.error(f"report asset must be a direct source child: {spec.filename}")
        content = resolved_path.read_bytes()
        if len(content) > MAX_ASSET_BYTES:
            parser.error(f"report asset exceeds {MAX_ASSET_BYTES} bytes: {spec.filename}")
        assets.append((spec, content))
    return assets


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    as_of_date = _validated_date(parser, "as-of-date", args.as_of_date)
    curve_date = _validated_date(parser, "curve-date", args.curve_date)
    account_report_date = _validated_date(parser, "account-report-date", args.account_report_date)
    if args.validation_passed < 0 or args.validation_failed < 0:
        parser.error("validation counts must be non-negative")
    if args.validation_failed != 0:
        parser.error("report bundle publication requires zero failed validation checks")
    title = str(args.title).strip()
    if not title:
        parser.error("title must not be blank")
    assets = _preflight_assets(parser, source_dir)

    if output_dir.exists() and (not output_dir.is_dir() or output_dir.is_symlink()):
        parser.error(f"output directory is unavailable or unsafe: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_rows: list[dict[str, object]] = []
    for spec, content in assets:
        _atomic_write(output_dir / spec.filename, content)
        artifact_rows.append(
            {
                "id": spec.artifact_id,
                "filename": spec.filename,
                "label": spec.label,
                "kind": spec.kind,
                "media_type": spec.media_type,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    manifest = {
        "schema_version": "macro-report-bundle-v1",
        "bundle_id": f"china-macro-rates-{as_of_date}",
        "title": title,
        "basis": "analytical",
        "as_of_date": as_of_date,
        "curve_date": curve_date,
        "account_report_date": account_report_date,
        "published_at": datetime.now(UTC).isoformat(),
        "source_label": source_dir.name,
        "observation_only": True,
        "formal_use_allowed": False,
        "validation": {
            "passed": args.validation_passed,
            "failed": args.validation_failed,
            "scope": "交付物一致性校验，不构成外部市场真值复核",
        },
        "warnings": [
            "研究材料，只读观察，不构成正式指标、限额依据或交易信号。",
            "材料日、曲线日与账户报告日不同，使用时必须保留日期标签。",
        ],
        "artifacts": artifact_rows,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_write(output_dir / "manifest.json", manifest_bytes)
    print(json.dumps({"status": "published", "bundle_id": manifest["bundle_id"], "artifacts": len(artifact_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
