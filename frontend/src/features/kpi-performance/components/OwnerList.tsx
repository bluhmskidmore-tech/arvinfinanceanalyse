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
      <Card className="kpi-owner-list-card kpi-owner-list-card--loading">
        <div className="kpi-owner-list__state">
          <Spin />
          <div className="kpi-owner-list__loading-text">加载考核对象…</div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className="kpi-owner-list-card"
      title="考核部室"
    >
      <div className="kpi-owner-list__search">
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索部室…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      {filtered.length === 0 ? (
        <Empty className="kpi-owner-list__empty" description="无匹配结果" />
      ) : (
        filtered.map((owner) => {
          const sel = selectedOwnerId === owner.owner_id;
          const rowClassName = [
            "kpi-owner-list__row",
            sel ? "kpi-owner-list__row--selected" : null,
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div
              key={owner.owner_id}
              role="button"
              tabIndex={0}
              className={rowClassName}
              onClick={() => onSelect(owner)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(owner);
              }}
            >
              <div className="kpi-owner-list__row-content">
                <div
                  className={[
                    "kpi-owner-list__avatar",
                    sel ? "kpi-owner-list__avatar--selected" : null,
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <BankOutlined />
                </div>
                <span
                  className={[
                    "kpi-owner-list__name",
                    sel ? "kpi-owner-list__name--selected" : null,
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {owner.owner_name}
                </span>
              </div>
            </div>
          );
        })
      )}
      <div className="kpi-owner-list__footer">
        共 <strong className="kpi-owner-list__footer-count">{filtered.length}</strong> 个部室
        {searchText && filtered.length !== owners.length ? (
          <span className="kpi-owner-list__filter-note">（筛选自 {owners.length}）</span>
        ) : null}
      </div>
    </Card>
  );
}

export default OwnerList;
