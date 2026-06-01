import type { CSSProperties } from "react";

import type { BondRating } from "../../data-structures/BondModel";

const toneMap: Record<string, CSSProperties> = {
  AAA: { background: "#defff1", color: "#0d5c38" },
  "AA+": { background: "#e6f4ff", color: "#135b93" },
  AA: { background: "#eef2ff", color: "#3347a8" },
  "AA-": { background: "#f4edff", color: "#6b36b3" },
  A: { background: "#fff4db", color: "#8a5c00" },
  NR: { background: "#f3f4f6", color: "#4b5563" },
};

export interface RatingBadgeProps {
  rating?: BondRating | string;
  outlook?: string;
}

export function RatingBadge({ rating = "NR", outlook }: RatingBadgeProps) {
  const tone = toneMap[rating] ?? toneMap.NR;

  return (
    <span
      style={{
        ...tone,
        borderRadius: 999,
        display: "inline-flex",
        gap: 6,
        padding: "4px 10px",
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      <span>{rating}</span>
      {outlook ? <span style={{ opacity: 0.72 }}>{outlook}</span> : null}
    </span>
  );
}
