import { useQuery } from "@tanstack/react-query";
import { Row, Col, Typography, Tag } from "antd";

import { apiClient } from "../../../api/client";
import { PlaceholderCard } from "../components/PlaceholderCard";

export function DashboardPage() {
  const { data } = useQuery({
    queryKey: ["dashboard-snapshot"],
    queryFn: () => apiClient.getDashboardSnapshot(),
  });

  const snapshot = data?.result;
  const meta = data?.result_meta;

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 28,
        }}
      >
        <div>
          <Typography.Title
            level={2}
            style={{
              margin: 0,
              fontSize: 34,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            {snapshot?.title ?? "管理层驾驶舱"}
          </Typography.Title>
          <Typography.Paragraph
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 760,
              color: "#5c6b82",
              fontSize: 15,
            }}
          >
            {snapshot?.subtitle}
          </Typography.Paragraph>
        </div>
        {meta ? (
          <Tag
            bordered={false}
            style={{
              margin: 0,
              borderRadius: 999,
              background: "#dfe8ff",
              color: "#1f5eff",
              paddingInline: 12,
              paddingBlock: 8,
              fontSize: 12,
              letterSpacing: "0.04em",
            }}
          >
            {meta.result_kind}
          </Tag>
        ) : null}
      </div>

      <Row gutter={[18, 18]}>
        {snapshot?.cards.map((card) => (
          <Col key={card.id} xs={24} md={12} xl={6}>
            <PlaceholderCard
              title={card.title}
              value={card.value}
              detail={card.detail}
            />
          </Col>
        ))}
      </Row>
    </section>
  );
}
