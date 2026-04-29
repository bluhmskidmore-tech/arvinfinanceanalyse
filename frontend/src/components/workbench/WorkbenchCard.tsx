import type { ReactNode } from "react";
import { Alert, Button, Empty, Skeleton, Tag } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { cx, tagColorForTone, toneClass } from "./utils";
import type { WorkbenchAction, WorkbenchBadge, WorkbenchDataState, WorkbenchTone } from "./types";

export interface WorkbenchCardProps {
  title: ReactNode;
  subtitle?: ReactNode;
  eyebrow?: ReactNode;
  tone?: WorkbenchTone;
  state?: WorkbenchDataState;
  stateMessage?: ReactNode;
  onRetry?: () => void;
  badges?: WorkbenchBadge[];
  actions?: WorkbenchAction[];
  children?: ReactNode;
  footer?: ReactNode;
  span?: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12;
  minHeight?: number;
  dense?: boolean;
  className?: string;
}

function StateBlock({ state, message, onRetry }: { state?: WorkbenchDataState; message?: ReactNode; onRetry?: () => void }) {
  if (!state || state === "ok" || state === "stale" || state === "fallback") return null;
  if (state === "loading") return <Skeleton active paragraph={{ rows: 5 }} />;
  if (state === "empty" || state === "explicit_miss") return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={message ?? "暂无数据"} />;
  if (state === "vendor_unavailable") return <Alert type="warning" showIcon message="供应商不可用" description={message ?? "该模块暂时无法从上游获取数据。"} />;
  return (
    <Alert
      type="error"
      showIcon
      message="数据载入失败"
      description={message ?? "请检查接口响应、数据日期或权限状态。"}
      action={onRetry ? <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>重试</Button> : undefined}
    />
  );
}

export function WorkbenchCard({
  title,
  subtitle,
  eyebrow,
  tone = "neutral",
  state = "ok",
  stateMessage,
  onRetry,
  badges = [],
  actions = [],
  children,
  footer,
  span = 4,
  minHeight,
  dense,
  className,
}: WorkbenchCardProps) {
  const blocked = state === "loading" || state === "error" || state === "empty" || state === "vendor_unavailable" || state === "explicit_miss";
  return (
    <article
      className={cx(
        "moss-card",
        `moss-card--span-${span}`,
        dense && "moss-card--dense",
        state === "stale" && "moss-card--stale",
        state === "fallback" && "moss-card--fallback",
        toneClass("moss-card", tone),
        className,
      )}
      style={minHeight ? { minHeight } : undefined}
    >
      <header className="moss-card__header">
        <div className="moss-card__heading">
          {eyebrow ? <div className="moss-card__eyebrow">{eyebrow}</div> : null}
          <h3 className="moss-card__title">{title}</h3>
          {subtitle ? <div className="moss-card__subtitle">{subtitle}</div> : null}
        </div>
        {badges.length || actions.length ? (
          <div className="moss-card__tools">
            {state === "stale" ? <Tag color="gold">Stale</Tag> : null}
            {state === "fallback" ? <Tag color="orange">Fallback</Tag> : null}
            {badges.map((badge) => (
              <Tag key={badge.key} color={tagColorForTone(badge.tone)}>
                {badge.label}
              </Tag>
            ))}
            {actions.map((action) => (
              <Button
                key={action.key}
                size="small"
                type={action.primary ? "primary" : "default"}
                danger={action.danger}
                disabled={action.disabled}
                icon={action.icon}
                onClick={action.onClick}
              >
                {action.label}
              </Button>
            ))}
          </div>
        ) : null}
      </header>
      <div className="moss-card__body">
        {blocked ? <StateBlock state={state} message={stateMessage} onRetry={onRetry} /> : children}
      </div>
      {footer && !blocked ? <footer className="moss-card__footer">{footer}</footer> : null}
    </article>
  );
}
