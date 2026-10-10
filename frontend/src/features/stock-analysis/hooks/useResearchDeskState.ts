import { useState } from "react";

import type {
  ResearchDeskDossierTab,
  ResearchDeskPoolTab,
} from "../components/research-desk/types";

/**
 * 研究台的本地 UI 状态：候选池 / 档案页签、自选、复核备注。
 *
 * 选中标的（selectedCode）仍留在页面：它的同步 effect 以分析查询之后才派生出的可见队列为输入，
 * 留在页面才能保持该 effect 的依赖数组不变且 setter 对 lint 可见为稳定。
 * 备注保存需要页面派生出的选中候选，所以由调用方在保存时传入；
 * 打开历史会把 candidate-history 端点标记为已请求，该动作属于页面级状态，通过回调注入。
 */
export function useResearchDeskState({
  onRequestCandidateHistory,
}: {
  onRequestCandidateHistory: () => void;
}) {
  const [poolTab, setPoolTab] = useState<ResearchDeskPoolTab>("queue");
  const [dossierTab, setDossierTab] = useState<ResearchDeskDossierTab>("summary");
  const [watchlistCodes, setWatchlistCodes] = useState<string[]>([]);
  const [noteDraft, setNoteDraft] = useState("");
  const [savedNote, setSavedNote] = useState("");

  const toggleWatchlist = (stockCode: string) => {
    setWatchlistCodes((current) =>
      current.includes(stockCode)
        ? current.filter((code) => code !== stockCode)
        : [...current, stockCode],
    );
  };
  const openHistory = () => {
    setPoolTab("history");
    setDossierTab("appendix");
    onRequestCandidateHistory();
  };
  const saveNote = (selectedCandidate: { stockName: string; stockCode: string } | null) => {
    const note = noteDraft.trim();
    if (!note) return;
    const prefix = selectedCandidate
      ? `${selectedCandidate.stockName} ${selectedCandidate.stockCode}：`
      : "";
    setSavedNote(`${prefix}${note}`);
  };

  return {
    poolTab,
    setPoolTab,
    dossierTab,
    setDossierTab,
    watchlistCodes,
    noteDraft,
    setNoteDraft,
    savedNote,
    toggleWatchlist,
    openHistory,
    saveNote,
  };
}
