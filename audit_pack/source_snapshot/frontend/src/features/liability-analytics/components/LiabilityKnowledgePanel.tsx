import { Card, Divider, Space, Spin, Tag, Typography } from "antd";

import type { LiabilityKnowledgeNote } from "../../../api/contracts";

const { Text } = Typography;

type LiabilityKnowledgePanelProps = {
  notes: LiabilityKnowledgeNote[];
  loading: boolean;
  errorText: string | null;
  statusNote?: string | null;
};

const panelStyle = {
  borderRadius: 16,
  border: "1px solid #dbe7f5",
  background: "linear-gradient(180deg, #f9fbff 0%, #ffffff 100%)",
  boxShadow: "0 10px 24px rgba(22, 32, 51, 0.06)",
} as const;

const noteCardStyle = {
  borderRadius: 14,
  border: "1px solid #e8eef7",
  background: "#ffffff",
} as const;

export function LiabilityKnowledgePanel({
  notes,
  loading,
  errorText,
  statusNote,
}: LiabilityKnowledgePanelProps) {
  if (loading) {
    return (
      <Card data-testid="liability-knowledge-panel" style={panelStyle}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Text strong>业务资料</Text>
          <div style={{ textAlign: "center", padding: "12px 0" }}>
            <Spin size="small" />
          </div>
        </Space>
      </Card>
    );
  }

  if (errorText) {
    return (
      <Card data-testid="liability-knowledge-panel" style={panelStyle}>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text strong>业务资料</Text>
          <Text type="secondary">{errorText}</Text>
        </Space>
      </Card>
    );
  }

  if (notes.length === 0) {
    return null;
  }

  return (
    <Card data-testid="liability-knowledge-panel" style={panelStyle}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Space align="center" wrap>
          <Text strong style={{ fontSize: 16 }}>
            业务资料
          </Text>
          {statusNote ? <Tag color="blue">{statusNote}</Tag> : null}
        </Space>
        <Text type="secondary">
          这些材料来自本机 Obsidian 金融市场笔记，帮助把当前页的负债结构、流动性约束和管理层解释口径对齐。
        </Text>
        {notes.map((note, index) => (
          <div key={note.id}>
            {index > 0 ? <Divider style={{ margin: "0 0 16px" }} /> : null}
            <Card size="small" style={noteCardStyle}>
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                <Text strong style={{ fontSize: 15 }}>
                  {note.title}
                </Text>
                <Text>{note.summary}</Text>
                <Text type="secondary">{note.why_it_matters}</Text>
                {note.key_questions.length > 0 ? (
                  <Space direction="vertical" size={4} style={{ width: "100%" }}>
                    <Text strong>关键追问</Text>
                    {note.key_questions.map((question) => (
                      <Text key={question}>• {question}</Text>
                    ))}
                  </Space>
                ) : null}
                <Text type="secondary">来源：{note.source_path}</Text>
              </Space>
            </Card>
          </div>
        ))}
      </Space>
    </Card>
  );
}
