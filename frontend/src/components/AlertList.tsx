import "./AlertList.css";

export type AlertItem = {
  level: "danger" | "warning" | "caution" | "info";
  title: string;
  detail?: string;
  time?: string;
};

export type AlertListProps = {
  items: AlertItem[];
};

export function AlertList({ items }: AlertListProps) {
  return (
    <div className="alert-list">
      {items.map((it, idx) => (
        <div key={`${it.title}-${idx}`} className="alert-list__item">
          <span
            aria-hidden
            className={`alert-list__dot alert-list__dot--${it.level}`}
          />
          <div className="alert-list__content">
            <div className="alert-list__title">{it.title}</div>
            {it.detail ? (
              <div className="alert-list__detail">{it.detail}</div>
            ) : null}
            {it.time ? (
              <div className="alert-list__time">{it.time}</div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
