from pathlib import Path

import pytest


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
    "features/workbench/module-home/PortfolioHomeLayout.tsx": (
        # Known backend field names and evidence-copy translation only.
        '"weighted_convexity", "total_spread_dv01", "reinvestment_ratio_1y",',
        '.replace(/直接展示 headline \\/ risk-indicators 字段，不以前端估算监管 DV01。/g, "风险指标口径见债券分析；监管 DV01 以已核验数据为准。")',
    ),
    "features/workbench/module-home/portfolioHomeViewModel.ts": (
        # These readouts format backend KPI values; the comment describes MoM display units.
        "* 收益率/票息/利差用 bp 差，未实现损益用亿元差，规模/久期/DV01 用相对百分比。",
        'label: "DV01 合计",',
        '''? `久期 ${formatBondHeadlineKpi("weighted_duration", formalBondKpis.weighted_duration)}，DV01 ${formatBondHeadlineKpi(
                "total_dv01",
                formalBondKpis.total_dv01,
              )}，${creditTone}（信用占比 ${formatRatePercent(formalRisk.credit_ratio)}%）。`''',
        '''? `久期 ${formatBondHeadlineKpi("weighted_duration", bondKpis.weighted_duration)}，DV01 ${formatBondHeadlineKpi(
                  "total_dv01",
                  bondKpis.total_dv01,
                )}，${creditTone}（信用占比 ${formatRatePercent(risk.credit_ratio)}%，仅分析/复核）。`''',
        '? `久期 ${formatYears(formalRisk.weighted_duration)} 年，DV01 ${formatDv01Wan(formalRisk.total_dv01)} 万元，${creditTone}。`',
        '''? `久期 ${formatYears(risk.weighted_duration)} 年，DV01 ${formatDv01Wan(
                    risk.total_dv01,
                  )} 万元，${creditTone}（仅分析/复核）。`''',
        'evidence: "直接展示 headline / risk-indicators 字段，不以前端估算监管 DV01。",',
    ),
    "features/workbench/module-home/riskHomeDetailModel.ts": (
        # Static field definitions and unit formatting for backend risk-tensor values.
        'const RISK_KRD_FIELDS: ReadonlyArray<{ key: keyof RiskTensorPayload; label: string }> = [',
        '{ key: "krd_1y", label: "KRD 1Y" },',
        '{ key: "krd_3y", label: "KRD 3Y" },',
        '{ key: "krd_5y", label: "KRD 5Y" },',
        '{ key: "krd_7y", label: "KRD 7Y" },',
        '{ key: "krd_10y", label: "KRD 10Y" },',
        '{ key: "krd_30y", label: "KRD 30Y" },',
        'const RISK_ACCOUNTING_DV01_FIELDS: ReadonlyArray<{ key: RiskAccountingDv01FieldKey; label: string }> = [',
        '{ key: "ac_dv01", label: "AC DV01（摊余成本）" },',
        '{ key: "oci_dv01", label: "OCI DV01（其他综合收益）" },',
        '{ key: "tpl_dv01", label: "TPL DV01（交易性）" },',
        '{ key: "other_dv01", label: "未分类 DV01" },',
        "// 保留正负号：负缺口/空头 KRD 的方向有业务含义，与风险张量页保持一致。",
        'subtitle: "监管 / 估值 / 利率风险 / CS01 / 凸性",',
        '{ key: "regulatory_dv01", label: "监管口径 DV01", format: "wan" },',
        '{ key: "portfolio_dv01", label: "估值 DV01", format: "wan" },',
        '{ key: "rate_risk_dv01", label: "利率风险 DV01", format: "wan" },',
        '{ key: "cs01", label: "CS01", format: "wan" },',
        '{ key: "portfolio_convexity", label: "组合凸性", format: "display" },',
        'title: "会计分类 DV01",',
        'fields: RISK_ACCOUNTING_DV01_FIELDS.map((field) => ({ ...field, format: "wan" as const })),',
        'title: "KRD 明细",',
        'fields: RISK_KRD_FIELDS.map((field) => ({ ...field, format: "wan" as const })),',
    ),
    "features/workbench/module-home/riskHomeViewModel.ts": (
        # Labels, disclosure copy, and readouts of already-computed tensor fields.
        '"监管 DV01 待接入，不能判定限额状态。"',
        'label: "监管 DV01",',
        'detail: "来自 regulatory_dv01；缺失时不使用组合 DV01 替代。",',
        'label: "组合 DV01",',
        'title: "久期与 DV01",',
        '? `DV01 ${riskTensorWanWithUnit(tensor.portfolio_dv01)}，修正久期 ${riskTensorDisplay(tensor.portfolio_modified_duration)}。`',
        '? `CS01 ${riskTensorWanWithUnit(tensor.cs01)}，前五大权重 ${riskTensorRatioPercent(tensor.issuer_top5_weight)}。`',
        'evidence: "CS01 是信用债 DV01 代理；首页只提供字段摘要，不在前端重算。",',
    ),
    "features/workbench/module-home/MarketPortfolioScenarioPanel.tsx": (
        # The amount is the API's estimated_impact; only explanatory copy is removed.
        "监管口径 DV01；估算需人工复核。",
        "基于已物化监管口径 DV01 的线性冲击估算，不代表实际损益、未来利润或完整债券重估。",
        "风险口径：监管口径 DV01（MTR-RSK-001R）。范围：",
        "固定平行上行10 bp；数据口径 scenario；使用监管 DV01。需要人工复核，不提供账户拆分或利率下行情景。",
    ),
    "features/workbench/module-home/RiskOverviewPage.tsx": (
        # JSX text explains the backend buckets and chart-width display scaling.
        "KRD 按到期期限桶汇总，条形长度为读数比例",
    ),
    "features/workbench/module-home/riskHomeAdapter.ts": (
        # Caption of the backend-provided cs01 field, not a risk calculation.
        'caption: "信用债 DV01 代理 · 每 bp",',
    ),
    "features/agent/components/AgentGenericCardsGrid.tsx": (
        # Agent card body copy documents backend ownership of formal PnL only.
        "Keeps formal PnL calculations inside existing MOSS intent handlers.",
    ),
    "features/cross-asset/components/utils.ts": (
        # This token pair appears only in the display-formatting doc comment;
        # the helper formats a backend-provided CNY impact value.
        "DV01/CS01",
    ),
    "features/publication-showcase/PublicationShowcasePage.tsx": (
        # Publication showcase is static marketing/demo copy and fixture values.
        'body: "由金融规则计算久期、DV01、损益桥和分类汇总。",',
        '<MetricCard label="组合 DV01" value="820" unit="万元/bp" detail="确定性计算 · 用于利率情景估算" />',
        '["组合复盘", "portfolio_review", "持仓 · 久期 · DV01", "database"],',
        '["久期 / DV01", "规则版本 FI-RISK-2.3", "已计算", "accent"],',
        "<div><span>主要证据</span><ul><li>组合 DV01 为 820 万元/bp</li><li>5年以上久期敞口占 34%</li><li>信用走阔 20bp 情景损益 -3,420 万元</li></ul></div>",
    ),
    "features/workbench/dashboard/dashboardCockpitModel.ts": DASHBOARD_COCKPIT_DISPLAY_ONLY_SNIPPETS,
    "features/workbench/dashboard-home/dashboardHomeBodyView.ts": (
        # Dashboard home body reads backend-provided metrics and fixed mock values
        # for display; these snippets are display-only field formatting. The
        # KRDCurveRiskPayload identifier is the api-layer response type name.
        "KRDCurveRiskPayload",
        '{ id: "dv01", label: "利率风险 DV01", value: dv01WanValueOrGap(payload.total_dv01) },',
        '{ id: "convexity", label: "加权凸性", value: numericValueOrGap(payload.weighted_convexity, "ratio") },',
        '{ id: "spread-dv01", label: "利差 DV01", value: dv01WanValueOrGap(payload.total_spread_dv01) },',
        '{ id: "dv01", label: "利率风险 DV01", value: "10,615.59 万" },',
        '{ id: "spread-dv01", label: "利差 DV01", value: GAP },',
    ),
    "features/workbench/dashboard-home/DashboardHomeOptionTwoLayout.tsx": (
        # Option two dedupes the risk panel cell whose backend-provided label
        # repeats the first-screen KPI; matching the label is display plumbing.
        'metric.label.toUpperCase().includes("DV01"),',
    ),
    "features/workbench/dashboard-home/DashboardHomeOptionTwoOverview.tsx": (
        # Option two declares the backend-provided KPI's display label only.
        '{ id: "dv01-wan", label: "DV01", sourceIds: ["dv01-wan", "dv01"] },',
    ),
    "features/workbench/dashboard-home/DashboardHomeOptionTwoSupportBand.tsx": (
        # KRD strip renders backend-provided per-tenor exposures; title/aria
        # strings are display copy only.
        "DV01 是组合敞口而非市场利率，与国债收益率同卡时标题覆盖不到卡内主体面积，",
        "组合层利差 DV01 原本只存在于一个 display:none 的指标条里，全页无处可见；",
        "期限 DV01 与利差 DV01 同属敞口口径，收在这张卡的页脚而不是另开一格。",
        '各期限 DV01',
        'title={`${bucket.tenor} DV01 ${bucket.dv01Display}（利率上行 1bp 的估值敏感度）`}',
    ),
    "features/workbench/dashboard-home/dashboardHomeFirstScreenView.ts": (
        # First-screen view model labels an already supplied DV01 display value.
        'label: "DV01",',
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
            '        tone: dv01Value === EM_DASH ? "muted" : "ok",\n'
            "      },"
        ),
        '"当前为 MOCK 模式，样例市值、信用占比、DV01、持仓只数和归因结论仅用于页面结构验证，不可用于业务决策。";',
        'detail: "切换真实数据源后再查看组合规模、信用占比、DV01、持仓只数和归因摘要。",',
        'evidence: "MOCK 模式不触发信用、久期、DV01 或归因驱动的行动建议。",',
        '"请切换正式数据源后再查看组合规模、信用占比、DV01、持仓只数和归因摘要。",',
    ),
    "features/pnl/PnlBridgePage.tsx": (
        # PnL bridge translates the backend effect-availability reason code
        # non_fvtpl_basis into display copy; the accounting-basis exclusion is
        # decided in backend/app/core_finance/pnl_bridge, not here.
        'non_fvtpl_basis: "非 FVTPL 口径不计市场效应",',
    ),
}

DISPLAY_ONLY_FILE_LINE_PREFIXES = {
    "features/pnl/pnlBridgePageSupport.ts": (
        # Backend effect-availability reason translated into display copy.
        "non_fvtpl_basis: ",
    ),
    "features/workbench/dashboard-home/lib/sanitizeMetricCopy.ts": (
        # Label/detail cleanup for backend-provided metric copy only.
        "*",
        "[/",
    ),
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
    "features/workbench/dashboard-home/dashboardHomeFirstScreenMockView.ts": (
        # Mock view labels only; values are fixed display fixtures.
        "label: ",
    ),
    "features/workbench/dashboard-home/TerminalHomeFirstScreen.tsx": (
        "code: ",
        "label: ",
        "<span",
        "<td",
        "{ label: ",
    ),
    "features/workbench/dashboard-home/TerminalHomeWorkGrid.tsx": (
        "<small>",
        "note: ",
    ),
    "features/workbench/dashboard-home/sections/BottomGridSection.tsx": (
        "<th>",
    ),
    "features/workbench/module-home/ModuleWorkbenchHomePage.tsx": (
        "if (title === ",
        "return ",
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
        "subtitle: ",
        "detail: ",
        "evidence: ",
        "value: ",
        "? ",
        "? `",
        "//",
        "* ",
        "const RISK_KRD_FIELDS:",
        "const RISK_ACCOUNTING_DV01_FIELDS:",
        "{ key: ",
        "for (const field of RISK_KRD_FIELDS)",
        "for (const field of RISK_ACCOUNTING_DV01_FIELDS)",
        "const raw = nativeToNumber(",
        "pushRiskTensorDetailRow(",
        '"',
        "tensor.",
    ),
    "features/workbench/module-home/PortfolioHoldingsHeroBand.tsx": (
        "<th>",
        "row.dv01Display ? ",
    ),
    "features/workbench/module-home/PortfolioHomeLayout.tsx": (
        # Label alias map for backend-provided fact KPIs; display copy only.
        "DV01: ",
        "/**",
        "<p>",
    ),
    "features/workbench/module-home/portfolioHomeModel.ts": (
        # Portfolio home model extracted from moduleHomeModel.ts: it labels and
        # formats backend-provided risk-tensor fields (weighted_convexity,
        # total_dv01) and never recomputes them; same prefix set as its parent.
        "label: ",
        "key: ",
        "source: ",
        "const raw = nativeToNumber(",
    ),
    "features/workbench/module-home/PortfolioStructureTabPanel.tsx": (
        # Compact list header cell and source-string cleanup; display copy only.
        "<span>",
        "const fallbackMetric = ",
        "{ key: ",
        "row.dv01Display",
    ),
    "features/workbench/module-home/portfolioHomeQuickAccess.ts": (
        "description: ",
    ),
    "features/workbench/module-home/riskHomeAdapter.ts": (
        # Display adapter: formats backend risk-tensor fields (labels, 万元
        # readouts, field keys) without recomputing risk measures.
        "const RISK_KRD_FIELDS",
        "{ key: ",
        "for (const field of RISK_KRD_FIELDS)",
        "title: ",
        "label: ",
        "key: ",
        "note: ",
        "amount: ",
        "series: ",
        "convexity: ",
        "const convexity = ",
        "dv01 !== null",
        "? `",
        '? "',
        "| ",
        "/*",
        "* ",
        "DV01RiskPayload,",
        "envelope?: ",
        "function riskBondUnitsValid",
        ": ",
        "peakKrdBucket = ",
        "rows.push(",
        "push(portfolioRows, ",
        "push(creditRows, ",
    ),
    "features/workbench/module-home/RiskOverviewPage.tsx": (
        # JSX display copy for backend-provided hero/KRD values; no computation.
        'note="KRD / 收益率曲线 / 现金流窗口 / 字段级明细"',
        "{hero.",
        "<div",
        "<span",
        "<b>",
        "<p ",
        "aria-label",
        "<em>",
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


@pytest.mark.parametrize(
    "relative_path, display_copy, calculation",
    [
        (
            "features/workbench/module-home/MarketPortfolioScenarioPanel.tsx",
            '<p>监管口径 DV01；估算需人工复核。</p>',
            "const derivedDV01 = amount * duration * 0.0001;",
        ),
        (
            "features/workbench/module-home/RiskOverviewPage.tsx",
            '<p>KRD 按到期期限桶汇总，条形长度为读数比例</p>',
            "const derivedKRD = amount * duration * 0.0001;",
        ),
        (
            "features/workbench/module-home/riskHomeAdapter.ts",
            'const caption = { caption: "信用债 DV01 代理 · 每 bp", };',
            "const derivedDV01 = amount * duration * 0.0001;",
        ),
        (
            "features/workbench/module-home/PortfolioHomeLayout.tsx",
            'const fields = ["weighted_convexity", "total_spread_dv01", "reinvestment_ratio_1y",];',
            "const convexity = amount * duration * duration;",
        ),
        (
            "features/workbench/module-home/portfolioHomeViewModel.ts",
            'const metric = { label: "DV01 合计", };',
            "const derivedDV01 = amount * duration * 0.0001;",
        ),
        (
            "features/workbench/module-home/riskHomeDetailModel.ts",
            'const fields = [{ key: "krd_1y", label: "KRD 1Y" },];',
            "const derivedKRD = amount * duration * 0.0001;",
        ),
        (
            "features/workbench/module-home/riskHomeViewModel.ts",
            'const detail = { evidence: "CS01 是信用债 DV01 代理；首页只提供字段摘要，不在前端重算。", };',
            "const derivedCS01 = amount * spreadDuration * 0.0001;",
        ),
    ],
)
def test_display_copy_registration_still_rejects_finance_calculations(
    tmp_path, monkeypatch, relative_path, display_copy, calculation,
):
    monkeypatch.setitem(globals(), "FRONTEND_SRC", tmp_path)
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text(display_copy, encoding="utf-8")
    test_frontend_source_does_not_contain_formal_finance_logic_tokens()

    path.write_text(f"{display_copy}\n{calculation}\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Finance logic leaked into frontend"):
        test_frontend_source_does_not_contain_formal_finance_logic_tokens()
