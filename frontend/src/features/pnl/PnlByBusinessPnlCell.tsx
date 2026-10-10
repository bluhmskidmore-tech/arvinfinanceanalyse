import { formatPnlWan, pnlWanCellTone } from "./pnlByBusinessDisplay";

export function PnlWanCell({
  raw,
  className,
}: {
  raw: string | number | null | undefined;
  className?: string;
}) {
  return (
    <td className={className} data-pnl-tone={pnlWanCellTone(raw)}>
      {formatPnlWan(raw)}
    </td>
  );
}
