import type {
  ContributionPayload,
} from "../../../api/contracts";
import { chipVariants, tableVariants } from "@heroui/styles";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";

type ContributionSectionProps = {
  data?: ContributionPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};
const contributionTableSlots = tableVariants({ variant: "primary" });
const contributionStatusChipSlots = chipVariants({ size: "sm", variant: "soft", color: "default" });

export default function ContributionSection({
  data,
  isLoading,
  isError,
  onRetry,
}: ContributionSectionProps) {
  return (
    <PageAsyncSection
      title="团队 / 账户 / 策略贡献"
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.rows.length === 0}
      onRetry={onRetry}
    >
      <div style={{ overflowX: "auto", padding: "12px" }}>
        <table
          aria-label="Contribution data"
          className={contributionTableSlots.base({ className: "min-w-full" })}
          data-slot="table"
        >
          <thead className={contributionTableSlots.header()} data-slot="table-header">
            <tr className={contributionTableSlots.row()}>
              <th className={contributionTableSlots.column()}>名称</th>
              <th className={contributionTableSlots.column()}>维度</th>
              <th className={contributionTableSlots.column()}>贡献</th>
              <th className={contributionTableSlots.column()}>完成度</th>
              <th className={contributionTableSlots.column()}>状态</th>
            </tr>
          </thead>
          <tbody className={contributionTableSlots.body()} data-slot="table-body">
            {(data?.rows || []).map((row) => (
              <tr className={contributionTableSlots.row()} key={row.id}>
                <td className={contributionTableSlots.cell()}>{row.name}</td>
                <td className={contributionTableSlots.cell({ className: "text-default-500" })}>{row.owner}</td>
                <td className={contributionTableSlots.cell({ className: "font-semibold text-success" })}>
                  {row.contribution.display}
                </td>
                <td className={contributionTableSlots.cell()}>
                  <div className="h-2 rounded-full bg-default-100 overflow-hidden min-w-[140px]">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${row.completion}%` }}
                    />
                  </div>
                </td>
                <td className={contributionTableSlots.cell()}>
                  <span className={contributionStatusChipSlots.base()} data-slot="chip">
                    <span className={contributionStatusChipSlots.label()}>{row.status}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageAsyncSection>
  );
}
