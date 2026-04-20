import type { CSSProperties, ReactNode } from "react";
import { Link } from "react-router-dom";

import { shellTokens } from "../../../theme/tokens";
import { TONE_COLOR, type Tone } from "../../../utils/tone";
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
  kind: "macro" | "supply" | "internal";
};

export type DashboardHeroMetric = {
  id: string;
  label: string;
  value: string;
  note: string;
  delta: string;
  tone: Tone;
  spark: "softUp" | "softDown" | "swing" | "flat";
};

export type DashboardJudgmentTag = {
  label: string;
  tone: "accent" | Tone;
};

export type DashboardJudgment = {
  title: string;
  body: string;
  bullets: string[];
  tags: DashboardJudgmentTag[];
};

export type DashboardAlert = {
  id: string;
  title: string;
  detail: string;
  severity: "high" | "medium" | "low";
};

const DISPLAY_FONT =
  '"Alibaba PuHuiTi 3.0", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei UI", sans-serif';

const panelStyle: CSSProperties = {
  display: "grid",
  gap: 16,
  padding: "22px clamp(18px, 1.4vw, 24px)",
  borderRadius: 28,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background:
    "linear-gradient(180deg, rgba(252, 251, 248, 0.98) 0%, rgba(247, 247, 242, 0.98) 100%)",
  boxShadow: "0 24px 60px rgba(22, 35, 46, 0.06)",
};

const sectionLabelStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: shellTokens.colorTextMuted,
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextPrimary,
  fontSize: 18,
  fontWeight: 800,
  letterSpacing: "-0.03em",
  fontFamily: DISPLAY_FONT,
};

const bodyTextStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 13,
  lineHeight: 1.75,
};

const severityPalette = {
  high: {
    bg: "#fdeceb",
    fg: "#be4137",
    border: "#f0c8c4",
    label: "高",
  },
  medium: {
    bg: "#fff4e4",
    fg: "#b76a12",
    border: "#f0d3ab",
    label: "中",
  },
  low: {
    bg: "#edf4ff",
    fg: "#2c67c9",
    border: "#d7e6fb",
    label: "低",
  },
} as const;

const calendarKindLabel = {
  macro: "宏观",
  supply: "供给",
  internal: "内部",
} as const;

const modulePalette = [
  { bg: "#edf4ff", fg: "#2c67c9", border: "#d8e6fb" },
  { bg: "#fff5e8", fg: "#c87917", border: "#f4dcc0" },
  { bg: "#f1ecff", fg: "#6f4bc4", border: "#e0d8f7" },
  { bg: "#eaf7ee", fg: "#2a8a57", border: "#d4e9da" },
] as const;

const moduleEntries = [
  {
    id: "bond-analysis",
    to: "/bond-analysis",
    title: "债券分析",
    eyebrow: "看久期、利差与持仓结构",
    question: "收益率曲线、信用利差和组合暴露现在最该看哪一段？",
    output: "进入后先看久期、Top 持仓与信用利差。",
  },
  {
    id: "cross-asset",
    to: "/cross-asset",
    title: "跨资产驱动",
    eyebrow: "看外部约束和传导",
    question: "利率、汇率、油价和风险偏好如何传导到债券定价？",
    output: "进入后先看环境得分、驱动矩阵和候选动作。",
  },
  {
    id: "balance-analysis",
    to: "/balance-analysis",
    title: "资产负债分析",
    eyebrow: "看缺口、滚续和期限错配",
    question: "短端压力、滚续节奏和错配位置具体落在哪一层？",
    output: "进入后先看净缺口、basis 与压力工作台。",
  },
  {
    id: "market-data",
    to: "/market-data",
    title: "市场数据",
    eyebrow: "看盘中上下文",
    question: "现券、资金、存单、期货和信用成交今天发生了什么？",
    output: "进入后先看利率行情、资金曲线和信用利差。",
  },
] as const;

function tagStyle(tone: DashboardJudgmentTag["tone"]): CSSProperties {
  if (tone === "accent") {
    return {
      background: shellTokens.colorAccentSoft,
      color: shellTokens.colorAccent,
      border: `1px solid ${shellTokens.colorBorderSoft}`,
    };
  }

  return {
    background: `${TONE_COLOR[tone]}18`,
    color: TONE_COLOR[tone],
    border: `1px solid ${TONE_COLOR[tone]}33`,
  };
}

function sparkPath(kind: DashboardHeroMetric["spark"]) {
  switch (kind) {
    case "softUp":
      return "M4 22 C 14 19, 22 14, 34 12 S 56 8, 82 4";
    case "softDown":
      return "M4 4 C 16 7, 26 14, 40 16 S 62 22, 82 20";
    case "swing":
      return "M4 18 C 16 22, 24 6, 38 8 S 58 24, 82 10";
    default:
      return "M4 13 C 18 13, 30 12, 44 13 S 62 13, 82 13";
  }
}

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
        gap: 12,
      }}
    >
      <div style={{ display: "grid", gap: 6 }}>
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
      {metrics.map((metric) => (
        <article
          key={metric.id}
          style={{
            position: "relative",
            overflow: "hidden",
            display: "grid",
            gap: 6,
            padding: "16px 16px 14px",
            minHeight: 126,
            borderRadius: 22,
            border: `1px solid ${shellTokens.colorBorderSoft}`,
            background: "rgba(255,255,255,0.86)",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.82)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <div style={{ display: "grid", gap: 4 }}>
              <span
                style={{
                  fontSize: 12,
                  color: shellTokens.colorTextMuted,
                  fontWeight: 700,
                }}
              >
                {metric.label}
              </span>
              <strong
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: 20,
                  lineHeight: 1.1,
                  letterSpacing: "-0.04em",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {metric.value}
              </strong>
            </div>
            <svg
              width="92"
              height="26"
              viewBox="0 0 86 26"
              aria-hidden="true"
            >
              <path
                d={sparkPath(metric.spark)}
                fill="none"
                stroke={TONE_COLOR[metric.tone]}
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <circle
                cx="82"
                cy={metric.spark === "softDown" ? 20 : metric.spark === "flat" ? 13 : 4}
                r="3.6"
                fill={TONE_COLOR[metric.tone]}
              />
            </svg>
          </div>
          <span
            style={{
              display: "inline-flex",
              width: "fit-content",
              alignItems: "center",
              padding: "3px 8px",
              borderRadius: 999,
              background: `${TONE_COLOR[metric.tone]}14`,
              color: TONE_COLOR[metric.tone],
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            {metric.delta}
          </span>
          <span
            style={{
              color: shellTokens.colorTextSecondary,
              fontSize: 12,
              lineHeight: 1.55,
            }}
          >
            {metric.note}
          </span>
        </article>
      ))}
    </div>
  );
}

export function DashboardGlobalJudgmentPanel({
  judgment,
}: {
  judgment: DashboardJudgment;
}) {
  return (
    <section data-testid="dashboard-global-judgment" style={panelStyle}>
      <DashboardSectionHeader eyebrow="First-screen Verdict" title={judgment.title} />
      <p style={{ ...bodyTextStyle, fontSize: 14 }}>{judgment.body}</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {judgment.tags.map((tag) => (
          <span
            key={tag.label}
            style={{
              ...tagStyle(tag.tone),
              display: "inline-flex",
              alignItems: "center",
              padding: "6px 12px",
              borderRadius: 999,
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            {tag.label}
          </span>
        ))}
      </div>
      <ul
        style={{
          margin: 0,
          paddingLeft: 18,
          display: "grid",
          gap: 10,
          color: shellTokens.colorTextSecondary,
          fontSize: 13,
          lineHeight: 1.6,
        }}
      >
        {judgment.bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>
    </section>
  );
}

export function DashboardModuleSnapshotPanel() {
  return (
    <section data-testid="dashboard-module-snapshot" style={panelStyle}>
      <DashboardSectionHeader eyebrow="Module Snapshot" title="模块快照" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 12,
        }}
      >
        {moduleEntries.map((entry, index) => {
          const palette = modulePalette[index % modulePalette.length];
          return (
            <Link
              key={entry.id}
              to={entry.to}
              style={{
                display: "grid",
                gap: 8,
                minHeight: 118,
                padding: 16,
                borderRadius: 20,
                border: `1px solid ${palette.border}`,
                background: "#ffffff",
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  width: "fit-content",
                  alignItems: "center",
                  padding: "4px 10px",
                  borderRadius: 999,
                  background: palette.bg,
                  color: palette.fg,
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                {entry.title}
              </span>
              <span style={{ color: shellTokens.colorTextPrimary, fontSize: 16, fontWeight: 700 }}>
                {entry.eyebrow}
              </span>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12, lineHeight: 1.55 }}>
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
      <DashboardSectionHeader eyebrow="Priority Watch" title="预警中心" />
      <div style={{ display: "grid", gap: 12 }}>
        {alerts.map((alert) => {
          const palette = severityPalette[alert.severity];
          return (
            <article
              key={alert.id}
              style={{
                display: "grid",
                gap: 6,
                paddingBottom: 12,
                borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    color: shellTokens.colorTextPrimary,
                    fontWeight: 700,
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 999,
                      background: palette.fg,
                    }}
                  />
                  {alert.title}
                </div>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: palette.bg,
                    color: palette.fg,
                    border: `1px solid ${palette.border}`,
                    fontSize: 12,
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                  }}
                >
                  {palette.label}
                </span>
              </div>
              <p style={{ ...bodyTextStyle, marginLeft: 22 }}>{alert.detail}</p>
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
      <DashboardSectionHeader eyebrow="Today" title="今日待办" />
      <div style={{ display: "grid", gap: 12 }}>
        {tasks.length === 0 ? (
          <p style={{ ...bodyTextStyle, margin: 0 }}>
            暂无待办条目。治理预警或任务类数据接入 executive 读链路后将显示在此。
          </p>
        ) : null}
        {tasks.map((task) => {
          const palette = severityPalette[task.priority];
          return (
            <article
              key={task.id}
              style={{
                display: "grid",
                gap: 8,
                paddingBottom: 12,
                borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 10,
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
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: palette.bg,
                    color: palette.fg,
                    border: `1px solid ${palette.border}`,
                    fontSize: 12,
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                  }}
                >
                  {palette.label}
                </span>
              </div>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>{task.due}</span>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function CalendarPanel({ items }: { items: DashboardHubCalendarItem[] }) {
  return (
    <section style={panelStyle}>
      <DashboardSectionHeader eyebrow="Calendar" title="关键日历" />
      <div style={{ display: "grid", gap: 12 }}>
        {items.length === 0 ? (
          <p style={{ ...bodyTextStyle, margin: 0 }}>
            暂无日历事件。宏观与供给类日程接入后将显示在此。
          </p>
        ) : null}
        {items.map((item, index) => {
          const severity = index === 0 ? "high" : index === 1 ? "medium" : "low";
          const palette = severityPalette[severity];
          return (
            <article
              key={item.id}
              style={{
                display: "grid",
                gridTemplateColumns: "84px minmax(0, 1fr) auto",
                alignItems: "center",
                gap: 14,
                paddingBottom: 12,
                borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
              }}
            >
              <span
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: 13,
                  fontWeight: 700,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {item.time.length >= 10 ? item.time.slice(5, 10) : item.time}
              </span>
              <div style={{ display: "grid", gap: 4 }}>
                <span style={{ color: shellTokens.colorTextPrimary, fontWeight: 700 }}>{item.title}</span>
                <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                  {calendarKindLabel[item.kind]}
                </span>
              </div>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: 999,
                  background: palette.bg,
                  color: palette.fg,
                  border: `1px solid ${palette.border}`,
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                {palette.label}
              </span>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function DashboardTasksCalendarPanels({
  tasks = [],
  calendarItems = [],
}: {
  tasks?: DashboardHubTask[];
  calendarItems?: DashboardHubCalendarItem[];
}) {
  return (
    <div
      data-testid="dashboard-tasks-calendar"
      style={{
        display: "grid",
        gap: 18,
        height: "100%",
      }}
    >
      <TodoPanel tasks={tasks} />
      <CalendarPanel items={calendarItems} />
    </div>
  );
}

export function DashboardModuleEntryGrid() {
  return (
    <section
      data-testid="dashboard-module-entry-grid"
      style={{
        ...panelStyle,
        gap: 18,
      }}
    >
      <DashboardSectionHeader eyebrow="Next Drill" title="模块联动入口" />
      <div className="dashboard-module-entry-grid">
        {moduleEntries.map((entry, index) => {
          const palette = modulePalette[index % modulePalette.length];
          return (
            <Link
              key={entry.id}
              to={entry.to}
              style={{
                display: "grid",
                gap: 16,
                alignContent: "start",
                minHeight: 218,
                padding: 18,
                borderRadius: 24,
                border: `1px solid ${shellTokens.colorBorderSoft}`,
                background: "#ffffff",
                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.82)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <span
                  style={{
                    display: "grid",
                    placeItems: "center",
                    width: 36,
                    height: 36,
                    borderRadius: 14,
                    background: palette.bg,
                    color: palette.fg,
                    fontWeight: 800,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {index + 1}
                </span>
                <div style={{ display: "grid", gap: 4 }}>
                  <span
                    style={{
                      color: shellTokens.colorTextPrimary,
                      fontSize: 18,
                      fontWeight: 800,
                      fontFamily: DISPLAY_FONT,
                    }}
                  >
                    {entry.title}
                  </span>
                  <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                    {entry.eyebrow}
                  </span>
                </div>
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                <span style={{ color: shellTokens.colorTextMuted, fontSize: 12, fontWeight: 700 }}>
                  回答什么？
                </span>
                <p style={{ ...bodyTextStyle, minHeight: 56 }}>{entry.question}</p>
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                <span style={{ color: shellTokens.colorTextMuted, fontSize: 12, fontWeight: 700 }}>
                  进入后先看
                </span>
                <span
                  style={{
                    color: palette.fg,
                    fontSize: 13,
                    fontWeight: 700,
                    lineHeight: 1.6,
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
