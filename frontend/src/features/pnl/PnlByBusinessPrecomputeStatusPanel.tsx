import { type PnlByBusinessPrecomputeStatus } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { usesPnlByBusinessReadinessProtocol } from "./pnlByBusinessPublicationModel";

function formatPrecomputeTimestamp(value: string | null | undefined): string {
  if (!value) {
    return EM_DASH;
  }
  return value.replace("T", " ").replace(/(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/, "");
}

function compactPrecomputeSourceVersion(value: string | null | undefined): string {
  if (!value) {
    return EM_DASH;
  }
  return value.length > 34 ? `${value.slice(0, 34)}…` : value;
}
export function PnlByBusinessPrecomputeStatusPanel({
  status,
  isLoading,
  isError,
  isRebuilding,
  rebuildError,
  onRebuild,
}: {
  status?: PnlByBusinessPrecomputeStatus;
  isLoading: boolean;
  isError: boolean;
  isRebuilding: boolean;
  rebuildError: string | null;
  onRebuild: () => void;
}) {
  const inflight = status?.status === "queued" || status?.status === "running";
  const retryPending = status?.failure_category === "automatic_retry_pending";
  const failed = status?.status === "failed";
  const servingLive = status?.serving_mode === "live_fallback";
  const usesReadinessProtocol = usesPnlByBusinessReadinessProtocol(status);
  const publishedReadinessError =
    status?.readiness === "failed" || status?.readiness === "source_missing";
  const publishedReadinessTitle = status?.readiness === "ready"
    ? "正式结构分析已发布"
    : status?.readiness === "pending"
      ? status.worker_stalled
        ? "正式结构分析准备停滞"
        : "正式结构分析准备中"
      : status?.readiness === "stale"
        ? "正式结构分析已过期"
        : status?.readiness === "failed"
          ? "正式结构分析准备失败"
          : status?.readiness === "source_missing"
            ? "正式结构分析源数据缺失"
            : null;
  const title = isError
    ? usesReadinessProtocol
      ? "正式结构分析状态不可用，已隐藏结构分析"
      : "预计算状态不可用，主结果继续按当前读路径展示"
    : isLoading && !status
      ? "正在读取预计算状态"
      : usesReadinessProtocol && publishedReadinessTitle
        ? publishedReadinessTitle
      : inflight
        ? retryPending
          ? "上次未完成，后台自动重试中"
          : servingLive
          ? "预计算重建中，当前使用实时计算"
          : "预计算重建中，当前继续使用已验证缓存"
        : failed
          ? servingLive
            ? "预计算失败，当前使用实时计算"
            : "最近一次预计算失败，当前仍使用已验证缓存"
          : status?.is_current
            ? "预计算已就绪"
            : "预计算未就绪，当前使用实时计算";
  // 「未就绪，使用实时计算」是降级中状态：左沿走琥珀而非就绪绿（§4 语义色承载状态）。
  const tone =
    failed || isError || publishedReadinessError
      ? "error"
      : inflight || servingLive || !status?.is_current
        ? "warning"
        : "ready";
  const cutoff = status?.report_date ?? status?.latest_available_as_of_date ?? EM_DASH;

  return (
    <section
      className={`pnl-by-business-precompute-status pnl-by-business-precompute-status--${tone}`}
      data-testid="pnl-by-business-precompute-status"
      aria-live="polite"
    >
      <div className="pnl-by-business-precompute-status__summary">
        <span className="pnl-by-business-precompute-status__eyebrow">读模型状态</span>
        <strong>{title}</strong>
        <small>
          {usesReadinessProtocol
            ? "结构分析只读取当前合格的固定发布代次；未就绪或失效时不回退实时计算。"
            : <>后台失败按任务策略自动重试最多 {status?.retry_policy.max_retries ?? 3} 次；实时计算与预计算使用同一后端口径。</>}
        </small>
        {status?.error_message ? (
          <span className="pnl-by-business-precompute-status__error" role="alert">
            {status.error_message}
          </span>
        ) : null}
        {rebuildError ? (
          <span className="pnl-by-business-precompute-status__error" role="alert">
            {rebuildError}
          </span>
        ) : null}
      </div>
      <div className="pnl-by-business-precompute-status__facts">
        <span><small>截至</small><strong>{cutoff}</strong></span>
        <span><small>生成</small><strong>{formatPrecomputeTimestamp(status?.generated_at ?? status?.finished_at)}</strong></span>
        <span title={status?.source_version ?? undefined}>
          <small>源版本</small><strong>{compactPrecomputeSourceVersion(status?.source_version)}</strong>
        </span>
        <span><small>记录</small><strong>{status?.record_count ?? EM_DASH}</strong></span>
      </div>
      <button
        type="button"
        className="pnl-by-business-action-button pnl-by-business-precompute-status__action"
        onClick={onRebuild}
        disabled={isLoading || inflight || status?.readiness === "pending" || isRebuilding}
        aria-label="重新生成预计算"
      >
        {isRebuilding || inflight ? "生成中..." : "重新生成预计算"}
      </button>
    </section>
  );
}
