import { Children, isValidElement, type Key, type ReactElement, type ReactNode } from "react";

type StockAnalysisTabsProps = {
  children: ReactNode;
  className?: string;
  selectedKey?: Key | null;
  onSelectionChange?: (key: Key) => void;
  size?: "sm" | "md" | "lg";
  "aria-label"?: string;
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
  const items = Children.toArray(children)
    .filter(isValidElement)
    .map((child, index) => {
      const element = child as ReactElement<StockAnalysisTabProps>;
      const key = String(element.key ?? index);
      return {
        key,
        label: element.props.title ?? key,
        children: element.props.children,
      };
    });
  const activeKey = selectedKey == null ? items[0]?.key : String(selectedKey);
  const activeItem = items.find((item) => item.key === activeKey) ?? items[0];
  const rootClassName = ["ant-tabs", "ant-tabs-top", tabsSizeClassMap[size], className].filter(Boolean).join(" ");

  return (
    <div
      aria-label={ariaLabel}
      className={rootClassName}
    >
      <div className="ant-tabs-nav" role="tablist">
        <div className="ant-tabs-nav-wrap">
          <div className="ant-tabs-nav-list">
            {items.map((item) => {
              const active = item.key === activeItem?.key;
              return (
                <div
                  className={`ant-tabs-tab${active ? " ant-tabs-tab-active" : ""}`}
                  data-node-key={item.key}
                  key={item.key}
                >
                  <button
                    aria-controls={`stock-analysis-tabpane-${item.key}`}
                    aria-selected={active}
                    className="ant-tabs-tab-btn"
                    id={`stock-analysis-tab-${item.key}`}
                    onClick={() => onSelectionChange?.(item.key)}
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
          {activeItem ? (
            <div
              aria-labelledby={`stock-analysis-tab-${activeItem.key}`}
              className="ant-tabs-tabpane ant-tabs-tabpane-active"
              id={`stock-analysis-tabpane-${activeItem.key}`}
              role="tabpanel"
            >
              {activeItem.children}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function StockAnalysisTab(_props: StockAnalysisTabProps) {
  return null;
}
