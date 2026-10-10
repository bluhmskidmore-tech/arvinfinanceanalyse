export type CrossAssetQueryFailureKind = "permission" | "load";

export type CrossAssetModuleFailure = {
  module: string;
  kind: CrossAssetQueryFailureKind;
};

export function classifyCrossAssetQueryFailure(error: unknown): CrossAssetQueryFailureKind {
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (/\(403\)/.test(message) || /not allowed to read/i.test(message)) {
    return "permission";
  }
  return "load";
}

export function linkageUnavailableSummary(kind: CrossAssetQueryFailureKind | undefined): string {
  if (kind === "permission") {
    return "联动分析权限受限，四维判断待开通。";
  }
  return "联动分析暂不可用，四维判断待恢复。";
}

export function linkageUnavailableEvidence(kind: CrossAssetQueryFailureKind | undefined): string {
  if (kind === "permission") {
    return "macro_bond_linkage.read 权限不足";
  }
  return "macro_bond_linkage.analysis 加载失败";
}
