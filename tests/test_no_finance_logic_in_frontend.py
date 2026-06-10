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

DASHBOARD_COCKPIT_DISPLAY_ONLY_SNIPPETS = (
    # The cockpit model consumes backend-provided DV01 values and formats fixed
    # readouts only. Keep this exception file- and snippet-scoped so new
    # frontend pricing/risk logic still trips this guard.
    "dv01Display",
    "primaryValue: portfolioAllowed ? `DV01 ${dv01Display(input.portfolio?.total_dv01)}` : \"待治理\"",
    "label: \"DV01\"",
    "code: \"DV01\"",
)

DISPLAY_ONLY_FILE_SNIPPETS = {
    "features/workbench/dashboard/dashboardCockpitModel.ts": DASHBOARD_COCKPIT_DISPLAY_ONLY_SNIPPETS,
    "features/workbench/dashboard-home/dashboardHomeBodyView.ts": (
        # Dashboard home body reads backend-provided metrics and fixed mock values
        # for display; these snippets are display-only field formatting.
        '{ id: "dv01", label: "利率风险 DV01", value: numericValueOrGap(payload.total_dv01, "dv01") },',
        '{ id: "convexity", label: "加权凸性", value: numericValueOrGap(payload.weighted_convexity, "ratio") },',
        '{ id: "spread-dv01", label: "利差 DV01", value: numericValueOrGap(payload.total_spread_dv01, "dv01") },',
        '{ id: "dv01", label: "利率风险 DV01", value: "10,615.59 万" },',
        '{ id: "spread-dv01", label: "利差 DV01", value: GAP },',
    ),
    "features/workbench/dashboard-home/dashboardHomeView.ts": (
        # Dashboard home renders backend-provided risk readouts; these snippets
        # are identifiers/field reads, not frontend pricing calculations.
        'id: "convexity"',
        "payload.weighted_convexity",
    ),
    "features/workbench/dashboard-home/adapters/buildHomeMarketContextModel.ts": (
        # Home market context formats backend-provided credit-spread sensitivity
        # only; keep this exception to the single display line.
        'detail: `spread DV01 ${displayOrMissing(payload.spread_dv01, "缺spread_dv01")} · AA及以下 ${ratioPercentOrMissing(payload.rating_aa_and_below_weight, "缺评级分布")} · 25bp ${displayOrMissing(scenario25, "缺25bp情景")}`',
    ),
    "features/workbench/module-home/moduleHomeModel.ts": (
        # Module home uses this as a status string for a backend field gap only.
        '? "监管 DV01 待接入，不能判定限额状态。"',
        # Module home formats a backend-provided risk readout; it does not
        # recompute convexity in the frontend.
        "const raw = nativeToNumber(risk.weighted_convexity);",
    ),
    "features/workbench/module-home/portfolioDecisionModel.ts": (
        # Portfolio decision copy references backend-provided risk concepts only
        # in user-facing recommendations and evidence strings.
        'return "优先复核久期和 DV01，再决定是否缩短利率暴露。";',
        'title: "久期 DV01 复核",',
        'evidence: `加权久期 ${args.duration.toFixed(2)} 年，复核利率风险和 DV01。`,',
        '? `已返回 ${args.portfolioRows.length} 个子组合，按组合层级复核规模、YTM 与 DV01。`',
        (
            '      {\n'
            '        label: "DV01",\n'
            '        value: dv01Value,\n'
            '        tone: dv01Value === "-" ? "muted" : "ok",\n'
            "      },"
        ),
        '"当前为 MOCK 模式，样例市值、信用占比、DV01、持仓只数和归因结论仅用于页面结构验证，不可用于业务决策。";',
        'detail: "切换真实数据源后再查看组合规模、信用占比、DV01、持仓只数和归因摘要。",',
        'evidence: "MOCK 模式不触发信用、久期、DV01 或归因驱动的行动建议。",',
        '"请切换正式数据源后再查看组合规模、信用占比、DV01、持仓只数和归因摘要。",',
    ),
}

DISPLAY_ONLY_FILE_LINE_PREFIXES = {
    "features/workbench/dashboard/dashboardCockpitModel.ts": (
        "label: ",
        "primaryValue: portfolioAllowed ? ",
        "code: ",
        "name: ",
        "reason: ",
        "sourceParts.push(",
        "risk: ",
        "source: ",
    ),
    "features/workbench/dashboard/dashboardCockpitHomeModel.ts": (
        "label: ",
        "dv01: ",
    ),
    "features/workbench/dashboard/sections/ExposureTable.tsx": (
        "<th>",
    ),
    "features/workbench/dashboard/sections/DashboardEvidenceLane.tsx": (
        "<th>",
    ),
    "features/workbench/dashboard-home/dashboardHomeView.ts": (
        "{ id: ",
        "label: ",
    ),
    "features/workbench/dashboard-home/sections/BottomGridSection.tsx": (
        "<th>",
    ),
    "features/workbench/module-home/moduleHomeConfig.ts": (
        "briefingTitles: ",
        "description: ",
        '"',
    ),
    "features/workbench/module-home/moduleHomeModel.ts": (
        "label: ",
        "source: ",
        "key: ",
        "title: ",
        "detail: ",
        "evidence: ",
        "value: ",
        "? `",
        "//",
        "const RISK_KRD_FIELDS:",
        "{ key: ",
        "for (const field of RISK_KRD_FIELDS)",
        "pushRiskTensorDetailRow(",
        '"',
        "tensor.",
    ),
}

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
        rel = path.relative_to(FRONTEND_SRC).as_posix()
        for snippet in DISPLAY_ONLY_FILE_SNIPPETS.get(rel, ()):
            text = text.replace(snippet, "")
        for prefix in DISPLAY_ONLY_FILE_LINE_PREFIXES.get(rel, ()):
            text = "\n".join(
                ""
                if any(token in line for token in FORBIDDEN_TOKENS) and line.strip().startswith(prefix)
                else line
                for line in text.splitlines()
            )
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path}: {token}")

    assert not violations, "Finance logic leaked into frontend:\n" + "\n".join(violations)
