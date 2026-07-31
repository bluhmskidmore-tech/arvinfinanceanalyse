import type { ReactNode } from "react";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";
import "./MarketDataDetailDeck.css";

type Props = {
  payload: LivermoreStrategyPayload | null | undefined;
};

type Primitive = boolean | number | string | null | undefined;

function formatNumber(value: number | null | undefined, fractionDigits = 4) {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(fractionDigits).replace(/\.?0+$/, "");
}

function formatPrimitive(value: Primitive) {
  if (value == null) {
    return "—";
  }
  if (typeof value === "number") {
    return formatNumber(value);
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  const text = value.trim();
  return text.length > 0 ? text : "—";
}

function preserveBackendKey(key: string) {
  return key.trim() || "未命名字段";
}

function listSummary(values: readonly Primitive[], fallback = "—") {
  const items = values
    .map((value) => formatPrimitive(value))
    .filter((value) => value !== "—");
  return items.length > 0 ? items.join(", ") : fallback;
}

function ScrollTable({
  headers,
  children,
  testId,
  tall = false,
}: {
  headers: readonly string[];
  children: ReactNode;
  testId: string;
  tall?: boolean;
}) {
  return (
    <div
      className={`market-data-detail-deck__scroll-panel${tall ? " market-data-detail-deck__scroll-panel--tall" : ""}`}
    >
      <table className="market-data-tushare-table" data-testid={testId}>
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function StateLine({
  testId,
  state = "empty",
  children,
}: {
  testId: string;
  state?: "empty" | "warning" | "error" | "loading";
  children: ReactNode;
}) {
  return (
    <div className="market-data-detail-deck__state" data-state={state} data-testid={testId}>
      {children}
    </div>
  );
}

function KeyValueGrid({ entries, testId }: {
  entries: Array<{ label: string; value: ReactNode }>;
  testId: string;
}) {
  return (
    <dl className="market-data-detail-deck__definition-grid" data-testid={testId}>
      {entries.map((entry) => (
        <div key={entry.label}>
          <dt>{entry.label}</dt>
          <dd>{entry.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function renderUnknownValue(value: unknown, path: string): ReactNode {
  if (value == null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return formatPrimitive(value as Primitive);
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "0";
    }
    const primitiveArray = value.every(
      (item) => item == null || ["string", "number", "boolean"].includes(typeof item),
    );
    if (primitiveArray) {
      return (
        <span data-testid={`market-data-detail-livermore-workbench-${path}`}>
          {listSummary(value as Primitive[])}
        </span>
      );
    }
    return (
      <div className="market-data-detail-deck__stack" data-testid={`market-data-detail-livermore-workbench-${path}`}>
        {value.map((item, index) => (
          <div className="market-data-detail-deck__group-card" key={`${path}-${index}`}>
            <strong>{`条目 ${index + 1}`}</strong>
            {renderUnknownValue(item, `${path}-${index}`)}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return "0";
    }
    const primitiveEntries = entries.filter(
      ([, item]) => item == null || ["string", "number", "boolean"].includes(typeof item),
    );
    const nestedEntries = entries.filter(
      ([, item]) => !(item == null || ["string", "number", "boolean"].includes(typeof item)),
    );
    return (
      <div className="market-data-detail-deck__stack" data-testid={`market-data-detail-livermore-workbench-${path}`}>
        {primitiveEntries.length > 0 ? (
          <KeyValueGrid
            testId={`market-data-detail-livermore-workbench-${path}-grid`}
            entries={primitiveEntries.map(([key, item]) => ({
              label: preserveBackendKey(key),
              value: formatPrimitive(item as Primitive),
            }))}
          />
        ) : null}
        {nestedEntries.map(([key, item]) => (
          <div className="market-data-detail-deck__group-card" key={`${path}-${key}`}>
            <strong>{preserveBackendKey(key)}</strong>
            {renderUnknownValue(item, `${path}-${key}`)}
          </div>
        ))}
      </div>
    );
  }

  return String(value);
}

function ModuleCard({
  title,
  caption,
  testId,
  count,
  children,
}: {
  title: string;
  caption?: string;
  testId: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <MarketDataSeriesCategoryCard
      title={title}
      caption={caption}
      count={count}
      tone="analytical"
      testId={testId}
      showLinkTierTag={false}
    >
      {children}
    </MarketDataSeriesCategoryCard>
  );
}

export function MarketDataLivermoreBusinessDetail({ payload }: Props) {
  if (!payload) {
    return (
      <ModuleCard
        title="Livermore 业务明细"
        caption="基于已返回的 Livermore 结果展示业务明细。"
        testId="market-data-detail-livermore-business"
      >
        <StateLine testId="market-data-detail-livermore-business-state">
          未返回 Livermore payload，当前无法展示业务明细。
        </StateLine>
      </ModuleCard>
    );
  }

  const sectorRank = payload.sector_rank;
  const stockCandidates = payload.stock_candidates;
  const uptrend = payload.uptrend_momentum_candidates;
  const freshTrend = payload.fresh_trend_watchlist;
  const meanReversion = payload.mean_reversion_candidates;
  const factorScreen = payload.factor_screen_candidates;
  const themeBreakout = payload.theme_breakout;
  const hybridFusion = payload.hybrid_fusion_candidates;
  const riskExit = payload.risk_exit;
  const cycleRotation = payload.cycle_rotation_framework;
  const workbenchSummary = payload.workbench_summary;

  return (
    <ModuleCard
      title="Livermore 业务明细"
      caption="以密集业务视图展示已返回的 Livermore payload，并保留后端原始措辞与候选名称。"
      testId="market-data-detail-livermore-business"
    >
      <div className="market-data-detail-deck__stack">
        <div className="market-data-detail-deck__kpi-row market-data-detail-deck__kpi-row--four" data-testid="market-data-detail-livermore-summary">
          <div>
            <span>结果日期</span>
            <strong style={tabularNumsStyle}>{payload.as_of_date ?? "—"}</strong>
          </div>
          <div>
            <span>请求日期</span>
            <strong style={tabularNumsStyle}>{payload.requested_as_of_date ?? "—"}</strong>
          </div>
          <div>
            <span>市场门控</span>
            <strong>{payload.market_gate.state}</strong>
          </div>
          <div>
            <span>已支持输出</span>
            <strong style={tabularNumsStyle}>{payload.supported_outputs.length}</strong>
          </div>
        </div>

        <KeyValueGrid
          testId="market-data-detail-livermore-market-gate"
          entries={[
            { label: "策略名称", value: payload.strategy_name },
            { label: "口径", value: payload.basis },
            { label: "风险敞口", value: formatNumber(payload.market_gate.exposure) },
            {
              label: "通过条件",
              value: `${payload.market_gate.passed_conditions}/${payload.market_gate.available_conditions}`,
            },
            { label: "所需条件", value: formatNumber(payload.market_gate.required_conditions, 0) },
          ]}
        />

        <ModuleCard
          title="模块状态"
          caption="展示已返回的模块状态、渲染模式与时效证据。"
          testId="market-data-detail-livermore-module-states"
          count={payload.module_states.length}
        >
          <ScrollTable
            headers={["模块", "状态", "渲染模式", "来源日期", "覆盖范围", "说明"]}
            testId="market-data-detail-livermore-module-states-table"
          >
            {payload.module_states.map((row) => (
              <tr key={row.key}>
                <td><strong>{row.key}</strong></td>
                <td>{row.state}</td>
                <td>{row.render_mode}</td>
                <td style={tabularNumsStyle}>{row.source_date ?? "—"}</td>
                <td>
                  <strong>{row.evidence_scope}</strong>
                  <small>{`滞后 ${formatNumber(row.lag_days, 0)} / 阈值 ${formatNumber(row.threshold_days, 0)}`}</small>
                </td>
                <td>
                  <small>{row.reasons.length > 0 ? row.reasons.join("; ") : "未返回额外阻断说明。"}</small>
                </td>
              </tr>
            ))}
          </ScrollTable>
        </ModuleCard>

        <div className="market-data-detail-deck__split">
          <ModuleCard
            title="规则就绪度"
            caption="展示后端返回的规则就绪状态与缺失输入证据。"
            testId="market-data-detail-livermore-rule-readiness"
            count={payload.rule_readiness.length}
          >
            <ScrollTable
              headers={["规则", "状态", "摘要", "所需输入", "缺失输入"]}
              testId="market-data-detail-livermore-rule-readiness-table"
            >
              {payload.rule_readiness.map((row) => (
                <tr key={row.key}>
                  <td>
                    <strong>{row.title}</strong>
                    <small>{row.key}</small>
                  </td>
                  <td>{row.status}</td>
                  <td>{row.summary}</td>
                  <td><small>{listSummary(row.required_inputs)}</small></td>
                  <td><small>{listSummary(row.missing_inputs, "0")}</small></td>
                </tr>
              ))}
            </ScrollTable>
          </ModuleCard>

          <ModuleCard
            title="诊断与数据缺口"
            caption="按原样展示已返回的诊断与数据缺口证据，不额外推断。"
            testId="market-data-detail-livermore-diagnostics"
          >
            <div className="market-data-detail-deck__stack">
              <ScrollTable
                headers={["严重级别", "代码", "消息", "输入族"]}
                testId="market-data-detail-livermore-diagnostics-table"
              >
                {payload.diagnostics.map((row) => (
                  <tr key={`${row.severity}-${row.code}`}>
                    <td>{row.severity}</td>
                    <td>{row.code}</td>
                    <td>{row.message}</td>
                    <td>{row.input_family ?? "—"}</td>
                  </tr>
                ))}
              </ScrollTable>
              <ScrollTable
                headers={["输入族", "状态", "证据", "新鲜度"]}
                testId="market-data-detail-livermore-data-gaps-table"
              >
                {payload.data_gaps.map((row, index) => (
                  <tr key={`${row.input_family}-${row.status}-${index}`}>
                    <td>{row.input_family}</td>
                    <td>{row.status}</td>
                    <td>
                      <strong>{row.evidence}</strong>
                      <small>{listSummary([row.input, row.business_date, row.age_days])}</small>
                    </td>
                    <td>{row.tier ?? "—"}</td>
                  </tr>
                ))}
              </ScrollTable>
            </div>
          </ModuleCard>
        </div>

        <ModuleCard
          title="板块排序（sector_rank）"
          caption="展示 sector_rank 返回内容，并在有数据时补充龙头成分股摘要。"
          testId="market-data-detail-livermore-sector-rank"
          count={sectorRank?.items.length}
        >
          {sectorRank ? (
            <div className="market-data-detail-deck__stack">
              <KeyValueGrid
                testId="market-data-detail-livermore-sector-rank-meta"
                entries={[
                  { label: "结果日期", value: sectorRank.as_of_date },
                  { label: "公式版本", value: sectorRank.formula_version },
                  { label: "公式状态", value: sectorRank.formula_status ?? "—" },
                  { label: "是否临时", value: formatPrimitive(sectorRank.is_provisional) },
                  { label: "板块数量", value: formatNumber(sectorRank.sector_count, 0) },
                  {
                    label: "龙头成分股口径",
                    value: listSummary([sectorRank.leader_constituent_method, sectorRank.leader_constituent_limit]),
                  },
                ]}
              />
              {sectorRank.formula_note ? (
                <StateLine testId="market-data-detail-livermore-sector-rank-note" state="warning">
                  {sectorRank.formula_note}
                </StateLine>
              ) : null}
              <ScrollTable
                headers={["排名", "板块", "得分", "板块概览", "龙头成分股"]}
                testId="market-data-detail-livermore-sector-rank-table"
              >
                {sectorRank.items.map((row) => (
                  <tr key={`${row.rank}-${row.sector_code}`}>
                    <td style={tabularNumsStyle}>{row.rank}</td>
                    <td>
                      <strong>{row.sector_name}</strong>
                      <small>{row.sector_code}</small>
                    </td>
                    <td style={tabularNumsStyle}>{formatNumber(row.score)}</td>
                    <td>
                      <strong>{`成分股 ${formatNumber(row.constituent_count, 0)}`}</strong>
                      <small>{`涨跌幅 ${formatNumber(row.avg_pctchange)} | 换手 ${formatNumber(row.avg_turn)} | 振幅 ${formatNumber(row.avg_amplitude)}`}</small>
                    </td>
                    <td>
                      <small>
                        {row.leader_constituents?.length
                          ? row.leader_constituents
                            .map((leader) => `#${leader.rank} ${leader.stock_name} (${leader.stock_code}) 涨跌幅 ${formatNumber(leader.pctchange)} 换手 ${formatNumber(leader.turn)}`)
                            .join("; ")
                          : "未返回龙头成分股。"}
                      </small>
                    </td>
                  </tr>
                ))}
              </ScrollTable>
            </div>
          ) : (
            <StateLine testId="market-data-detail-livermore-sector-rank-state">
              当前 payload 未返回 sector_rank。
            </StateLine>
          )}
        </ModuleCard>

        <ModuleCard
          title="候选个股（stock_candidates）"
          caption="展示 stock_candidates 候选行与返回的覆盖字段。"
          testId="market-data-detail-livermore-stock-candidates"
          count={stockCandidates?.candidate_count}
        >
          {stockCandidates ? (
            <div className="market-data-detail-deck__stack">
              <KeyValueGrid
                testId="market-data-detail-livermore-stock-candidates-meta"
                entries={[
                  { label: "结果日期", value: stockCandidates.as_of_date },
                  { label: "公式版本", value: stockCandidates.formula_version },
                  { label: "市场门控", value: stockCandidates.market_state },
                  { label: "筛选策略", value: stockCandidates.selection_policy ?? "—" },
                  { label: "候选数量", value: formatNumber(stockCandidates.candidate_count, 0) },
                  {
                    label: "基本面覆盖",
                    value: stockCandidates.fundamental_overlay
                      ? listSummary([
                        stockCandidates.fundamental_overlay.status,
                        stockCandidates.fundamental_overlay.input_candidate_count,
                        stockCandidates.fundamental_overlay.factor_missing_count,
                      ])
                      : "未返回",
                  },
                ]}
              />
              {stockCandidates.items.length > 0 ? (
                <ScrollTable
                  headers={["排名", "个股", "形态", "趋势证据", "覆盖字段"]}
                  testId="market-data-detail-livermore-stock-candidates-table"
                  tall
                >
                  {stockCandidates.items.map((row) => (
                    <tr key={`${row.rank}-${row.stock_code}`}>
                      <td style={tabularNumsStyle}>{row.rank}</td>
                      <td>
                        <strong>{row.stock_name}</strong>
                        <small>{`${row.stock_code} | ${row.sector_name} (${row.sector_code})`}</small>
                      </td>
                    <td>
                      <strong>{`收盘 ${formatNumber(row.close)} | 突破位 ${formatNumber(row.breakout_level)}`}</strong>
                      <small>{`10日均线 ${formatNumber(row.ema10)} | 20日均线 ${formatNumber(row.ma20)} | 60日均线 ${formatNumber(row.ma60)} | 120日均线 ${formatNumber(row.ma120)}`}</small>
                    </td>
                    <td>
                      <strong>{`收盘强度 ${formatNumber(row.close_strength)} | 缺口归一值 ${formatNumber(row.gap_norm)}`}</strong>
                      <small>{`突破延展 ${formatNumber(row.breakout_extension_norm)} | 异常换手 ${formatNumber(row.abnormal_turnover)} | 板块排名 ${formatNumber(row.sector_rank, 0)}`}</small>
                    </td>
                    <td>
                      <strong>{`因子分数 ${formatNumber(row.factor_score)} | 覆盖排名 ${formatNumber(row.factor_overlay_rank, 0)}`}</strong>
                      <small>{`PE ${formatNumber(row.pe)} | PB ${formatNumber(row.pb)} | PS ${formatNumber(row.ps)} | ROE ${formatNumber(row.roe)} | 股息率 ${formatNumber(row.dividend_yield)}`}</small>
                    </td>
                    </tr>
                  ))}
                </ScrollTable>
              ) : (
                <StateLine testId="market-data-detail-livermore-stock-candidates-state">
                  stock_candidates 已返回，但候选行数量为 0。
                </StateLine>
              )}
            </div>
          ) : (
            <StateLine testId="market-data-detail-livermore-stock-candidates-state">
              当前 payload 未返回 stock_candidates。
            </StateLine>
          )}
        </ModuleCard>

        <div className="market-data-detail-deck__split">
          <ModuleCard
            title="上升趋势观察（uptrend_momentum_candidates）"
            caption="展示 uptrend_momentum_candidates 返回的观察候选。"
            testId="market-data-detail-livermore-uptrend-momentum-candidates"
            count={uptrend?.candidate_count}
          >
            {uptrend ? (
              uptrend.items.length > 0 ? (
                <ScrollTable
                  headers={["排名", "个股", "趋势", "区间收益", "成交特征"]}
                  testId="market-data-detail-livermore-uptrend-momentum-candidates-table"
                >
                  {uptrend.items.map((row) => (
                    <tr key={`${row.rank}-${row.stock_code}`}>
                      <td style={tabularNumsStyle}>{row.rank}</td>
                      <td>
                        <strong>{row.stock_name}</strong>
                        <small>{`${row.stock_code} | ${row.sector_name}`}</small>
                      </td>
                      <td>
                        <strong>{`收盘 ${formatNumber(row.close)}`}</strong>
                        <small>{`20日均线 ${formatNumber(row.ma20)} | 60日均线 ${formatNumber(row.ma60)} | 120日均线 ${formatNumber(row.ma120)}`}</small>
                      </td>
                      <td>
                        <strong>{`20日收益 ${formatNumber(row.return_20d)} | 60日收益 ${formatNumber(row.return_60d)}`}</strong>
                        <small>{`120日收益 ${formatNumber(row.return_120d)} | 距20日均线 ${formatNumber(row.close_to_ma20)}`}</small>
                      </td>
                      <td>
                        <strong>{`得分 ${formatNumber(row.score)}`}</strong>
                        <small>{`量比 ${formatNumber(row.amount_ratio)} | 涨跌幅 ${formatNumber(row.pctchange)} | 换手 ${formatNumber(row.turn)} | 振幅 ${formatNumber(row.amplitude)}`}</small>
                      </td>
                    </tr>
                  ))}
                </ScrollTable>
              ) : (
                <StateLine testId="market-data-detail-livermore-uptrend-momentum-candidates-state">
                  uptrend_momentum_candidates 已返回，但候选行数量为 0。
                </StateLine>
              )
            ) : (
              <StateLine testId="market-data-detail-livermore-uptrend-momentum-candidates-state">
                当前 payload 未返回 uptrend_momentum_candidates。
              </StateLine>
            )}
          </ModuleCard>

          <ModuleCard
            title="新趋势观察（fresh_trend_watchlist）"
            caption="展示 fresh_trend_watchlist 候选与概念标签。"
            testId="market-data-detail-livermore-fresh-trend-watchlist"
            count={freshTrend?.candidate_count}
          >
            {freshTrend ? (
              freshTrend.items.length > 0 ? (
                <ScrollTable
                  headers={["排名", "个股", "概念", "趋势", "观察证据"]}
                  testId="market-data-detail-livermore-fresh-trend-watchlist-table"
                >
                  {freshTrend.items.map((row) => (
                    <tr key={`${row.rank}-${row.stock_code}`}>
                      <td style={tabularNumsStyle}>{row.rank}</td>
                      <td>
                        <strong>{row.stock_name}</strong>
                        <small>{`${row.stock_code} | ${row.sector_name}`}</small>
                      </td>
                      <td><small>{listSummary(row.concepts, "未返回概念标签。")}</small></td>
                      <td>
                        <strong>{`收盘 ${formatNumber(row.close)}`}</strong>
                        <small>{`20日均线 ${formatNumber(row.ma20)} | 60日均线 ${formatNumber(row.ma60)} | 120日均线 ${formatNumber(row.ma120)}`}</small>
                      </td>
                      <td>
                        <strong>{`得分 ${formatNumber(row.score)} | 涨停天数 ${formatNumber(row.hlimitedays, 0)}`}</strong>
                        <small>{`20日收益 ${formatNumber(row.return_20d)} | 60日收益 ${formatNumber(row.return_60d)} | 量比 ${formatNumber(row.amount_ratio)}`}</small>
                      </td>
                    </tr>
                  ))}
                </ScrollTable>
              ) : (
                <StateLine testId="market-data-detail-livermore-fresh-trend-watchlist-state">
                  fresh_trend_watchlist 已返回，但候选行数量为 0。
                </StateLine>
              )
            ) : (
              <StateLine testId="market-data-detail-livermore-fresh-trend-watchlist-state">
                当前 payload 未返回 fresh_trend_watchlist。
              </StateLine>
            )}
          </ModuleCard>
        </div>

        <div className="market-data-detail-deck__split">
          <ModuleCard
            title="超跌反弹观察（mean_reversion_candidates）"
            caption="展示 mean_reversion_candidates 返回的回撤与价格证据。"
            testId="market-data-detail-livermore-mean-reversion-candidates"
            count={meanReversion?.candidate_count}
          >
            {meanReversion ? (
              meanReversion.items.length > 0 ? (
                <ScrollTable
                  headers={["排名", "个股", "回撤", "价格上下文", "得分"]}
                  testId="market-data-detail-livermore-mean-reversion-candidates-table"
                >
                  {meanReversion.items.map((row) => (
                    <tr key={`${row.rank}-${row.stock_code}`}>
                      <td style={tabularNumsStyle}>{row.rank}</td>
                      <td>
                        <strong>{row.stock_name}</strong>
                        <small>{`${row.stock_code} | ${row.sector_name}`}</small>
                      </td>
                    <td>
                        <strong>{`20日回撤 ${formatNumber(row.drawdown_20d)} | 60日回撤 ${formatNumber(row.drawdown_60d)}`}</strong>
                      </td>
                      <td>
                        <strong>{`收盘 ${formatNumber(row.close)}`}</strong>
                        <small>{`5日均线 ${formatNumber(row.ma5)} | 10日均线 ${formatNumber(row.ma10)} | 收盘强度 ${formatNumber(row.close_strength)} | 量比 ${formatNumber(row.vol_ratio)}`}</small>
                      </td>
                      <td style={tabularNumsStyle}>{formatNumber(row.score)}</td>
                    </tr>
                  ))}
                </ScrollTable>
              ) : (
                <StateLine testId="market-data-detail-livermore-mean-reversion-candidates-state">
                  mean_reversion_candidates 已返回，但候选行数量为 0。
                </StateLine>
              )
            ) : (
              <StateLine testId="market-data-detail-livermore-mean-reversion-candidates-state">
                当前 payload 未返回 mean_reversion_candidates。
              </StateLine>
            )}
          </ModuleCard>

          <ModuleCard
            title="多因子观察（factor_screen_candidates）"
            caption="展示 factor_screen_candidates 候选与覆盖说明。"
            testId="market-data-detail-livermore-factor-screen-candidates"
            count={factorScreen?.candidate_count}
          >
            {factorScreen ? (
              <div className="market-data-detail-deck__stack">
                <KeyValueGrid
                  testId="market-data-detail-livermore-factor-screen-candidates-meta"
                  entries={[
                    { label: "结果日期", value: factorScreen.as_of_date },
                    { label: "因子快照日期", value: factorScreen.factor_snapshot_as_of_date ?? "—" },
                    { label: "公式版本", value: factorScreen.formula_version },
                    { label: "市场门控", value: factorScreen.market_state },
                    { label: "覆盖说明", value: factorScreen.coverage_note },
                    {
                      label: "覆盖情况",
                      value: listSummary([
                        factorScreen.coverage_count,
                        factorScreen.coverage_denominator,
                        factorScreen.coverage_ratio,
                        factorScreen.coverage_threshold,
                      ]),
                    },
                  ]}
                />
                {factorScreen.items.length > 0 ? (
                  <ScrollTable
                    headers={["排名", "个股", "行业板块", "估值", "质量"]}
                    testId="market-data-detail-livermore-factor-screen-candidates-table"
                  >
                    {factorScreen.items.map((row) => (
                      <tr key={`${row.rank}-${row.stock_code}`}>
                        <td style={tabularNumsStyle}>{row.rank}</td>
                        <td>
                          <strong>{row.stock_name}</strong>
                          <small>{row.stock_code}</small>
                        </td>
                        <td>
                          <strong>{row.sector_name}</strong>
                          <small>{row.industry}</small>
                        </td>
                        <td>
                          <strong>{`score ${formatNumber(row.score)}`}</strong>
                          <small>{`PE ${formatNumber(row.pe)} | PB ${formatNumber(row.pb)} | 股息率 ${formatNumber(row.dividend_yield)}`}</small>
                        </td>
                        <td>
                          <strong>{`ROE ${formatNumber(row.roe)} | 毛利率 ${formatNumber(row.gross_margin)}`}</strong>
                          <small>{`三个月收益 ${formatNumber(row.three_month_return)} | 十二个月收益 ${formatNumber(row.twelve_month_return)}`}</small>
                        </td>
                      </tr>
                    ))}
                  </ScrollTable>
                ) : (
                  <StateLine testId="market-data-detail-livermore-factor-screen-candidates-state">
                    factor_screen_candidates 已返回，但候选行数量为 0。
                  </StateLine>
                )}
              </div>
            ) : (
              <StateLine testId="market-data-detail-livermore-factor-screen-candidates-state">
                当前 payload 未返回 factor_screen_candidates。
              </StateLine>
            )}
          </ModuleCard>
        </div>

        <ModuleCard
          title="题材异动（theme_breakout）"
          caption="展示 theme_breakout 题材、嵌套个股摘要、证据状态与复核项。"
          testId="market-data-detail-livermore-theme-breakout"
          count={themeBreakout?.theme_count}
        >
          {themeBreakout ? (
            <div className="market-data-detail-deck__stack">
              <KeyValueGrid
                testId="market-data-detail-livermore-theme-breakout-meta"
                entries={[
                  { label: "结果日期", value: themeBreakout.as_of_date },
                  { label: "公式版本", value: themeBreakout.formula_version },
                  { label: "是否代理", value: formatPrimitive(themeBreakout.is_proxy) },
                  { label: "题材数量", value: formatNumber(themeBreakout.theme_count, 0) },
                  { label: "证据摘要", value: themeBreakout.evidence_state?.summary ?? "—" },
                ]}
              />
              {themeBreakout.evidence_state ? (
                <div className="market-data-detail-deck__group-card" data-testid="market-data-detail-livermore-theme-breakout-evidence-state">
                  <strong>证据状态</strong>
                  {renderUnknownValue(themeBreakout.evidence_state, "theme-evidence-state")}
                </div>
              ) : null}
              {themeBreakout.items.length > 0 ? (
                <ScrollTable
                  headers={["排名", "题材", "上游板块", "广度", "成分股摘要"]}
                  testId="market-data-detail-livermore-theme-breakout-table"
                  tall
                >
                  {themeBreakout.items.map((row) => (
                    <tr key={`${row.rank}-${row.theme_key}`}>
                      <td style={tabularNumsStyle}>{row.rank}</td>
                      <td>
                        <strong>{row.theme_name}</strong>
                      <small>{`${row.theme_key} | ${row.source_kind ?? "—"} | ${row.reason}`}</small>
                    </td>
                      <td>
                        <strong>{row.parent_sector_name}</strong>
                      <small>{`上游板块排名 ${formatNumber(row.parent_sector_rank, 0)} | 成分数 ${formatNumber(row.member_count, 0)}`}</small>
                    </td>
                    <td>
                      <strong>{`上涨家数 ${formatNumber(row.advance_count, 0)} | 强势股数 ${formatNumber(row.strong_stock_count, 0)} | 涨停股数 ${formatNumber(row.limit_stock_count, 0)}`}</strong>
                      <small>{`上涨占比 ${formatNumber(row.advance_ratio)} | 平均涨跌幅 ${formatNumber(row.avg_pctchange)} | 平均换手 ${formatNumber(row.avg_turn)} | 平均振幅 ${formatNumber(row.avg_amplitude)}`}</small>
                    </td>
                    <td>
                      <small>
                        {row.items.length > 0
                            ? row.items
                              .map((item) => `${item.stock_name} (${item.stock_code}) 板块排名 ${formatNumber(item.sector_rank, 0)} 收盘 ${formatNumber(item.close)} 涨跌幅 ${formatNumber(item.pctchange)} 强势 ${formatPrimitive(item.strong)}`)
                              .join("; ")
                            : "未返回嵌套个股。"}
                      </small>
                    </td>
                  </tr>
                ))}
              </ScrollTable>
              ) : (
                <StateLine testId="market-data-detail-livermore-theme-breakout-state">
                  theme_breakout 已返回，但题材行数量为 0。
                </StateLine>
              )}
              {themeBreakout.review_items?.length ? (
                <ScrollTable
                  headers={["题材", "门控", "原因", "成分股摘要"]}
                  testId="market-data-detail-livermore-theme-breakout-review-items-table"
                >
                  {themeBreakout.review_items.map((row, index) => (
                    <tr key={`${row.theme_key}-${index}`}>
                      <td>
                        <strong>{row.theme_name}</strong>
                        <small>{`排名 ${formatNumber(row.rank, 0)} | ${row.source_kind ?? "—"}`}</small>
                      </td>
                      <td><small>{listSummary([...(row.failed_gates ?? []), ...(row.failed_gate_codes ?? [])], "未返回失败门控。")}</small></td>
                      <td>{row.reason}</td>
                      <td>
                        <small>
                          {row.items.length > 0
                            ? row.items.map((item) => `${item.stock_name} (${item.stock_code}) 收盘 ${formatNumber(item.close)}`).join("; ")
                            : "未返回嵌套个股。"}
                        </small>
                      </td>
                    </tr>
                  ))}
                </ScrollTable>
              ) : null}
            </div>
          ) : (
            <StateLine testId="market-data-detail-livermore-theme-breakout-state">
              当前 payload 未返回 theme_breakout。
            </StateLine>
          )}
        </ModuleCard>

        <div className="market-data-detail-deck__split">
          <ModuleCard
            title="融合观察（hybrid_fusion_candidates）"
            caption="展示 hybrid_fusion_candidates 候选与返回证据。"
            testId="market-data-detail-livermore-hybrid-fusion-candidates"
            count={hybridFusion?.candidate_count}
          >
            {hybridFusion ? (
              <div className="market-data-detail-deck__stack">
                <KeyValueGrid
                  testId="market-data-detail-livermore-hybrid-fusion-candidates-meta"
                  entries={[
                    { label: "结果日期", value: hybridFusion.as_of_date },
                    { label: "公式版本", value: hybridFusion.formula_version },
                    { label: "市场门控", value: hybridFusion.market_state },
                    { label: "仅观察", value: formatPrimitive(hybridFusion.observation_only) },
                    { label: "宏观分数", value: formatNumber(hybridFusion.macro_score) },
                    { label: "覆盖说明", value: hybridFusion.coverage_note ?? "—" },
                  ]}
                />
                {hybridFusion.items.length > 0 ? (
                  <ScrollTable
                    headers={["排名", "个股", "融合分数", "支持分数", "动作与证据"]}
                    testId="market-data-detail-livermore-hybrid-fusion-candidates-table"
                    tall
                  >
                    {hybridFusion.items.map((row) => (
                      <tr key={`${row.rank}-${row.stock_code}`}>
                        <td style={tabularNumsStyle}>{row.rank}</td>
                        <td>
                          <strong>{row.stock_name}</strong>
                          <small>{`${row.stock_code} | ${row.sector_name} (${row.sector_code})`}</small>
                        </td>
                      <td>
                          <strong>{`融合分数 ${formatNumber(row.fusion_score)} | 置信度 ${row.confidence}`}</strong>
                          <small>{row.reason}</small>
                      </td>
                      <td>
                          <strong>{`周期分 ${formatNumber(row.cycle_score)} | Lifecourt 代理分 ${formatNumber(row.lifecourt_proxy_score)}`}</strong>
                          <small>{`注意力分 ${formatNumber(row.attention_score)} | 价格确认分 ${formatNumber(row.price_confirm_score)} | 拥挤惩罚 ${formatNumber(row.crowding_penalty)} | 因子名次可用 ${formatPrimitive(row.factor_rank_available)}`}</small>
                      </td>
                      <td>
                          <strong>{row.fusion_action ?? "—"}</strong>
                          <small>{renderUnknownValue(row.evidence, `hybrid-evidence-${row.stock_code}`)}</small>
                        </td>
                      </tr>
                    ))}
                  </ScrollTable>
                ) : (
                  <StateLine testId="market-data-detail-livermore-hybrid-fusion-candidates-state">
                    hybrid_fusion_candidates 已返回，但候选行数量为 0。
                  </StateLine>
                )}
              </div>
            ) : (
              <StateLine testId="market-data-detail-livermore-hybrid-fusion-candidates-state">
                当前 payload 未返回 hybrid_fusion_candidates。
              </StateLine>
            )}
          </ModuleCard>

          <ModuleCard
            title="风险退出（risk_exit）"
            caption="展示 risk_exit 触发行与 watch_items，保持返回内容原样。"
            testId="market-data-detail-livermore-risk-exit"
            count={riskExit?.signal_count}
          >
            {riskExit ? (
              <div className="market-data-detail-deck__stack">
                <KeyValueGrid
                  testId="market-data-detail-livermore-risk-exit-meta"
                  entries={[
                    { label: "结果日期", value: riskExit.as_of_date },
                    { label: "公式版本", value: riskExit.formula_version },
                    { label: "持仓数量", value: formatNumber(riskExit.position_count, 0) },
                    { label: "信号数量", value: formatNumber(riskExit.signal_count, 0) },
                    { label: "排除持仓数", value: formatNumber(riskExit.excluded_position_count, 0) },
                    { label: "历史不足数", value: formatNumber(riskExit.insufficient_history_count, 0) },
                  ]}
                />
                {riskExit.items.length > 0 ? (
                  <ScrollTable
                    headers={["个股", "原因", "入场上下文", "最新上下文"]}
                    testId="market-data-detail-livermore-risk-exit-items-table"
                  >
                    {riskExit.items.map((row) => (
                      <tr key={`${row.stock_code}-${row.reason}`}>
                        <td>
                          <strong>{row.stock_name}</strong>
                          <small>{row.stock_code}</small>
                        </td>
                      <td>{row.reason}</td>
                      <td>
                          <strong>{`建仓成本 ${formatNumber(row.entry_cost)} | 成本可用 ${formatPrimitive(row.entry_cost_available)}`}</strong>
                          <small>{`建仓后K线数 ${formatNumber(row.bars_since_entry, 0)}`}</small>
                      </td>
                      <td>
                          <strong>{`最新收盘 ${formatNumber(row.latest_close)} | 最新EMA10 ${formatNumber(row.latest_ema10)}`}</strong>
                          <small>{`前收 ${formatNumber(row.prior_close)} | 前EMA10 ${formatNumber(row.prior_ema10)}`}</small>
                      </td>
                    </tr>
                  ))}
                  </ScrollTable>
                ) : (
                  <StateLine testId="market-data-detail-livermore-risk-exit-items-state">
                    risk_exit 已返回，但触发行数量为 0。
                  </StateLine>
                )}
                {riskExit.watch_items ? (
                  riskExit.watch_items.length > 0 ? (
                    <ScrollTable
                      headers={["个股", "入场上下文", "最新上下文", "观察"]}
                      testId="market-data-detail-livermore-risk-exit-watch-items-table"
                    >
                      {riskExit.watch_items.map((row) => (
                        <tr key={row.stock_code}>
                          <td>
                            <strong>{row.stock_name}</strong>
                          <small>{row.stock_code}</small>
                          </td>
                          <td>
                            <strong>{`建仓成本 ${formatNumber(row.entry_cost)} | 成本可用 ${formatPrimitive(row.entry_cost_available)}`}</strong>
                            <small>{`建仓后K线数 ${formatNumber(row.bars_since_entry, 0)}`}</small>
                          </td>
                          <td>
                            <strong>{`最新收盘 ${formatNumber(row.latest_close)} | 最新EMA10 ${formatNumber(row.latest_ema10)}`}</strong>
                            <small>{`前收 ${formatNumber(row.prior_close)} | 前EMA10 ${formatNumber(row.prior_ema10)}`}</small>
                          </td>
                          <td>
                            <strong>{`观察价 ${formatNumber(row.exit_watch_price)}`}</strong>
                            <small>{`已触发 ${formatPrimitive(row.triggered)}`}</small>
                          </td>
                        </tr>
                      ))}
                    </ScrollTable>
                  ) : (
                    <StateLine testId="market-data-detail-livermore-risk-exit-watch-items-state">
                      risk_exit.watch_items 已返回空数组。
                    </StateLine>
                  )
                ) : (
                  <StateLine testId="market-data-detail-livermore-risk-exit-watch-items-state">
                    当前 payload 未返回 risk_exit.watch_items。
                  </StateLine>
                )}
              </div>
            ) : (
              <StateLine testId="market-data-detail-livermore-risk-exit-state">
                当前 payload 未返回 risk_exit。
              </StateLine>
            )}
          </ModuleCard>
        </div>

        <div className="market-data-detail-deck__split">
          <ModuleCard
            title="已支持输出（supported_outputs）"
            caption="列出当前 payload 返回的 supported_outputs。"
            testId="market-data-detail-livermore-supported-outputs"
            count={payload.supported_outputs.length}
          >
            <ScrollTable
              headers={["输出键"]}
              testId="market-data-detail-livermore-supported-outputs-table"
            >
              {payload.supported_outputs.map((row) => (
                <tr key={row}>
                  <td>{row}</td>
                </tr>
              ))}
            </ScrollTable>
          </ModuleCard>

          <ModuleCard
            title="未支持输出（unsupported_outputs）"
            caption="列出后端返回的 unsupported_outputs 及原因。"
            testId="market-data-detail-livermore-unsupported-outputs"
            count={payload.unsupported_outputs.length}
          >
            {payload.unsupported_outputs.length > 0 ? (
              <ScrollTable
                headers={["输出键", "原因"]}
                testId="market-data-detail-livermore-unsupported-outputs-table"
              >
                {payload.unsupported_outputs.map((row) => (
                  <tr key={row.key}>
                    <td>{row.key}</td>
                    <td>{row.reason}</td>
                  </tr>
                ))}
              </ScrollTable>
            ) : (
              <StateLine testId="market-data-detail-livermore-unsupported-outputs-state">
                未返回 unsupported_outputs 行。
              </StateLine>
            )}
          </ModuleCard>
        </div>

        <ModuleCard
          title="周期轮动框架（cycle_rotation_framework）"
          caption="展示 cycle_rotation_framework 的层级、策略与边界说明。"
          testId="market-data-detail-livermore-cycle-rotation-framework"
        >
          {cycleRotation ? (
            <div className="market-data-detail-deck__stack">
              <KeyValueGrid
                testId="market-data-detail-livermore-cycle-rotation-framework-meta"
                entries={[
                  { label: "策略名称", value: cycleRotation.strategy_name },
                  { label: "展示名称", value: cycleRotation.display_name },
                  { label: "仅观察", value: formatPrimitive(cycleRotation.observation_only) },
                  { label: "实现阶段", value: cycleRotation.implementation_stage },
                  { label: "评分公式", value: cycleRotation.score_formula },
                  { label: "调仓节奏", value: cycleRotation.rebalance_cadence },
                  { label: "边界", value: cycleRotation.boundary },
                ]}
              />
              <ScrollTable
                headers={["层级", "权重", "状态", "证据", "输入"]}
                testId="market-data-detail-livermore-cycle-rotation-framework-layers-table"
              >
                {cycleRotation.layers.map((row) => (
                  <tr key={row.key}>
                    <td>
                      <strong>{row.title}</strong>
                      <small>{row.key}</small>
                    </td>
                    <td style={tabularNumsStyle}>{formatNumber(row.weight)}</td>
                    <td>{row.status}</td>
                    <td>{row.evidence}</td>
                    <td>
                      <strong>{`可用 ${row.available_inputs.length}`}</strong>
                      <small>{`可用: ${listSummary(row.available_inputs, "0")} | 缺失: ${listSummary(row.missing_inputs, "0")}`}</small>
                    </td>
                  </tr>
                ))}
              </ScrollTable>
              {cycleRotation.constraints.length > 0 ? (
                <div className="market-data-detail-deck__group-card" data-testid="market-data-detail-livermore-cycle-rotation-framework-constraints">
                  <strong>约束条件</strong>
                  <ul className="market-data-detail-deck__compact-list">
                    {cycleRotation.constraints.map((row) => (
                      <li key={row}><span>{row}</span></li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {cycleRotation.macro_layer ? (
                <div className="market-data-detail-deck__group-card" data-testid="market-data-detail-livermore-cycle-rotation-framework-macro-layer">
                  <strong>宏观层</strong>
                  {renderUnknownValue(cycleRotation.macro_layer, "cycle-macro-layer")}
                </div>
              ) : null}
              {cycleRotation.lifecourt_overlay ? (
                <div className="market-data-detail-deck__group-card" data-testid="market-data-detail-livermore-cycle-rotation-framework-lifecourt-overlay">
                  <strong>Lifecourt 覆盖层</strong>
                  {renderUnknownValue(cycleRotation.lifecourt_overlay, "cycle-lifecourt-overlay")}
                </div>
              ) : null}
              {cycleRotation.fusion_policy ? (
                <div className="market-data-detail-deck__stack" data-testid="market-data-detail-livermore-cycle-rotation-framework-fusion-policy">
                  <KeyValueGrid
                    testId="market-data-detail-livermore-cycle-rotation-framework-fusion-policy-grid"
                    entries={[
                      { label: "周期权重", value: formatNumber(cycleRotation.fusion_policy.cycle_weight) },
                      { label: "Life 权重", value: formatNumber(cycleRotation.fusion_policy.life_weight) },
                      { label: "冲突策略", value: cycleRotation.fusion_policy.conflict_policy },
                    ]}
                  />
                  <ScrollTable
                    headers={["周期", "Life", "动作"]}
                    testId="market-data-detail-livermore-cycle-rotation-framework-fusion-policy-matrix-table"
                  >
                    {cycleRotation.fusion_policy.matrix.map((row, index) => (
                      <tr key={`${row.cycle}-${row.life}-${index}`}>
                        <td>{row.cycle}</td>
                        <td>{row.life}</td>
                        <td>{row.action}</td>
                      </tr>
                    ))}
                  </ScrollTable>
                </div>
              ) : null}
            </div>
          ) : (
            <StateLine testId="market-data-detail-livermore-cycle-rotation-framework-state">
              当前 payload 未返回 cycle_rotation_framework。
            </StateLine>
          )}
        </ModuleCard>

        <ModuleCard
          title="工作台摘要（workbench_summary）"
          caption="以可读方式展开 workbench_summary 返回的嵌套数据。"
          testId="market-data-detail-livermore-workbench-summary"
        >
          {workbenchSummary ? (
            <div className="market-data-detail-deck__group-card" data-testid="market-data-detail-livermore-workbench-summary-body">
              {renderUnknownValue(workbenchSummary, "workbench-summary")}
            </div>
          ) : (
            <StateLine testId="market-data-detail-livermore-workbench-summary-state">
              当前 payload 未返回 workbench_summary。
            </StateLine>
          )}
        </ModuleCard>
      </div>
    </ModuleCard>
  );
}
