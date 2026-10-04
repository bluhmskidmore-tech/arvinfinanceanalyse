import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentAnswerPanel } from "../features/agent/components/AgentAnswerPanel";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("Chat answer reading", () => {
  it("renders headings, lists and tables without altering the source numbers", () => {
    render(<AgentAnswerPanel answer={"## 对比\n\n- **方案甲**\n- 方案乙\n\n| 名称 | 示例值 |\n| --- | --- |\n| 甲 | 12.50 |"} />);
    expect(screen.getByRole("heading", { name: "对比" })).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("方案甲").tagName).toBe("STRONG");
    expect(screen.getByRole("cell", { name: "12.50" })).toBeVisible();
  });

  it("copies only the code and keeps the existing paragraph mounted during streaming", async () => {
    const copy = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: copy } });
    const view = render(<AgentAnswerPanel answer={"第一段\n\n```js\nconst value = 1;\n```"} />);
    const paragraph = screen.getByText("第一段");
    fireEvent.click(screen.getByRole("button", { name: "复制代码" }));
    await waitFor(() => expect(copy).toHaveBeenCalledWith("const value = 1;\n"));
    expect(await screen.findByText("已复制")).toBeVisible();
    view.rerender(<AgentAnswerPanel answer={"第一段补充\n\n```js\nconst value = 1;\n```"} />);
    expect(screen.getByText("第一段补充")).toBe(paragraph);
    vi.unstubAllGlobals();
  });

  it("does not execute HTML, allow script links or load model-generated image URLs", () => {
    const view = render(<AgentAnswerPanel answer={'<script>alert(1)</script>\n\n[危险链接](javascript:alert%281%29)\n\n![说明](https://example.invalid/pixel.png)\n\n[正常链接](https://example.com)'} />);
    expect(view.container.querySelector("script")).toBeNull();
    expect(view.container.querySelector("img")).toBeNull();
    expect(view.container.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(screen.getByRole("link", { name: "正常链接" })).toHaveAttribute("rel", "noopener noreferrer");
  });
});
