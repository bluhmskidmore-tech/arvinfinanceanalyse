import * as React from "react";
import { BankOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Input, Spin } from "antd";

import type { KpiOwner, KpiOwnerAuthorityMeta } from "../../../api/contracts";
import { PageStateSurface } from "../../../components/page/PagePrimitives";

export type OwnerListProps = {
  owners: KpiOwner[];
  selectedOwnerId: number | null;
  onSelect: (owner: KpiOwner) => void;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  /** 后端在“空考核对象”时下发的权威口径治理元信息；有值表示结构化空态，非搜索无结果。 */
  meta?: KpiOwnerAuthorityMeta | null;
};

/** 把底层错误（HTTP 状态码文案 / 网络异常）翻译成不泄露内部堆栈的用户可读原因。 */
function describeOwnersLoadError(error: Error): string {
  const message = error.message || String(error);
  const apiStatusMatch = /^KPI API (\d+)$/.exec(message);
  if (apiStatusMatch) {
    return `KPI 服务返回 ${apiStatusMatch[1]}`;
  }
  const isNetworkFailure =
    error instanceof TypeError || /failed to fetch|network/i.test(message);
  if (isNetworkFailure) {
    return `网络请求失败：${message}`;
  }
  return message || "未知错误";
}

export function OwnerList({
  owners,
  selectedOwnerId,
  onSelect,
  loading = false,
  error = null,
  onRetry,
  meta = null,
}: OwnerListProps) {
  const [searchText, setSearchText] = React.useState("");

  const filtered = React.useMemo(() => {
    const q = searchText.trim().toLowerCase();
    return owners
      .filter((o) => (q ? o.owner_name.toLowerCase().includes(q) : true))
      .sort((a, b) => a.owner_name.localeCompare(b.owner_name));
  }, [owners, searchText]);

  if (loading) {
    return (
      <PageStateSurface
        variant="loading"
        testId="kpi-owner-list-panel"
        className="kpi-owner-list-card kpi-owner-list-card--loading kpi-owner-list__state"
      >
        <Spin />
        <div className="kpi-owner-list__loading-text">加载考核对象…</div>
      </PageStateSurface>
    );
  }

  if (error) {
    return (
      <PageStateSurface
        variant="error"
        testId="kpi-owner-list-error-state"
        className="kpi-owner-list-card kpi-owner-list-card--error kpi-owner-list__state"
        title="考核对象加载失败"
        description={describeOwnersLoadError(error)}
        actions={
          <Button size="small" onClick={onRetry}>
            重试加载考核对象
          </Button>
        }
      />
    );
  }

  if (owners.length === 0) {
    if (meta) {
      return (
        <PageStateSurface
          variant="definition-pending"
          testId="kpi-owner-list-empty-state"
          className="kpi-owner-list-card kpi-owner-list-card--empty kpi-owner-list__state"
          title="权威考核对象尚未就绪"
          description={`治理状态：${meta.authority_status}`}
        >
          <p className="kpi-owner-list__empty-detail">原因：{meta.reason}</p>
        </PageStateSurface>
      );
    }
    return (
      <PageStateSurface
        variant="empty"
        testId="kpi-owner-list-empty-state"
        className="kpi-owner-list-card kpi-owner-list-card--empty kpi-owner-list__state"
        title="当前年度暂无考核部室"
        description="接口已正常返回 0 个考核对象"
      />
    );
  }

  return (
    <section
      data-testid="kpi-owner-list-panel"
      className="kpi-owner-list-card"
    >
      <div className="kpi-owner-list__header">
        <h2 className="kpi-owner-list__title">考核部室</h2>
      </div>
      <div className="kpi-owner-list__search">
        <Input
          allowClear
          aria-label="搜索考核部室"
          prefix={<SearchOutlined aria-hidden="true" />}
          placeholder="搜索部室…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      {filtered.length === 0 ? (
        <PageStateSurface
          variant="empty"
          testId="kpi-owner-list-empty-state"
          className="kpi-owner-list__empty"
          title="无匹配结果"
          description="请调整部室搜索条件"
        />
      ) : (
        filtered.map((owner) => {
          const sel = selectedOwnerId === owner.owner_id;
          const rowClassName = [
            "kpi-owner-list__row",
            sel ? "kpi-owner-list__row--selected" : null,
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div
              key={owner.owner_id}
              role="button"
              tabIndex={0}
              aria-pressed={sel}
              className={rowClassName}
              onClick={() => onSelect(owner)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(owner);
              }}
            >
              <div className="kpi-owner-list__row-content">
                <div
                  className={[
                    "kpi-owner-list__avatar",
                    sel ? "kpi-owner-list__avatar--selected" : null,
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <BankOutlined aria-hidden="true" />
                </div>
                <span
                  className={[
                    "kpi-owner-list__name",
                    sel ? "kpi-owner-list__name--selected" : null,
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {owner.owner_name}
                </span>
              </div>
            </div>
          );
        })
      )}
      <div className="kpi-owner-list__footer">
        共 <strong className="kpi-owner-list__footer-count">{filtered.length}</strong> 个部室
        {searchText && filtered.length !== owners.length ? (
          <span className="kpi-owner-list__filter-note">（筛选自 {owners.length}）</span>
        ) : null}
      </div>
    </section>
  );
}

export default OwnerList;
