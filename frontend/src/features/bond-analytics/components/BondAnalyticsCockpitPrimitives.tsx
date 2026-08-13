import type { CSSProperties, ReactNode } from "react";

import { designTokens } from "../../../theme/designSystem";
import { DONUT_CHART_COLORS, IB_ACCENT_BAR } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const dt = designTokens;

export function SectionCardTitle({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className={styles.sectionCardTitle}>
      <div className={styles.sectionCardTitleEyebrow}>{eyebrow}</div>
      <div className={styles.sectionCardTitleText}>{title}</div>
    </div>
  );
}

export function MobileReadoutField({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: ReactNode;
}) {
  return (
    <div className={styles.mobileReadoutField}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

export function EmptyEvidencePanel({ text }: { text: string }) {
  return <div className={styles.emptyEvidencePanel}>{text}</div>;
}

export function PendingReadModelPanel({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className={styles.pendingReadModelPanel}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

export function ProgressStack({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.progressList}>
      {items.map((item) => (
        <div key={item.key} className={styles.referenceProgressRow}>
          <div className={styles.progressHeader}>
            <span>{item.label}</span>
            <span className={styles.progressCaption}>{item.caption}</span>
          </div>
          <div className={styles.referenceProgressTrack}>
            <div
              className={styles.referenceProgressBar}
              style={{
                width: `${Math.max(8, (Math.abs(item.value) / maxValue) * 100)}%`,
                background: item.color ?? IB_ACCENT_BAR,
              }}
            />
          </div>
          {item.detail ? <div className={styles.progressDetail}>{item.detail}</div> : null}
        </div>
      ))}
    </div>
  );
}

export function MaturityColumnChart({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.maturityChart}>
      {items.slice(0, 7).map((item) => (
        <div key={item.key} className={styles.maturityColumn}>
          <span>{item.caption}</span>
          <div
            style={{
              height: `${Math.max(10, (Math.abs(item.value) / maxValue) * 118)}px`,
              background: item.color ?? IB_ACCENT_BAR,
            }}
          />
          <small>{item.label}</small>
        </div>
      ))}
    </div>
  );
}

function buildDonutGradient(items: Array<{ value: number; color?: string }>) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  if (total <= 0) {
    return "conic-gradient(var(--moss-color-neutral-200) 0 100%)";
  }

  let cursor = 0;
  const stops = items.map((item, index) => {
    const start = cursor;
    cursor += (Math.max(item.value, 0) / total) * 100;
    const color = item.color ?? DONUT_CHART_COLORS[index % DONUT_CHART_COLORS.length];
    return `${color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
  });

  return `conic-gradient(${stops.join(", ")})`;
}

export function DistributionDonut({
  items,
  center,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  center: string;
  emptyText: string;
}) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  if (items.length === 0 || total <= 0) {
    return <EmptyEvidencePanel text={emptyText} />;
  }

  return (
    <div className={styles.referenceDonutPanel}>
      <div className={styles.referenceDonutLegend}>
        {items.slice(0, 5).map((item, index) => (
          <div key={item.key} className={styles.referenceDonutLegendRow}>
            <span style={{ background: item.color ?? DONUT_CHART_COLORS[index % DONUT_CHART_COLORS.length] }} />
            <strong>{item.label}</strong>
            <em>{item.caption}</em>
          </div>
        ))}
      </div>
      <div
        className={styles.referenceDonut}
        style={{ "--donut": buildDonutGradient(items) } as CSSProperties}
      >
        <span>{center}</span>
      </div>
    </div>
  );
}

export function RegionDistributionPanel({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const topItems = items.slice(0, 8);
  const maxValue = Math.max(...topItems.map((item) => Math.abs(item.value)), 1);

  if (topItems.length === 0) {
    return (
      <div className={styles.regionConcentrationPanel}>
        <EmptyEvidencePanel text={emptyText} />
      </div>
    );
  }

  return (
    <div className={styles.regionConcentrationPanel}>
      <div className={styles.regionList}>
        {topItems.map((item) => (
          <div key={item.key} className={styles.regionRow}>
            <div className={styles.regionRowHeader}>
              <strong>{item.label}</strong>
              <span>{item.caption}</span>
            </div>
            <div className={styles.regionTrack}>
              <i
                style={{
                  width: `${Math.max(7, (Math.abs(item.value) / maxValue) * 100)}%`,
                  background: item.color ?? "var(--dh-api-blue)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
