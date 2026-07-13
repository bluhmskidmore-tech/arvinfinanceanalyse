import { describe, expect, it } from "vitest";

import type { LivermoreStrategyPayload } from "../api/contracts";
import {
  buildThemeBreakoutCards,
  buildThemeBreakoutPanelSummary,
  buildThemeEvidenceStateRows,
  localizeThemeSourceKind,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";

function currentOverlayPayload(): LivermoreStrategyPayload {
  return {
    theme_breakout: {
      as_of_date: "2026-07-08",
      formula_version: "rv_livermore_theme_breakout_real_concept_v4",
      is_proxy: false,
      theme_count: 1,
      evidence_state: {
        concept_membership: {
          input_family: "concept_membership",
          status: "current_overlay",
          state: "current_overlay",
          concept_source_kind: "tushare_current_overlay",
          source_kind: "tushare_ths_current_overlay",
          member_count: 12,
          matched_row_count: 1,
          point_in_time: false,
          historical_use_allowed: false,
          message:
            "Current Tushare THS concept overlay is available for the latest observation date; it is non-point-in-time and remains partial evidence.",
        },
      },
      items: [
        {
          rank: 1,
          as_of_date: "2026-07-08",
          theme_key: "concept:C001",
          theme_name: "机器人",
          source_kind: "tushare_current_overlay",
          parent_sector_code: "801730",
          parent_sector_name: "机械设备",
          parent_sector_rank: 2,
          member_count: 1,
          advance_count: 1,
          advance_ratio: 1,
          strong_stock_count: 1,
          limit_stock_count: 0,
          avg_pctchange: 4.2,
          avg_turn: 3.1,
          avg_amplitude: 5.4,
          movement_event_count: 1,
          observation_only: true,
          reason: "Observation-only leaders are available.",
          items: [
            {
              stock_code: "000001.SZ",
              stock_name: "样本股份",
              sector_code: "801730",
              sector_name: "机械设备",
              sector_rank: 2,
              open: 10,
              high: 10.8,
              low: 9.9,
              close: 10.6,
              pctchange: 4.2,
              turn: 3.1,
              amplitude: 5.4,
              close_strength: 0.8,
              closed_up_limit: false,
              strong: true,
              concept_source_kind: "tushare_current_overlay",
            },
          ],
        },
      ],
    },
  } as unknown as LivermoreStrategyPayload;
}

describe("stock-analysis theme evidence model", () => {
  it("preserves parent and nested current-overlay provenance as observation-only copy", () => {
    const payload = currentOverlayPayload();
    const cards = buildThemeBreakoutCards(payload);

    expect(localizeThemeSourceKind("tushare_current_overlay", false)).toBe("当前概念覆盖");
    expect(cards[0]).toMatchObject({
      sourceKindLabel: "当前概念覆盖",
      boundaryLabel: "当前覆盖 · 非时点 · 不可历史使用 · 仅观察",
    });
    expect(cards[0].leaders[0]).toMatchObject({
      sourceKindLabel: "当前概念覆盖",
    });
  });

  it("renders current overlay as partial evidence rather than a ready point-in-time taxonomy", () => {
    const payload = currentOverlayPayload();
    const cards = buildThemeBreakoutCards(payload);
    const evidenceRows = buildThemeEvidenceStateRows(payload);
    const summary = buildThemeBreakoutPanelSummary({
      payload,
      cards,
      reviewCount: 0,
    });

    expect(evidenceRows[0]).toMatchObject({
      status: "current_overlay",
      statusLabel: "当前覆盖 · 非时点 · 不可历史使用 · 仅观察",
      rowCountLabel: "成分 12 / 命中 1",
    });
    expect(summary).toMatchObject({
      badgeLabel: "当前覆盖",
      tone: "warning",
      complianceDetail: "当前覆盖 · 非时点 · 不可历史使用 · 仅观察",
    });
  });
});
