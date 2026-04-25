import { Alert } from "antd";

import type { ResultMeta } from "../../../api/contracts";

type MacroLatestReadinessBannerProps = {
  testId: string;
  isLoading: boolean;
  isError: boolean;
  hasSeries: boolean;
  meta: ResultMeta | undefined;
};

function vendorStaleLabel(status: ResultMeta["vendor_status"]) {
  if (status === "vendor_stale") {
    return "供应商数据可能陈旧（vendor_stale）";
  }
  if (status === "vendor_unavailable") {
    return "供应商不可用（vendor_unavailable）";
  }
  return null;
}

function alertType(
  tone: "loading" | "error" | "empty" | "warn" | "ok",
): "info" | "error" | "warning" | "success" {
  if (tone === "error") {
    return "error";
  }
  if (tone === "warn") {
    return "warning";
  }
  if (tone === "empty") {
    return "warning";
  }
  if (tone === "loading") {
    return "info";
  }
  return "success";
}

/**
 * 区分：载入失败、无数据、供应商陈旧、快照降级、正常。
 * 不推断业务日期是否“过期”，仅展示后端 result_meta 与查询状态。
 */
export function MacroLatestReadinessBanner({
  testId,
  isLoading,
  isError,
  hasSeries,
  meta,
}: MacroLatestReadinessBannerProps) {
  let tone: "loading" | "error" | "empty" | "warn" | "ok" = "ok";
  const parts: string[] = [];

  if (isLoading) {
    tone = "loading";
    parts.push("宏观序列 latest 读面载入中…");
  } else if (isError) {
    tone = "error";
    parts.push("宏观序列 latest 读面载入失败；请使用下方区块内「重试」。");
  } else if (!hasSeries) {
    tone = "empty";
    parts.push("宏观序列 latest 读面返回空：当前无可展示序列（非前端补数）。");
  } else {
    parts.push("宏观序列 latest 读面已返回数据。");
    const stale = meta ? vendorStaleLabel(meta.vendor_status) : null;
    if (stale) {
      tone = "warn";
      parts.push(stale);
    }
    if (meta?.fallback_mode === "latest_snapshot") {
      tone = tone === "ok" ? "warn" : tone;
      parts.push("结果含快照降级（fallback_mode=latest_snapshot）。");
    }
    if (meta?.quality_flag && meta.quality_flag !== "ok") {
      tone = tone === "ok" ? "warn" : tone;
      parts.push(`quality_flag=${meta.quality_flag}。`);
    }
  }

  return (
    <Alert
      data-testid={testId}
      type={alertType(tone)}
      showIcon
      message={parts.join(" ")}
    />
  );
}
