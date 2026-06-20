import { Button, Card } from "antd";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import type { BondAnalyticsHeadlineTile, BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

const dt = designTokens;
const headlinePanelStyle = panelStyle(displayTokens.surface.section);
const headlineTileSurface = `linear-gradient(180deg, ${dt.color.neutral[50]} 0%, ${displayTokens.surface.section} 100%)`;

export interface BondAnalyticsHeadlineZoneProps {
  headlineTile: BondAnalyticsHeadlineTile | null;
  headlineCtaLabel: string | null;
  promotedItems: BondAnalyticsReadinessItem[];
  warningItems: BondAnalyticsReadinessItem[];
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsHeadlineZone({
  headlineTile,
  headlineCtaLabel,
  promotedItems,
  warningItems,
  onOpenModuleDetail,
}: BondAnalyticsHeadlineZoneProps) {
  return (
    <Card
      size="small"
      data-testid="bond-analysis-headline-zone"
      style={headlinePanelStyle}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.5fr) minmax(260px, 0.9fr)",
          gap: dt.space[4],
          alignItems: "start",
        }}
      >
        <div style={{ display: "grid", gap: dt.space[4] }}>
          <div style={EYEBROW}>首屏焦点</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: dt.space[3], flexWrap: "wrap" }}>
            <div style={{ display: "grid", gap: dt.space[2] }}>
              <div
                style={{
                  fontSize: dt.fontSize[30],
                  lineHeight: dt.lineHeight.tight,
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                  color: dt.color.primary[900],
                  maxWidth: 540,
                }}
              >
                只突出已经通过真值闸门的受治理内容。
              </div>
              <div style={{ color: dt.color.neutral[600], fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed, maxWidth: 620 }}>
                首屏分析位保持收窄：动作归因只有在溯源干净时才进入主位，其余模块保留为就绪状态或下钻入口。
              </div>
            </div>

            {headlineTile && headlineCtaLabel ? (
              <Button
                size="small"
                type="default"
                onClick={() => onOpenModuleDetail(headlineTile.key)}
                data-testid={`bond-analysis-open-headline-${headlineTile.key}`}
              >
                {headlineCtaLabel}
              </Button>
            ) : null}
          </div>

          {headlineTile ? (
            <button
              type="button"
              onClick={() => onOpenModuleDetail(headlineTile.key)}
              style={{
                border: `1px solid ${dt.color.neutral[200]}`,
                background: headlineTileSurface,
                borderRadius: dt.radius.xl,
                padding: dt.space[5],
                textAlign: "left",
                cursor: "pointer",
                display: "grid",
                gap: dt.space[3],
              }}
              data-testid={`bond-analysis-headline-${headlineTile.key}`}
            >
              <div style={{ ...EYEBROW, color: dt.color.primary[700] }}>{headlineTile.label}</div>
              <div
                style={{
                  fontSize: dt.fontSize[30],
                  lineHeight: 1,
                  fontWeight: 800,
                  letterSpacing: "-0.05em",
                  color: dt.color.primary[800],
                  ...tabularNumsStyle,
                }}
              >
                {headlineTile.value}
              </div>
              <div style={{ fontSize: dt.fontSize[14], fontWeight: 700, color: dt.color.info[600] }}>{headlineTile.caption}</div>
              <div style={{ fontSize: dt.fontSize[13], color: dt.color.neutral[700], lineHeight: 1.6 }}>{headlineTile.detail}</div>
            </button>
          ) : (
            <div
              style={{
                border: `1px dashed ${dt.color.neutral[300]}`,
                borderRadius: dt.radius.xl,
                padding: dt.space[4],
                background: `${dt.color.neutral[50]}D9`,
                display: "grid",
                gap: dt.space[2],
              }}
            >
              <div style={{ ...EYEBROW, color: dt.color.neutral[600] }}>闸门结果</div>
              <div style={{ fontSize: dt.fontSize[20], fontWeight: 700, color: dt.color.primary[900] }}>
                暂无模块满足主位分析条件。
              </div>
              <div style={{ color: dt.color.neutral[600], fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed }}>
                这里保持驾驶舱诚实：就绪状态、异常和下钻路径继续可见，不用推断指标填满首屏。
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            borderRadius: dt.radius.xl,
            border: `1px solid ${dt.color.neutral[200]}`,
            background: dt.color.neutral[50],
            padding: dt.space[4],
            display: "grid",
            gap: dt.space[3],
          }}
        >
          <div style={EYEBROW}>治理边界</div>

          <div style={{ display: "grid", gap: dt.space[3] }}>
            <div
              style={{
                borderRadius: dt.radius.lg,
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                background: displayTokens.surface.section,
                border: `1px solid ${dt.color.neutral[200]}`,
              }}
            >
              <div style={{ color: dt.color.primary[900], fontSize: dt.fontSize[13], fontWeight: 700 }}>当前主位</div>
              <div style={{ marginTop: dt.space[1], color: dt.color.neutral[600], fontSize: dt.fontSize[12], lineHeight: 1.55 }}>
                {promotedItems.length > 0
                  ? promotedItems.map((item) => item.label).join(", ")
                  : "暂无。只有出现可用于总览的证据后才会进入主位。"}
              </div>
            </div>
            <div
              style={{
                borderRadius: dt.radius.lg,
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                background: warningItems.length > 0 ? dt.color.warning[50] : displayTokens.surface.section,
                border:
                  warningItems.length > 0 ? `1px solid ${dt.color.warning[200]}` : `1px solid ${dt.color.neutral[200]}`,
              }}
            >
              <div style={{ color: dt.color.primary[900], fontSize: dt.fontSize[13], fontWeight: 700 }}>观察风险</div>
              <div style={{ marginTop: dt.space[1], color: dt.color.neutral[600], fontSize: dt.fontSize[12], lineHeight: 1.55 }}>
                {warningItems.length > 0
                  ? warningItems.map((item) => item.label).join(", ")
                  : "当前总览边界内没有仅预警模块。"}
              </div>
            </div>
          </div>

          <div
            style={{
              borderTop: `1px solid ${dt.color.neutral[200]}`,
              paddingTop: dt.space[3],
              color: dt.color.neutral[600],
              fontSize: dt.fontSize[12],
              lineHeight: 1.65,
            }}
          >
            后续和暂缓页面仍显示在右上侧栏，便于用户看清哪些内容被有意留在当前受治理视图之外。
          </div>
        </div>
      </div>
    </Card>
  );
}
