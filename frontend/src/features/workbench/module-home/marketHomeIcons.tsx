import type { ReactNode } from "react";

export type MarketIconProps = {
  className?: string;
  size?: number;
};

function MarketIconFrame({ className, size = 18, children }: MarketIconProps & { children: ReactNode }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function MarketIconYieldCurve({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path d="M2.5 13.5L6 9.5L9.5 11L15.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <path d="M2.5 15.5H15.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconCrossAsset({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path d="M3 9H15M9 3V15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <rect x="5" y="5" width="8" height="8" stroke="currentColor" strokeWidth="1.5" />
    </MarketIconFrame>
  );
}

export function MarketIconMacroToolkit({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <rect x="3" y="3" width="12" height="12" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6 7H12M6 10H12M6 13H9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconEquity({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path d="M3 13V8M7 13V5M11 13V9M15 13V3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <path d="M2 15H16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconFx({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path d="M4 6H14M4 12H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <path d="M7 4L5 6L7 8M11 10L13 12L11 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconCommodity({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path d="M3 12L6 6L9 9L12 5L15 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <path d="M2.5 14.5H15.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconLiquidity({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path
        d="M2.5 11.5C4.5 9.5 6 12 9 10.5C12 9 13.5 11.5 15.5 9.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="square"
      />
      <path d="M2.5 14H15.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconCredit({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <rect x="3.5" y="5" width="11" height="8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3.5 8.5H14.5" stroke="currentColor" strokeWidth="1.5" />
    </MarketIconFrame>
  );
}

export function MarketIconRisk({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <path d="M9 3.5L15 14.5H3L9 3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="miter" />
      <path d="M9 7V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <path d="M9 12.5H9.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}

export function MarketIconCrisis({ className, size }: MarketIconProps) {
  return (
    <MarketIconFrame className={className} size={size}>
      <circle cx="9" cy="9.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M9 6.5V10M9 12H9.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </MarketIconFrame>
  );
}
