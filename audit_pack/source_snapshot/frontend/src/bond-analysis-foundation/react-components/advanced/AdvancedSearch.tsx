import { useState, type FormEvent } from "react";

import type { BondSearchRequest, BondRating } from "../../data-structures/BondModel";

export interface AdvancedSearchProps {
  initialValue?: BondSearchRequest;
  onSearch?: (request: BondSearchRequest) => void;
}

export function AdvancedSearch({ initialValue, onSearch }: AdvancedSearchProps) {
  const [query, setQuery] = useState(initialValue?.query ?? "");
  const [rating, setRating] = useState(initialValue?.ratings?.[0] ?? "");
  const [yieldMin, setYieldMin] = useState(initialValue?.yieldRange?.min?.toString() ?? "");
  const [yieldMax, setYieldMax] = useState(initialValue?.yieldRange?.max?.toString() ?? "");
  const [maturityDateFrom, setMaturityDateFrom] = useState(initialValue?.maturityDateFrom ?? "");
  const [maturityDateTo, setMaturityDateTo] = useState(initialValue?.maturityDateTo ?? "");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    onSearch?.({
      query: query || undefined,
      ratings: rating ? [rating as BondRating] : undefined,
      yieldRange:
        yieldMin || yieldMax
          ? {
              min: yieldMin ? Number(yieldMin) : undefined,
              max: yieldMax ? Number(yieldMax) : undefined,
            }
          : undefined,
      maturityDateFrom: maturityDateFrom || undefined,
      maturityDateTo: maturityDateTo || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        <label>
          搜索词
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
        <label>
          到期起始
          <input value={maturityDateFrom} onChange={(event) => setMaturityDateFrom(event.target.value)} />
        </label>
        <label>
          收益率下限
          <input value={yieldMin} onChange={(event) => setYieldMin(event.target.value)} />
        </label>
        <label>
          收益率上限
          <input value={yieldMax} onChange={(event) => setYieldMax(event.target.value)} />
        </label>
        <label>
          到期结束
          <input value={maturityDateTo} onChange={(event) => setMaturityDateTo(event.target.value)} />
        </label>
      </div>
      <button type="submit">执行高级筛选</button>
    </form>
  );
}
