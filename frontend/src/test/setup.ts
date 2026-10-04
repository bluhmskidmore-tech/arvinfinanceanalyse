import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import "../lib/agGridSetup";

configure({
  asyncUtilTimeout: 5000,
});

afterEach(() => {
  cleanup();
  removeInjectedComponentStyles();
  vi.restoreAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

// antd cssinjs（style[data-css-hash]）与 rc-util（style[rc-util-key]，@ant-design/icons）把样式注入
// document.head 后不会随组件卸载移除。jsdom 的 getComputedStyle 对每个元素都要遍历全部样式规则做
// selector 匹配，RTL 的 *ByRole 可见性检查和 user-event 的 pointer-events 检查都依赖它；同文件前面
// 用例残留的样式表会让后续重交互用例慢一个数量级（MacroToolkitPage.test.tsx 全文件 206s，清掉后约 60s）。
// 两类样式在下一次组件挂载时都会经 updateCSS 按 key 重新注入，卸载后移除等价于每个用例在干净文档里运行。
function removeInjectedComponentStyles() {
  document.querySelectorAll("style[data-css-hash], style[rc-util-key]").forEach((node) => {
    node.remove();
  });
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

const originalGetComputedStyle = window.getComputedStyle.bind(window);

Object.defineProperty(window, "getComputedStyle", {
  writable: true,
  value: (element: Element, pseudoElt?: string) =>
    pseudoElt ? originalGetComputedStyle(element) : originalGetComputedStyle(element, pseudoElt),
});
