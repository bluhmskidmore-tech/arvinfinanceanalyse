import {
  Children,
  isValidElement,
  useId,
  useRef,
  type Key,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
} from "react";

type StockAnalysisTabsProps = {
  children: ReactNode;
  className?: string;
  selectedKey?: Key | null;
  onSelectionChange?: (key: Key) => void;
  size?: "sm" | "md" | "lg";
  "aria-label": string;
};

type StockAnalysisTabProps = {
  children?: ReactNode;
  title?: ReactNode;
};

const tabsSizeClassMap: Record<NonNullable<StockAnalysisTabsProps["size"]>, string> = {
  sm: "ant-tabs-small",
  md: "ant-tabs-middle",
  lg: "ant-tabs-large",
};

export function StockAnalysisTabs({
  children,
  className,
  selectedKey,
  onSelectionChange,
  size = "md",
  "aria-label": ariaLabel,
}: StockAnalysisTabsProps) {
  const instanceId = useId().replace(/:/g, "");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const items: Array<{ key: string; label: ReactNode; children: ReactNode; tabId: string; panelId: string }> = [];
  Children.forEach(children, (child, index) => {
    if (!isValidElement(child)) return;
    const element = child as ReactElement<StockAnalysisTabProps>;
    const key = String(element.key ?? index);
    items.push({
      key,
      label: element.props.title ?? key,
      children: element.props.children,
      tabId: `stock-analysis-tabs-${instanceId}-tab-${index}`,
      panelId: `stock-analysis-tabs-${instanceId}-panel-${index}`,
    });
  });
  const activeKey = selectedKey == null ? items[0]?.key : String(selectedKey);
  const activeItem = items.find((item) => item.key === activeKey) ?? items[0];
  const rootClassName = ["ant-tabs", "ant-tabs-top", tabsSizeClassMap[size], className].filter(Boolean).join(" ");

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % items.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + items.length) % items.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;
    if (nextIndex == null || !items[nextIndex]) return;

    event.preventDefault();
    tabRefs.current[nextIndex]?.focus();
    onSelectionChange?.(items[nextIndex].key);
  };

  return (
    <div className={rootClassName}>
      <div aria-label={ariaLabel} className="ant-tabs-nav" role="tablist">
        <div className="ant-tabs-nav-wrap">
          <div className="ant-tabs-nav-list">
            {items.map((item, index) => {
              const active = item.key === activeItem?.key;
              return (
                <div
                  className={`ant-tabs-tab${active ? " ant-tabs-tab-active" : ""}`}
                  data-node-key={item.key}
                  key={item.key}
                >
                  <button
                    aria-controls={item.panelId}
                    aria-selected={active}
                    className="ant-tabs-tab-btn"
                    id={item.tabId}
                    onClick={() => onSelectionChange?.(item.key)}
                    onKeyDown={(event) => handleTabKeyDown(event, index)}
                    ref={(node) => {
                      tabRefs.current[index] = node;
                    }}
                    role="tab"
                    tabIndex={active ? 0 : -1}
                    type="button"
                  >
                    {item.label}
                  </button>
                </div>
              );
            })}
            <div className="ant-tabs-ink-bar ant-tabs-ink-bar-animated" />
          </div>
        </div>
        <div className="ant-tabs-nav-operations" />
      </div>
      <div className="ant-tabs-content-holder">
        <div className="ant-tabs-content ant-tabs-content-top">
          {items.map((item) => {
            const active = item.key === activeItem?.key;
            return (
              <div
                aria-labelledby={item.tabId}
                className={`ant-tabs-tabpane${active ? " ant-tabs-tabpane-active" : ""}`}
                hidden={!active}
                id={item.panelId}
                key={item.key}
                role="tabpanel"
              >
                {active ? item.children : null}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function StockAnalysisTab(_props: StockAnalysisTabProps) {
  return null;
}
