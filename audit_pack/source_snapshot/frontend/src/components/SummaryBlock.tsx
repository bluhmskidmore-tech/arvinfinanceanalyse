import { Tag } from "antd";

import { shellTokens } from "../theme/tokens";

export type SummaryBlockProps = {
  title: string;
  content: string;
  tags?: { label: string; color?: string }[];
};

export function SummaryBlock({ title, content, tags }: SummaryBlockProps) {
  const showTitle = title.trim().length > 0;
  return (
    <div>
      {showTitle ? (
        <div style={{ fontSize: 14, fontWeight: "bold", color: shellTokens.colorTextPrimary, marginBottom: 8 }}>
          {title}
        </div>
      ) : null}
      <p
        style={{
          margin: 0,
          fontSize: 14,
          color: "#31425b",
          lineHeight: 1.8,
        }}
      >
        {content}
      </p>
      {tags && tags.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          {tags.map((t) => (
            <Tag key={t.label} color={t.color}>
              {t.label}
            </Tag>
          ))}
        </div>
      ) : null}
    </div>
  );
}
