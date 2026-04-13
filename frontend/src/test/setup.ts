import "@testing-library/jest-dom/vitest";

import "../lib/agGridSetup";

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
