import type { SectionLeadProps as SharedSectionLeadProps } from "../../../components/page/SectionLead";
import styles from "./BondAnalyticsDetailPrimitives.module.css";

export type SectionLeadProps = SharedSectionLeadProps;

/** 债券明细页的 Nocturne 节题层；共享 SectionLead 保持其他主题现状。 */
export function SectionLead({ eyebrow, title, description, testId }: SectionLeadProps) {
  return (
    <div data-testid={testId} className={styles.sectionLead}>
      <span className={styles.sectionEyebrow}>{eyebrow}</span>
      <h2 className={styles.sectionTitle}>{title}</h2>
      <p className={styles.sectionDescription}>{description}</p>
    </div>
  );
}
