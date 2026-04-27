import { describe, expect, it } from "vitest";

import type {
  ApiEnvelope,
  ExecutiveMetric,
  Numeric,
  OverviewPayload,
  PnlAttributionPayload,
  ResultMeta,
  VerdictPayload,
} from "../../../api/contracts";
import { adaptDashboard } from "./executiveDashboardAdapter";

function makeNumeric(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 1,
    unit: "yuan",
    display: "+1.00 亿",
    precision: 2,
    sign_aware: true,
    ...partial,
  };
}

function makeMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_test",
    basis: "analytical",
    result_kind: "executive.overview",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-18T00:00:00",
    ...partial,
  };
}

function makeOverviewEnv(
  overrides: {
    meta?: Partial<ResultMeta>;
    metrics?: ExecutiveMetric[];
  } = {},
): ApiEnvelope<OverviewPayload> {
  return {
    result_meta: makeMeta(overrides.meta),
    result: {
      title: "经营总览",
      metrics: overrides.metrics ?? [
        {
          id: "aum",
          label: "资产规模",
          caliber_label: "本币资产口径",
          value: makeNumeric({ raw: 123_456_000_000, display: "1,234.56 亿", sign_aware: false }),
          delta: makeNumeric({ raw: 0.023, unit: "pct", display: "+2.30%" }),
          tone: "positive",
          detail: "...",
        },
      ],
    },
  };
}

function makeAttributionEnv(
  overrides: {
    meta?: Partial<ResultMeta>;
    total?: Numeric;
    segments?: PnlAttributionPayload["segments"];
  } = {},
): ApiEnvelope<PnlAttributionPayload> {
  return {
    result_meta: makeMeta(overrides.meta),
    result: {
      title: "经营贡献拆解",
      total: overrides.total ?? makeNumeric({ raw: 3_200_000_000, display: "+32.00 亿" }),
      segments: overrides.segments ?? [
        {
          id: "carry",
          label: "Carry",
          amount: makeNumeric({ raw: 1_500_000_000, display: "+15.00 亿" }),
          tone: "positive",
        },
        {
          id: "roll",
          label: "Roll-down",
          amount: makeNumeric({ raw: -300_000_000, display: "-3.00 亿" }),
          tone: "negative",
        },
      ],
    },
  };
}

describe("adaptDashboard · normal path", () => {
  it("returns ok state when envelope is healthy", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv(),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.overview.state.kind).toBe("ok");
    expect(out.attribution.state.kind).toBe("ok");
    expect(out.overview.vm?.metrics).toHaveLength(1);
    expect(out.overview.vm?.metrics[0]?.value.raw).toBe(123_456_000_000);
    expect(out.overview.vm?.metrics[0]?.caliberLabel).toBe("本币资产口径");
    expect(out.attribution.vm?.total.display).toBe("+32.00 亿");
  });

  it("passes Numeric shape through untouched", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv(),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.overview.vm?.metrics[0]?.value).toMatchObject({
      raw: expect.any(Number),
      unit: "yuan",
      display: expect.any(String),
      sign_aware: false,
    });
  });
});

describe("adaptDashboard · null raw", () => {
  it("handles Numeric with raw=null gracefully", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv({
        metrics: [
          {
            id: "nim",
            label: "净息差",
            value: makeNumeric({ raw: null, unit: "pct", display: "—", sign_aware: true }),
            delta: makeNumeric({ raw: null, unit: "pct", display: "无环比" }),
            tone: "neutral",
            detail: "...",
          },
        ],
      }),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.overview.vm?.metrics[0]?.value.raw).toBeNull();
    expect(out.overview.vm?.metrics[0]?.value.display).toBe("—");
    expect(out.overview.state.kind).toBe("ok");
  });
});

describe("adaptDashboard · negative values", () => {
  it("preserves negative raw and sign_aware semantics", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv(),
      attributionEnv: makeAttributionEnv({
        total: makeNumeric({ raw: -1_200_000_000, display: "-12.00 亿" }),
        segments: [
          {
            id: "trading",
            label: "交易损益",
            amount: makeNumeric({ raw: -1_200_000_000, display: "-12.00 亿" }),
            tone: "negative",
          },
        ],
      }),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.attribution.vm?.total.raw).toBeLessThan(0);
    expect(out.attribution.vm?.segments[0]?.tone).toBe("negative");
    expect(out.attribution.vm?.segments[0]?.amount.display).toBe("-12.00 亿");
  });
});

describe("adaptDashboard · fallback_mode", () => {
  it("maps latest_snapshot fallback to fallback state", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv({
        meta: {
          fallback_mode: "latest_snapshot",
          filters_applied: {
            requested_report_date: "2026-04-10",
            effective_report_dates: { balance: "2026-04-08" },
          },
        },
      }),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.overview.state.kind).toBe("fallback");
    if (out.overview.state.kind === "fallback") {
      expect(out.overview.state.effective_date).toBe("2026-04-08");
    }
  });
});

describe("adaptDashboard · explicit_miss", () => {
  it("maps explicit_miss source_version to explicit_miss state", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv(),
      attributionEnv: makeAttributionEnv({
        meta: {
          source_version: "sv_exec_dashboard_explicit_miss_v1",
          quality_flag: "warning",
          vendor_status: "vendor_unavailable",
          filters_applied: { report_date: "2025-11-30" },
        },
      }),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.attribution.state.kind).toBe("explicit_miss");
    if (out.attribution.state.kind === "explicit_miss") {
      expect(out.attribution.state.requested_date).toBe("2025-11-30");
    }
  });
});

describe("adaptDashboard · vendor_unavailable", () => {
  it("maps vendor_unavailable meta to vendor_unavailable state", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv(),
      attributionEnv: makeAttributionEnv({
        meta: {
          vendor_status: "vendor_unavailable",
          source_version: "sv_regular",
          quality_flag: "warning",
        },
      }),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.attribution.state.kind).toBe("vendor_unavailable");
  });
});

describe("adaptDashboard · stale", () => {
  it("maps vendor_stale to stale state", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv({
        meta: { vendor_status: "vendor_stale", quality_flag: "stale" },
      }),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.overview.state.kind).toBe("stale");
  });
});

describe("adaptDashboard · loading / error", () => {
  it("returns loading when flag set", () => {
    const out = adaptDashboard({
      overviewEnv: undefined,
      attributionEnv: undefined,
      overviewLoading: true,
      overviewError: false,
      attributionLoading: true,
      attributionError: false,
    });
    expect(out.overview.state.kind).toBe("loading");
    expect(out.attribution.state.kind).toBe("loading");
  });

  it("returns error when flag set", () => {
    const out = adaptDashboard({
      overviewEnv: undefined,
      attributionEnv: undefined,
      overviewLoading: false,
      overviewError: true,
      attributionLoading: false,
      attributionError: true,
    });
    expect(out.overview.state.kind).toBe("error");
    expect(out.attribution.state.kind).toBe("error");
  });
});

describe("adaptDashboard · verdict coercion", () => {
  it("normalizes malformed verdict fields so list keys and JSX do not throw", () => {
    const noProto = Object.create(null) as object;
    const badVerdict = {
      conclusion: "定调结论",
      tone: "neutral" as const,
      reasons: [
        {
          label: noProto,
          value: noProto,
          detail: noProto,
          tone: "neutral" as const,
        },
      ],
      suggestions: [{ text: noProto, link: null }],
    };

    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv(),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
      verdictPayload: badVerdict as unknown as VerdictPayload,
    });

    expect(out.verdict?.suggestions[0]?.text).toBe("{}");
    expect(out.verdict?.reasons[0]?.value).toBe("{}");
    expect(out.verdict?.reasons[0]?.tone).toBe("neutral");
  });
});

describe("adaptDashboard · mixed effective_date", () => {
  it("resolves effective_date as 'mixed' when multiple domains diverge", () => {
    const out = adaptDashboard({
      overviewEnv: makeOverviewEnv({
        meta: {
          fallback_mode: "latest_snapshot",
          filters_applied: {
            effective_report_dates: {
              balance: "2026-04-08",
              pnl: "2026-04-07",
              liability: "2026-04-08",
              risk: "2026-04-06",
            },
          },
        },
      }),
      attributionEnv: makeAttributionEnv(),
      overviewLoading: false,
      overviewError: false,
      attributionLoading: false,
      attributionError: false,
    });
    expect(out.overview.state.kind).toBe("fallback");
    if (out.overview.state.kind === "fallback") {
      expect(out.overview.state.effective_date).toBe("mixed");
    }
  });
});
