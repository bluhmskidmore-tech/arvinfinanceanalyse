import * as React from "react";
import { BankOutlined, SearchOutlined } from "@ant-design/icons";
import { Card, Empty, Input, Spin } from "antd";

import type { KpiOwner } from "../../../api/contracts";

export type OwnerListProps = {
  owners: KpiOwner[];
  selectedOwnerId: number | null;
  onSelect: (owner: KpiOwner) => void;
  loading?: boolean;
};

export function OwnerList({
  owners,
  selectedOwnerId,
  onSelect,
  loading = false,
}: OwnerListProps) {
  const [searchText, setSearchText] = React.useState("");

  const filtered = React.useMemo(() => {
    const q = searchText.trim().toLowerCase();
    return owners
      .filter((o) => (q ? o.owner_name.toLowerCase().includes(q) : true))
      .sort((a, b) => a.owner_name.localeCompare(b.owner_name));
  }, [owners, searchText]);

  if (loading) {
    return (
      <Card style={{ minHeight: 400 }}>
        <div style={{ padding: 48, textAlign: "center" }}>
          <Spin />
          <div style={{ marginTop: 12, color: "#64748b" }}>加载考核对象…</div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="考核部室"
      styles={{ body: { padding: 0, maxHeight: 560, overflow: "auto" } }}
    >
      <div style={{ padding: 12, borderBottom: "1px solid #f0f0f0" }}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索部室…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      {filtered.length === 0 ? (
        <Empty style={{ padding: 24 }} description="无匹配结果" />
      ) : (
        filtered.map((owner) => {
          const sel = selectedOwnerId === owner.owner_id;
          return (
            <div
              key={owner.owner_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(owner)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(owner);
              }}
              style={{
                padding: "12px 16px",
                cursor: "pointer",
                borderLeft: sel ? "4px solid #1677ff" : "4px solid transparent",
                background: sel ? "#e6f4ff" : undefined,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    display: "grid",
                    placeItems: "center",
                    background: sel ? "#1677ff" : "#f1f5f9",
                    color: sel ? "#fff" : "#475569",
                  }}
                >
                  <BankOutlined />
                </div>
                <span
                  style={{
                    fontWeight: sel ? 600 : 400,
                    color: sel ? "#0958d9" : "#334155",
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {owner.owner_name}
                </span>
              </div>
            </div>
          );
        })
      )}
      <div
        style={{
          padding: "10px 12px",
          borderTop: "1px solid #f0f0f0",
          fontSize: 12,
          color: "#94a3b8",
          textAlign: "center",
        }}
      >
        共 <strong style={{ color: "#475569" }}>{filtered.length}</strong> 个部室
        {searchText && filtered.length !== owners.length ? (
          <span style={{ marginLeft: 4 }}>（筛选自 {owners.length}）</span>
        ) : null}
      </div>
    </Card>
  );
}

export default OwnerList;
