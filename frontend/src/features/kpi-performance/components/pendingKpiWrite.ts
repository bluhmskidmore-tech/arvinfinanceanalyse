/** Stopping the local wait or losing a response never proves a server write was cancelled. */
export type KpiWriteOutcome = { changed: boolean; confirmed: boolean; error?: string };
export type PendingKpiWrite = Promise<KpiWriteOutcome>;
export type KpiPendingWriteProps = {
  writePending?: boolean;
  /** Share the same page-level recovery for an explicit stop and an unconfirmed rejection. */
  onUnconfirmedWrite?: (write: PendingKpiWrite, notice?: string) => void;
};

export function observeKpiWrite<T>(
  operation: Promise<T>,
  outcome: (result: T) => KpiWriteOutcome = () => ({ changed: true, confirmed: true }),
): PendingKpiWrite {
  return Promise.resolve(operation).then(outcome, (error: unknown) => ({
    changed: false,
    confirmed: false,
    error: error instanceof Error ? error.message : "写入请求未确认成功",
  }));
}

export type KpiStoppedWrite = {
  id: number;
  contextKey: string;
  contextLabel: string;
  /** Keep every unconfirmed request in this owner/year until each response settles. */
  writes: Record<number, KpiWriteOutcome | undefined>;
  outcome?: KpiWriteOutcome;
  notice?: string;
  readbackDone?: boolean;
  released?: boolean;
};
