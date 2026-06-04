import { Button, Card, Spin } from "antd";
import type { CSSProperties, ReactNode } from "react";
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
  if (error) {
    return (
      <Card
        className="section-card"
        title={title}
        extra={extra}
        style={style}
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
      className="section-card"
      title={title}
      extra={extra}
      style={style}
      styles={{ body: { padding: noPadding ? 0 : undefined } }}
    >
      <Spin spinning={loading}>{children}</Spin>
    </Card>
  );
}
