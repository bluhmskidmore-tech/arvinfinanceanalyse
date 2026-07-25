import type { CrossAssetStatusFlag } from "./crossAssetDriversPageModel";

export type CrossAssetStatusStripTone = "ok" | "warn" | "stale" | "error" | "info";

export type CrossAssetStatusStripFlag = {
  tone: CrossAssetStatusStripTone;
  label: string;
};

/**
 * 把 view model 的 CrossAssetStatusFlag[]（tone: normal/caution/warning/danger）
 * 归一到状态带 chip 形状（tone: ok/warn/stale/error/info）。
 *
 * 映射：danger→error；warning/caution→warn；normal→ok；
 * 特判：id=stale→stale（陈旧单独成档），id=dual-source→info（双源就绪为提示性信息）。
 */
function stripToneFor(flag: CrossAssetStatusFlag): CrossAssetStatusStripTone {
  if (flag.id === "stale") {
    return "stale";
  }
  if (flag.id === "dual-source") {
    return "info";
  }
  switch (flag.tone) {
    case "danger":
      return "error";
    case "warning":
    case "caution":
      return "warn";
    case "normal":
      return "ok";
    default:
      return "info";
  }
}

/** 归一状态旗标供 S1 数据状态带消费；空/无效输入归一为 []，按 tone|label 去重。 */
export function buildStatusStripFlags(
  statusFlags: CrossAssetStatusFlag[] | null | undefined,
): CrossAssetStatusStripFlag[] {
  if (!statusFlags?.length) {
    return [];
  }
  const seen = new Set<string>();
  const flags: CrossAssetStatusStripFlag[] = [];
  for (const flag of statusFlags) {
    const label = flag.label?.trim();
    if (!label) {
      continue;
    }
    const tone = stripToneFor(flag);
    const dedupeKey = `${tone}|${label}`;
    if (seen.has(dedupeKey)) {
      continue;
    }
    seen.add(dedupeKey);
    flags.push({ tone, label });
  }
  return flags;
}
