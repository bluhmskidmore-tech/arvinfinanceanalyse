import type { HomeResearchCalendarModel } from "../adapters/buildHomeResearchCalendarModel";
import styles from "../dashboardHome.module.css";

type ResearchCalendarSectionProps = {
  calendar: HomeResearchCalendarModel;
};

function severityClass(severity: HomeResearchCalendarModel["items"][number]["severity"]): string {
  if (severity === "high") {
    return styles.dhCalendarSeverityHigh ?? "";
  }
  if (severity === "medium") {
    return styles.dhCalendarSeverityMedium ?? "";
  }
  return styles.dhCalendarSeverityLow ?? "";
}

export function ResearchCalendarSection({ calendar }: ResearchCalendarSectionProps) {
  return (
    <section data-testid="dashboard-home-research-calendar" className={styles.dhCalendarSection}>
      <article className={`${styles.dhCard} ${styles.dhTableCard}`}>
        <div className={styles.dhSectionTitle}>
          <span>研究日历</span>
          <span className={styles.dhCalendarWindow}>{calendar.windowLabel}</span>
        </div>
        {calendar.message ? (
          <p className={styles.dhCalendarMessage} data-testid="dashboard-home-research-calendar-message">
            {calendar.message}
          </p>
        ) : null}
        {calendar.status === "ready" && calendar.items.length > 0 ? (
          <div className={styles.dhTableCardBody}>
            <table className={styles.dhTable}>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>标题</th>
                  <th>类型</th>
                  <th>优先级</th>
                  <th>金额</th>
                </tr>
              </thead>
              <tbody>
                {calendar.items.map((item) => (
                  <tr key={item.id}>
                    <td className={styles.dhNum}>{item.date}</td>
                    <td>{item.title}</td>
                    <td>{item.kindLabel}</td>
                    <td className={severityClass(item.severity)}>{item.severity}</td>
                    <td className={styles.dhNum}>{item.amountLabel}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
