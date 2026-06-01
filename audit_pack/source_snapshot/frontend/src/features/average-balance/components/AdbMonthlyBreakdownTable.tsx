import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { AdbMonthlyBreakdownItem } from "../../../api/contracts";

type AdbMonthlyBreakdownTableProps = {
  rows: AdbMonthlyBreakdownItem[];
  columns: ColumnsType<AdbMonthlyBreakdownItem>;
  rowKeyPrefix: string;
};

export default function AdbMonthlyBreakdownTable({
  rows,
  columns,
  rowKeyPrefix,
}: AdbMonthlyBreakdownTableProps) {
  return (
    <div data-testid="adb-monthly-breakdown-table">
      <Table
        size="small"
        pagination={false}
        rowKey={(row) => `${rowKeyPrefix}-${row.category}`}
        columns={columns}
        dataSource={rows}
      />
    </div>
  );
}
