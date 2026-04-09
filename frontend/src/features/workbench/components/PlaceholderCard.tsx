import { Card, Typography } from "antd";

type PlaceholderCardProps = {
  title: string;
  value: string;
  detail: string;
};

export function PlaceholderCard({
  title,
  value,
  detail,
}: PlaceholderCardProps) {
  return (
    <Card
      variant="borderless"
      style={{
        minHeight: 170,
        boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
      }}
    >
      <Typography.Text
        style={{
          color: "#6c7b91",
          fontSize: 13,
          letterSpacing: "0.02em",
        }}
      >
        {title}
      </Typography.Text>
      <Typography.Title
        level={3}
        style={{
          marginTop: 14,
          marginBottom: 10,
          fontSize: 28,
          fontWeight: 600,
          color: "#162033",
        }}
      >
        {value}
      </Typography.Title>
      <Typography.Paragraph
        style={{
          marginBottom: 0,
          color: "#5c6b82",
          fontSize: 14,
        }}
      >
        {detail}
      </Typography.Paragraph>
    </Card>
  );
}
