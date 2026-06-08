import {
  DatabaseOutlined,
  FireOutlined,
} from "@ant-design/icons";

import type {
  FactorScreenCandidateItem,
  FactorScreenCandidatesPayload,
  MeanReversionCandidateItem,
  MeanReversionCandidatesPayload,
} from "../../../api/contracts";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import { CompactStatusTile } from "./StockAnalysisStatusPrimitives";

type StockAnalysisObservationPreviewProps = {
  factorScreenPayload: FactorScreenCandidatesPayload | undefined;
  factorPreviewItems: FactorScreenCandidateItem[];
  factorScreenCoverageNote: string | null;
  meanReversionMarketActive: boolean;
  meanReversionPayload: MeanReversionCandidatesPayload | undefined;
  meanReversionPreviewItems: MeanReversionCandidateItem[];
  onOpenFactorDetail: (row: FactorScreenCandidateItem) => void;
  onOpenMeanReversionDetail: (row: MeanReversionCandidateItem) => void;
};

export function StockAnalysisObservationPreview({
  factorScreenPayload,
  factorPreviewItems,
  factorScreenCoverageNote,
  meanReversionMarketActive,
  meanReversionPayload,
  meanReversionPreviewItems,
  onOpenFactorDetail,
  onOpenMeanReversionDetail,
}: StockAnalysisObservationPreviewProps) {
  const meanReversionCount = meanReversionMarketActive
    ? meanReversionPayload?.candidate_count ?? 0
    : "paused";

  return (
    <section
      className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
      id="stock-analysis-observation-preview"
      data-testid="stock-analysis-observation-preview"
    >
      <div className={SA_SECTION_HEAD}>
        <div className="min-w-0">
          <p className={SA_SECTION_EYEBROW}>多策略观察池</p>
          <h2 className={SA_CARD_TITLE}>Factor / mean-reversion pool</h2>
          <div className="stock-analysis-page__lower-signal-strip" aria-label="Observation pool status">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
              <DatabaseOutlined aria-hidden="true" /> Factor {factorScreenPayload?.candidate_count ?? 0}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-600">
              <FireOutlined aria-hidden="true" /> Mean reversion {meanReversionCount}
            </span>
          </div>
        </div>
        <span className={SA_PILL}>
          Factor {factorScreenPayload?.candidate_count ?? 0} / Mean reversion {meanReversionCount}
        </span>
      </div>

      <div className="stock-analysis-page__observation-preview-grid">
        <div className="stock-analysis-page__observation-preview-panel">
          <h3>Factor top {factorPreviewItems.length || 0}</h3>
          {!factorScreenPayload ? (
            <CompactStatusTile
              icon={<DatabaseOutlined />}
              label="Factor"
              value="Pending"
              tone="warning"
              testId="stock-analysis-factor-preview-empty"
            />
          ) : factorPreviewItems.length === 0 ? (
            <CompactStatusTile
              icon={<DatabaseOutlined />}
              label="Factor"
              value="0 candidates"
              testId="stock-analysis-factor-preview-empty"
            />
          ) : (
            <div className="stock-analysis-page__table-wrap">
              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Stock</th>
                    <th scope="col">Sector</th>
                    <th scope="col">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {factorPreviewItems.map((row) => (
                    <tr
                      key={row.stock_code}
                      className="stock-analysis-page__row--clickable"
                      data-testid={`factor-preview-row-${row.stock_code}`}
                      onClick={() => onOpenFactorDetail(row)}
                    >
                      <td className="stock-analysis-page__table-number">{row.rank}</td>
                      <td>
                        {row.stock_name}
                        <small className="stock-analysis-page__tabular"> {row.stock_code}</small>
                      </td>
                      <td>{row.sector_name}</td>
                      <td className="stock-analysis-page__table-number">{row.score.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {factorScreenCoverageNote ? (
            <p className="stock-analysis-page__footnote">{factorScreenCoverageNote}</p>
          ) : null}
        </div>

        <div className="stock-analysis-page__observation-preview-panel">
          <h3>Mean reversion {meanReversionMarketActive ? "top" : ""}</h3>
          {!meanReversionMarketActive ? (
            <CompactStatusTile
              icon={<FireOutlined />}
              label="Mean reversion"
              value="Paused"
              tone="warning"
              testId="stock-analysis-mean-reversion-preview-empty"
            />
          ) : !meanReversionPayload ? (
            <CompactStatusTile
              icon={<FireOutlined />}
              label="Mean reversion"
              value="Pending"
              tone="warning"
              testId="stock-analysis-mean-reversion-preview-empty"
            />
          ) : meanReversionPreviewItems.length === 0 ? (
            <CompactStatusTile
              icon={<FireOutlined />}
              label="Mean reversion"
              value="0 candidates"
              testId="stock-analysis-mean-reversion-preview-empty"
            />
          ) : (
            <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
              {meanReversionPreviewItems.map((row) => {
                const openMeanReversionDetail = () => onOpenMeanReversionDetail(row);

                return (
                  <li
                    key={row.stock_code}
                    className="stock-analysis-page__mean-reversion-row stock-analysis-page__row--clickable"
                    data-testid={`mean-reversion-preview-row-${row.stock_code}`}
                    onClick={openMeanReversionDetail}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openMeanReversionDetail();
                      }
                    }}
                  >
                    <span>
                      #{row.rank} {row.stock_name}{" "}
                      <small className="stock-analysis-page__tabular">{row.stock_code}</small>
                    </span>
                    <span className="stock-analysis-page__mean-reversion-metrics">
                      <span>{row.sector_name}</span>
                      <span className="stock-analysis-page__mean-reversion-dd">
                        20d drawdown {(row.drawdown_20d * 100).toFixed(1)}%
                      </span>
                      <span>Score {row.score.toFixed(2)}</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
