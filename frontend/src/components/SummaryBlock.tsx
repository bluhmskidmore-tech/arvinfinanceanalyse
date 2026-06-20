import { Tag } from "antd";

import "./SummaryBlock.css";

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
        <div className="summary-block__title">
          {title}
        </div>
      ) : null}
      <p className="summary-block__content">
        {content}
      </p>
      {tags && tags.length > 0 ? (
        <div className="summary-block__tags">
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
