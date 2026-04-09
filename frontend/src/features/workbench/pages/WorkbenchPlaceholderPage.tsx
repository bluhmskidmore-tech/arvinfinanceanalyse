import { useQuery } from "@tanstack/react-query";
import { Card, List, Typography } from "antd";
import { useLocation } from "react-router-dom";

import { apiClient } from "../../../api/client";
import { workbenchNavigation } from "../../../mocks/navigation";

export function WorkbenchPlaceholderPage() {
  const location = useLocation();
  const section =
    workbenchNavigation.find((item) => item.path === location.pathname) ??
    workbenchNavigation[0];

  const { data } = useQuery({
    queryKey: ["workbench-placeholder", section.key],
    queryFn: () => apiClient.getPlaceholderSnapshot(section.key),
  });

  const snapshot = data?.result;

  return (
    <section>
      <Typography.Title
        level={2}
        style={{
          marginTop: 0,
          marginBottom: 10,
          fontSize: 32,
          fontWeight: 600,
          letterSpacing: "-0.03em",
        }}
      >
        {snapshot?.title ?? section.label}
      </Typography.Title>
      <Typography.Paragraph
        style={{
          marginBottom: 24,
          color: "#5c6b82",
          fontSize: 15,
        }}
      >
        {snapshot?.summary}
      </Typography.Paragraph>

      <Card
        variant="borderless"
        style={{
          boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
        }}
      >
        <List
          dataSource={snapshot?.highlights ?? []}
          renderItem={(item) => (
            <List.Item style={{ color: "#5c6b82" }}>{item}</List.Item>
          )}
        />
      </Card>
    </section>
  );
}
