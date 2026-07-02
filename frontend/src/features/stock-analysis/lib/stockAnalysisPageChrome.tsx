import {
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import shellStyles from "../../workbench/dashboard-home/dashboardHomeShell.module.css";

/** Shared dashboard-home shell classes (single visual source of truth). */
export const SA_SHELL_PAGE = shellStyles.dhPage;
export const SA_SHELL_LAYOUT = shellStyles.dhLayout;
export const SA_SHELL_MAIN = shellStyles.dhMain;
export const SA_SHELL_RAIL = shellStyles.dhRail;
export const SA_SHELL_TOPBAR = shellStyles.dhTopbar;
export const SA_SHELL_TOPBAR_LEFT = shellStyles.dhTopbarLeft;
export const SA_SHELL_TOPBAR_RIGHT = shellStyles.dhTopbarRight;
export const SA_SHELL_TITLE = shellStyles.dhTitle;
export const SA_SHELL_TITLE_BRAND = shellStyles.dhTitleBrand;
export const SA_SHELL_STATUS_ROW = shellStyles.dhStatusRow;
export const SA_SHELL_STATUS_PILL = shellStyles.dhStatusPill;
export const SA_SHELL_NUM = shellStyles.dhNum;
export const SA_SHELL_REVIEW_RAIL = shellStyles.dhReviewRail;
export const SA_SHELL_REVIEW_RAIL_HEAD = shellStyles.dhReviewRailHead;
export const SA_SHELL_REVIEW_LIST = shellStyles.dhReviewList;
export const SA_SHELL_DATA_NOTE = shellStyles.dhDataNote;
export const SA_RAIL_INNER = "stock-analysis-page__rail-inner";

export const SA_FIRST_CARD = `${shellStyles.dhCard} stock-analysis-page__dh-panel stock-analysis-page__dh-card`;
export const SA_FIRST_HERO = `${shellStyles.dhTerminalHero} stock-analysis-page__dh-hero`;
export const SA_CARD_TITLE = "m-0";
export const SA_SECTION_HEAD = `${shellStyles.dhTerminalPanelHead} stock-analysis-page__dh-section-head`;
export const SA_SECTION_DESC = `${shellStyles.dhMuted} stock-analysis-page__dh-section-desc`;
export const SA_SECTION_EYEBROW = `${shellStyles.dhReportKicker} stock-analysis-page__dh-section-eyebrow`;
export const SA_PILL = `${shellStyles.dhStatusPill} stock-analysis-page__dh-pill`;

// Static icon arrays are shared page chrome, not component modules.
// eslint-disable-next-line react-refresh/only-export-components
export const DECISION_GRID_ICONS = [
  <ClockCircleOutlined key="date" />,
  <DatabaseOutlined key="basis" />,
  <SafetyCertificateOutlined key="boundary" />,
  <CheckCircleOutlined key="gate" />,
];

// eslint-disable-next-line react-refresh/only-export-components
export const FIRST_SCREEN_ICONS = [
  <BarChartOutlined key="sectors" />,
  <ThunderboltOutlined key="consensus" />,
  <StockOutlined key="queue" />,
  <FireOutlined key="events" />,
];

// eslint-disable-next-line react-refresh/only-export-components
export const SECTION_HEAD_ICONS = [
  <LineChartOutlined key="sector" />,
  <SafetyCertificateOutlined key="risk" />,
  <DatabaseOutlined key="boundary" />,
];
