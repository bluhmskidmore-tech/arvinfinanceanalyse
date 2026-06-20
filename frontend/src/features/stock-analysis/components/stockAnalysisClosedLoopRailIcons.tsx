import {
  BarChartOutlined,
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

export type ClosedLoopRailKey = "entry_gate" | "adversarial_gate" | "risk_exit" | "replay" | "lineage";

export function closedLoopRailIcon(key: ClosedLoopRailKey) {
  if (key === "entry_gate") return <LineChartOutlined />;
  if (key === "adversarial_gate") return <ThunderboltOutlined />;
  if (key === "risk_exit") return <FireOutlined />;
  if (key === "replay") return <BarChartOutlined />;
  return <DatabaseOutlined />;
}
