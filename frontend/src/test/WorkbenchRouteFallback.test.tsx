import { render, screen } from "@testing-library/react";

import { WorkbenchRouteFallback } from "../router/WorkbenchRouteFallback";

describe("WorkbenchRouteFallback", () => {
  it("exposes an accessible loading status without inline styles", () => {
    render(<WorkbenchRouteFallback />);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("页面加载中");
    expect(status).not.toHaveAttribute("style");
  });
});
