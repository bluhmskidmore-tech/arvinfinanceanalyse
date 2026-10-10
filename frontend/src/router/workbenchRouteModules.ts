import { Children, isValidElement, lazy, type ReactNode } from "react";

type ModuleLoader = () => Promise<unknown>;
type LazyPageComponent = Awaited<ReturnType<Parameters<typeof lazy>[0]>>["default"];

const elementModuleLoaders = new WeakMap<object, ModuleLoader>();

export function lazyWorkbenchPage<T extends LazyPageComponent>(
  loader: () => Promise<{ default: T }>,
) {
  let modulePromise: Promise<{ default: T }> | undefined;
  const loadModule = () => {
    // This loader serves the active route only. Retain failures as React.lazy
    // does, so Vite's failed-CSS cache cannot turn a later retry into success.
    modulePromise ??= loader();
    return modulePromise;
  };
  const page = lazy(loadModule);
  elementModuleLoaders.set(page, loadModule);
  return page;
}

export function preloadWorkbenchRouteElement(element: ReactNode): void {
  Children.forEach(element, (child) => {
    if (!isValidElement<{ children?: ReactNode }>(child)) return;
    if (typeof child.type === "object" && child.type !== null) {
      void elementModuleLoaders.get(child.type)?.().catch(() => undefined);
    }
    // These are the route's declared elements, never a rendered page tree.
    // Loading a module does not mount its component or bypass its read boundary.
    preloadWorkbenchRouteElement(child.props.children);
  });
}
