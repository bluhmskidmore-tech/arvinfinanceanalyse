import { describe, expect, it } from "vitest";

import { routerFuture } from "../router/routerFuture";

describe("routerFuture", () => {
  it("enables only the expected React Router v7 future flags", () => {
    expect(routerFuture).toEqual({
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    });
  });
});
