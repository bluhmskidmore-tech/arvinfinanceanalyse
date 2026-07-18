import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { LightIcon, type LightIconName } from "../../../components/LightIcon";
import type {
  HomeDecisionAction,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";
import {
  buildHomeSearchIndex,
  filterHomeSearchIndex,
  type HomeSearchEntry,
} from "./homeSearchIndex";
import styles from "./dashboardHomeShell.module.css";

type HomeSearchBoxProps = {
  value: string;
  onValueChange: (value: string) => void;
  terminalKpis: readonly HomeTerminalKpi[];
  decisionActions: readonly HomeDecisionAction[];
  reportDate: string;
};

const LISTBOX_ID = "dashboard-home-search-listbox";
const NO_RESULTS_COPY = "未找到相关指标、报告或动作";

function optionId(entry: HomeSearchEntry, index: number): string {
  return `dashboard-home-search-option-${index}-${entry.id}`;
}

function targetWithReportDate(target: string, reportDate: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(reportDate)) {
    return target;
  }

  const hashIndex = target.indexOf("#");
  const hash = hashIndex >= 0 ? target.slice(hashIndex) : "";
  const pathAndSearch = hashIndex >= 0 ? target.slice(0, hashIndex) : target;
  const searchIndex = pathAndSearch.indexOf("?");
  const path = searchIndex >= 0 ? pathAndSearch.slice(0, searchIndex) : pathAndSearch;
  const search = searchIndex >= 0 ? pathAndSearch.slice(searchIndex + 1) : "";
  const params = new URLSearchParams(search);
  params.set("report_date", reportDate);

  return `${path}?${params.toString()}${hash}`;
}

function entryTypeIcon(type: HomeSearchEntry["type"]): LightIconName {
  switch (type) {
    case "page":
      return "appstore";
    case "metric":
      return "bar-chart";
    case "action":
      return "thunderbolt";
    default:
      return "search";
  }
}

/**
 * 首页搜索/命令入口（combobox）。
 *
 * - 搜索对象：现有页面路由、当前首屏指标、当前可执行动作（均来自可信来源）。
 * - 键盘：↑/↓ 选择、Enter 跳转、Esc 关闭、Ctrl/Cmd+K 聚焦。
 * - 无结果时显示"未找到相关指标、报告或动作"并允许清空。
 * - 使用 combobox/listbox 语义，保证键盘与屏幕阅读器可用。
 * - 搜索仅做导航，不改变首页报告日期或业务筛选。
 */
export function HomeSearchBox({
  value,
  onValueChange,
  terminalKpis,
  decisionActions,
  reportDate,
}: HomeSearchBoxProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const index = useMemo(
    () => buildHomeSearchIndex({ terminalKpis, decisionActions }),
    [terminalKpis, decisionActions],
  );
  const results = useMemo(() => filterHomeSearchIndex(index, value), [index, value]);
  const hasQuery = value.trim().length > 0;
  const showResults = open && hasQuery;
  const showNoResults = showResults && results.length === 0;
  const safeActiveIndex =
    results.length > 0 && activeIndex < results.length ? activeIndex : 0;

  useEffect(() => {
    if (activeIndex >= results.length) {
      setActiveIndex(0);
    }
  }, [activeIndex, results.length]);

  // 激活项滚动入视口
  useEffect(() => {
    if (!showResults) {
      return;
    }
    const list = listRef.current;
    if (!list) {
      return;
    }
    const active = list.querySelector<HTMLElement>(`[data-index="${safeActiveIndex}"]`);
    if (active && typeof active.scrollIntoView === "function") {
      active.scrollIntoView({ block: "nearest" });
    }
  }, [safeActiveIndex, showResults]);

  const commitEntry = useCallback(
    (entry: HomeSearchEntry | undefined) => {
      if (!entry) {
        return;
      }
      const target = entry.to;
      setOpen(false);
      if (target) {
        navigate(targetWithReportDate(target, reportDate));
      } else {
        // 本页指标：不离开首页，仅收起候选并清空输入
        onValueChange("");
        inputRef.current?.blur();
      }
    },
    [navigate, onValueChange, reportDate],
  );

  // Ctrl/Cmd+K 聚焦或打开搜索
  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && (event.key === "k" || event.key === "K")) {
        event.preventDefault();
        const input = inputRef.current;
        if (input) {
          input.focus();
          input.select();
          setOpen(true);
        }
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (results.length > 0) {
        setActiveIndex((current) => (current + 1) % results.length);
      }
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (results.length > 0) {
        setActiveIndex((current) =>
          current - 1 < 0 ? results.length - 1 : current - 1,
        );
      }
      return;
    }
    if (event.key === "Enter") {
      if (showResults && results.length > 0) {
        event.preventDefault();
        commitEntry(results[safeActiveIndex]);
      }
      return;
    }
    if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        setOpen(false);
      } else if (value) {
        event.preventDefault();
        onValueChange("");
      }
      return;
    }
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onValueChange(event.target.value);
    setOpen(true);
    setActiveIndex(0);
  };

  const handleFocus = () => {
    if (hasQuery) {
      setOpen(true);
    }
  };

  // Pointer down only preserves the combobox state; click performs the action so
  // assistive technologies that synthesize click events can commit an option.
  const handleOptionMouseDown = (event: React.MouseEvent) => {
    event.preventDefault();
  };

  const clearQuery = () => {
    onValueChange("");
    inputRef.current?.focus();
  };

  const activeOptionId =
    showResults && results.length > 0
      ? optionId(results[safeActiveIndex], safeActiveIndex)
      : undefined;

  return (
    <div className={styles.dhSearch} data-testid="dashboard-home-search-box">
      <LightIcon className={styles.dhSearchIcon} name="search" />
      <input
        ref={inputRef}
        aria-label="搜索指标、报告或动作入口"
        placeholder="搜索指标、报告或动作（Ctrl/Cmd+K）"
        role="combobox"
        aria-expanded={showResults && !showNoResults}
        aria-controls={results.length > 0 ? LISTBOX_ID : undefined}
        aria-autocomplete="list"
        aria-activedescendant={activeOptionId}
        autoComplete="off"
        value={value}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onKeyDown={handleKeyDown}
        onBlur={() => {
          // 延迟收起，给 onMouseDown 留出触发窗口
          window.setTimeout(() => setOpen(false), 120);
        }}
      />
      {value ? (
        <button
          type="button"
          aria-label="清空搜索"
          className={styles.dhSearchClear}
          onMouseDown={(event) => {
            event.preventDefault();
          }}
          onClick={clearQuery}
        >
          ×
        </button>
      ) : null}
      {showNoResults ? (
        <div className={styles.dhSearchNoResults} role="status">
          {NO_RESULTS_COPY}
          <button
            type="button"
            className={styles.dhSearchClearInline}
            onMouseDown={(event) => {
              event.preventDefault();
            }}
            onClick={clearQuery}
          >
            清空
          </button>
        </div>
      ) : showResults ? (
        <ul
          id={LISTBOX_ID}
          ref={listRef}
          role="listbox"
          aria-label="搜索结果"
          className={styles.dhSearchListbox}
        >
          {results.map((entry, index) => (
            <li
              key={entry.id}
              id={optionId(entry, index)}
              role="option"
              aria-selected={index === safeActiveIndex}
              data-index={index}
              data-testid={`dashboard-home-search-option-${entry.id}`}
              className={`${styles.dhSearchOption} ${
                index === safeActiveIndex ? styles.dhSearchOptionActive : ""
              }`}
              onMouseDown={handleOptionMouseDown}
              onClick={() => commitEntry(entry)}
              onMouseEnter={() => setActiveIndex(index)}
            >
              <LightIcon name={entryTypeIcon(entry.type)} />
              <span className={styles.dhSearchOptionName}>{entry.name}</span>
              <span className={styles.dhSearchOptionType}>{entry.typeLabel}</span>
              <span className={styles.dhSearchOptionDesc}>{entry.description}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
