import { describe, expect, it } from "vitest";

import type {
  DashboardOverviewVM,
  DashboardPnlAttributionVM,
} from "../adapters/executiveDashboardAdapter";
import type { Numeric } from "../../../api/contracts";
import {
  selectOverviewCards,
  selectPnlMaxAbsAmount,
  selectPnlSegmentsForChart,
  selectPnlSegmentsForList,
  selectPnlTotal,
} from "./executiveDashboardSelectors";

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

function makeOverviewVM(): DashboardOverviewVM {
  return {
    title: "经营总览",
    metrics: [
      {
        id: "aum",
        label: "资产规模",
        value: makeNumeric({ raw: 123_456_000_000, display: "1,234.56 亿", sign_aware: false }),
        delta: makeNumeric({ raw: 0.023, unit: "pct", display: "+2.30%" }),
        tone: "positive",
        detail: "来自 formal balance",
        history: null,
      },
      {
        id: "yield",
        label: "年内收益",
        value: makeNumeric({ raw: 3_200_000_000, display: "+32.00 亿" }),
        delta: makeNumeric({ raw: 0.05, unit: "pct", display: "+5.00%" }),
        tone: "positive",
        detail: "来自 formal fi",
        history: null,
      },
    ],
  };
}

function makeAttributionVM(): DashboardPnlAttributionVM {
  return {
    title: "经营贡献拆解",
    total: makeNumeric({ raw: 3_200_000_000, display: "+32.00 亿" }),
    segments: [
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
      {
        id: "credit",
        label: "信用利差",
        amount: makeNumeric({ raw: 2_000_000_000, display: "+20.00 亿" }),
        tone: "positive",
      },
      {
        id: "trading",
        label: "交易损益",
        amount: makeNumeric({ raw: 0, display: "+0.00 亿" }),
        tone: "neutral",
      },
    ],
  };
}

describe("selectOverviewCards", () => {
  it("returns one card per metric in input order", () => {
    const vm = makeOverviewVM();
    const cards = selectOverviewCards(vm);
    expect(cards).toHaveLength(2);
    expect(cards[0]?.id).toBe("aum");
    expect(cards[1]?.id).toBe("yield");
  });

  it("each card preserves Numeric references from VM (no copy)", () => {
    const vm = makeOverviewVM();
    const cards = selectOverviewCards(vm);
    expect(cards[0]?.value).toBe(vm.metrics[0]?.value);
    expect(cards[0]?.delta).toBe(vm.metrics[0]?.delta);
  });

  it("returns [] when vm is null", () => {
    expect(selectOverviewCards(null)).toEqual([]);
  });
});

describe("selectPnlTotal", () => {
  it("returns the total Numeric from vm", () => {
    const vm = makeAttributionVM();
    expect(selectPnlTotal(vm)).toBe(vm.total);
  });

  it("returns null Numeric when vm is null", () => {
    const total = selectPnlTotal(null);
    expect(total).toBeNull();
  });
});

describe("selectPnlSegmentsForChart · selectPnlSegmentsForList · consistency", () => {
  it("both selectors return segment lists with IDENTICAL raw numbers in order", () => {
    const vm = makeAttributionVM();
    const chart = selectPnlSegmentsForChart(vm);
    const list = selectPnlSegmentsForList(vm);

    expect(chart.map((s) => s.id)).toEqual(list.map((s) => s.id));
    expect(chart.map((s) => s.amount.raw)).toEqual(list.map((s) => s.amount.raw));
    expect(chart.map((s) => s.amount.display)).toEqual(list.map((s) => s.amount.display));
  });

  it("returns empty array when vm is null", () => {
    expect(selectPnlSegmentsForChart(null)).toEqual([]);
    expect(selectPnlSegmentsForList(null)).toEqual([]);
  });

  it("preserves segment tone from VM (not recomputed)", () => {
    const vm = makeAttributionVM();
    const chart = selectPnlSegmentsForChart(vm);
    expect(chart.map((s) => s.tone)).toEqual(vm.segments.map((s) => s.tone));
  });
});

describe("selectPnlMaxAbsAmount", () => {
  it("returns max |raw| across segments", () => {
    const vm = makeAttributionVM();
    expect(selectPnlMaxAbsAmount(vm)).toBe(2_000_000_000);
  });

  it("treats raw=null as 0", () => {
    const vm: DashboardPnlAttributionVM = {
      ...makeAttributionVM(),
      segments: [
        {
          id: "x",
          label: "x",
          amount: makeNumeric({ raw: null, display: "—" }),
          tone: "neutral",
        },
        {
          id: "y",
          label: "y",
          amount: makeNumeric({ raw: -500, display: "-500" }),
          tone: "negative",
        },
      ],
    };
    expect(selectPnlMaxAbsAmount(vm)).toBe(500);
  });

  it("returns 0 when vm is null or empty", () => {
    expect(selectPnlMaxAbsAmount(null)).toBe(0);
    const emptyVM: DashboardPnlAttributionVM = {
      ...makeAttributionVM(),
      segments: [],
    };
    expect(selectPnlMaxAbsAmount(emptyVM)).toBe(0);
  });
});

describe("cross-selector consistency invariant", () => {
  it("the total 金额和所有 segments 的 raw 累加允许有一定差异（舍入），但两个子图读的是同一 segments.raw 序列", () => {
    const vm = makeAttributionVM();
    const chart = selectPnlSegmentsForChart(vm);
    const list = selectPnlSegmentsForList(vm);
    for (let i = 0; i < chart.length; i++) {
      expect(chart[i]?.amount.raw).toBe(list[i]?.amount.raw);
      expect(chart[i]?.amount).toBe(list[i]?.amount); // reference equality -- no copy
    }
  });
});
