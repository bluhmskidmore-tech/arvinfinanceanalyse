import type { ReactNode } from "react";

export type DrilldownRenderHarnessProps = {
  children: ReactNode;
};

/**
 * 中性的测试用渲染根节点：仅包裹 children，不包含路由、数据获取或业务交互。
 * 供未来 row / trace drilldown 相关用例挂载 UI 时使用。
 */
export function DrilldownRenderHarness({ children }: DrilldownRenderHarnessProps) {
  return (
    <div data-testid="drilldown-render-harness" className="moss-drilldown-test-harness">
      {children}
    </div>
  );
}
