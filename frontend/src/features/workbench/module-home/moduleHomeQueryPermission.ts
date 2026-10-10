import type { UseQueryResult } from "@tanstack/react-query";

import { ActionRequestError } from "../../../api/transport";
import type { ModuleHomeStatus } from "./moduleHomeModel";

/*
 * 模块首页读链路的 RBAC 拒绝（403）单独成态：重试不会改变结果，不能和网络故障混成同一句
 * 「读取失败，可重试」（2026-09-02 走查 /reports、/cube-query，默认 viewer 身份下 cube
 * 维度目录一律 403）。只有带 status 的域客户端错误（ActionRequestError）能被识别，其余
 * 仍按读取失败处理。
 */

type ModuleHomeQuery = UseQueryResult<unknown> | undefined;

export function queryIsForbidden(query: ModuleHomeQuery): boolean {
  return Boolean(
    query?.isError && query.error instanceof ActionRequestError && query.error.status === 403,
  );
}

export function hasForbiddenOnlyErrors(queries: Record<string, ModuleHomeQuery>): boolean {
  const failed = Object.values(queries).filter((query) => query?.isError);
  return failed.length > 0 && failed.every((query) => queryIsForbidden(query));
}

export function forbiddenQueryStatus(key: string, label: string): ModuleHomeStatus {
  return {
    key,
    label,
    value: "无权限",
    detail: "当前角色无权访问该读链路（403），不使用前端补数。",
    tone: "watch",
  };
}

/** 全部失败都是权限拒绝时的页级状态；否则返回 null 让调用方沿用原有失败 / 读取中 / 已接入判断。 */
export function forbiddenOnlyPageState(
  queries: Record<string, ModuleHomeQuery>,
): { stateLabel: string; stateDetail: string } | null {
  if (!hasForbiddenOnlyErrors(queries)) {
    return null;
  }
  return {
    stateLabel: "部分无权限",
    stateDetail: "部分读链路被后端按角色拒绝（403），需开通相应读权限；不使用前端补数。",
  };
}

export function cubeDimensionsMissingDetail(query: ModuleHomeQuery): string {
  return queryIsForbidden(query) ? "当前角色无权读取维度目录（403）。" : "维度目录读取失败或未返回。";
}
