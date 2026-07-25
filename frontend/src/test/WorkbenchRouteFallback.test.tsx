import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";

import { WorkbenchRouteFallback } from "../router/WorkbenchRouteFallback";

const fallbackCss = readFileSync(
  resolve(process.cwd(), "src/router/WorkbenchRouteFallback.module.css"),
  "utf8",
);

describe("WorkbenchRouteFallback", () => {
  it("exposes an accessible loading status without inline styles", () => {
    render(<WorkbenchRouteFallback />);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("页面加载中");
    expect(status).not.toHaveAttribute("style");
  });

  it("reserves stable route geometry with a motion-safe skeleton", () => {
    expect(fallbackCss).toContain("width: 100%;");
    expect(fallbackCss).toMatch(/min-height:\s*clamp\(/);
    expect(fallbackCss).toContain("box-sizing: border-box;");
    expect(fallbackCss).toContain(".routeFallback::after");
    expect(fallbackCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(fallbackCss).toContain("animation: none;");
  });
});
