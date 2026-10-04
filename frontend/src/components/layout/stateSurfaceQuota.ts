import { createContext, useContext, useEffect } from "react";

/**
 * `StateSurface` 的全页状态配额（DESIGN.md §6「同一事实全页最多出现两处」）。
 *
 * 单独成文件而不是并入 `StateSurface.tsx`：那个文件只导出组件，HMR 才能对原语
 * 生效（`react-refresh/only-export-components`）。Context、hook 与常量属于非组件
 * 导出，归到这里。
 */

/** 配额上限：同一 `dedupeKey` 的第 3 个同时挂载实例触发告警。 */
export const STATE_SURFACE_DEDUPE_LIMIT = 2;

type StateSurfaceQuotaCounts = Record<string, number>;

export type StateSurfaceQuotaContextValue = {
  /** 每个 `dedupeKey` 的实时计数，供页面测试断言 `counts[key] <= STATE_SURFACE_DEDUPE_LIMIT`。 */
  counts: StateSurfaceQuotaCounts;
  register: (key: string) => void;
  unregister: (key: string) => void;
};

export const StateSurfaceQuotaContext = createContext<StateSurfaceQuotaContextValue | null>(null);

/** 读取实时配额登记表。没有 Provider 时返回 `null`。 */
export function useStateSurfaceQuota(): StateSurfaceQuotaContextValue | null {
  return useContext(StateSurfaceQuotaContext);
}

/**
 * 挂载时登记、卸载或 key 变化时注销，因此统计的是「此刻同时挂载了几个」而不是
 * 「历史上出现过几次」。没有 Provider 时静默跳过（fail-open：内容永不被这个机制
 * 挡住，§6 不能静默吞态）。
 */
export function useDedupeRegistration(dedupeKey: string | undefined): void {
  const quota = useStateSurfaceQuota();
  const register = quota?.register;
  const unregister = quota?.unregister;

  useEffect(() => {
    if (!dedupeKey || !register || !unregister) return undefined;
    register(dedupeKey);
    return () => unregister(dedupeKey);
    // register/unregister 是无依赖 useCallback 且不读 counts，引用稳定；
    // 只有 dedupeKey 变化才该重跑，否则任一 key 计数变化会连锁重注册全页实例。
  }, [dedupeKey, register, unregister]);
}
