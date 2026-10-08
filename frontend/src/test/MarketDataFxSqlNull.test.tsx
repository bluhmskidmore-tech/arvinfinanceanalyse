import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import httpPayload from "./fixtures/fxSqlNullHttp.json";
import MarketDataExplorerView from "../features/market-data/pages/MarketDataExplorerView";
import { buildMarketFinancialChartSections } from "../features/workbench/module-home/marketFinancialChartsModel";
import { formatChoiceMacroValue } from "../utils/choiceMacroFormat";
import { sparklineFromChoicePoint } from "../features/workbench/module-home/marketHomeRowEnrichment";
import { buildTerminalSparklineValues } from "../features/market-data/lib/marketDataTerminalModel";
import { resolveCrossAssetKpis, crossAssetTrendLines } from "../features/cross-asset/lib/crossAssetKpiModel";
import type { ChoiceMacroLatestPoint } from "../api/contracts";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiEnvelope, FxAnalyticalPayload } from "../api/contracts";
import { createRealMarketDataClient } from "../api/marketDataClient";
import { EM_DASH } from "../utils/format";
const chart = vi.hoisted(() => ({ render: vi.fn() }));
vi.mock("../components/charts/ChartCard", () => ({ ChartCard: (props: { testId?: string; option: unknown }) => {
  chart.render(props); return <figure data-testid={props.testId} />;
}}));
import { MarketDataFxThemeCard } from "../features/market-data/components/MarketDataFxThemeCard";
import type { FxAnalyticalGroup } from "../api/contracts";

// Exercise the current theme-card consumer; the obsolete deck is not restored.
function FxGroups({ groups, groupTitle }: { groups: FxAnalyticalGroup[]; groupTitle: (title: string) => string }) {
  return <>{groups.map((group) => <MarketDataFxThemeCard key={group.group_key} group={group} title={groupTitle(group.title)} />)}</>;
}

function envelope(values: (number | null)[]): ApiEnvelope<FxAnalyticalPayload> {
  return {
    result_meta: { basis: "analytical", formal_use_allowed: false, quality_flag: "warning" },
    result: { read_target: "duckdb", groups: [{ group_key: "fx_swap_curve", title: "Swap", description: "Synthetic", series: [{
      group_key: "fx_swap_curve", series_id: "NULL_SWAP", series_name: "C-Swap", trade_date: "2026-10-06", value_numeric: values[0], frequency: "daily", unit: "bp", source_version: "synthetic-0", vendor_version: "synthetic-0", quality_flag: "warning", latest_change: null,
      recent_points: values.map((value, i) => ({ trade_date: `2026-10-0${6-i}`, value_numeric: value, source_version: `synthetic-${i}`, vendor_version: `synthetic-${i}`, quality_flag: "ok" })),
    }] }] },
  } as ApiEnvelope<FxAnalyticalPayload>;
}

describe("B1 FX wire null consumers", () => {
  beforeEach(() => chart.render.mockClear());
  it("renders missing prior without crashing or inventing a zero and preserves the chart gap", () => {
    const body=envelope([-1,null,0]);
    render(<FxGroups groups={body.result.groups} groupTitle={(x)=>x} />);
    const row=screen.getByTestId("market-data-fx-series-fx_swap_curve-NULL_SWAP");
    expect(row.querySelector(".market-data-series-compact-prior")?.textContent).toBe(`10-05 ${EM_DASH}`);
    expect(row.querySelector(".market-data-terminal-sparkline")).toBeNull();
    fireEvent.click(screen.getByTestId("market-data-fx-series-fx_swap_curve-chart-toggle-NULL_SWAP"));
    const props=chart.render.mock.calls.find(([x])=>x.testId==="market-data-fx-series-fx_swap_curve-time-chart-NULL_SWAP")?.[0];
    expect(props?.option).toMatchObject({xAxis:{data:["2026-10-04","2026-10-05","2026-10-06"]},series:[{data:[0,null,-1],connectNulls:false}]});
  });
  it("renders missing latest as missing while preserving a real zero", () => {
    const body=envelope([null,0,-1]);
    render(<FxGroups groups={body.result.groups} groupTitle={(x)=>x} />);
    const row=screen.getByTestId("market-data-fx-series-fx_swap_curve-NULL_SWAP");
    expect(row.querySelector(".market-data-series-compact-value")?.textContent).toBe(EM_DASH);
    expect(row.querySelector(".market-data-series-compact-prior")?.textContent).toBe("10-05 0.00");
  });
  it("normalizes only invalid wire numerics, keeps metadata, zero and negative unchanged", async () => {
    const wire=envelope([Number.NaN,0,-1]);
    const fetchImpl=vi.fn(async()=>({ok:true,status:200,headers:new Headers(),json:async()=>wire})) as unknown as typeof fetch;
    const client=createRealMarketDataClient({fetchImpl,baseUrl:""});
    const body=await client.getFxAnalytical();
    expect(body.result.groups[0].series[0].value_numeric).toBeNull();
    expect(body.result.groups[0].series[0].recent_points?.map((p)=>p.value_numeric)).toEqual([null,0,-1]);
    expect(body.result.groups[0].series[0].source_version).toBe("synthetic-0");
  });
});


function FxRead({ client }: { client: ReturnType<typeof createRealMarketDataClient> }) {
  const query=useQuery({queryKey:["synthetic-fx-null"],queryFn:()=>client.getFxAnalytical(),retry:false});
  return <MarketDataExplorerView stableSeries={[]} fallbackSeries={[]} missingStableSeries={[]} catalog={[]}
    fxGroups={query.data?.result.groups ?? []} macroLoading={false} macroError={false} macroEmpty onMacroRetry={()=>undefined}
    fxLoading={query.isLoading} fxError={query.isError} onFxRetry={()=>{void query.refetch();}} observationDate="2026-10-07" />;
}

describe("synthetic DuckDB HTTP response replay through actual client and explorer", () => {
  it("shows a real SQL-null fallback through the actual read path and retries a domain 503", async () => {
    const fetchImpl=vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({detail:{code:"fx_analytical_unavailable",message:"no valid input rows",error_message:"no valid input rows"}}),{status:503}))
      .mockResolvedValueOnce(new Response(JSON.stringify(httpPayload),{status:200}));
    const client=createRealMarketDataClient({fetchImpl,baseUrl:""});
    const queryClient=new QueryClient({defaultOptions:{queries:{retry:false}}});
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/market-data?domain=fx"]}><FxRead client={client}/></MemoryRouter></QueryClientProvider>);
    fireEvent.click(await screen.findByRole("button",{name:/重试/}));
    const row=await screen.findByTestId("market-data-fx-series-middle_rate-synthetic-fx");
    expect(row.querySelector(".market-data-series-compact-value")?.textContent).toBe("7.2");
    expect(row.querySelector(".market-data-series-compact-value-stack")).toHaveAttribute("title","7.2 synthetic-unit");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const body=queryClient.getQueryData<ApiEnvelope<FxAnalyticalPayload>>(["synthetic-fx-null"]);
    expect(body?.result.groups[0].series[0]).toMatchObject({trade_date:"2026-10-05",source_version:"sv_synthetic_observation_1",latest_change:null});
    expect(body?.result.groups[0].series[0].recent_points?.[0].value_numeric).toBeNull();
    expect(body?.result_meta.filters_applied?.warnings).toEqual(httpPayload.result_meta.filters_applied.warnings);
    queryClient.clear();
  });
  it.each([
    [503,"fx_analytical_read_failed"],
    [503,"fx_analytical_unavailable"],
    [409,"system_read_generation_unavailable"],
    [403,"permission_denied"],
  ])("preserves %s domain error content (%s) without normalizing it into empty data",async(status,code)=>{
    const client=createRealMarketDataClient({baseUrl:"",fetchImpl:vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:{code,message:"Synthetic read failure"}}),{status}))});
    await expect(client.getFxAnalytical()).rejects.toThrow(code);
  });
  it("shared macro consumers do not manufacture values or undated trends from FX null",()=>{
    const point={...httpPayload.result.groups[0].series[0],series_id:"CA.USDCNY",value_numeric:null,latest_change:null} as ChoiceMacroLatestPoint;
    expect(formatChoiceMacroValue(point)).toBe(EM_DASH);
    expect(sparklineFromChoicePoint(point)).toBeUndefined();
    expect(buildTerminalSparklineValues(point)).toEqual([]);
    const kpi=resolveCrossAssetKpis([point]).find((item)=>item.format==="fx");
    expect(kpi?.valueLabel).toBe(EM_DASH);
    expect(crossAssetTrendLines([point]).every((line)=>line.values.length===0)).toBe(true);
  });
});


describe("shared FX historical chart semantics",()=>{
  it("uses the first available observation as base while retaining the leading null date",()=>{
    const values=[null,7,7.1,7.2,7.3,7.4,7.5,7.6,7.7];
    const point: ChoiceMacroLatestPoint={
      series_id:"CA.USDCNY",series_name:"USD/CNY",value_numeric:7.7,unit:"CNY/USD",trade_date:"2026-09-09",source_version:"synthetic",vendor_version:"synthetic",quality_flag:"ok",
      recent_points:values.map((value,i)=>({trade_date:`2026-09-0${i+1}`,value_numeric:value,source_version:"synthetic",vendor_version:"synthetic",quality_flag:"ok"})),
    };
    const chart=buildMarketFinancialChartSections({latest:{read_target:"duckdb",series:[point]}}).flatMap((section)=>section.charts).find((candidate)=>candidate.key==="cross-asset-index");
    expect(chart?.option).toMatchObject({xAxis:{data:point.recent_points?.map((p)=>p.trade_date)},series:[{data:[null,100,...values.slice(2).map((v)=>v! / 7 * 100)]}]});
  });
});

describe("FX duplicate-date lineage at the client boundary",()=>{
  it("keeps both observed source identities and the selected fallback headline",async()=>{
    const wire=structuredClone(httpPayload);
    const selected=wire.result.groups[0].series[0];
    selected.recent_points[0].trade_date=selected.recent_points[1].trade_date;
    const client=createRealMarketDataClient({baseUrl:"",fetchImpl:vi.fn().mockResolvedValue(new Response(JSON.stringify(wire),{status:200}))});
    const normalized=await client.getFxAnalytical();
    const actual=normalized.result.groups[0].series[0];
    expect(actual.recent_points).toHaveLength(3);
    expect(actual.recent_points?.slice(0,2).map((p)=>[p.trade_date,p.value_numeric,p.source_version])).toEqual([
      ["2026-10-05",null,"sv_synthetic_observation_0"],
      ["2026-10-05",7.2,"sv_synthetic_observation_1"],
    ]);
    expect(actual.source_version).toBe("sv_synthetic_observation_1");
    expect(actual.value_numeric).toBe(7.2);
  });
});


it("does not present the selected fallback quote itself as a prior-date value",async()=>{
  const client=createRealMarketDataClient({baseUrl:"",fetchImpl:vi.fn().mockResolvedValue(new Response(JSON.stringify(httpPayload),{status:200}))});
  const payload=await client.getFxAnalytical();
  const selected=payload.result.groups[0].series[0];
  selected.recent_points=selected.recent_points?.slice(0,2);
  render(<FxGroups groups={payload.result.groups} groupTitle={(x)=>x}/>);
  const row=screen.getByTestId("market-data-fx-series-middle_rate-synthetic-fx");
  expect(row.querySelector(".market-data-series-compact-value")?.textContent).toBe("7.2");
  expect(row.querySelector(".market-data-series-compact-prior")).toBeNull();
});
