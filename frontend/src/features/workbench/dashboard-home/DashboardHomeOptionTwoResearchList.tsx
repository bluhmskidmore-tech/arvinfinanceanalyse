import type {
  HomeResearchReportRow,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";
import {
  normalizeHomeResearchLink,
  normalizeHomeResearchPublishedDate,
} from "./dashboardHomeResearchContract";
import { formatResearchTitleDisplay } from "./lib/researchTitleDisplay";
import styles from "./dashboardHomeOptionTwoResearchList.module.css";

import { EM_DASH } from "../../../utils/format";
const GAP = EM_DASH;
const MAX_VISIBLE_REPORTS = 5;

export type DashboardHomeOptionTwoResearchListProps = {
  reports: readonly HomeResearchReportRow[];
  state: HomeTerminalListState;
};

function rawResearchTitle(row: HomeResearchReportRow): string {
  return row.title.trim() || GAP;
}

function researchDisplayTitle(row: HomeResearchReportRow): string {
  const rawTitle = rawResearchTitle(row);
  if (rawTitle === GAP) return rawTitle;

  // 可见标题统一走共享清洗（去扩展名/尾部日期戳、下划线转空格）；原文保留在 title/aria-label。
  const cleaned = formatResearchTitleDisplay(rawTitle);
  if (row.isNewsFallback) return cleaned;

  let candidate = cleaned;
  const managedPrefixes = [...new Set(
    [row.institution, row.source]
      .map((value) => value.trim().replaceAll("_", " "))
      .filter((value) => value.length > 0 && value !== GAP),
  )].sort((left, right) => right.length - left.length);

  for (const managedPrefix of managedPrefixes) {
    const boundary = `${managedPrefix} `;
    if (candidate.startsWith(boundary)) {
      candidate = candidate.slice(boundary.length).trim();
      break;
    }
  }

  return candidate || cleaned;
}

function researchSummary(row: HomeResearchReportRow, displayTitle: string): string | null {
  if (row.isNewsFallback) return null;

  let candidate = row.summary.trim();
  if (!candidate || candidate === GAP) return null;

  const titleCandidates = [...new Set([rawResearchTitle(row), displayTitle])]
    .filter((title) => title !== GAP)
    .sort((left, right) => right.length - left.length);

  for (const title of titleCandidates) {
    if (candidate === title) return null;
    if (!candidate.startsWith(title)) continue;

    const remainder = candidate.slice(title.length);
    const duplicatePrefix = /^\s*[：:—–-]\s*(.*)$/s.exec(remainder);
    if (duplicatePrefix) {
      candidate = duplicatePrefix[1].trim();
      break;
    }
  }

  return !candidate || candidate === GAP || titleCandidates.includes(candidate)
    ? null
    : candidate;
}

function usableInstitution(value: string): string | null {
  const candidate = value.trim();
  return candidate && candidate !== GAP && candidate.toLowerCase() !== "tushare_research"
    ? candidate
    : null;
}

function researchInstitution(row: HomeResearchReportRow): string | null {
  return usableInstitution(row.institution) ?? usableInstitution(row.source);
}

function researchLink(
  value: string | null,
): { href: string; isPdf: boolean } | null {
  const href = normalizeHomeResearchLink(value);
  if (!href) return null;

  return {
    href,
    isPdf: /\.pdf$/i.test(new URL(href).pathname),
  };
}

function noticeLabel(
  state: HomeTerminalListState,
  hasNewsFallback: boolean,
): string | null {
  if (hasNewsFallback) {
    return state.label.includes("新闻补位")
      ? state.label
      : `${state.kind === "ready" ? "" : `${state.label} · `}新闻补位`;
  }
  return state.kind === "ready" ? null : state.label;
}

export function DashboardHomeOptionTwoResearchList({
  reports,
  state,
}: DashboardHomeOptionTwoResearchListProps) {
  const visibleReports = reports.slice(0, MAX_VISIBLE_REPORTS);
  const notice = noticeLabel(
    state,
    visibleReports.some((report) => report.isNewsFallback),
  );

  return (
    <section
      aria-label="研究报告列表"
      className={styles.root}
      data-state={state.kind}
      data-testid="dashboard-home-research-reports"
    >
      {visibleReports.length === 0 ? (
        <div className={styles.emptyState} data-state={state.kind} role="status">
          {state.label}
        </div>
      ) : (
        <>
          {notice ? (
            <div className={styles.notice} data-state={state.kind} role="status">
              {notice}
            </div>
          ) : null}
          <div className={styles.scroller}>
            <table className={styles.table}>
              <colgroup>
                <col className={styles.titleColumn} />
                <col className={styles.summaryColumn} />
                <col className={styles.dateColumn} />
                <col className={styles.institutionColumn} />
                <col className={styles.linkColumn} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">标题</th>
                  <th scope="col">摘要</th>
                  <th scope="col">发布日期</th>
                  <th scope="col">机构</th>
                  <th scope="col">原文</th>
                </tr>
              </thead>
              <tbody>
                {visibleReports.map((row) => {
                  const rawTitle = rawResearchTitle(row);
                  const displayTitle = researchDisplayTitle(row);
                  const summary = researchSummary(row, displayTitle);
                  const institution = researchInstitution(row);
                  const publishedDate = row.isNewsFallback
                    ? null
                    : normalizeHomeResearchPublishedDate(row.publishedAt);
                  const link = researchLink(row.link);

                  return (
                    <tr key={row.id} data-testid="dashboard-home-research-row">
                      <td aria-label={rawTitle} title={rawTitle}>
                        {displayTitle}
                      </td>
                      <td title={summary ?? undefined}>{summary ?? GAP}</td>
                      <td>
                        {publishedDate ? (
                          <time dateTime={publishedDate} title={publishedDate}>
                            {publishedDate}
                          </time>
                        ) : (
                          GAP
                        )}
                      </td>
                      <td title={institution ?? undefined}>{institution ?? GAP}</td>
                      <td>
                        {link ? (
                          <a
                            aria-label={`${link.isPdf ? "打开PDF原文" : "打开原文"}：${rawTitle}`}
                            href={link.href}
                            rel="noreferrer"
                            target="_blank"
                          >
                            {link.isPdf ? "PDF" : "原文"}
                          </a>
                        ) : (
                          GAP
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
