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

const OBSERVATION_PREVIEW_DEFAULT_COUNT = 1;

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
    : "暂停";
  const visibleFactorPreviewItems = factorPreviewItems.slice(0, OBSERVATION_PREVIEW_DEFAULT_COUNT);
  const extraFactorPreviewItems = factorPreviewItems.slice(OBSERVATION_PREVIEW_DEFAULT_COUNT);
  const visibleMeanReversionPreviewItems = meanReversionPreviewItems.slice(0, OBSERVATION_PREVIEW_DEFAULT_COUNT);
  const extraMeanReversionPreviewItems = meanReversionPreviewItems.slice(OBSERVATION_PREVIEW_DEFAULT_COUNT);

  const renderFactorPreviewRow = (row: FactorScreenCandidateItem) => (
    <tr
      key={row.stock_code}
      data-testid={`factor-preview-row-${row.stock_code}`}
    >
      <td className="stock-analysis-page__table-number">{row.rank}</td>
      <td>
        <button
          aria-label={`查看${row.stock_name}（${row.stock_code}）详情`}
          className="stock-analysis-page__factor-detail-button"
          onClick={() => onOpenFactorDetail(row)}
          type="button"
        >
          <span>{row.stock_name}</span>
          <small className="stock-analysis-page__tabular"> {row.stock_code}</small>
        </button>
      </td>
      <td>{row.sector_name}</td>
      <td className="stock-analysis-page__table-number">{row.score.toFixed(4)}</td>
    </tr>
  );

  const renderMeanReversionPreviewRow = (row: MeanReversionCandidateItem) => {
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
            20日回撤{" "}
            {row.drawdown_20d != null && Number.isFinite(row.drawdown_20d)
              ? `${(row.drawdown_20d * 100).toFixed(1)}%`
              : "待补"}
          </span>
          <span>
            评分{" "}
            {row.score != null && Number.isFinite(row.score) ? row.score.toFixed(2) : "待补"}
          </span>
        </span>
      </li>
    );
  };

  return (
    <section
      className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band`}
      id="stock-analysis-observation-preview"
      data-testid="stock-analysis-observation-preview"
    >
      <div className={SA_SECTION_HEAD}>
        <div className="stock-analysis-page__min-w-0">
          <p className={SA_SECTION_EYEBROW}>多策略观察池</p>
          <h2 className={SA_CARD_TITLE}>多因子 / 超跌观察池</h2>
          <div className="stock-analysis-page__lower-signal-strip" aria-label="观察池状态">
            <span className="stock-analysis-page__signal-pill">
              <DatabaseOutlined aria-hidden="true" /> 多因子 {factorScreenPayload?.candidate_count ?? 0}
            </span>
            <span className="stock-analysis-page__signal-pill">
              <FireOutlined aria-hidden="true" /> 超跌 {meanReversionCount}
            </span>
          </div>
        </div>
        <span className={SA_PILL}>
          多因子 {factorScreenPayload?.candidate_count ?? 0} / 超跌 {meanReversionCount}
        </span>
      </div>

      <div className="stock-analysis-page__observation-preview-grid">
        <div className="stock-analysis-page__observation-preview-panel">
          <h3>多因子候选</h3>
          {!factorScreenPayload ? (
            <CompactStatusTile
              icon={<DatabaseOutlined />}
              label="多因子"
              value="待返回"
              tone="warning"
              testId="stock-analysis-factor-preview-empty"
            />
          ) : factorPreviewItems.length === 0 ? (
            <CompactStatusTile
              icon={<DatabaseOutlined />}
              label="多因子"
              value="0 个候选"
              testId="stock-analysis-factor-preview-empty"
            />
          ) : (
            <>
              <div className="stock-analysis-page__table-wrap">
                <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">标的</th>
                      <th scope="col">板块</th>
                      <th scope="col">评分</th>
                    </tr>
                  </thead>
                  <tbody>{visibleFactorPreviewItems.map(renderFactorPreviewRow)}</tbody>
                </table>
              </div>
              {extraFactorPreviewItems.length > 0 ? (
                <details
                  className="stock-analysis-page__observation-preview-more"
                  data-testid="stock-analysis-factor-preview-more"
                >
                  <summary className="stock-analysis-page__observation-preview-more-summary">
                    <span>更多候选</span>
                    <small>余 {extraFactorPreviewItems.length} 只</small>
                  </summary>
                  <div className="stock-analysis-page__table-wrap stock-analysis-page__observation-preview-extra">
                    <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                      <tbody>{extraFactorPreviewItems.map(renderFactorPreviewRow)}</tbody>
                    </table>
                  </div>
                </details>
              ) : null}
            </>
          )}
          {factorScreenCoverageNote ? (
            <p className="stock-analysis-page__footnote">{factorScreenCoverageNote}</p>
          ) : null}
        </div>

        <div className="stock-analysis-page__observation-preview-panel">
          <h3>{meanReversionMarketActive ? "超跌候选" : "超跌状态"}</h3>
          {!meanReversionMarketActive ? (
            <CompactStatusTile
              icon={<FireOutlined />}
              label="超跌"
              value="暂停"
              tone="warning"
              testId="stock-analysis-mean-reversion-preview-empty"
            />
          ) : !meanReversionPayload ? (
            <CompactStatusTile
              icon={<FireOutlined />}
              label="超跌"
              value="待返回"
              tone="warning"
              testId="stock-analysis-mean-reversion-preview-empty"
            />
          ) : meanReversionPreviewItems.length === 0 ? (
            <CompactStatusTile
              icon={<FireOutlined />}
              label="超跌"
              value="0 个候选"
              testId="stock-analysis-mean-reversion-preview-empty"
            />
          ) : (
            <>
              <ul className="stock-analysis-page__list stock-analysis-page__list--compact">
                {visibleMeanReversionPreviewItems.map(renderMeanReversionPreviewRow)}
              </ul>
              {extraMeanReversionPreviewItems.length > 0 ? (
                <details
                  className="stock-analysis-page__observation-preview-more"
                  data-testid="stock-analysis-mean-reversion-preview-more"
                >
                  <summary className="stock-analysis-page__observation-preview-more-summary">
                    <span>更多候选</span>
                    <small>余 {extraMeanReversionPreviewItems.length} 只</small>
                  </summary>
                  <ul className="stock-analysis-page__list stock-analysis-page__list--compact stock-analysis-page__observation-preview-extra">
                    {extraMeanReversionPreviewItems.map(renderMeanReversionPreviewRow)}
                  </ul>
                </details>
              ) : null}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
