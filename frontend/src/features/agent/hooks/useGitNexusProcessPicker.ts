import { useDeferredValue, useEffect, useRef, useState } from "react";

export type GitNexusProcessPickerOptions = {
  /** 最近使用过的仓库路径，用于给输入框一个初始值。 */
  recentRepoPaths: string[];
  /** 已固定的仓库路径，用于派生"未固定的最近仓库"与"当前仓库是否已固定"。 */
  pinnedRepoPaths: string[];
};

/**
 * GitNexus 仓库与流程选择器的状态归属。
 *
 * 这里只持有选择器自己的状态与两道并发闸门，不发请求：
 * - `processStateRequestVersionRef` 是"进程状态版本门"，提问、切换仓库、再次读取都会 bump，
 *   迟到的响应据此判断还能不能写回流程列表；
 * - `processLoadSequenceRef` 是"读取序号"，只有最后发起的那次读取负责把
 *   `processLoading` 复位，先返回的请求不得把仍在读取中的按钮改回可用态。
 *
 * 两者必须分开：版本门会被提问 bump，若用它复位 loading，按钮会永久卡在"读取中..."。
 */
export function useGitNexusProcessPicker({
  recentRepoPaths,
  pinnedRepoPaths,
}: GitNexusProcessPickerOptions) {
  const [repoPath, setRepoPath] = useState(() => recentRepoPaths[0] ?? "");
  const [availableProcesses, setAvailableProcesses] = useState<string[]>([]);
  const [processSearch, setProcessSearch] = useState("");
  const [selectedProcess, setSelectedProcess] = useState("");
  const [processLoading, setProcessLoading] = useState(false);
  const repoPathRef = useRef(repoPath);
  const processStateRequestVersionRef = useRef(0);
  const processLoadSequenceRef = useRef(0);

  repoPathRef.current = repoPath;

  const deferredProcessSearch = useDeferredValue(processSearch);
  const filteredProcesses = availableProcesses.filter((processName) =>
    processName.toLowerCase().includes(deferredProcessSearch.trim().toLowerCase()),
  );
  const recentUnpinnedRepoPaths = recentRepoPaths.filter((path) => !pinnedRepoPaths.includes(path));
  const isCurrentRepoPinned = pinnedRepoPaths.includes(repoPath.trim());

  // 选中项始终跟随可见列表：搜索词把当前选中项过滤掉后自动改选第一条，列表为空则清空选中。
  useEffect(() => {
    if (!filteredProcesses.length) {
      setSelectedProcess("");
      return;
    }
    if (!selectedProcess || !filteredProcesses.includes(selectedProcess)) {
      setSelectedProcess(filteredProcesses[0] ?? "");
    }
  }, [filteredProcesses, selectedProcess]);

  function beginProcessStateRequest() {
    processStateRequestVersionRef.current += 1;
    return processStateRequestVersionRef.current;
  }

  function invalidateActiveRequest() {
    processStateRequestVersionRef.current += 1;
  }

  function canCommitProcessState(requestVersion: number, requestRepoPath: string) {
    return (
      processStateRequestVersionRef.current === requestVersion &&
      requestRepoPath === repoPathRef.current.trim()
    );
  }

  /** 领取一次读取序号；只有持有最新序号的调用才可以复位 `processLoading`。 */
  function beginProcessLoadSequence() {
    processLoadSequenceRef.current += 1;
    return processLoadSequenceRef.current;
  }

  function isLatestProcessLoad(sequence: number) {
    return processLoadSequenceRef.current === sequence;
  }

  return {
    repoPath,
    setRepoPath,
    repoPathRef,
    availableProcesses,
    setAvailableProcesses,
    processSearch,
    setProcessSearch,
    selectedProcess,
    setSelectedProcess,
    processLoading,
    setProcessLoading,
    filteredProcesses,
    recentUnpinnedRepoPaths,
    isCurrentRepoPinned,
    beginProcessStateRequest,
    invalidateActiveRequest,
    canCommitProcessState,
    beginProcessLoadSequence,
    isLatestProcessLoad,
  };
}
