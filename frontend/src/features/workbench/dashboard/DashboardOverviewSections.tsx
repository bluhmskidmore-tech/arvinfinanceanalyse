import type { CSSProperties, ReactNode } from "react";
import { Link } from "react-router-dom";

import type { VerdictPayload } from "../../../api/contracts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";
import { TONE_COLOR, type Tone } from "../../../utils/tone";

import { buildSparkPath } from "./sparklinePath";
export type DashboardHubTask = {
  id: string;
  title: string;
  due: string;
  priority: "high" | "medium" | "low";
};

export type DashboardHubCalendarItem = {
  id: string;
  title: string;
  time: string;
  kind: "macro" | "supply" | "auction" | "internal";
  severity: "high" | "medium" | "low";
};

export type DashboardCalendarPanelState = {
  status: "ready" | "loading" | "no-data" | "no-high-medium" | "error";
  message?: string | null;
};

export type DashboardHeroMetric = {
  id: string;
  label: string;
  caliberLabel: string | null;
  value: string;
  note: string;
  delta: string;
  tone: Tone;
  history: number[] | null;
};

export type DashboardAlert = {
  id: string;
  title: string;
  detail: string;
  severity: "high" | "medium" | "low";
};

const sectionTitleFont = designTokens.fontFamily.sans;

const panelStyle: CSSProperties = {
  display: "grid",
  gap: designTokens.space[3],
  padding: `${designTokens.space[4]}px ${designTokens.space[4]}px`,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "#ffffff",
};

const sectionLabelStyle: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: shellTokens.colorTextMuted,
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextPrimary,
  fontSize: designTokens.fontSize[14],
  fontWeight: 700,
  letterSpacing: "-0.01em",
  fontFamily: sectionTitleFont,
};

const bodyTextStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: designTokens.fontSize[12],
  lineHeight: designTokens.lineHeight.normal,
};

const metricCaliberTagStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "2px 6px",
  borderRadius: 999,
  background: shellTokens.colorBgMuted,
  color: shellTokens.colorTextSecondary,
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: "0.02em",
  whiteSpace: "nowrap",
};

const severityPalette = {
  high: {
    bg: designTokens.color.danger[50],
    fg: designTokens.color.danger[600],
    border: designTokens.color.danger[200],
    label: "高",
  },
  medium: {
    bg: designTokens.color.warning[50],
    fg: designTokens.color.warning[600],
    border: designTokens.color.warning[200],
    label: "中",
  },
  low: {
    bg: designTokens.color.info[50],
    fg: designTokens.color.info[600],
    border: designTokens.color.info[200],
    label: "低",
  },
} as const;

const calendarKindLabel = {
  macro: "宏观",
  supply: "供给",
  auction: "招标",
  internal: "内部",
} as const;

const modulePalette = [
  {
    bg: designTokens.color.info[50],
    fg: designTokens.color.info[600],
    border: designTokens.color.info[200],
  },
  {
    bg: designTokens.color.warning[50],
    fg: designTokens.color.warning[600],
    border: designTokens.color.warning[200],
  },
  {
    bg: designTokens.color.primary[50],
    fg: designTokens.color.primary[700],
    border: designTokens.color.primary[200],
  },
  {
    bg: designTokens.color.success[50],
    fg: designTokens.color.success[600],
    border: designTokens.color.success[200],
  },
] as const;

const moduleEntries = [
  {
    id: "bond-analysis",
    to: "/bond-analysis",
    title: "债券分析",
    eyebrow: "看久期、利差与持仓结构",
    question: "收益率曲线、信用利差和组合暴露现在最该看哪一段？",
    output: "进入后先看久期、Top 持仓与信用利差。",
    spotlight: true,
  },
  {
    id: "cross-asset",
    to: "/cross-asset",
    title: "跨资产驱动",
    eyebrow: "看外部约束和传导",
    question: "利率、汇率、油价和风险偏好如何传导到债券定价？",
    output: "进入后先看环境得分、驱动矩阵和候选动作。",
    spotlight: true,
  },
  {
    id: "balance-analysis",
    to: "/balance-analysis",
    title: "资产负债分析",
    eyebrow: "看缺口、滚续和期限错配",
    question: "短端压力、滚续节奏和错配位置具体落在哪一层？",
    output: "进入后先看净缺口、basis 与压力工作台。",
    spotlight: true,
  },
  {
    id: "product-category-pnl",
    to: "/product-category-pnl",
    title: "产品损益",
    eyebrow: "看经营贡献和正式产品行",
    question: "本期经营贡献由哪些产品分类拉动，是否需要继续追到调整审计？",
    output: "进入后先看产品分类损益、FTP 与手工调整链路。",
    spotlight: true,
  },
  {
    id: "risk-overview",
    to: "/risk-overview",
    title: "风险总览",
    eyebrow: "看 DV01、张量和下钻证据",
    question: "组合风险暴露、估值压力和重点下钻现在集中在哪些维度？",
    output: "进入后先看风险张量、KRD 曲线与信用利差迁移。",
    spotlight: true,
  },
  {
    id: "market-data",
    to: "/market-data",
    title: "市场数据",
    eyebrow: "看盘中上下文",
    question: "现券、资金、存单、期货和信用成交今天发生了什么？",
    output: "进入后先看利率行情、资金曲线和信用利差。",
    spotlight: true,
  },
  {
    id: "decision-items",
    to: "/decision-items",
    title: "决策事项",
    eyebrow: "处理预警和今日确认",
    question: "哪些规则命中项需要确认、忽略或补充备注？",
    output: "进入后先看高/中优先级事项与处理状态。",
    spotlight: false,
  },
  {
    id: "pnl-bridge",
    to: "/pnl-bridge",
    title: "损益解释",
    eyebrow: "看实际、解释和残差",
    question: "今日损益由 carry、roll-down、利率、利差还是残差解释？",
    output: "进入后先看桥接汇总、效应拆解和残差质量。",
    spotlight: false,
  },
  {
    id: "positions",
    to: "/positions",
    title: "持仓透视",
    eyebrow: "定位具体券和客户暴露",
    question: "哪些持仓、客户或分布项正在驱动组合变化？",
    output: "进入后先看持仓明细、分布和客户下钻。",
    spotlight: false,
  },
  {
    id: "platform-config",
    to: "/platform-config",
    title: "中台配置",
    eyebrow: "看数据源和治理状态",
    question: "数据源、回退状态和系统健康是否支持当前业务判断？",
    output: "进入后先看系统健康检查与数据源状态。",
    spotlight: false,
  },
] as const;

function DashboardSectionHeader(props: {
  eyebrow: string;
  title: string;
  extra?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: designTokens.space[3],
      }}
    >
      <div style={{ display: "grid", gap: designTokens.space[2] }}>
        <span style={sectionLabelStyle}>{props.eyebrow}</span>
        <h2 style={sectionTitleStyle}>{props.title}</h2>
      </div>
      {props.extra}
    </div>
  );
}

export function DashboardOverviewHeroStrip({
  metrics,
}: {
  metrics: DashboardHeroMetric[];
}) {
  return (
    <div
      data-testid="dashboard-overview-hero-strip"
      className="dashboard-overview-hero-strip"
    >
      {metrics.map((metric) => {
        const toneColor = TONE_COLOR[metric.tone];
        const hist = metric.history;
        const hasRealHistory = hist != null && hist.length >= 2;
        const sparkD = buildSparkPath(metric.history ?? [], 78, 22);
        return (
          <article
            key={metric.id}
            style={{
              position: "relative",
              overflow: "hidden",
              display: "grid",
              gap: 6,
              padding: "14px 14px 12px",
              minHeight: 116,
              borderRadius: designTokens.radius.md,
              border: `1px solid ${shellTokens.colorBorderSoft}`,
              background: "#ffffff",
            }}
          >
            <span
              aria-hidden="true"
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                height: 3,
                background: toneColor,
                opacity: 0.85,
              }}
            />
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: designTokens.space[2],
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: 6,
                  minWidth: 0,
                  flex: 1,
                }}
              >
                <span
                  style={{
                    fontSize: designTokens.fontSize[12],
                    color: shellTokens.colorTextMuted,
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    minWidth: 0,
                  }}
                  title={metric.label}
                >
                  {metric.label}
                </span>
                {metric.caliberLabel ? (
                  <span style={metricCaliberTagStyle}>{metric.caliberLabel}</span>
                ) : null}
              </div>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "1px 6px",
                  borderRadius: 4,
                  background: `${toneColor}14`,
                  color: toneColor,
                  fontSize: 11,
                  fontWeight: 700,
                  ...tabularNumsStyle,
                  whiteSpace: "nowrap",
                }}
              >
                {metric.delta}
              </span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                justifyContent: "space-between",
                gap: designTokens.space[2],
              }}
            >
              <strong
                style={{
                  ...tabularNumsStyle,
                  color: shellTokens.colorTextPrimary,
                  fontSize: 26,
                  lineHeight: 1.1,
                  letterSpacing: "-0.02em",
                  fontWeight: 700,
                }}
              >
                {metric.value}
              </strong>
              <svg
                width="78"
                height="22"
                viewBox="0 0 78 22"
                aria-hidden="true"
                style={{ flexShrink: 0, marginBottom: 2 }}
              >
                <title>{hasRealHistory ? "近 30 日趋势" : "近 30 日历史尚未接入"}</title>
                <path
                  d={sparkD}
                  fill="none"
                  stroke={hasRealHistory ? toneColor : "#c9d4d2"}
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeDasharray={hasRealHistory ? undefined : "3 3"}
                  opacity={hasRealHistory ? 0.85 : 0.6}
                />
              </svg>
            </div>
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: 11,
                lineHeight: 1.45,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
              title={metric.note}
            >
              {metric.note}
            </span>
          </article>
        );
      })}
    </div>
  );
}

const suggestionEyebrowStyle: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: "0.12em",
  color: shellTokens.colorTextMuted,
};

export function DashboardGlobalJudgmentPanel({ verdict }: { verdict: VerdictPayload }) {
  const badgeTone = verdict.tone as Tone;
  return (
    <section data-testid="dashboard-global-judgment" style={panelStyle}>
      <DashboardSectionHeader
        eyebrow="定调"
        title="今日定调"
        extra={
          <span
            aria-label={`定调 ${verdict.tone}`}
            title={verdict.tone}
            style={{
              width: 10,
              height: 10,
              borderRadius: 3,
              background: TONE_COLOR[badgeTone],
              flexShrink: 0,
              marginTop: 2,
            }}
          />
        }
      />
      <strong
        style={{
          margin: 0,
          display: "block",
          color: shellTokens.colorTextPrimary,
          fontSize: designTokens.fontSize[14],
          fontWeight: 700,
          letterSpacing: "-0.02em",
          lineHeight: designTokens.lineHeight.snug,
        }}
      >
        {verdict.conclusion}
      </strong>
      {verdict.reasons.length > 0 ? (
        <div
          style={{
            display: "grid",
            gap: designTokens.space[3],
          }}
        >
          {verdict.reasons.map((reason, index) => (
            <div
              key={`${reason.label}-${index}`}
              style={{
                display: "grid",
                gridTemplateColumns: "10px minmax(0, 1fr)",
                gap: designTokens.space[2],
                alignItems: "start",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 8,
                  height: 8,
                  marginTop: 5,
                  borderRadius: "50%",
                  background: TONE_COLOR[reason.tone as Tone],
                  flexShrink: 0,
                }}
              />
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: designTokens.fontSize[12],
                    lineHeight: designTokens.lineHeight.normal,
                    color: shellTokens.colorTextPrimary,
                  }}
                >
                  <strong style={{ fontWeight: 700 }}>{reason.label}</strong>{" "}
                  <strong
                    style={{
                      ...tabularNumsStyle,
                      fontSize: designTokens.fontSize[14],
                      fontWeight: 700,
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {reason.value}
                  </strong>
                  <span style={{ color: shellTokens.colorTextSecondary }}> — {reason.detail}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <div style={{ display: "grid", gap: designTokens.space[2] }}>
        <div style={suggestionEyebrowStyle}>建议</div>
        <ul
          style={{
            margin: 0,
            paddingLeft: designTokens.space[4],
            display: "grid",
            gap: 8,
            color: shellTokens.colorTextSecondary,
            fontSize: designTokens.fontSize[12],
            lineHeight: designTokens.lineHeight.relaxed,
          }}
        >
          {verdict.suggestions.map((s, index) => (
            <li key={`${s.text}-${index}`} style={{ paddingLeft: 2 }}>
              <span style={{ color: shellTokens.colorTextPrimary }}>{s.text}</span>
              {s.link ? (
                <>
                  {" "}
                  <Link
                    to={s.link}
                    style={{
                      fontWeight: 700,
                      color: shellTokens.colorAccent,
                      textDecoration: "none",
                      whiteSpace: "nowrap",
                    }}
                  >
                    → 下钻
                  </Link>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function DashboardModuleSnapshotPanel() {
  return (
    <section data-testid="dashboard-module-snapshot" style={panelStyle}>
      <DashboardSectionHeader eyebrow="模块快照" title="模块快照" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: designTokens.space[3],
        }}
      >
        {moduleEntries
          .filter((entry) => entry.spotlight)
          .map((entry, index) => {
            const palette = modulePalette[index % modulePalette.length];
            return (
              <Link
                key={entry.id}
                to={entry.to}
                style={{
                  position: "relative",
                  display: "grid",
                  gap: designTokens.space[2],
                  minHeight: 112,
                  padding: designTokens.space[3] + 2,
                  borderRadius: designTokens.radius.md,
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  background: "#ffffff",
                  overflow: "hidden",
                  textDecoration: "none",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    bottom: 0,
                    width: 3,
                    background: palette.fg,
                    opacity: 0.7,
                  }}
                />
                <span
                  style={{
                    display: "inline-flex",
                    width: "fit-content",
                    alignItems: "center",
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: palette.bg,
                    color: palette.fg,
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.02em",
                  }}
                >
                  {entry.title}
                </span>
                <span
                  style={{
                    color: shellTokens.colorTextPrimary,
                    fontSize: designTokens.fontSize[13],
                    fontWeight: 700,
                    lineHeight: 1.35,
                  }}
                >
                  {entry.eyebrow}
                </span>
                <span
                  style={{
                    color: shellTokens.colorTextSecondary,
                    fontSize: 11,
                    lineHeight: 1.45,
                  }}
                >
                  {entry.output}
                </span>
              </Link>
            );
          })}
      </div>
    </section>
  );
}

export function DashboardAlertCenterPanel({
  alerts,
}: {
  alerts: DashboardAlert[];
}) {
  return (
    <section data-testid="dashboard-alert-center" style={panelStyle}>
      <DashboardSectionHeader eyebrow="优先关注" title="预警中心" />
      <div style={{ display: "grid", gap: designTokens.space[3] }}>
        {alerts.map((alert) => {
          const palette = severityPalette[alert.severity];
          return (
            <article
              key={alert.id}
              style={{
                display: "grid",
                gap: designTokens.space[2],
                paddingBottom: designTokens.space[3],
                borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: designTokens.space[3],
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: designTokens.space[2] + designTokens.space[1],
                    color: shellTokens.colorTextPrimary,
                    fontWeight: 700,
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: designTokens.space[3],
                      height: designTokens.space[3],
                      borderRadius: 999,
                      background: palette.fg,
                    }}
                  />
                  {alert.title}
                </div>
                <span
                  style={{
                    padding: `${designTokens.space[1]}px ${designTokens.space[2] + designTokens.space[1]}px`,
                    borderRadius: 999,
                    background: palette.bg,
                    color: palette.fg,
                    border: `1px solid ${palette.border}`,
                    fontSize: designTokens.fontSize[12],
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                  }}
                >
                  {palette.label}
                </span>
              </div>
              <p
                style={{
                  ...bodyTextStyle,
                  marginLeft: designTokens.space[5] + designTokens.space[2],
                }}
              >
                {alert.detail}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function TodoPanel({ tasks }: { tasks: DashboardHubTask[] }) {
  return (
    <section style={panelStyle}>
      <DashboardSectionHeader eyebrow="今日事项" title="今日待办" />
      <div style={{ display: "grid", gap: designTokens.space[3] }}>
        {tasks.length === 0 ? (
          <p style={{ ...bodyTextStyle, margin: 0 }}>
            暂无需要今日处理的高/中优先级事项。低优先级观察仍可在预警中心查看。
          </p>
        ) : null}
        {tasks.map((task) => {
          const palette = severityPalette[task.priority];
          return (
            <article
              key={task.id}
              style={{
                display: "grid",
                gap: designTokens.space[2],
                paddingBottom: designTokens.space[3],
                borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: designTokens.space[2] + designTokens.space[1],
                }}
              >
                <span
                  style={{
                    color: shellTokens.colorTextPrimary,
                    fontWeight: 700,
                    lineHeight: 1.55,
                  }}
                >
                  {task.title}
                </span>
                <span
                  style={{
                    padding: `${designTokens.space[1]}px ${designTokens.space[2] + designTokens.space[1]}px`,
                    borderRadius: 999,
                    background: palette.bg,
                    color: palette.fg,
                    border: `1px solid ${palette.border}`,
                    fontSize: designTokens.fontSize[12],
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                  }}
                >
                  {palette.label}
                </span>
              </div>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: designTokens.fontSize[12] }}>
                {task.due}
              </span>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function CalendarPanel({
  items,
  state,
}: {
  items: DashboardHubCalendarItem[];
  state?: DashboardCalendarPanelState;
}) {
  const resolvedState =
    state ?? (items.length > 0
      ? { status: "ready" as const, message: null }
      : {
          status: "no-data" as const,
          message: "暂无日历事件。宏观与供给类日程接入后将显示在此。",
        });

  return (
    <section style={panelStyle}>
      <DashboardSectionHeader eyebrow="关键日历" title="关键日历" />
      <div style={{ display: "grid", gap: designTokens.space[3] }}>
        {resolvedState.status !== "ready" ? (
          <p style={{ ...bodyTextStyle, margin: 0 }}>
            {resolvedState.message}
          </p>
        ) : null}
        {resolvedState.status === "ready"
          ? items.map((item) => {
              const palette = severityPalette[item.severity];
              return (
                <article
                  key={item.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: `${designTokens.space[10] + designTokens.space[5]}px minmax(0, 1fr) auto`,
                    alignItems: "center",
                    gap: designTokens.space[4] + designTokens.space[1],
                    paddingBottom: designTokens.space[3],
                    borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
                  }}
                >
                  <span
                    style={{
                      ...tabularNumsStyle,
                      color: shellTokens.colorTextPrimary,
                      fontSize: designTokens.fontSize[13],
                      fontWeight: 700,
                    }}
                  >
                    {item.time.length >= 10 ? item.time.slice(5, 10) : item.time}
                  </span>
                  <div style={{ display: "grid", gap: designTokens.space[1] }}>
                    <span style={{ color: shellTokens.colorTextPrimary, fontWeight: 700 }}>
                      {item.title}
                    </span>
                    <span
                      style={{
                        color: shellTokens.colorTextSecondary,
                        fontSize: designTokens.fontSize[12],
                      }}
                    >
                      {calendarKindLabel[item.kind]}
                    </span>
                  </div>
                  <span
                    style={{
                      padding: `${designTokens.space[1]}px ${designTokens.space[2] + designTokens.space[1]}px`,
                      borderRadius: 999,
                      background: palette.bg,
                      color: palette.fg,
                      border: `1px solid ${palette.border}`,
                      fontSize: designTokens.fontSize[12],
                      fontWeight: 700,
                    }}
                  >
                    {palette.label}
                  </span>
                </article>
              );
            })
          : null}
      </div>
    </section>
  );
}

export function DashboardTasksCalendarPanels({
  tasks = [],
  calendarItems = [],
  calendarState,
}: {
  tasks?: DashboardHubTask[];
  calendarItems?: DashboardHubCalendarItem[];
  calendarState?: DashboardCalendarPanelState;
}) {
  return (
    <div
      data-testid="dashboard-tasks-calendar"
      style={{
        display: "grid",
        gap: designTokens.space[4] + designTokens.space[2],
        height: "100%",
      }}
    >
      <TodoPanel tasks={tasks} />
      <CalendarPanel items={calendarItems} state={calendarState} />
    </div>
  );
}

export function DashboardModuleEntryGrid() {
  return (
    <section
      data-testid="dashboard-module-entry-grid"
      style={{
        ...panelStyle,
        gap: designTokens.space[4] + designTokens.space[2],
      }}
    >
      <DashboardSectionHeader eyebrow="下钻入口" title="模块联动入口" />
      <div className="dashboard-module-entry-grid">
        {moduleEntries.map((entry, index) => {
          const palette = modulePalette[index % modulePalette.length];
          return (
            <Link
              key={entry.id}
              to={entry.to}
              style={{
                position: "relative",
                display: "grid",
                gap: designTokens.space[3],
                alignContent: "start",
                minHeight: 220,
                padding: designTokens.space[4],
                borderRadius: designTokens.radius.md,
                border: `1px solid ${shellTokens.colorBorderSoft}`,
                background: "#ffffff",
                overflow: "hidden",
                textDecoration: "none",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 3,
                  background: palette.fg,
                  opacity: 0.7,
                }}
              />
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: designTokens.space[3],
                }}
              >
                <span
                  style={{
                    display: "grid",
                    placeItems: "center",
                    width: designTokens.space[4] + designTokens.space[5],
                    height: designTokens.space[4] + designTokens.space[5],
                    borderRadius: designTokens.radius.sm + designTokens.space[2],
                    background: palette.bg,
                    color: palette.fg,
                    fontWeight: 800,
                    ...tabularNumsStyle,
                  }}
                >
                  {index + 1}
                </span>
                <div style={{ display: "grid", gap: 2 }}>
                  <span
                    style={{
                      color: shellTokens.colorTextPrimary,
                      fontSize: designTokens.fontSize[14],
                      fontWeight: 700,
                      fontFamily: sectionTitleFont,
                    }}
                  >
                    {entry.title}
                  </span>
                  <span style={{ color: shellTokens.colorTextMuted, fontSize: 11 }}>
                    {entry.eyebrow}
                  </span>
                </div>
              </div>
              <div style={{ display: "grid", gap: designTokens.space[2] }}>
                <span
                  style={{
                    color: shellTokens.colorTextMuted,
                    fontSize: designTokens.fontSize[12],
                    fontWeight: 700,
                  }}
                >
                  回答什么？
                </span>
                <p style={{ ...bodyTextStyle, minHeight: designTokens.space[7] * 2 }}>
                  {entry.question}
                </p>
              </div>
              <div style={{ display: "grid", gap: designTokens.space[2] }}>
                <span
                  style={{
                    color: shellTokens.colorTextMuted,
                    fontSize: designTokens.fontSize[12],
                    fontWeight: 700,
                  }}
                >
                  进入后先看
                </span>
                <span
                  style={{
                    color: palette.fg,
                    fontSize: designTokens.fontSize[13],
                    fontWeight: 700,
                    lineHeight: designTokens.lineHeight.normal,
                  }}
                >
                  {entry.output}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
      <p style={bodyTextStyle}>
        首页负责先做状态判断、分流和优先级排序；需要展开原因链条时，再进入对应专题页继续分析。
      </p>
    </section>
  );
}
