import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../components/PlaceholderCard";
import { workbenchNavigation } from "../../../mocks/navigation";

export default function WorkbenchPlaceholderPage() {
  const client = useApiClient();
  const location = useLocation();
  const section =
    workbenchNavigation.find((item) => item.path === location.pathname) ??
    workbenchNavigation[0];

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["workbench-placeholder", section.key],
    queryFn: () => client.getPlaceholderSnapshot(section.key),
    retry: false,
  });

  const snapshot = data?.result;
  const isEmpty =
    !isLoading &&
    !isError &&
    Boolean(data) &&
    (!snapshot ||
      (!snapshot.summary?.trim() &&
        (!snapshot.highlights || snapshot.highlights.length === 0)));

  return (
    <section>
      <h1
        style={{
          marginTop: 0,
          marginBottom: 10,
          fontSize: 32,
          fontWeight: 600,
          letterSpacing: "-0.03em",
        }}
      >
        {snapshot?.title ?? section.label}
      </h1>

      <AsyncSection
        title="模块说明"
        isLoading={isLoading}
        isError={isError}
        isEmpty={isEmpty}
        onRetry={() => void refetch()}
      >
        {snapshot ? (
          <>
            <PlaceholderCard
              title="概述"
              value={snapshot.summary || "（暂无概述）"}
              detail="后端就绪后由契约字段替换本段静态文案。"
              valueVariant="text"
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: 16,
                marginTop: 20,
              }}
            >
              {(snapshot.highlights ?? []).map((item, index) => (
                <PlaceholderCard
                  key={`${item}-${index}`}
                  title={`规划要点 ${index + 1}`}
                  value={item}
                  detail="占位卡片：后续映射到真实模块能力。"
                  valueVariant="text"
                />
              ))}
            </div>
          </>
        ) : null}
      </AsyncSection>
    </section>
  );
}
