from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
FORBIDDEN_TOKENS = (
    "DV01",
    "KRD",
    "CS01",
    "convexity",
    "FVTPL",
    "FVOCI",
    "债券月均金额",
    "formal PnL",
)


# Display-only / fixture surfaces — labels & mocks, not pricing logic.
DISPLAY_ONLY_DIRS = (
    "features/bond-analytics/",
    "features/bond-dashboard/",
    "features/balance-analysis/",
    "features/balance-movement-analysis/",
    "features/executive-dashboard/",
    "features/liability-analytics/",
    "features/pnl-attribution/",
    "features/risk-overview/",
    "features/risk-tensor/",
    "api/",
    "mocks/",
    "test/",
)

CONTRACT_ONLY_DIRS = (
    "bond-analysis-foundation/",
)

DISPLAY_COPY_SNIPPETS = (
    "看 DV01、张量和下钻证据",
    "进入后先看风险张量、KRD 曲线与信用利差迁移。",
    "DV01 / NIM / 久期与利差",
    "DV01 / KRD / 信用利差迁移",
)


def _is_test_file(path: Path) -> bool:
    return path.name.endswith((".test.ts", ".test.tsx"))


def _is_display_only(path: Path) -> bool:
    rel = path.relative_to(FRONTEND_SRC).as_posix()
    return (
        _is_test_file(path)
        or any(rel.startswith(d) for d in DISPLAY_ONLY_DIRS)
        or any(rel.startswith(d) for d in CONTRACT_ONLY_DIRS)
    )


def test_frontend_source_does_not_contain_formal_finance_logic_tokens():
    if not FRONTEND_SRC.exists():
        return

    files = sorted(
        (
            f
            for f in list(FRONTEND_SRC.rglob("*.ts")) + list(FRONTEND_SRC.rglob("*.tsx"))
            if not _is_display_only(f)
        ),
        key=lambda p: p.as_posix(),
    )
    violations: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for snippet in DISPLAY_COPY_SNIPPETS:
            text = text.replace(snippet, "")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path}: {token}")

    assert not violations, "Finance logic leaked into frontend:\n" + "\n".join(violations)
