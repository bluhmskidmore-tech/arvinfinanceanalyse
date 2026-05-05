import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { readHttpJsonDetail } from "./httpResponseError";
import type { ApiEnvelope } from "./contracts";

type FetchLike = typeof fetch;

type MacroToolkitClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

export type MacroToolkitScriptRecord = {
  name: string;
  filename: string;
  group: string;
  default_data_sources: string[];
  optional_dependencies: string[];
  notes: string;
  path: string;
  available: boolean;
};

export type MacroToolkitOutputFile = {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: string;
};

export type MacroToolkitSourceCheck = {
  alias: string;
  row_count: number;
  latest: null | {
    date: string;
    series_id: string;
    vendor_name: string;
    value: number;
  };
};

export type MacroToolkitPayload = {
  default_data_sources: string[];
  toolkit_root: string;
  output_dir: string;
  scripts: MacroToolkitScriptRecord[];
  groups: string[];
  omitted_scripts: Record<string, string>;
  output_files: MacroToolkitOutputFile[];
  source_checks: MacroToolkitSourceCheck[];
  warnings: string[];
};

export type MacroToolkitIndicator = {
  key: string;
  alias: string;
  label: string;
  group: string;
  unit: string;
  row_count: number;
  latest_date: string | null;
  latest_value: number | null;
  previous_value: number | null;
  change: number | null;
  change_pct: number | null;
  source: string | null;
  series_id: string | null;
  quality: "ok" | "missing";
};

export type MacroToolkitSignalCard = {
  key: string;
  title: string;
  stance: string;
  tone: "positive" | "neutral" | "negative" | "missing";
  score: number | null;
  evidence: string[];
};

export type MacroToolkitAnalysisPayload = {
  default_data_sources: string[];
  as_of_date: string | null;
  conclusion: {
    stance: string;
    tone: "positive" | "neutral" | "negative" | "missing";
    summary: string;
    recommended_action: string;
  };
  coverage: {
    indicator_count: number;
    hit_count: number;
    hit_rate: number;
    script_count: number;
    output_file_count: number;
  };
  indicators: MacroToolkitIndicator[];
  signal_cards: MacroToolkitSignalCard[];
  output_files: MacroToolkitOutputFile[];
  source_checks: MacroToolkitSourceCheck[];
  warnings: string[];
};

export type MacroToolkitRunResponse = {
  status: "completed" | "failed" | "timeout";
  script: MacroToolkitScriptRecord;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  output_files: MacroToolkitOutputFile[];
  message?: string;
};

export type MacroToolkitClientMethods = {
  getMacroToolkitAnalysis: () => Promise<ApiEnvelope<MacroToolkitAnalysisPayload>>;
  getMacroToolkitScripts: () => Promise<ApiEnvelope<MacroToolkitPayload>>;
  runMacroToolkitScript: (
    name: string,
    options?: { timeoutSeconds?: number; argv?: string[] },
  ) => Promise<MacroToolkitRunResponse>;
};

const MOCK_ANALYSIS: MacroToolkitAnalysisPayload = {
  default_data_sources: ["choice", "tushare"],
  as_of_date: "2026-04-30",
  conclusion: {
    stance: "中性观察",
    tone: "neutral",
    summary: "风险资产和资金利率证据接近，当前适合观察数据延续性，而不是给出单边结论。",
    recommended_action: "优先运行 signal_aggregator / risk_monitor 形成交易层信号。",
  },
  coverage: {
    indicator_count: 8,
    hit_count: 7,
    hit_rate: 0.875,
    script_count: 24,
    output_file_count: 0,
  },
  indicators: [
    {
      key: "hs300",
      alias: "sh000300",
      label: "沪深300",
      group: "风险资产",
      unit: "点",
      row_count: 120,
      latest_date: "2026-04-30",
      latest_value: 4807.3069,
      previous_value: 4778.1201,
      change: 29.1868,
      change_pct: 0.6108,
      source: "tushare",
      series_id: "CA.CSI300",
      quality: "ok",
    },
    {
      key: "dr007",
      alias: "DR007.IB",
      label: "DR007",
      group: "流动性",
      unit: "%",
      row_count: 248,
      latest_date: "2026-04-30",
      latest_value: 1.82,
      previous_value: 1.89,
      change: -0.07,
      change_pct: -3.7037,
      source: "choice",
      series_id: "CA.DR007",
      quality: "ok",
    },
    {
      key: "aa_5y",
      alias: "S0059760",
      label: "5Y AA 信用债",
      group: "信用",
      unit: "%",
      row_count: 6,
      latest_date: "2026-04-30",
      latest_value: 2.91,
      previous_value: null,
      change: null,
      change_pct: null,
      source: "choice",
      series_id: "legacy.yield.choice.aa_credit.5Y",
      quality: "ok",
    },
  ],
  signal_cards: [
    {
      key: "liquidity",
      title: "流动性",
      stance: "偏松",
      tone: "positive",
      score: 78,
      evidence: ["DR007 1.82%"],
    },
    {
      key: "risk_appetite",
      title: "风险偏好",
      stance: "改善",
      tone: "positive",
      score: 72,
      evidence: ["沪深300 +0.61%"],
    },
    {
      key: "credit",
      title: "信用利差",
      stance: "中性",
      tone: "neutral",
      score: 55,
      evidence: ["AA-国债 5Y 57.0bp"],
    },
    {
      key: "outputs",
      title: "脚本产物",
      stance: "待生成",
      tone: "neutral",
      score: 45,
      evidence: ["尚未发现输出文件"],
    },
  ],
  output_files: [],
  source_checks: [],
  warnings: [
    "cffexmemberrank member-rank data has scripts and CSV output contracts, but no formal DuckDB table is materialized yet.",
  ],
};

const MOCK_SCRIPTS: MacroToolkitScriptRecord[] = [
  {
    name: "signal_aggregator",
    filename: "signal_aggregator.py",
    group: "macro_signal",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: ["pandas"],
    notes: "",
    path: "scripts/signal_aggregator.py",
    available: true,
  },
  {
    name: "merrill_clock_cn",
    filename: "merrill_clock_cn.py",
    group: "macro_signal",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: ["pandas"],
    notes: "",
    path: "scripts/merrill_clock_cn.py",
    available: true,
  },
  {
    name: "debug_wind",
    filename: "debug_wind.py",
    group: "diagnostic",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: [],
    notes: "",
    path: "scripts/debug_wind.py",
    available: true,
  },
];

const MOCK_PAYLOAD: MacroToolkitPayload = {
  default_data_sources: ["choice", "tushare"],
  toolkit_root: "backend/app/core_finance/macro/toolkit",
  output_dir: "data/macro_toolkit/output",
  scripts: MOCK_SCRIPTS,
  groups: ["diagnostic", "macro_signal"],
  omitted_scripts: {
    "credit_bond_portfolio.py": "Source file has a syntax error in the provided toolkit copy.",
  },
  output_files: [],
  source_checks: [
    {
      alias: "sh000300",
      row_count: 120,
      latest: {
        date: "2026-04-30",
        series_id: "CA.CSI300",
        vendor_name: "tushare",
        value: 4807.3069,
      },
    },
    {
      alias: "M0067855",
      row_count: 851,
      latest: {
        date: "2026-04-30",
        series_id: "EMM00058124",
        vendor_name: "choice",
        value: 6.8628,
      },
    },
  ],
  warnings: [
    "cffexmemberrank member-rank data has scripts and CSV output contracts, but no formal DuckDB table is materialized yet.",
  ],
};

export function createMockMacroToolkitClient(): MacroToolkitClientMethods {
  return {
    async getMacroToolkitAnalysis() {
      return buildMockApiEnvelope("macro_toolkit.analysis", MOCK_ANALYSIS, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "macro_toolkit_mock",
        vendor_version: "choice+tushare",
        rule_version: "rv_macro_toolkit_ui_v1",
        cache_version: "none",
      });
    },
    async getMacroToolkitScripts() {
      return buildMockApiEnvelope("macro_toolkit.scripts", MOCK_PAYLOAD, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "macro_toolkit_mock",
        vendor_version: "choice+tushare",
        rule_version: "rv_macro_toolkit_ui_v1",
        cache_version: "none",
      });
    },
    async runMacroToolkitScript(name) {
      const script = MOCK_SCRIPTS.find((item) => item.name === name) ?? MOCK_SCRIPTS[0]!;
      return {
        status: "completed",
        script,
        exit_code: 0,
        stdout: `mock run completed: ${script.name}`,
        stderr: "",
        output_files: [],
      };
    },
  };
}

export function createRealMacroToolkitClient({
  fetchImpl,
  baseUrl,
}: MacroToolkitClientFactoryOptions): MacroToolkitClientMethods {
  return {
    getMacroToolkitAnalysis: () =>
      requestJson<MacroToolkitAnalysisPayload>(fetchImpl, baseUrl, "/ui/macro/toolkit/analysis"),
    getMacroToolkitScripts: () =>
      requestJson<MacroToolkitPayload>(fetchImpl, baseUrl, "/ui/macro/toolkit/scripts"),
    runMacroToolkitScript: (name, options) =>
      requestActionJson<MacroToolkitRunResponse>(
        fetchImpl,
        baseUrl,
        `/ui/macro/toolkit/scripts/${encodeURIComponent(name)}/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            argv: options?.argv ?? [],
            timeout_seconds: options?.timeoutSeconds ?? 120,
          }),
        },
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestActionJson<TResponse>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as TResponse;
}
