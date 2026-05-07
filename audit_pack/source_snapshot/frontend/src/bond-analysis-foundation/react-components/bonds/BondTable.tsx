import { useState } from "react";

import type { Bond, BondListQuery, BondRating } from "../../data-structures/BondModel";
import { EmptyState } from "../common/EmptyState";
import { Loading } from "../common/Loading";
import { BondTableRow } from "./BondTableRow";

export interface BondTableProps {
  bonds: Bond[];
  loading?: boolean;
  selectedBondId?: string | null;
  onSelectBond?: (bond: Bond) => void;
  onFilterChange?: (filters: BondListQuery) => void;
  onSortChange?: (sortBy: BondListQuery["sortBy"], sortOrder: BondListQuery["sortOrder"]) => void;
}

export function BondTable({
  bonds,
  loading = false,
  selectedBondId,
  onSelectBond,
  onFilterChange,
  onSortChange,
}: BondTableProps) {
  const [query, setQuery] = useState("");
  const [rating, setRating] = useState("");

  if (loading) {
    return <Loading label="正在加载债券列表" />;
  }

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <label>
          搜索
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label>
          评级
          <select value={rating} onChange={(event) => setRating(event.target.value)}>
            <option value="">全部</option>
            <option value="AAA">AAA</option>
            <option value="AA+">AA+</option>
            <option value="AA">AA</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() =>
            onFilterChange?.({
              query: query || undefined,
              ratings: rating ? [rating as BondRating] : undefined,
            })
          }
        >
          应用筛选
        </button>
      </div>

      {bonds.length === 0 ? (
        <EmptyState title="暂无债券列表" description="可以先扩大筛选范围或切换交易日。" />
      ) : (
        <div style={{ overflowX: "auto", borderRadius: 18, border: "1px solid #d0d5dd", background: "#fff" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f8fafc", textAlign: "left" }}>
                <th style={{ padding: "12px 10px" }}>动作</th>
                <th style={{ padding: "12px 10px" }}>代码</th>
                <th style={{ padding: "12px 10px" }}>发行人</th>
                <th style={{ padding: "12px 10px" }}>
                  <button type="button" onClick={() => onSortChange?.("cleanPrice", "desc")}>
                    价格
                  </button>
                </th>
                <th style={{ padding: "12px 10px" }}>
                  <button type="button" onClick={() => onSortChange?.("yieldToMaturity", "desc")}>
                    收益率
                  </button>
                </th>
                <th style={{ padding: "12px 10px" }}>收益率变动</th>
                <th style={{ padding: "12px 10px" }}>评级</th>
              </tr>
            </thead>
            <tbody>
              {bonds.map((bond) => (
                <BondTableRow
                  key={bond.bondId}
                  bond={bond}
                  selected={selectedBondId === bond.bondId}
                  onSelect={onSelectBond}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
