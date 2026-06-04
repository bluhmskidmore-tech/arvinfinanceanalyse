import { Button, Card, Spin } from "antd";
import type { CSSProperties, ReactNode } from "react";
import { displayTokens } from "../theme/displayTokens";
import "./SectionCard.css";

export type SectionCardProps = {
  title: string;
  extra?: ReactNode;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  children: ReactNode;
  noPadding?: boolean;
  style?: CSSProperties;
};

export function SectionCard({
  title,
  extra,
  loading = false,
  error = false,
  onRetry,
  children,
  noPadding = false,
  style,
}: SectionCardProps) {
  const cardStyle: CSSProperties = {
    background: displayTokens.surface.section,
    border: displayTokens.surface.sectionBorder,
    boxShadow: displayTokens.surface.sectionShadow,
    borderRadius: displayTokens.radius.section,
    ...style,
  };

  if (error) {
    return (
      <Card
        title={title}
        extra={extra}
        style={cardStyle}
        styles={{ body: { padding: noPadding ? 0 : undefined } }}
      >
        <div className="section-card__error">
          <span className="section-card__error-text">区块加载失败。</span>
          {onRetry ? (
            <Button type="default" onClick={onRetry}>
              重试
            </Button>
          ) : null}
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={title}
      extra={extra}
      style={cardStyle}
      styles={{ body: { padding: noPadding ? 0 : undefined } }}
    >
      <Spin spinning={loading}>{children}</Spin>
    </Card>
  );
}
