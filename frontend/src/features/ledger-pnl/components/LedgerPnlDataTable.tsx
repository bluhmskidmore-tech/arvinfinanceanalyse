import { useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import { EM_DASH } from "../../../utils/format";

import "./LedgerPnlDataTable.css";

export type LedgerPnlDataTableColumn<T> = {
  key: string;
  header: string;
  align?: "left" | "right";
  /** 单元格渲染 */
  render: (row: T) => ReactNode;
  /** 提供则该列可排序；返回 null 视为最小（排在最后） */
  sortValue?: (row: T) => number | string | null;
  /** 提供则该列参与搜索匹配（大小写不敏感、trim） */
  searchValue?: (row: T) => string;
  /** 列宽提示，例如 "120px" 或 "18%" */
  width?: string;
  /** 该列是否为数值列（启用 tabular-nums 与右对齐默认值） */
  numeric?: boolean;
};

export type LedgerPnlDataTableSort = { key: string; direction: "asc" | "desc" };

type LedgerPnlDataTableProps<T> = {
  testId: string;
  title: string;
  /** 标题右侧的补充说明，例如 "共 340 个科目" */
  caption?: ReactNode;
  columns: LedgerPnlDataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  isLoading?: boolean;
  isError?: boolean;
  loadingMessage: string;
  errorMessage: string;
  emptyMessage: string;
  /** 未提供则不显示搜索框 */
  searchPlaceholder?: string;
  defaultSort?: LedgerPnlDataTableSort;
  /** 每页条数，默认 25；传 0 表示不分页 */
  pageSize?: number;
  /** 工具条右侧插槽，例如"清除筛选"按钮 */
  toolbarExtra?: ReactNode;
  /** 表格上方的提示条（例如口径警告），整块渲染 */
  notice?: ReactNode;
  /** 表体最大高度，例如 "520px"；设置后表体内滚且表头吸顶 */
  maxBodyHeight?: string;
  /** 行点击回调，提供则行可点击（带 hover 态与键盘可达） */
  onRowClick?: (row: T) => void;
};

const DEFAULT_PAGE_SIZE = 25;

function compareValues(a: number | string | null, b: number | string | null, direction: 1 | -1): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  if (typeof a === "number" && typeof b === "number") {
    return (a - b) * direction;
  }
  return String(a).localeCompare(String(b), "zh-Hans") * direction;
}

function columnAlignment<T>(column: LedgerPnlDataTableColumn<T>): "left" | "right" {
  return column.align ?? (column.numeric ? "right" : "left");
}

export function LedgerPnlDataTable<T>(props: LedgerPnlDataTableProps<T>): JSX.Element {
  const {
    testId,
    title,
    caption,
    columns,
    rows,
    rowKey,
    isLoading = false,
    isError = false,
    loadingMessage,
    errorMessage,
    emptyMessage,
    searchPlaceholder,
    defaultSort,
    pageSize = DEFAULT_PAGE_SIZE,
    toolbarExtra,
    notice,
    maxBodyHeight,
    onRowClick,
  } = props;

  const [searchTerm, setSearchTerm] = useState("");
  const [sort, setSort] = useState<LedgerPnlDataTableSort | null>(defaultSort ?? null);
  const [page, setPage] = useState(1);

  const columnByKey = useMemo(() => new Map(columns.map((column) => [column.key, column])), [columns]);
  const searchableColumns = useMemo(() => columns.filter((column) => column.searchValue), [columns]);
  const normalizedSearch = searchTerm.trim().toLowerCase();

  const filteredRows = useMemo(() => {
    if (!normalizedSearch || searchableColumns.length === 0) return rows;
    return rows.filter((row) =>
      searchableColumns.some((column) =>
        column.searchValue!(row).trim().toLowerCase().includes(normalizedSearch),
      ),
    );
  }, [rows, normalizedSearch, searchableColumns]);

  const sortedRows = useMemo(() => {
    if (!sort) return filteredRows;
    const column = columnByKey.get(sort.key);
    if (!column?.sortValue) return filteredRows;
    const sortValue = column.sortValue;
    const direction = sort.direction === "asc" ? 1 : -1;
    return [...filteredRows].sort((rowA, rowB) =>
      compareValues(sortValue(rowA), sortValue(rowB), direction),
    );
  }, [filteredRows, sort, columnByKey]);

  const isUnpaged = pageSize === 0;
  const totalRows = sortedRows.length;
  const totalPages = isUnpaged ? 1 : Math.max(1, Math.ceil(totalRows / pageSize));
  const currentPage = isUnpaged ? 1 : Math.min(Math.max(page, 1), totalPages);
  const showPagination = !isUnpaged && totalRows > pageSize;

  const pagedRows = useMemo(() => {
    if (isUnpaged) return sortedRows;
    const start = (currentPage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, isUnpaged, currentPage, pageSize]);

  function handleSearchChange(value: string) {
    setSearchTerm(value);
    setPage(1);
  }

  function computeStateContent(): { role: "status" | "alert"; node: ReactNode } | null {
    if (isLoading) return { role: "status", node: loadingMessage };
    if (isError) return { role: "alert", node: errorMessage };
    if (rows.length === 0) return { role: "status", node: emptyMessage };
    if (sortedRows.length === 0) {
      return {
        role: "status",
        node: (
          <span className="ledger-pnl-data-table__no-match">
            没有匹配&ldquo;{searchTerm}&rdquo;的记录
            <button
              type="button"
              className="ledger-pnl-data-table__clear-search"
              onClick={() => handleSearchChange("")}
            >
              清除搜索
            </button>
          </span>
        ),
      };
    }
    return null;
  }

  const stateContent = computeStateContent();

  function handleSortClick(column: LedgerPnlDataTableColumn<T>) {
    setSort((prev) => {
      if (!prev || prev.key !== column.key) {
        return { key: column.key, direction: "asc" };
      }
      if (prev.direction === "asc") {
        return { key: column.key, direction: "desc" };
      }
      return defaultSort ?? null;
    });
    setPage(1);
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, row: T) {
    if (!onRowClick) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowClick(row);
    }
  }

  const rangeStart = totalRows === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const rangeEnd = isUnpaged ? totalRows : Math.min(currentPage * pageSize, totalRows);

  return (
    <div className="ledger-pnl-data-table" data-testid={testId}>
      <div className="ledger-pnl-data-table__toolbar">
        <div className="ledger-pnl-data-table__heading">
          <h3 className="ledger-pnl-data-table__title">{title}</h3>
          {caption ? <span className="ledger-pnl-data-table__caption">{caption}</span> : null}
        </div>
        <div className="ledger-pnl-data-table__controls">
          {searchPlaceholder ? (
            <input
              type="search"
              className="ledger-pnl-data-table__search"
              data-testid={`${testId}-search`}
              placeholder={searchPlaceholder}
              aria-label={`${title}搜索`}
              value={searchTerm}
              onChange={(event) => handleSearchChange(event.target.value)}
            />
          ) : null}
          {toolbarExtra}
        </div>
      </div>
      {notice ? <div className="ledger-pnl-data-table__notice">{notice}</div> : null}
      <div
        className="ledger-pnl-data-table__scroll"
        style={maxBodyHeight ? { maxHeight: maxBodyHeight } : undefined}
      >
        <table className="ledger-pnl-data-table__table" aria-label={title}>
          <thead>
            <tr>
              {columns.map((column) => {
                const alignment = columnAlignment(column);
                const isSortable = Boolean(column.sortValue);
                const isActive = sort?.key === column.key;
                const ariaSort: "ascending" | "descending" | "none" | undefined = isSortable
                  ? isActive
                    ? sort!.direction === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                  : undefined;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    className={`ledger-pnl-data-table__th ledger-pnl-data-table__th--${alignment}`}
                    style={column.width ? { width: column.width } : undefined}
                    aria-sort={ariaSort}
                  >
                    {isSortable ? (
                      <button
                        type="button"
                        className="ledger-pnl-data-table__sort-button"
                        onClick={() => handleSortClick(column)}
                      >
                        <span>{column.header}</span>
                        <span
                          aria-hidden="true"
                          className="ledger-pnl-data-table__sort-icon"
                          data-direction={isActive ? sort!.direction : "none"}
                        />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {stateContent ? (
              <tr>
                <td colSpan={columns.length} className="ledger-pnl-data-table__state-cell">
                  <div role={stateContent.role}>{stateContent.node}</div>
                </td>
              </tr>
            ) : (
              pagedRows.map((row) => {
                const clickable = Boolean(onRowClick);
                return (
                  <tr
                    key={rowKey(row)}
                    className={
                      clickable
                        ? "ledger-pnl-data-table__row ledger-pnl-data-table__row--clickable"
                        : "ledger-pnl-data-table__row"
                    }
                    role={clickable ? "button" : undefined}
                    tabIndex={clickable ? 0 : undefined}
                    onClick={clickable ? () => onRowClick!(row) : undefined}
                    onKeyDown={clickable ? (event) => handleRowKeyDown(event, row) : undefined}
                  >
                    {columns.map((column) => {
                      const alignment = columnAlignment(column);
                      const numericClass = column.numeric ? " ledger-pnl-data-table__td--numeric" : "";
                      return (
                        <td
                          key={column.key}
                          className={`ledger-pnl-data-table__td ledger-pnl-data-table__td--${alignment}${numericClass}`}
                        >
                          {column.render(row) ?? EM_DASH}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {showPagination ? (
        <div className="ledger-pnl-data-table__pagination">
          <span className="ledger-pnl-data-table__range" data-testid={`${testId}-range`}>
            第 {rangeStart}-{rangeEnd} 条 / 共 {totalRows} 条
          </span>
          <div className="ledger-pnl-data-table__pagination-controls">
            <span className="ledger-pnl-data-table__page-indicator">
              第 {currentPage}/{totalPages} 页
            </span>
            <button
              type="button"
              className="ledger-pnl-data-table__page-button"
              data-testid={`${testId}-prev`}
              disabled={currentPage <= 1}
              onClick={() => setPage(Math.max(1, currentPage - 1))}
            >
              上一页
            </button>
            <button
              type="button"
              className="ledger-pnl-data-table__page-button"
              data-testid={`${testId}-next`}
              disabled={currentPage >= totalPages}
              onClick={() => setPage(Math.min(totalPages, currentPage + 1))}
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
