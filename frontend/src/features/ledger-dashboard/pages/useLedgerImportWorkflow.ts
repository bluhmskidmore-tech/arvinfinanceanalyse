import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { DataSourceMode } from "../../../api/client";
import {
  LedgerRequestError,
  type LedgerClientMethods,
  type LedgerImportRunData,
} from "../../../api/ledgerClient";
import { ledgerImportStatusIsTerminal } from "./ledgerDashboardPageModel";

const PENDING_RUN_STORAGE_KEY = "moss.ledgerImport.pendingRun.v1";
const POLL_INTERVAL_MS = 1_000;
const REQUEST_TIMEOUT_MS = 10_000;
const MAX_POLL_ATTEMPTS = 60;
const MAX_IMPORT_BYTES = 16 * 1024 * 1024;
const SUPPORTED_SUFFIXES = [".csv", ".xls", ".xlsx"];

type LedgerImportClient = Pick<LedgerClientMethods, "importLedger" | "getLedgerImportStatus"> & {
  mode: DataSourceMode;
};

type StoredPendingRun = {
  run_id: string;
  mode: DataSourceMode;
  file_name: string;
};

function restorePendingRun(mode: DataSourceMode): LedgerImportRunData | null {
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(PENDING_RUN_STORAGE_KEY) ?? "null") as
      | StoredPendingRun
      | null;
    if (!stored?.run_id || stored.mode !== mode) {
      return null;
    }
    return {
      run_id: stored.run_id,
      status: "queued",
      file_name: stored.file_name || "--",
    };
  } catch {
    window.sessionStorage.removeItem(PENDING_RUN_STORAGE_KEY);
    return null;
  }
}

function storePendingRun(run: LedgerImportRunData, mode: DataSourceMode) {
  window.sessionStorage.setItem(
    PENDING_RUN_STORAGE_KEY,
    JSON.stringify({ run_id: run.run_id, mode, file_name: run.file_name } satisfies StoredPendingRun),
  );
}

function validateLedgerFile(file: File): string | null {
  const suffix = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!SUPPORTED_SUFFIXES.includes(suffix)) {
    return "仅支持 .csv、.xls 或 .xlsx 文件";
  }
  if (file.size > MAX_IMPORT_BYTES) {
    return "文件不得超过 16 MiB";
  }
  return null;
}

export function useLedgerImportWorkflow(client: LedgerImportClient) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [run, setRun] = useState<LedgerImportRunData | null>(() => restorePendingRun(client.mode));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [pollingError, setPollingError] = useState<string | null>(null);
  const [pollCycle, setPollCycle] = useState(0);
  const runId = run?.run_id ?? null;
  const isPending = Boolean(run && !ledgerImportStatusIsTerminal(run.status));

  useEffect(() => {
    if (!runId || !isPending) {
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let activeController: AbortController | null = null;

    const poll = async () => {
      const controller = new AbortController();
      activeController = controller;
      let requestTimedOut = false;
      const requestTimeout = setTimeout(() => {
        requestTimedOut = true;
        controller.abort();
      }, REQUEST_TIMEOUT_MS);
      try {
        const response = await client.getLedgerImportStatus(runId, controller.signal);
        if (cancelled) return;
        attempts += 1;
        setPollingError(null);
        setRun(response.data);
        if (ledgerImportStatusIsTerminal(response.data.status)) {
          window.sessionStorage.removeItem(PENDING_RUN_STORAGE_KEY);
          await queryClient.invalidateQueries({ queryKey: ["bank-ledger"] });
          return;
        }
      } catch (error) {
        if (cancelled) return;
        attempts += 1;
        if (requestTimedOut) {
          setPollingError("导入状态请求超时，系统将继续重试");
        } else if (error instanceof LedgerRequestError && error.status === 404) {
          window.sessionStorage.removeItem(PENDING_RUN_STORAGE_KEY);
          setRun(null);
          setPollingError("导入任务记录不存在，无法继续确认状态");
          return;
        } else if (error instanceof LedgerRequestError && error.status === 403) {
          setPollingError("当前账号无权查询导入状态；任务结果尚未确认");
          return;
        } else {
          setPollingError("当前无法确认导入状态，系统将继续重试");
        }
      } finally {
        clearTimeout(requestTimeout);
        if (activeController === controller) activeController = null;
      }

      if (attempts >= MAX_POLL_ATTEMPTS) {
        setPollingError("导入状态查询超时；任务结果尚未确认，可稍后继续查询");
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      activeController?.abort();
      if (timer) clearTimeout(timer);
    };
  }, [client, isPending, pollCycle, queryClient, runId]);

  const chooseFile = (nextFile: File | null) => {
    setFile(nextFile);
    setSubmissionError(nextFile ? validateLedgerFile(nextFile) : null);
  };

  const submit = async () => {
    if (!file) {
      setSubmissionError("请先选择台账文件");
      return;
    }
    const validationError = validateLedgerFile(file);
    if (validationError) {
      setSubmissionError(validationError);
      return;
    }
    setIsSubmitting(true);
    setSubmissionError(null);
    setPollingError(null);
    try {
      const response = await client.importLedger(file);
      setRun(response.data);
      storePendingRun(response.data, client.mode);
    } catch (error) {
      setSubmissionError(
        error instanceof LedgerRequestError ? error.message : "台账文件上传失败，请稍后重试",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    file,
    run,
    isPending,
    isSubmitting,
    submissionError,
    pollingError,
    chooseFile,
    submit,
    retryStatus: () => {
      setPollingError(null);
      setPollCycle((current) => current + 1);
    },
  };
}
