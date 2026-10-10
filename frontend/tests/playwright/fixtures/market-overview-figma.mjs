import fs from "node:fs";
import { loadMock } from "./mock-module.mjs";

// Only the browser test imports this module. Production never reads design fixtures.
const root = new URL("../../../", import.meta.url);
// Frozen copies of the approved synthetic design inputs keep clean checkouts reproducible.
export const fixed = JSON.parse(fs.readFileSync(new URL("market-overview-fixed.json", import.meta.url), "utf8"));
export const risk = JSON.parse(fs.readFileSync(new URL("market-overview-risk-v1.4.json", import.meta.url), "utf8"));
const { buildMockMarketOverviewSnapshot } = loadMock(new URL("src/mocks/marketOverviewSnapshot.ts", root));
const { createMockMacroToolkitClient } = loadMock(new URL("src/mocks/macroToolkitMockClient.ts", root));
const macroClient = createMockMacroToolkitClient();
const { buildMockChoiceNewsEnvelope } = loadMock(new URL("src/mocks/choiceNewsMocks.ts", root));
const date = fixed.observationDate;
const previous = fixed.comparisonDate;
const points = (values) => fixed.dates.map((day, index) => ({ trade_date: `2026-${day}`, value_numeric: values[index] }));

export function buildDesignSnapshot() {
  const envelope = buildMockMarketOverviewSnapshot();
  const p = envelope.result;
  Object.assign(envelope.result_meta, { as_of_date: date, generated_at: `${date}T16:00:00+08:00`, source_surface: "synthetic-browser-test" });
  Object.assign(p.funding_observation, { observation_date: date, comparison_date: previous, summary: "资金价格小幅回落", interpretation: "FDR007（代理）较前期下行 2.00 bp", policy_deviation_bp: null });
  const funding = { ...p.funding_observation.rows[0], label: "FDR007", series_id: "FDR007", value: 1.37, previous_value: 1.39, observation_date: date, previous_date: previous, change_bp: -2, is_proxy: true, recent_points: points(fixed.funding), reason: "FDR007 为代理参考，不能替代本行融资成本。" };
  p.funding_observation.rows = [funding]; p.funding_observation.evidence = [funding];
  Object.assign(p.rates_observation, { observation_date: date, comparison_date: previous, summary: "国债三期限下行，10Y 降幅较大", interpretation: "10Y 下行 1 bp；2Y、5Y 各下行 0.5 bp" });
  p.rates_observation.rows = p.rates_observation.rows.map((row, i) => ({ ...row, value: fixed.curve.current[i], previous_value: fixed.curve.previous[i], change_bp: i === 2 ? -1 : -0.5, observation_date: date, previous_date: previous, recent_points: points(i === 0 ? fixed.rates2Y : i === 2 ? fixed.rates10Y : fixed.rates2Y.map((v) => v + 0.17)) }));
  p.rates_observation.evidence = p.rates_observation.rows;
  p.rates_observation.spreads = p.rates_observation.spreads.map((spread) => {
    const shortIndex = spread.key === "term_10y_2y" ? 0 : 1;
    const current = Number(((fixed.curve.current[2] - fixed.curve.current[shortIndex]) * 100).toFixed(2));
    const prior = Number(((fixed.curve.previous[2] - fixed.curve.previous[shortIndex]) * 100).toFixed(2));
    return { ...spread, value_bp: current, previous_value_bp: prior, change_bp: Number((current - prior).toFixed(2)), observation_date: date, comparison_date: previous };
  });
  p.tape.slots = [p.tape.slots[0], p.tape.slots[1], p.tape.slots[3], p.tape.slots[6]].map((slot, i) => ({ ...slot, value: [1.68, 1.37, null, 7.09][i], change: [-1, -2, null, -0.03][i], change_unit: i === 3 ? "%" : "bp", trade_date: date, label: i === 1 ? "FDR007（代理）" : slot.label, series_id: i === 1 ? "FDR007" : slot.series_id, status: i === 2 ? "unavailable" : "ok", reason: i === 2 ? "暂无有效报价" : null }));
  p.pulse.items = fixed.homeMacro.map((row, i) => ({ ...p.pulse.items[i], label: row.label, latest_value: row.current, previous_value: row.previous, change: Number((row.current - row.previous).toFixed(2)), latest_date: row.periodKey, published_at: row.publishedAt, source: "合成示例", series_id: ["M0000612", "M0001227", "M0017126", "M5525763"][i] }));
  Object.assign(p.crisis, risk.current, { status: "degraded", reason: "刷新回执待核验，商品波动窗口不完整", report_date: date, requested_report_date: date, rule_version: risk.rule_version, data_status: "degraded", score_history: risk.history, score_trends: risk.trends, score_trend: risk.trends[0], available_component_count: 4, component_count: 5, available_weight: 0.85, warnings: ["COMMODITY_VOL_UNAVAILABLE"], dependency_gate: { status: "blocked", blocked_by: [risk.current.dependency], reason_code: "required_refresh_step_not_ready" } });
  p.signals = risk.signals;
  p.actions.items = risk.actions.map((row, i) => ({ ...row, key: ["refresh_gate_blocked", "news_human_review", "crisis_regime_review"][i], basis: "analytical", evidence: { reason: row.label } }));
  p.news.latest = fixed.homeEvents.map((row, i) => ({ event_key: `synthetic-${i}`, received_at: `${i === 2 ? previous : date}T10:00:00+08:00`, topic_code: ["liquidity", "growth", "overseas"][i], group_id: "synthetic", summary: row.title }));
  p.news.sample.latest_received_at = `${date}T10:00:00+08:00`;
  p.news.compare = { ...risk.news_compare, review_items: [] };
  const series = (id, name, unit, history) => ({ series_id: id, series_name: name, display_name: name, unit, frequency: "D", vendor_name: "synthetic", quality_flag: "ok", source_version: "synthetic", vendor_version: "synthetic", trade_date: history.at(-1).trade_date, value_numeric: history.at(-1).value_numeric, recent_points: history });
  p.charts.market_rates.series = [series("E1000180", "国债到期收益率10年", "%", points(fixed.rates10Y)), series("EMM00588704", "国债到期收益率2年", "%", points(fixed.rates2Y))];
  const crossNames = ["Brent spot price", "中证全债指数", "USD/CNY", "沪深300指数收盘价", "铜主力期货收盘价"];
  p.charts.choice_latest.series = fixed.cross.map((row, i) => series(`synthetic-cross-${i}`, crossNames[i], "index", [...fixed.dates.slice(0, 6).map((day) => ({ trade_date: `2026-${day}`, value_numeric: 100 })), { trade_date: `2026-${row.from}`, value_numeric: 100 }, { trade_date: `2026-${row.to}`, value_numeric: 100 + row.value }]));
  p.dates.tape_span = { earliest: date, latest: date };
  p.dates.computed_on = date; p.dates.surfaces.forEach((row) => { row.latest = date; row.age_days = 0; });
  Object.assign(p.gate, { human_reason: "宏观更新结果与评分完整性待核验，已核验的资金和曲线观察可读。", recovery_action: "复核刷新回执并补齐商品波动窗口。" });
  return envelope;
}

export function buildDesignFullAnalysis() {
  const commodities = risk.commodities.map((row, i) => ({ ...row, field: ["rebar", "iron_ore", "copper", "aluminum", "crude_oil", "gold"][i], available: true, used_in_formula: false, series_id: `synthetic-${i}`, source: "合成示例", date_alignment_status: "aligned", decision_label: "继续观察", reason: "继续积累有效样本并复核", correlation_threshold: risk.admission.correlation_threshold }));
  return { result_meta: { basis: "analytical", formal_use_allowed: false }, result: { report_date: date, as_of_date: date, capability_results: [{ key: "crisis_score_cn", status: "degraded", label: "Crisis Score", score: -0.6, result: { crisis_score: -0.6, regime: "宽松", data_status: "degraded", components: risk.components, weights: Object.fromEntries(risk.components.map((r) => [r.key, r.weight])), score_history: risk.history, risk_gate: risk.current.risk_gate, input_evidence: { inputs: [], missing_inputs: [], stale_inputs: [] }, warnings: ["COMMODITY_VOL_UNAVAILABLE"], commodity_coverage: { available_count: 6, tracked_count: 6, items: commodities }, shadow_impact: { ...risk.shadow, candidate_contributions: commodities.map((row) => ({ ...row, candidate_value: row.latest_return_z })) }, commodity_candidate_admission: { ...risk.admission, items: commodities, decision_counts: { recommend_include: 0, watch: 6, do_not_include: 0 } }, commodity_candidate_approval_pack: { summary: "6 类商品继续观察，尚未纳入正式评分。", copy_text: "合成审批材料：商品影子试算不替代正式评分。需要人工复核与审批。" } } }] } };
}

export function buildDesignScenario() {
  const s = fixed.normalScenario;
  return { result_meta: { fallback_mode: "none", result_kind: "risk.tensor.scenario_stress", basis: "scenario", formal_use_allowed: false }, result: { report_date: date, basis: "scenario", rule_version: "synthetic-scenario-v1", source: { source_version: "synthetic" }, evidence: { requested_report_date: date, actual_risk_date: date, date_status: "verified", fallback_status: "none", fallback_date: null, metric_id: s.metricId, scope_label: "适用监管口径持仓", amount_display_allowed: true, human_review_required: true, coverage: { status: "complete", total_position_count: 120, included_position_count: 100, excluded_position_count: 20, missing_risk_position_count: 0, reasons: [] } }, scenarios: [{ scenario_key: s.scenarioKey, source_field: "regulatory_dv01", data_status: "available", human_review_required: true, shock: { raw: 10, raw_text: "10", unit: "bp", display: "10", precision: 2, sign_aware: true }, estimated_impact: { raw: s.estimatedImpactYuan, raw_text: String(s.estimatedImpactYuan), unit: "yuan", display: String(s.estimatedImpactYuan), precision: 2, sign_aware: true } }], warnings: [], source_warnings: [] } };
}

export async function interceptDesignData(page) {
  const reads = { snapshot: 0, full: 0, scenario: 0, paths: [], writes: [], errors: [] };
  page.on("pageerror", (error) => reads.errors.push(error.message));
  await page.route("**/*", async (route) => {
    const req = route.request(); const path = new URL(req.url()).pathname;
    if (/^\/(ui|api)\//.test(path)) reads.paths.push(path);
    if (/^\/(ui|api)\//.test(path) && !["GET", "HEAD", "OPTIONS"].includes(req.method())) reads.writes.push(path);
    let json;
    if (path === "/api/system-read-publication") json = { enabled: false, generation: null, coverage_dates: {} };
    if (path === "/ui/market-overview/snapshot") { reads.snapshot++; json = buildDesignSnapshot(); }
    if (path === "/ui/macro/choice-series/latest" || path === "/ui/market-data/rates") {
      const snapshot = buildDesignSnapshot();
      const formal = path.endsWith("/rates");
      json = { ...snapshot, result: snapshot.result.charts[formal ? "market_rates" : "choice_latest"],
        result_meta: { ...snapshot.result_meta, basis: formal ? "formal" : "analytical", formal_use_allowed: formal } };
    }
    if (path === "/ui/market-data/catalog") {
      const snapshot = buildDesignSnapshot();
      json = { ...snapshot, result: { series: [...snapshot.result.charts.choice_latest.series, ...snapshot.result.charts.market_rates.series] } };
    }
    if (path === "/ui/news/choice-events/latest") json = buildMockChoiceNewsEnvelope({ limit: 500, offset: 0, includePayloadJson: false });
    if (path === "/ui/macro/toolkit/analysis") {
      reads.full++;
      json = await macroClient.getMacroToolkitAnalysis({ detail: new URL(req.url()).searchParams.get("detail") ?? "full" });
      if (new URL(req.url()).searchParams.get("detail") !== "core") {
        // The chart workbench also consumes full analysis. Keep the existing
        // complete DTO and replace only the synthetic crisis drawer capability.
        const crisis = buildDesignFullAnalysis().result.capability_results[0];
        Object.assign(json.result, { report_date: date, as_of_date: date });
        json.result.capability_results = json.result.capability_results.map(row => row.key === crisis.key
          ? { ...row, ...crisis, result: { ...row.result, ...crisis.result } }
          : row);
      }
    }
    if (path === "/ui/macro/toolkit/analysis/strategy-summaries") json = await macroClient.getMacroToolkitStrategySummaries();
    if (path === "/api/risk/tensor/dates") json = { result_meta: { basis: "formal", formal_use_allowed: false, fallback_mode: "none", result_kind: "risk.tensor.dates" }, result: { report_dates: [date], blocked_report_dates: [] } };
    if (path === "/api/risk/scenario-stress") { reads.scenario++; json = buildDesignScenario(); }
    if (json) return route.fulfill({ status: 200, contentType: "application/json", json });
    if (/^\/(ui|api|health)(\/|$)/.test(path)) return route.fulfill({ status: 503, json: { detail: "Not part of the design browser fixture" } });
    return route.continue();
  });
  return reads;
}
