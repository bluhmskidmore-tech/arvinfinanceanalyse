import { render, screen } from "@testing-library/react";

import { WorkbenchRouteFallback } from "../router/WorkbenchRouteFallback";

describe("WorkbenchRouteFallback", () => {
  it("exposes an accessible loading status", () => {
    render(<WorkbenchRouteFallback />);

    expect(screen.getByRole("status")).toHaveTextContent("页面载入中");
  });
});
