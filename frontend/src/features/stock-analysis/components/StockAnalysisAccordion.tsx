import { Children, isValidElement, type Key, type ReactElement, type ReactNode } from "react";
import { Collapse } from "antd";

type StockAnalysisAccordionKeys = Iterable<Key> | "all";

type StockAnalysisAccordionProps = {
  children: ReactNode;
  className?: string;
  itemClasses?: {
    title?: string;
    content?: string;
  };
  selectedKeys?: StockAnalysisAccordionKeys;
  onSelectionChange?: (keys: Set<string>) => void;
};

type StockAnalysisAccordionItemProps = {
  children: ReactNode;
  title?: ReactNode;
  "aria-label"?: string;
};

function normalizeAccordionKey(key: Key | null, fallbackIndex: number) {
  const rawKey = key == null ? String(fallbackIndex) : String(key);
  if (rawKey.startsWith(".$")) return rawKey.slice(2);
  if (rawKey.startsWith(".")) return rawKey.slice(1);
  return rawKey;
}

export function StockAnalysisAccordion({
  children,
  className,
  itemClasses,
  selectedKeys,
  onSelectionChange,
}: StockAnalysisAccordionProps) {
  const items = Children.toArray(children)
    .filter(isValidElement)
    .map((child, index) => {
      const element = child as ReactElement<StockAnalysisAccordionItemProps>;
      const key = normalizeAccordionKey(element.key, index);
      return {
        key,
        label: <span className={itemClasses?.title}>{element.props.title ?? element.props["aria-label"] ?? key}</span>,
        children: <div className={itemClasses?.content}>{element.props.children}</div>,
      };
    });

  const activeKey =
    selectedKeys === "all"
      ? items.map((item) => item.key)
      : selectedKeys
        ? Array.from(selectedKeys).map(String)
        : undefined;

  return (
    <Collapse
      activeKey={activeKey}
      bordered={false}
      className={className}
      items={items}
      onChange={(keys) => {
        if (!onSelectionChange) return;
        onSelectionChange(new Set((Array.isArray(keys) ? keys : [keys]).map(String)));
      }}
    />
  );
}

export function StockAnalysisAccordionItem(_props: StockAnalysisAccordionItemProps) {
  return null;
}
