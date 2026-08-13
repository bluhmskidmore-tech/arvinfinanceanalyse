import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LedgerPnlSectionNav,
  type LedgerPnlSectionNavItem,
} from "../features/ledger-pnl/components/LedgerPnlSectionNav";

const ITEMS: LedgerPnlSectionNavItem[] = [
  { id: "ledger-summary", label: "损益概览", badge: "3 项待补", tone: "warning" },
  { id: "ledger-bridge", label: "损益桥接", badge: "已核对", tone: "ok" },
];

class IntersectionObserverMock {
  static instances: IntersectionObserverMock[] = [];

  readonly observe = vi.fn();
  readonly disconnect = vi.fn();

  constructor(readonly callback: IntersectionObserverCallback) {
    IntersectionObserverMock.instances.push(this);
  }

  unobserve = vi.fn();
  takeRecords = vi.fn(() => []);
  root = null;
  rootMargin = "0px 0px 0px 0px";
  thresholds = [0];
}

let originalIntersectionObserver: typeof IntersectionObserver | undefined;
let targets: HTMLElement[] = [];

function addTarget(id: string) {
  const target = document.createElement("section");
  target.id = id;
  document.body.append(target);
  targets.push(target);
  return target;
}

function triggerIntersection(target: Element) {
  const observer = IntersectionObserverMock.instances.at(-1);
  if (!observer) throw new Error("未创建 IntersectionObserver。");

  observer.callback(
    [{
      boundingClientRect: target.getBoundingClientRect(),
      intersectionRatio: 1,
      intersectionRect: target.getBoundingClientRect(),
      isIntersecting: true,
      rootBounds: null,
      target,
      time: 0,
    }] as IntersectionObserverEntry[],
    observer as unknown as IntersectionObserver,
  );
}

beforeEach(() => {
  originalIntersectionObserver = window.IntersectionObserver;
  IntersectionObserverMock.instances = [];
  Object.defineProperty(window, "IntersectionObserver", {
    configurable: true,
    value: IntersectionObserverMock,
  });
});

afterEach(() => {
  targets.forEach((target) => target.remove());
  targets = [];
  Object.defineProperty(window, "IntersectionObserver", {
    configurable: true,
    value: originalIntersectionObserver,
  });
});

describe("LedgerPnlSectionNav", () => {
  it("渲染全部章节标签和状态徽标", () => {
    ITEMS.forEach((item) => addTarget(item.id));

    render(<LedgerPnlSectionNav items={ITEMS} />);

    expect(screen.getByTestId("ledger-pnl-section-nav")).toHaveAttribute("aria-label", "页面章节导航");
    expect(screen.getByText("损益概览")).toBeVisible();
    expect(screen.getByText("损益桥接")).toBeVisible();
    expect(screen.getByText("3 项待补")).toBeVisible();
    expect(screen.getByText("已核对")).toBeVisible();
  });

  it("点击章节按钮后滚动并将焦点交给目标区块", () => {
    const target = addTarget("ledger-summary");
    const scrollIntoView = vi.fn();
    Object.defineProperty(target, "scrollIntoView", { configurable: true, value: scrollIntoView });

    render(<LedgerPnlSectionNav items={[ITEMS[0]]} />);
    fireEvent.click(screen.getByTestId("ledger-pnl-section-nav-item-ledger-summary"));

    expect(scrollIntoView).toHaveBeenCalledWith({ block: "start", behavior: "smooth" });
    expect(target).toHaveAttribute("tabindex", "-1");
    expect(document.activeElement).toBe(target);
  });

  it("目标区块不存在时保留禁用按钮", () => {
    render(<LedgerPnlSectionNav items={[ITEMS[0]]} />);

    const button = screen.getByTestId("ledger-pnl-section-nav-item-ledger-summary");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-disabled", "true");
  });

  it("章节为空时不渲染导航", () => {
    const { container } = render(<LedgerPnlSectionNav items={[]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("根据进入视口的最上方章节高亮对应按钮", () => {
    const target = addTarget("ledger-bridge");

    render(<LedgerPnlSectionNav items={[ITEMS[1]]} />);
    act(() => {
      triggerIntersection(target);
    });

    const button = screen.getByTestId("ledger-pnl-section-nav-item-ledger-bridge");
    expect(button).toHaveAttribute("aria-current", "true");
    expect(button).toHaveClass("ledger-pnl-section-nav__item--active");
  });
});
