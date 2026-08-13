import type { ComponentType } from "react";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

export type ReactEChartsComponent = ComponentType<EChartsReactProps>;

let loadedReactECharts: ReactEChartsComponent | null = null;
let reactEChartsRequest: Promise<ReactEChartsComponent> | null = null;

/** 已完成加载时同步返回组件，供 LazyReactECharts 首帧直接渲染。 */
export function getLoadedReactECharts(): ReactEChartsComponent | null {
  return loadedReactECharts;
}

/**
 * 动态拉取共享 ECharts 包装器（`lib/echarts`）。
 *
 * 静态 import 会把 echarts-misc + zrender + echarts-for-react 拉进路由 chunk 的
 * 静态依赖图，本页首屏因此要多下约 230KB gzip；改成动态 import 后这些 chunk
 * 只在第一个图表真正要渲染时才请求。
 */
export function loadReactECharts(): Promise<ReactEChartsComponent> {
  reactEChartsRequest ??= import("../../../lib/echarts").then((module) => {
    loadedReactECharts = module.default;
    return module.default;
  });
  return reactEChartsRequest;
}

/**
 * 页面挂载后在浏览器空闲时预热 ECharts chunk，让用户首次展开图表工作区时
 * 无需现场下载约 230KB gzip。空闲预取不与首屏数据请求争带宽；
 * 不支持 requestIdleCallback 的环境（Safari/jsdom）退化为短延时。
 */
export function prefetchReactEChartsWhenIdle(): void {
  if (reactEChartsRequest || typeof window === "undefined") {
    return;
  }
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(() => void loadReactECharts(), { timeout: 3000 });
  } else {
    window.setTimeout(() => void loadReactECharts(), 1500);
  }
}

// 组件测试在 render 之后同步读取图表内容，异步首帧会把断言读空。测试构建里在模块求值
// 阶段就发起预取，等测试体开始执行时缓存已就绪，首帧即可同步渲染。生产构建中
// `import.meta.env.MODE` 被替换成字面量 "production"，整个分支被摇掉。
if (import.meta.env.MODE === "test") {
  void loadReactECharts();
}
