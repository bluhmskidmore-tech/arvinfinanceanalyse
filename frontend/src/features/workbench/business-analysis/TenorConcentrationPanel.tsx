import { EvidencePanel } from "../../../components/page/PagePrimitives";
import styles from "./TenorConcentrationPanel.module.css";

type GapRow = { tenor: string; netGap: string; note: string };

const GAP_ROWS: GapRow[] = [
  { tenor: "1年内净缺口", netGap: "-373.0", note: "短端滚续敏感" },
  { tenor: "1-3年净缺口", netGap: "-128.5", note: "中期再定价" },
  { tenor: "3年以上净缺口", netGap: "+96.2", note: "长久期缓冲" },
];

export function TenorConcentrationPanel() {
  return (
    <EvidencePanel heading="期限与集中度（示意）">
      <p className={styles.note}>
        下列缺口与期限为经营管理示意读数，正式阈值与口径以资产负债分析页及风控规则为准。
      </p>
      <div className={styles.list}>
        {GAP_ROWS.map((row) => (
          <div
            key={row.tenor}
            className={`${styles.row} ${
              row.netGap.startsWith("-") ? styles.rowNegative : styles.rowPositive
            }`}
          >
            <div>
              <div className={styles.rowTitle}>{row.tenor}</div>
              <div className={styles.rowNote}>{row.note}</div>
            </div>
            <div
              className={`${styles.value} ${
                row.netGap.startsWith("-") ? styles.valueNegative : styles.valuePositive
              }`}
            >
              {row.netGap} 亿
            </div>
          </div>
        ))}
      </div>
    </EvidencePanel>
  );
}
