import { Link } from "react-router-dom";

import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import {
  DASHBOARD_MOCK_CALENDAR,
  DASHBOARD_MOCK_TASKS,
} from "./dashboardHubMock";

const cardStyle = {
  display: "grid",
  gap: 10,
  padding: 20,
  borderRadius: 18,
  background: "#ffffff",
  border: "1px solid #e4ebf5",
  minHeight: 160,
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
    question: "利率、曲线、信用利差怎么走，组合该买卖什么？",
    output: "中段优于长端，信用以票息为主",
  },
  {
    key: "cross-asset",
    to: "/cross-asset",
    title: "跨资产驱动",
    question: "中美利率、原油、A股、商品对债券定价怎么传导？",
    output: "外部约束增强 / 风险偏好趋于稳定",
  },
  {
    key: "balance-analysis",
    to: "/balance-analysis",
    title: "资产负债分析",
    question: "期限缺口、成本压力、滚续安排、风险指标？",
    output: "1年内缺口 -373.0 亿 / 浮盈 68.5 亿",
  },
  {
    key: "market-data",
    to: "/market-data",
    title: "市场数据",
    question: "现券、资金、期货、存单和信用成交在盘中怎么变化？",
    output: "DR007 1.82% / AAA 3Y 45bp / 10Y 国债 1.94%",
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
    <section data-testid="dashboard-module-snapshot">
      <h2
        style={{
          margin: "0 0 12px",
          fontSize: 18,
          fontWeight: 600,
          color: "#162033",
        }}
      >
        专题入口
      </h2>
      <p
        style={{
          margin: "0 0 16px",
          color: "#5c6b82",
          fontSize: 14,
          lineHeight: 1.7,
          maxWidth: 900,
        }}
      >
        驾驶舱只做总览与分流；利率曲线细节、盘中成交与正式口径明细请在对应专题页查看。
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 18,
        }}
      >
        {MODULE_ENTRIES.map((m) => (
          <div key={m.key} style={cardStyle}>
            <span style={{ fontWeight: 600, color: "#162033", fontSize: 16 }}>{m.title}</span>
            <span style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.65 }}>{m.question}</span>
            <span style={{ color: "#162033", fontSize: 13, fontWeight: 600, lineHeight: 1.55 }}>
              {m.output}
            </span>
            <Link
              to={m.to}
              style={{
                marginTop: "auto",
                width: "fit-content",
                fontSize: 13,
                fontWeight: 600,
                color: "#1f5eff",
                textDecoration: "none",
              }}
            >
              进入 →
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
      <h2
        style={{
          margin: 0,
          fontSize: 16,
          fontWeight: 600,
          color: "#162033",
        }}
      >
        结构与期限（摘要）
      </h2>
      <p style={{ margin: 0, color: "#5c6b82", fontSize: 14, lineHeight: 1.75 }}>
        净缺口、滚续压力与现金流投影在资产负债与现金流专题中维护；此处仅提供跳转。
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <Link
          to="/balance-analysis"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#1f5eff",
            textDecoration: "none",
          }}
        >
          资产负债分析
        </Link>
        <Link
          to="/cashflow-projection"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#1f5eff",
            textDecoration: "none",
          }}
        >
          现金流预测
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
        gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        gap: 18,
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
                gap: 6,
                padding: 14,
                borderRadius: 14,
                border: "1px solid #e8edf5",
                background: "#fbfcfe",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ fontWeight: 600, color: "#31425b" }}>{task.title}</span>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 600,
                    background: priorityStyle[task.priority].bg,
                    color: priorityStyle[task.priority].fg,
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
                background: "#fbfcfe",
              }}
            >
              <div style={{ display: "grid", gap: 4 }}>
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
