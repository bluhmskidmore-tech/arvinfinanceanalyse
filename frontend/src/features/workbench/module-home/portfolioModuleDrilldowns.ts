import {
  primaryWorkbenchNavigation,
  resolveWorkbenchGroupKey,
  type WorkbenchSection,
} from "../../../mocks/navigation";
import type { ModuleHomeDrilldown } from "./moduleHomeConfig";

function sectionToDrilldown(section: WorkbenchSection): ModuleHomeDrilldown {
  return {
    key: section.key,
    label: section.label,
    path: section.path,
    description: section.description,
    statusLabel: section.readinessLabel,
    icon: section.icon,
  };
}

/** 与侧栏「组合工作台」分组下的 live 子页面数量保持一致（当前为 16）。 */
export function getPortfolioModuleDrilldowns(): ModuleHomeDrilldown[] {
  return primaryWorkbenchNavigation
    .filter((section) => resolveWorkbenchGroupKey(section) === "portfolio")
    .map(sectionToDrilldown);
}

export const PORTFOLIO_MODULE_DRILLDOWN_COUNT = getPortfolioModuleDrilldowns().length;
