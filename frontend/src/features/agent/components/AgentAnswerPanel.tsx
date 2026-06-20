import type { CSSProperties } from "react";

export function AgentAnswerPanel({ answer, testId }: { answer: string; testId?: string }) {
  const segments = splitAnswerIntoSegments(answer);

  if (segments.length === 0) {
    return null;
  }

  return (
    <div data-testid={testId} className="agent-answer-panel">
      {segments.map((segment, index) => (
        <p
          key={`${index}-${segment}`}
          data-testid="agent-answer-segment"
          style={{ "--agent-answer-segment-delay": `${index * 70}ms` } as CSSProperties}
        >
          {segment}
        </p>
      ))}
    </div>
  );
}

function splitAnswerIntoSegments(answer: string) {
  const paragraphs = answer
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (paragraphs.length > 1) {
    return paragraphs;
  }

  const trimmedAnswer = answer.trim();
  return trimmedAnswer ? [trimmedAnswer] : [];
}
