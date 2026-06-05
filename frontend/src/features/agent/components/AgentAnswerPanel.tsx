import { shellTokens as t } from "../../../theme/tokens";

export function AgentAnswerPanel({ answer, testId }: { answer: string; testId?: string }) {
  if (!answer.trim()) {
    return null;
  }

  return (
    <div
      data-testid={testId}
      style={{
        padding: 20,
        borderRadius: 16,
        border: `1px solid ${t.colorBorderSoft}`,
        background: t.colorBgCanvas,
        color: t.colorTextPrimary,
        fontSize: 15,
        lineHeight: 1.75,
      }}
    >
      {answer}
    </div>
  );
}
