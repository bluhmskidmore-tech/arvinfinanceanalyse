import { Link } from "react-router-dom";

export type ProductCategoryApiLedgerRow = {
  method: "GET" | "POST";
  path: string;
  status: string;
  tone: "live" | "loading" | "error" | "contracted";
};

type ProductCategoryApiContractLedgerProps = {
  readRows: ProductCategoryApiLedgerRow[];
  writeRows: ProductCategoryApiLedgerRow[];
  adjustmentCount: number;
  eventCount: number;
  canExport: boolean;
  isExporting: boolean;
  exportError: string | null;
  exportedFilename: string | null;
  onCreateAdjustment: () => void;
  onExport: () => void;
};

export function ProductCategoryApiContractLedger(
  props: ProductCategoryApiContractLedgerProps,
) {
  const readErrorCount = props.readRows.filter(
    (row) => row.tone === "error",
  ).length;
  const readLoadingCount = props.readRows.filter(
    (row) => row.tone === "loading",
  ).length;

  return (
    <section
      className="product-category-api-ledger"
      data-testid="product-category-api-contract-ledger"
      aria-label="产品分类损益后端端点衔接状态"
    >
      <header className="product-category-api-ledger__header">
        <div>
          <p className="product-category-api-ledger__eyebrow">
            后端端点与治理闭环
          </p>
          <h2>11 个前端衔接动作</h2>
          <p>
            本清单展示前端集成与本会话调用状态，不是服务健康检查；写操作已衔接且受权限控制，
            不代表本次会话已执行或已完成治理签署。
          </p>
        </div>
        <span
          className={`product-category-api-ledger__runtime ${
            readErrorCount > 0
              ? "is-error"
              : readLoadingCount > 0
                ? "is-loading"
                : "is-live"
          }`}
          data-testid="product-category-api-contract-runtime"
        >
          读接口已联调 {props.readRows.length}/{props.readRows.length} ·
          写接口已联调 {props.writeRows.length}/{props.writeRows.length}
        </span>
      </header>

      <div className="product-category-api-ledger__columns">
        <section data-testid="product-category-api-read-surfaces">
          <h3>只读接口</h3>
          <div className="product-category-api-ledger__rows">
            {props.readRows.map((row) => (
              <div
                className={`product-category-api-ledger__row is-${row.tone}`}
                data-endpoint-state={row.tone}
                data-testid={`product-category-api-endpoint-${row.path
                  .replace(/[^a-z0-9]+/gi, "-")
                  .replace(/^-|-$/g, "")
                  .toLowerCase()}`}
                key={`${row.method}:${row.path}`}
              >
                <span className="product-category-api-ledger__method">
                  {row.method}
                </span>
                <code>{row.path}</code>
                <strong>{row.status}</strong>
              </div>
            ))}
          </div>
        </section>
        <section data-testid="product-category-api-write-surfaces">
          <h3>写入与轮询接口</h3>
          <div className="product-category-api-ledger__rows">
            {props.writeRows.map((row) => (
              <div
                className={`product-category-api-ledger__row is-${row.tone}`}
                data-endpoint-state={row.tone}
                key={`${row.method}:${row.path}`}
              >
                <span className="product-category-api-ledger__method">
                  {row.method}
                </span>
                <code>{row.path}</code>
                <strong>{row.status}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>

      <footer className="product-category-api-ledger__workflow">
        <div>
          <h3>手工调整与审计流</h3>
          <strong>
            {props.adjustmentCount} 项生效 · {props.eventCount} 项事件
          </strong>
          <p>
            {props.exportedFilename
              ? `已导出 ${props.exportedFilename}；`
              : "可导出 CSV；"}
            新增 → 编辑 → 撤销 → 恢复；所有动作写入事件流，刷新状态通过 run_id
            轮询。
          </p>
          {props.exportError ? (
            <p className="product-category-api-ledger__error" role="alert">
              {props.exportError}
            </p>
          ) : null}
        </div>
        <div className="product-category-api-ledger__actions">
          <button type="button" onClick={props.onCreateAdjustment}>
            新增调整
          </button>
          <button
            type="button"
            data-testid="product-category-export-adjustments"
            disabled={!props.canExport || props.isExporting}
            onClick={props.onExport}
          >
            {props.isExporting ? "导出中..." : "导出 CSV"}
          </button>
          <Link to="/product-category-pnl/audit">打开审计账本</Link>
        </div>
      </footer>
    </section>
  );
}

