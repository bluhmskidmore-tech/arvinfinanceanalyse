import { Link } from "react-router-dom";

import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import {
  DASHBOARD_MOCK_CALENDAR,
  DASHBOARD_MOCK_TASKS,
} from "./dashboardHubMock";

const sectionLeadStyle = {
  margin: "0 0 16px",
  color: "#5c6b82",
  fontSize: 14,
  lineHeight: 1.7,
} as const;

const cardStyle = {
  display: "grid",
  gap: 12,
  padding: 20,
  borderRadius: 20,
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(247,250,255,0.98) 100%)",
  border: "1px solid #e4ebf5",
  minHeight: 180,
} as const;

const entryAccentStyle = {
  display: "inline-flex",
  alignItems: "center",
  width: "fit-content",
  padding: "4px 10px",
  borderRadius: 999,
  background: "#e7efff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
} as const;

const ctaStyle = {
  marginTop: "auto",
  width: "fit-content",
  fontSize: 13,
  fontWeight: 600,
  color: "#1f5eff",
  textDecoration: "none",
} as const;

const teaserChipStyle = {
  padding: "6px 10px",
  borderRadius: 999,
  background: "#eef3fb",
  color: "#4c5d75",
  fontSize: 12,
  fontWeight: 600,
} as const;

const MODULE_ENTRIES: Array<{
  key: string;
  to: string;
  title: string;
  question: string;
  output: string;
}> = [
  {
    key: "bond-analysis",
    to: "/bond-analysis",
    title: "债券分析",
    question: "利率、曲线与信用利差怎么走，当前组合应优先关注哪一段？",
    output: "当前以中段优于长端，信用以票息策略为主。",
  },
  {
    key: "cross-asset",
    to: "/cross-asset",
    title: "跨资产驱动",
    question: "宏观利率、油价、汇率和权益市场如何传导到债券定价？",
    output: "外部约束仍强，风险偏好处于修复阶段。",
  },
  {
    key: "balance-analysis",
    to: "/balance-analysis",
    title: "资产负债分析",
    question: "期限缺口、资金压力点和口径拆分分别落在哪里？",
    output: "正式缺口与压力分析仍以资产负债工作簿为主链路。",
  },
  {
    key: "market-data",
    to: "/market-data",
    title: "市场数据",
    question: "现券、资金、期货、存单和信用成交今日有哪些关键变化？",
    output: "盘中上下文与期限结构校验仍以市场页为准。",
  },
];

const priorityStyle: Record<
  (typeof DASHBOARD_MOCK_TASKS)[number]["priority"],
  { bg: string; fg: string; label: string }
> = {
  high: { bg: "#fde8e6", fg: "#b74c45", label: "高" },
  medium: { bg: "#fff3dd", fg: "#cc7a1a", label: "中" },
  low: { bg: "#e6f0ff", fg: "#1f5eff", label: "低" },
};

const calendarKindLabel: Record<
  (typeof DASHBOARD_MOCK_CALENDAR)[number]["kind"],
  string
> = {
  macro: "宏观",
  supply: "供给",
  internal: "内部",
};

export function DashboardModuleSnapshot() {
  return (
    <section data-testid="dashboard-module-snapshot" style={cardStyle}>
      <div style={{ display: "grid", gap: 8 }}>
        <span style={entryAccentStyle}>模块快照</span>
        <h2
          style={{
            margin: 0,
            fontSize: 18,
            fontWeight: 600,
            color: "#162033",
          }}
        >
          模块入口
        </h2>
      </div>
      <p style={{ ...sectionLeadStyle, marginBottom: 0 }}>
        驾驶舱只停留在编排层。明细分析、盘中观察和正式结果核对，仍然放在各自的工作台页面中。
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 14,
        }}
      >
        {MODULE_ENTRIES.map((entry) => (
          <div
            key={entry.key}
            style={{
              display: "grid",
              gap: 10,
              minHeight: 176,
              padding: 16,
              borderRadius: 16,
              background: "#ffffff",
              border: "1px solid #e8edf5",
            }}
          >
            <span style={entryAccentStyle}>{entry.title}</span>
            <span style={{ color: "#708197", fontSize: 12, lineHeight: 1.6 }}>解决问题</span>
            <span style={{ color: "#31425b", fontSize: 13, lineHeight: 1.65 }}>
              {entry.question}
            </span>
            <span style={{ color: "#708197", fontSize: 12, lineHeight: 1.6 }}>当前输出</span>
            <span style={{ color: "#162033", fontSize: 13, fontWeight: 600, lineHeight: 1.55 }}>
              {entry.output}
            </span>
            <Link to={entry.to} style={ctaStyle}>
              进入
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}

export function DashboardStructureMaturityTeaser() {
  return (
    <section data-testid="dashboard-structure-teaser" style={cardStyle}>
      <div style={{ display: "grid", gap: 8 }}>
        <span style={entryAccentStyle}>结构与期限</span>
        <h2
          style={{
            margin: 0,
            fontSize: 18,
            fontWeight: 600,
            color: "#162033",
          }}
        >
          结构概览
        </h2>
      </div>
      <p style={{ ...sectionLeadStyle, marginBottom: 0 }}>
        缺口分析、资金压力、资产负债匹配和现金流投影仍走受治理的读链路，驾驶舱只保留紧凑入口。
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <span style={teaserChipStyle}>资产 / 负债 / 全量</span>
        <span style={teaserChipStyle}>CNY / CNX 口径</span>
        <span style={teaserChipStyle}>缺口 / 压力 / 工作簿</span>
        <span style={teaserChipStyle}>正式结果元数据</span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
        }}
      >
        <div
          style={{
            padding: 14,
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e8edf5",
          }}
        >
          <div style={{ color: "#8090a8", fontSize: 12, marginBottom: 6 }}>正式工作簿</div>
          <div style={{ color: "#162033", fontWeight: 600 }}>资产负债分析</div>
        </div>
        <div
          style={{
            padding: 14,
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e8edf5",
          }}
        >
          <div style={{ color: "#8090a8", fontSize: 12, marginBottom: 6 }}>投影链路</div>
          <div style={{ color: "#162033", fontWeight: 600 }}>现金流预测</div>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <Link to="/balance-analysis" style={ctaStyle}>
          进入资产负债分析
        </Link>
        <Link to="/cashflow-projection" style={ctaStyle}>
          进入现金流预测
        </Link>
      </div>
    </section>
  );
}

export function DashboardTasksAndCalendar() {
  return (
    <div
      data-testid="dashboard-tasks-calendar"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
        gap: 18,
        height: "100%",
      }}
    >
      <AsyncSection
        title="今日待办"
        isLoading={false}
        isError={false}
        isEmpty={DASHBOARD_MOCK_TASKS.length === 0}
        onRetry={() => undefined}
        extra={
          <span
            style={{
              padding: "4px 10px",
              borderRadius: 999,
              background: "#fff3dd",
              color: "#b35a16",
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            演示数据
          </span>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          {DASHBOARD_MOCK_TASKS.map((task) => (
            <div
              key={task.id}
              style={{
                display: "grid",
                gap: 8,
                padding: 14,
                borderRadius: 14,
                border: "1px solid #e8edf5",
                background: "#ffffff",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <span style={{ fontWeight: 600, color: "#31425b", lineHeight: 1.55 }}>
                  {task.title}
                </span>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 600,
                    background: priorityStyle[task.priority].bg,
                    color: priorityStyle[task.priority].fg,
                    whiteSpace: "nowrap",
                  }}
                >
                  {priorityStyle[task.priority].label}
                </span>
              </div>
              <span style={{ color: "#8090a8", fontSize: 12 }}>{task.due}</span>
            </div>
          ))}
        </div>
      </AsyncSection>
      <AsyncSection
        title="关键日历"
        isLoading={false}
        isError={false}
        isEmpty={DASHBOARD_MOCK_CALENDAR.length === 0}
        onRetry={() => undefined}
        extra={
          <span
            style={{
              padding: "4px 10px",
              borderRadius: 999,
              background: "#fff3dd",
              color: "#b35a16",
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            演示数据
          </span>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          {DASHBOARD_MOCK_CALENDAR.map((item) => (
            <div
              key={item.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                padding: 14,
                borderRadius: 14,
                border: "1px solid #e8edf5",
                background: "#ffffff",
              }}
            >
              <div style={{ display: "grid", gap: 6 }}>
                <span style={{ fontWeight: 600, color: "#31425b" }}>{item.title}</span>
                <span style={{ color: "#8090a8", fontSize: 12 }}>{item.time}</span>
              </div>
              <span
                style={{
                  alignSelf: "start",
                  padding: "2px 8px",
                  borderRadius: 999,
                  fontSize: 11,
                  fontWeight: 600,
                  background: "#edf3ff",
                  color: "#1f5eff",
                  whiteSpace: "nowrap",
                }}
              >
                {calendarKindLabel[item.kind]}
              </span>
            </div>
          ))}
        </div>
      </AsyncSection>
    </div>
  );
}
