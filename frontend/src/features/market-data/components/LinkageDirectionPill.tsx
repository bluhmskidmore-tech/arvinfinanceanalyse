import {
  formatLinkageDirectionLabel,
  linkageDirectionPillClass,
} from "../lib/marketDataLinkageFormat";

type LinkageDirectionPillProps = {
  direction: string | null | undefined;
  className?: string;
};

export function LinkageDirectionPill({ direction, className }: LinkageDirectionPillProps) {
  const label = formatLinkageDirectionLabel(direction);
  const pillClass = linkageDirectionPillClass(direction);
  return <span className={className ? `${pillClass} ${className}` : pillClass}>{label}</span>;
}
