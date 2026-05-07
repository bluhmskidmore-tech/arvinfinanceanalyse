import { useEffect, useState } from "react";
import { isReservedBoundaryHttpMessage } from "../../../api/httpResponseError";
import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import "./LivermoreStrategyPanel.css";

type StockCandidate = NonNullable<LivermoreStrategyModel["stockCandidates"]>["items"][number];

type WatchPoolItem = {
  stockCode: string;
  stockName: string;
  sectorName: string;
  entryTrigger: string;
  pullbackWatch: string;
  defenseLine: string;
  addedFromDate: string | null;
};

type Props = {
  model: LivermoreStrategyModel | null;
  isLoading: boolean;
  isError: boolean;
  fetchErrorDetail?: string | null;
  onRetry: () => void;
  onRefreshGateSupplement?: () => Promise<{ status: string; computed_rows: number; message?: string }>;
};

function statusClass(status: string) {
  return `livermore-strategy-panel__status livermore-strategy-panel__status--${status}`;
}

const WATCH_POOL_STORAGE_KEY = "moss:livermore-watch-pool";

function readWatchPool(): WatchPoolItem[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(WATCH_POOL_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as WatchPoolItem[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item) => item.stockCode && item.stockName);
  } catch {
    return [];
  }
}

function writeWatchPool(items: WatchPoolItem[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(WATCH_POOL_STORAGE_KEY, JSON.stringify(items));
}

function buildWatchPoolItem(
  candidate: StockCandidate,
  addedFromDate: string | null,
): WatchPoolItem {
  return {
    stockCode: candidate.stockCode,
    stockName: candidate.stockName,
    sectorName: candidate.sectorName,
    entryTrigger: candidate.entryTrigger,
    pullbackWatch: candidate.pullbackWatch,
    defenseLine: candidate.defenseLine,
    addedFromDate,
  };
}

function positionRiskIsInactive(model: LivermoreStrategyModel, inputFamily: string) {
  return inputFamily === "position_risk" && model.riskExit === null;
}

export function LivermoreStrategyPanel({
  model,
  isLoading,
  isError,
  fetchErrorDetail,
  onRetry,
  onRefreshGateSupplement,
}: Props) {
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [watchPool, setWatchPool] = useState<WatchPoolItem[]>(readWatchPool);

  useEffect(() => {
    writeWatchPool(watchPool);
  }, [watchPool]);

  const handleRefreshGate = async () => {
    if (!onRefreshGateSupplement || refreshing) return;
    setRefreshing(true);
    setRefreshResult(null);
    try {
      const res = await onRefreshGateSupplement();
      if (res.status === "completed") {
        setRefreshResult(`已计算 ${res.computed_rows} 条门控数据`);
        setTimeout(() => onRetry(), 600);
      } else {
        setRefreshResult(res.message || `状态: ${res.status}`);
      }
    } catch (err) {
      setRefreshResult(`刷新失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRefreshing(false);
    }
  };
  if (isLoading) {
    return (
      <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
        <div className="livermore-strategy-panel__state">正在加载 Livermore 分析结果。</div>
      </section>
    );
  }

  if (isError) {
    const reserved =
      Boolean(fetchErrorDetail?.trim()) &&
      isReservedBoundaryHttpMessage(fetchErrorDetail ?? "");
    return (
      <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
        <div className="livermore-strategy-panel__state livermore-strategy-panel__state--error">
          {reserved ? (
            <div>Livermore 分析本轮不可用（接口保留）。</div>
          ) : (
            <div>Livermore 分析结果加载失败。</div>
          )}
          <button
            className="livermore-strategy-panel__retry"
            onClick={onRetry}
            type="button"
          >
            重试
          </button>
        </div>
      </section>
    );
  }

  if (!model) {
    return (
      <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
        <div className="livermore-strategy-panel__state">当前暂无 Livermore 结果。</div>
      </section>
    );
  }

  const noData = model.marketGate.state === "NO_DATA";
  const sectorRank = model.sectorRank;
  const stockCandidates = model.stockCandidates;
  const riskExit = model.riskExit;
  const watchedCodes = new Set(watchPool.map((item) => item.stockCode));

  const addToWatchPool = (candidate: StockCandidate) => {
    setWatchPool((current) => {
      if (current.some((item) => item.stockCode === candidate.stockCode)) {
        return current;
      }
      return [buildWatchPoolItem(candidate, model.asOfDate), ...current];
    });
  };

  const removeFromWatchPool = (stockCode: string) => {
    setWatchPool((current) => current.filter((item) => item.stockCode !== stockCode));
  };

  return (
    <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
      <div className="livermore-strategy-panel__header">
        <div className="livermore-strategy-panel__title">
          <h2 className="livermore-strategy-panel__name">{model.strategyName}</h2>
          <div className="livermore-strategy-panel__meta">
            {model.asOfDate
              ? `结果日期 ${model.asOfDate}${model.requestedAsOfDate ? ` · 请求 ${model.requestedAsOfDate}` : ""}`
              : "结果日期待定"}
          </div>
        </div>
        <div className="livermore-strategy-panel__actions">
          {onRefreshGateSupplement ? (
            <button
              className="livermore-strategy-panel__refresh-btn"
              onClick={handleRefreshGate}
              disabled={refreshing}
              type="button"
              title="从已有 CSI300 数据计算 breadth / limit-up 门控"
            >
              {refreshing ? "计算中…" : "刷新门控数据"}
            </button>
          ) : null}
          {refreshResult ? (
            <span className="livermore-strategy-panel__refresh-result">{refreshResult}</span>
          ) : null}
          <span className="livermore-strategy-panel__badge">分析口径 · 不生成交易指令</span>
        </div>
      </div>

      {model.statusNotes.length > 0 ? (
        <div
          className="livermore-strategy-panel__notes"
          data-testid="livermore-status-notes"
        >
          {model.statusNotes.map((note) => (
            <div key={note}>{note}</div>
          ))}
        </div>
      ) : null}

      <div className="livermore-strategy-panel__metrics">
        <div className="livermore-strategy-panel__metric" data-testid="livermore-market-state">
          <div className="livermore-strategy-panel__metric-label">市场门控</div>
          <div className="livermore-strategy-panel__metric-value">{model.marketGate.state}</div>
          <div className="livermore-strategy-panel__metric-detail">
            需要至少 {model.marketGate.requiredConditions} 条通过
          </div>
        </div>
        <div className="livermore-strategy-panel__metric" data-testid="livermore-exposure">
          <div className="livermore-strategy-panel__metric-label">仓位系数</div>
          <div className="livermore-strategy-panel__metric-value">
            {model.marketGate.exposureDisplay}
          </div>
          <div className="livermore-strategy-panel__metric-detail">由后端结果直接提供</div>
        </div>
        <div className="livermore-strategy-panel__metric" data-testid="livermore-gate-count">
          <div className="livermore-strategy-panel__metric-label">门控确认</div>
          <div className="livermore-strategy-panel__metric-value">
            {model.marketGate.passedConditions} / {model.marketGate.availableConditions}
          </div>
          <div className="livermore-strategy-panel__metric-detail">
            可计算 {model.marketGate.availableConditions} 条
          </div>
        </div>
        <div className="livermore-strategy-panel__metric">
          <div className="livermore-strategy-panel__metric-label">已支持输出</div>
          <div className="livermore-strategy-panel__metric-value">
            {model.supportedOutputs.length}
          </div>
          <div className="livermore-strategy-panel__metric-detail">
            {model.supportedOutputs.map((item) => item.label).join("、") || "暂无"}
          </div>
        </div>
      </div>

      {noData ? (
        <div className="livermore-strategy-panel__state">暂无可用 Livermore 输入。</div>
      ) : null}

      <div className="livermore-strategy-panel__grid">
        <div className="livermore-strategy-panel__block">
          <h3 className="livermore-strategy-panel__block-title">市场门控条件</h3>
          <ul className="livermore-strategy-panel__list">
            {model.marketGate.conditions.map((condition) => (
              <li className="livermore-strategy-panel__row" key={condition.key}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{condition.label}</span>
                  <span className="livermore-strategy-panel__row-detail">
                    {condition.evidence}
                  </span>
                </span>
                <span className={statusClass(condition.status)}>{condition.statusLabel}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="livermore-strategy-panel__block" data-testid="livermore-rule-readiness">
          <h3 className="livermore-strategy-panel__block-title">规则就绪度</h3>
          <ul className="livermore-strategy-panel__list">
            {model.ruleBlocks.map((block) => (
              <li className="livermore-strategy-panel__row" key={block.key}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{block.title}</span>
                  <span className="livermore-strategy-panel__row-detail">{block.summary}</span>
                </span>
                <span className={statusClass(block.status)}>{block.statusLabel}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="livermore-strategy-panel__grid">
        <div className="livermore-strategy-panel__block" data-testid="livermore-data-gaps">
          <h3 className="livermore-strategy-panel__block-title">数据缺口</h3>
          <ul className="livermore-strategy-panel__list">
            {model.dataGaps.map((gap) => (
              <li className="livermore-strategy-panel__row" key={gap.inputFamily}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{gap.inputFamily}</span>
                  <span className="livermore-strategy-panel__row-detail">{gap.evidence}</span>
                </span>
                <span className={statusClass(positionRiskIsInactive(model, gap.inputFamily) ? "info" : gap.status)}>
                  {positionRiskIsInactive(model, gap.inputFamily) ? "未启用" : gap.statusLabel}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="livermore-strategy-panel__block" data-testid="livermore-diagnostics">
          <h3 className="livermore-strategy-panel__block-title">诊断</h3>
          <ul className="livermore-strategy-panel__list">
            {model.diagnostics.map((item) => (
              <li className="livermore-strategy-panel__row" key={`${item.severity}:${item.code}`}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{item.code}</span>
                  <span className="livermore-strategy-panel__row-detail">{item.message}</span>
                </span>
                <span className={statusClass(item.severity)}>{item.severityLabel}</span>
              </li>
            ))}
          </ul>
        </div>

        {sectorRank ? (
          <div className="livermore-strategy-panel__block" data-testid="livermore-sector-rank">
            <h3 className="livermore-strategy-panel__block-title">板块排序</h3>
            <div className="livermore-strategy-panel__row-detail">
              {sectorRank.formulaVersion}
            </div>
            <ul className="livermore-strategy-panel__list">
              {sectorRank.items.map((item) => (
                <li className="livermore-strategy-panel__row" key={`${item.rank}:${item.sectorCode}`}>
                  <span className="livermore-strategy-panel__row-main">
                    <span className="livermore-strategy-panel__row-title">
                      #{item.rank} {item.sectorName} · {item.sectorCode}
                    </span>
                    <span className="livermore-strategy-panel__row-detail">
                      分数 {item.score} · 成分股 {item.constituentCount}
                    </span>
                  </span>
                  <span className={statusClass("ready")}>可用</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {stockCandidates ? (
          <div className="livermore-strategy-panel__block" data-testid="livermore-stock-candidates">
            <h3 className="livermore-strategy-panel__block-title">个股候选</h3>
            <div className="livermore-strategy-panel__row-detail">
              {stockCandidates.formulaVersion}
            </div>
            <ul className="livermore-strategy-panel__list">
              {stockCandidates.items.map((item) => (
                <li className="livermore-strategy-panel__row" key={`${item.rank}:${item.stockCode}`}>
                  <span className="livermore-strategy-panel__row-main">
                    <span className="livermore-strategy-panel__row-title">
                      #{item.rank} {item.stockName} · {item.stockCode}
                    </span>
                    <span className="livermore-strategy-panel__row-detail">
                      {item.sectorName} · 板块第 {item.sectorRank} 名 · 现价 {item.close}
                    </span>
                    <span className="livermore-strategy-panel__row-detail">
                      突破买点 {item.entryTrigger} · 回踩观察 {item.pullbackWatch} · 防守位 {item.defenseLine}
                    </span>
                    <span className="livermore-strategy-panel__row-detail">
                      CLV {item.closeStrength} · gap {item.gapNorm} · 异常换手 {item.abnormalTurnover}
                    </span>
                  </span>
                  <span className="livermore-strategy-panel__row-actions">
                    <span className={statusClass("ready")}>{stockCandidates.marketState}</span>
                    <button
                      className="livermore-strategy-panel__watch-btn"
                      disabled={watchedCodes.has(item.stockCode)}
                      onClick={() => addToWatchPool(item)}
                      type="button"
                    >
                      {watchedCodes.has(item.stockCode) ? "已入池" : "加入观察"}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {stockCandidates ? (
          <div className="livermore-strategy-panel__block" data-testid="livermore-watch-pool">
            <h3 className="livermore-strategy-panel__block-title">观察池</h3>
            <div className="livermore-strategy-panel__row-detail">
              本地观察池仅记录策略触发价位，不生成交易指令。
            </div>
            {watchPool.length > 0 ? (
              <ul className="livermore-strategy-panel__list">
                {watchPool.map((item) => (
                  <li className="livermore-strategy-panel__row" key={item.stockCode}>
                    <span className="livermore-strategy-panel__row-main">
                      <span className="livermore-strategy-panel__row-title">
                        {item.stockName} · {item.stockCode}
                      </span>
                      <span className="livermore-strategy-panel__row-detail">
                        {item.sectorName} · 买点 {item.entryTrigger} · 回踩 {item.pullbackWatch} · 防守 {item.defenseLine}
                      </span>
                      <span className="livermore-strategy-panel__row-detail">
                        来源日期 {item.addedFromDate ?? "未标记"}
                      </span>
                    </span>
                    <button
                      className="livermore-strategy-panel__watch-btn"
                      onClick={() => removeFromWatchPool(item.stockCode)}
                      type="button"
                    >
                      移出
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="livermore-strategy-panel__state">尚未选中候选股。</div>
            )}
          </div>
        ) : null}

        {riskExit ? (
          <div className="livermore-strategy-panel__block" data-testid="livermore-risk-exit">
            <h3 className="livermore-strategy-panel__block-title">Risk exit</h3>
            <div className="livermore-strategy-panel__row-detail">
              {riskExit.formulaVersion}
            </div>
            <div className="livermore-strategy-panel__row-detail">
              Positions {riskExit.positionCount} | Signals {riskExit.signalCount}
            </div>
            <ul className="livermore-strategy-panel__list">
              {riskExit.items.map((item) => (
                <li className="livermore-strategy-panel__row" key={`${item.stockCode}:${item.reason}`}>
                  <span className="livermore-strategy-panel__row-main">
                    <span className="livermore-strategy-panel__row-title">
                      {item.stockName} | {item.stockCode}
                    </span>
                    <span className="livermore-strategy-panel__row-detail">
                      {item.reason} | entry {item.entryCost} | bars {item.barsSinceEntry}
                    </span>
                    <span className="livermore-strategy-panel__row-detail">
                      close {item.latestClose} | ema10 {item.latestEma10}
                    </span>
                  </span>
                  <span className={statusClass("ready")}>Ready</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div
          className="livermore-strategy-panel__block"
          data-testid="livermore-unsupported-outputs"
        >
          <h3 className="livermore-strategy-panel__block-title">未开放输出</h3>
          <ul className="livermore-strategy-panel__list">
            {model.unsupportedOutputs.map((item) => (
              <li className="livermore-strategy-panel__row" key={item.key}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{item.label}</span>
                  <span className="livermore-strategy-panel__row-detail">{item.reason}</span>
                </span>
                <span className={statusClass(item.key === "risk_exit" ? "info" : "missing")}>
                  {item.key === "risk_exit" ? "未启用" : "未开放"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
