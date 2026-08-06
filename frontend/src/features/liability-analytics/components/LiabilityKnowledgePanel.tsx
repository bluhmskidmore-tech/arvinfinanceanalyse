import { Card, Divider, Space, Spin, Tag, Typography } from "antd";

import type { LiabilityKnowledgeNote } from "../../../api/liabilityAdbContracts";

const { Text } = Typography;

type LiabilityKnowledgePanelProps = {
  notes: LiabilityKnowledgeNote[];
  loading: boolean;
  errorText: string | null;
  statusNote?: string | null;
};

export function LiabilityKnowledgePanel({
  notes,
  loading,
  errorText,
  statusNote,
}: LiabilityKnowledgePanelProps) {
  if (loading) {
    return (
      <Card data-testid="liability-knowledge-panel" className="liability-knowledge-panel">
        <div className="liability-knowledge-panel__stack--tight">
          <Text strong>业务资料</Text>
          <div className="liability-knowledge-panel__loading">
            <Spin size="small" />
          </div>
        </div>
      </Card>
    );
  }

  if (errorText) {
    return (
      <Card data-testid="liability-knowledge-panel" className="liability-knowledge-panel">
        <div className="liability-knowledge-panel__stack--tight">
          <Text strong>业务资料</Text>
          <Text type="secondary">{errorText}</Text>
        </div>
      </Card>
    );
  }

  if (notes.length === 0) {
    return null;
  }

  return (
    <Card data-testid="liability-knowledge-panel" className="liability-knowledge-panel">
      <div className="liability-knowledge-panel__stack">
        <Space align="center" wrap>
          <Text strong className="liability-knowledge-panel__title">
            业务资料
          </Text>
          {statusNote ? (
            <Tag className="liability-ib-tag liability-ib-tag--accent">{statusNote}</Tag>
          ) : null}
        </Space>
        <Text type="secondary">
          这些材料来自本机 Obsidian 金融市场笔记，帮助把当前页的负债结构、流动性约束和管理层解释口径对齐。
        </Text>
        {notes.map((note, index) => (
          <div key={`${note.id || note.source_path || note.title}-${index}`}>
            {index > 0 ? <Divider className="liability-knowledge-divider" /> : null}
            <Card size="small" className="liability-knowledge-note">
              <div className="liability-knowledge-note__stack">
                <Text strong className="liability-knowledge-note__title">
                  {note.title}
                </Text>
                <Text>{note.summary}</Text>
                <Text type="secondary">{note.why_it_matters}</Text>
                {note.key_questions.length > 0 ? (
                  <div className="liability-knowledge-note__stack">
                    <Text strong>关键追问</Text>
                    {note.key_questions.map((question, questionIndex) => (
                      <Text key={`${question}-${questionIndex}`}>• {question}</Text>
                    ))}
                  </div>
                ) : null}
                <Text type="secondary">来源：{note.source_path}</Text>
              </div>
            </Card>
          </div>
        ))}
      </div>
    </Card>
  );
}
