import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader, PageV2Shell, PageV2SurfacePanel } from "../components/page/PagePrimitives";

describe("PagePrimitives v2 opt-in contract", () => {
  it("keeps the legacy primitives classless while exposing opt-in v2 surfaces", () => {
    render(
      <>
        <PageHeader title="旧标题" description="旧页面仍走 v1 默认输出" />
        <PageV2Shell testId="v2-shell">
          <PageV2SurfacePanel testId="v2-panel">v2 content</PageV2SurfacePanel>
        </PageV2Shell>
      </>,
    );

    expect(screen.getByText("旧标题").closest("section")).not.toHaveClass("moss-page-v2-shell");
    expect(screen.getByTestId("v2-shell")).toHaveClass("moss-page-v2-shell");
    expect(screen.getByTestId("v2-panel")).toHaveClass("moss-page-v2-surface");
  });
});
