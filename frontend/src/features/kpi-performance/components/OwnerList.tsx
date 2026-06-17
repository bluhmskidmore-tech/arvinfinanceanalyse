import * as React from "react";
import { BankOutlined, SearchOutlined } from "@ant-design/icons";
import { Input, Spin } from "antd";

import type { KpiOwner } from "../../../api/contracts";
import { PageStateSurface } from "../../../components/page/PagePrimitives";

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
      <PageStateSurface
        variant="loading"
        testId="kpi-owner-list-panel"
        className="kpi-owner-list-card kpi-owner-list-card--loading kpi-owner-list__state"
      >
        <Spin />
        <div className="kpi-owner-list__loading-text">加载考核对象…</div>
      </PageStateSurface>
    );
  }

  return (
    <section
      data-testid="kpi-owner-list-panel"
      className="kpi-owner-list-card"
    >
      <div className="kpi-owner-list__header">
        <span className="kpi-owner-list__eyebrow">OWNER</span>
        <h2 className="kpi-owner-list__title">考核部室</h2>
      </div>
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
        <PageStateSurface
          variant="empty"
          testId="kpi-owner-list-empty-state"
          className="kpi-owner-list__empty"
          title="无匹配结果"
          description="请调整部室搜索条件"
        />
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
    </section>
  );
}

export default OwnerList;
