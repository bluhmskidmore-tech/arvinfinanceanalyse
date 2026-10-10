import type { ModuleHomeDataState, ModuleHomeSourceQueries } from "./moduleHomeModel";

const SNAPSHOT_STATE_LABELS: Record<ModuleHomeDataState, string> = {
  loading: "读取中",
  empty: "暂无数据",
  error: "读取失败",
  partial: "部分可用",
  stale: "数据过期",
  ready: "数据可用",
};

/** 首屏状态只反映本次快照，不把尚未展开的明细查询计作缺失来源。 */
export function buildMarketHomeSnapshotState(query: ModuleHomeSourceQueries["marketSnapshot"]) {
  const envelope = query?.data;
  let dataState: ModuleHomeDataState;
  let stateDetail: string;
  if (!envelope) {
    dataState = query?.isLoading ? "loading" : query?.isError ? "error" : "empty";
    stateDetail = dataState === "loading"
      ? "正在读取市场总览快照。"
      : dataState === "error"
        ? "市场快照读取失败，当前不形成判断。"
        : "市场快照暂未返回可用数据。";
  } else if (query?.isError) {
    dataState = "partial";
    stateDetail = "快照刷新失败，当前保留上次成功读取的数据。";
  } else {
    const { result, result_meta: meta } = envelope;
    const components = Object.values(result.components);
    const hasStaleSource = meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale" ||
      components.some((component) => component.quality_flag === "stale" || component.vendor_status === "vendor_stale");
    const hasPartialSource = meta.quality_flag !== "ok" || meta.vendor_status !== "ok" || meta.fallback_mode !== "none" ||
      components.some((component) => component.status !== "ok") || result.gate?.level !== "ok";
    dataState = hasStaleSource ? "stale" : hasPartialSource ? "partial" : "ready";
    stateDetail = dataState === "stale"
      ? "快照包含过期来源，请按各项观测日期核验。"
      : result.gate?.level === "blocked"
        ? "判断所需来源暂不可用；已返回行情保留展示。"
        : dataState === "partial"
          ? "快照部分来源受限，使用前请核验对应证据。"
          : "市场快照已返回，各项数据沿用各自观测日期。";
  }
  return { dataState, stateLabel: SNAPSHOT_STATE_LABELS[dataState], stateDetail };
}
