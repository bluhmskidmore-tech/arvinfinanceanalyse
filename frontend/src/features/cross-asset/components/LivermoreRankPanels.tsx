import type {
  FactorScreenCandidatesPayload,
  LivermoreSectorRankPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import {
  buildLivermoreFactorCandidateRows,
  buildLivermoreSectorRankRows,
} from "../lib/crossAssetLivermoreRanks";
import { crossAssetPanelClass } from "./shared";
import "./LivermoreRankPanels.css";

function formatScore(value: number | null) {
  return value == null ? EM_DASH : value.toFixed(2);
}

function formatSignedPct(value: number | null) {
  if (value == null) {
    return { text: EM_DASH, tone: "neutral" as const };
  }
  const text = `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
  return { text, tone: value > 0 ? ("positive" as const) : value < 0 ? ("negative" as const) : ("neutral" as const) };
}

function formatPlainNumber(value: number | null) {
  return value == null ? EM_DASH : String(value);
}

function formatPe(value: number | null) {
  return value == null ? EM_DASH : value.toFixed(1);
}

export function LivermoreSectorRankPanel({
  payload,
  isLoading,
  isError,
  limit = 12,
}: {
  payload: LivermoreSectorRankPayload | null;
  isLoading: boolean;
  isError: boolean;
  limit?: number;
}) {
  const { rows, meta } = buildLivermoreSectorRankRows(payload, limit);
  const hint = `${meta.sectorCount} 个行业 · as-of ${meta.asOfDate}${meta.isProvisional ? " · 暂定公式" : ""}`;

  return (
    <section data-testid="cross-asset-livermore-sector-rank" className={`${crossAssetPanelClass} cross-asset-livermore-rank`}>
      <div className="cross-asset-livermore-rank__header">
        <div className="cross-asset-livermore-rank__heading">
          <span className="cross-asset-livermore-rank__eyebrow">Livermore 行业强度</span>
          <h2 className="cross-asset-livermore-rank__title">行业排名 Top {limit}</h2>
          <p className="cross-asset-livermore-rank__description">
            按行业综合评分排序，附行业成分只数与前两名领涨股，仅作观察口径。
          </p>
        </div>
        <div className="cross-asset-livermore-rank__meta">
          <span>{hint}</span>
        </div>
      </div>

      {isLoading ? (
        <div className="cross-asset-livermore-rank__message">正在读取行业排名。</div>
      ) : isError ? (
        <div className="cross-asset-livermore-rank__message cross-asset-livermore-rank__message--warning">
          行业排名加载失败。
        </div>
      ) : !payload || rows.length === 0 ? (
        <div className="cross-asset-livermore-rank__message cross-asset-livermore-rank__message--warning">
          暂无可展示的行业排名。
        </div>
      ) : (
        <>
          <div className="cross-asset-livermore-rank__table-wrap">
            <table className="cross-asset-livermore-rank__table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">行业</th>
                  <th scope="col">评分</th>
                  <th scope="col">均涨跌幅</th>
                  <th scope="col">龙头股</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const pct = formatSignedPct(row.avgPctChange);
                  return (
                    <tr key={`${row.rank}-${row.sectorName}`} data-testid={`cross-asset-livermore-sector-rank-row-${row.rank}`}>
                      <td className="cross-asset-livermore-rank__num">{row.rank}</td>
                      <td>
                        <div className="cross-asset-livermore-rank__sector">
                          <strong>{row.sectorName}</strong>
                          <small>{row.constituentCount == null ? EM_DASH : `${row.constituentCount} 只成分股`}</small>
                        </div>
                      </td>
                      <td className="cross-asset-livermore-rank__num">{formatScore(row.score)}</td>
                      <td className={`cross-asset-livermore-rank__num cross-asset-livermore-rank__num--${pct.tone}`}>
                        {pct.text}
                      </td>
                      <td className="cross-asset-livermore-rank__leaders">
                        {row.leaderNames.length > 0 ? row.leaderNames.join("、") : EM_DASH}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="cross-asset-livermore-rank__footer">
            <span>仅观察 · 不构成交易指令</span>
          </div>
        </>
      )}
    </section>
  );
}

export function LivermoreFactorCandidatesPanel({
  payload,
  isLoading,
  isError,
  limit = 10,
}: {
  payload: FactorScreenCandidatesPayload | null;
  isLoading: boolean;
  isError: boolean;
  limit?: number;
}) {
  const { rows, meta } = buildLivermoreFactorCandidateRows(payload, limit);
  const hint = `${meta.candidateCount} 只候选 / 样本 ${formatPlainNumber(meta.inputStockCount)} 只 · as-of ${meta.asOfDate}`;

  return (
    <section data-testid="cross-asset-livermore-factor-candidates" className={`${crossAssetPanelClass} cross-asset-livermore-rank`}>
      <div className="cross-asset-livermore-rank__header">
        <div className="cross-asset-livermore-rank__heading">
          <span className="cross-asset-livermore-rank__eyebrow">Livermore 因子筛选</span>
          <h2 className="cross-asset-livermore-rank__title">
            候选股 Top {limit}
            {meta.observationOnly ? (
              <span className="cross-asset-livermore-rank__badge">仅观察</span>
            ) : null}
          </h2>
          <p className="cross-asset-livermore-rank__description">
            按因子综合评分筛选的观察名单，展示估值与近三月涨幅事实，不生成交易指令。
          </p>
        </div>
        <div className="cross-asset-livermore-rank__meta">
          <span>{hint}</span>
        </div>
      </div>

      {isLoading ? (
        <div className="cross-asset-livermore-rank__message">正在读取因子筛选候选股。</div>
      ) : isError ? (
        <div className="cross-asset-livermore-rank__message cross-asset-livermore-rank__message--warning">
          因子筛选候选股加载失败。
        </div>
      ) : !payload || rows.length === 0 ? (
        <div className="cross-asset-livermore-rank__message cross-asset-livermore-rank__message--warning">
          暂无可展示的候选股。
        </div>
      ) : (
        <>
          <div className="cross-asset-livermore-rank__table-wrap">
            <table className="cross-asset-livermore-rank__table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">股票</th>
                  <th scope="col">行业</th>
                  <th scope="col">评分</th>
                  <th scope="col">PE</th>
                  <th scope="col">3月涨幅</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const pct = formatSignedPct(row.threeMonthReturnPct);
                  return (
                    <tr key={`${row.rank}-${row.stockCode}`} data-testid={`cross-asset-livermore-factor-row-${row.rank}`}>
                      <td className="cross-asset-livermore-rank__num">{row.rank}</td>
                      <td>
                        <div className="cross-asset-livermore-rank__stock">
                          <strong>{row.stockName}</strong>
                          <small>{row.stockCode}</small>
                        </div>
                      </td>
                      <td>{row.sectorName}</td>
                      <td className="cross-asset-livermore-rank__num">{formatScore(row.score)}</td>
                      <td className="cross-asset-livermore-rank__num">{formatPe(row.pe)}</td>
                      <td className={`cross-asset-livermore-rank__num cross-asset-livermore-rank__num--${pct.tone}`}>
                        {pct.text}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="cross-asset-livermore-rank__footer">
            <span>仅观察 · 不构成交易指令</span>
          </div>
        </>
      )}
    </section>
  );
}
