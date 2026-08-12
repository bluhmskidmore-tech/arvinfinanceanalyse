import { useEffect, useState, type ComponentType } from "react";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

type ReactEChartsComponent = ComponentType<EChartsReactProps>;

let loadedReactECharts: ReactEChartsComponent | null = null;
let reactEChartsRequest: Promise<ReactEChartsComponent> | null = null;

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

// 组件测试在 render 之后同步读取图表内容，异步首帧会把断言读空。测试构建里在模块求值
// 阶段就发起预取，等测试体开始执行时缓存已就绪，首帧即可同步渲染。生产构建中
// `import.meta.env.MODE` 被替换成字面量 "production"，整个分支被摇掉。
if (import.meta.env.MODE === "test") {
  void loadReactECharts();
}

export function LazyReactECharts(props: EChartsReactProps) {
  const [ReactECharts, setReactECharts] = useState<ReactEChartsComponent | null>(
    () => loadedReactECharts,
  );

  useEffect(() => {
    if (ReactECharts) {
      return undefined;
    }
    let active = true;
    void loadReactECharts().then((component) => {
      if (active) {
        setReactECharts(() => component);
      }
    });
    return () => {
      active = false;
    };
  }, [ReactECharts]);

  if (!ReactECharts) {
    // 复用画布自身的类名占位：高度逐主题、逐断点与真实画布一致，出图时不抖动。
    return <div className={props.className} aria-hidden="true" />;
  }

  return <ReactECharts {...props} />;
}
