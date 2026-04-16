import { useState } from "react";
import { Link } from "react-router-dom";

import AverageBalanceView from "../components/AverageBalanceView";

export default function AverageBalancePage() {
  const [showFullView, setShowFullView] = useState(false);

  if (showFullView) {
    return <AverageBalanceView />;
  }

  return (
    <section style={{ display: "grid", gap: 18 }}>
      <div
        style={{
          background: "linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%)",
          border: "1px solid #dbe7f5",
          borderRadius: 24,
          padding: 24,
        }}
      >
        <h1 style={{ color: "#162033", fontSize: 28, margin: 0 }}>ADB Analytical View</h1>
        <p style={{ color: "#5c6b82", lineHeight: 1.7, margin: "12px 0 0", maxWidth: 840 }}>
          ADB 是 balance-analysis 的 analytical 子视图。
        </p>
        <p style={{ color: "#5c6b82", lineHeight: 1.7, margin: "6px 0 0", maxWidth: 840 }}>
          正式资产负债口径请从 governed balance-analysis 页面进入；这里保留完整 ADB
          analytical 视图用于兼容和深入观察。
        </p>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <Link
          to="/balance-analysis"
          style={{
            alignItems: "center",
            background: "#162033",
            borderRadius: 12,
            color: "#ffffff",
            display: "inline-flex",
            fontWeight: 600,
            padding: "10px 14px",
            textDecoration: "none",
          }}
        >
          进入正式资产负债分析
        </Link>
        <button
          type="button"
          onClick={() => setShowFullView(true)}
          style={{
            background: "#ffffff",
            border: "1px solid #cddcff",
            borderRadius: 12,
            color: "#1f5eff",
            cursor: "pointer",
            fontWeight: 600,
            padding: "10px 14px",
          }}
        >
          打开完整 ADB analytical 视图
        </button>
      </div>
    </section>
  );
}
