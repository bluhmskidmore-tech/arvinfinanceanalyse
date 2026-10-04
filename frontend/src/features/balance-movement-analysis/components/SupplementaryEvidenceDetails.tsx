import { useState, type ReactNode } from "react";

export function SupplementaryEvidenceDetails({ renderContent }: {
  renderContent: () => ReactNode;
}) {
  const [hasOpened, setHasOpened] = useState(false);
  return (
    <details
      className="balance-movement-data-states__pass"
      onToggle={(event) => {
        if (event.currentTarget.open) setHasOpened(true);
      }}
    >
      <summary>
        <strong>契约通过条件</strong>
        <span>
          所有状态均在正文可见；展开查看完整校准、控制科目与历史异常证据。
        </span>
      </summary>
      {hasOpened ? (
        <div className="balance-movement-data-states__supplementary-content">
          {renderContent()}
        </div>
      ) : null}
    </details>
  );
}
