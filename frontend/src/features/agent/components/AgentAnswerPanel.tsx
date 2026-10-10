import { useEffect, useRef, useState, type ReactNode } from "react";
import { CheckOutlined, CopyOutlined } from "@ant-design/icons";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import "../AgentAnswerMarkdown.css";

const HERMES_UNKNOWN_TOOLSETS_WARNING = "Warning: Unknown toolsets: evidence, query, research";

function AgentCodeBlock({ children }: { children?: ReactNode }) {
  const codeRef = useRef<HTMLPreElement>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  useEffect(() => {
    if (copyState === "idle") return;
    const timer = window.setTimeout(() => setCopyState("idle"), 2000);
    return () => window.clearTimeout(timer);
  }, [copyState]);
  return (
    <div className="agent-code-block">
      <div className="agent-code-block__toolbar">
        <span>代码</span>
        <button type="button" aria-label="复制代码" onClick={async () => {
          try {
            await navigator.clipboard.writeText(codeRef.current?.textContent ?? "");
            setCopyState("copied");
          } catch {
            setCopyState("error");
          }
        }}>
          {copyState === "copied" ? <CheckOutlined aria-hidden="true" /> : <CopyOutlined aria-hidden="true" />}
          <span role="status">{copyState === "copied" ? "已复制" : copyState === "error" ? "请手动复制" : "复制"}</span>
        </button>
      </div>
      <pre ref={codeRef}>{children}</pre>
    </div>
  );
}

const markdownComponents: Components = {
  p: ({ children }) => <p data-testid="agent-answer-segment">{children}</p>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
  // Model-generated image URLs must not issue background requests while reading a reply.
  img: ({ alt }) => <span>{alt || "图片"}</span>,
  table: ({ children }) => <div className="agent-answer-table"><table>{children}</table></div>,
  pre: AgentCodeBlock,
};

type StructuredAnswerSection = "conclusion" | "keyNumbers" | "evidence" | "boundary" | "nextStep";

type StructuredAnswer = {
  conclusion: string;
  keyNumbers: Array<{ label: string; value: string }>;
  evidence: string;
  boundary: string;
  nextStep: string;
};

const structuredSectionLabels: Record<string, StructuredAnswerSection> = {
  "结论": "conclusion",
  "关键数字": "keyNumbers",
  "证据": "evidence",
  "口径边界": "boundary",
  "下一步": "nextStep",
};

const keyNumberLabels: Record<string, string> = {
  "total pnl": "总损益",
  "interest 514": "利息收入（514）",
  "fair value 516": "公允价值变动（516）",
  "capital gain 517": "资本利得（517）",
};

function parseKeyNumbers(value: string) {
  return value
    .split(/[;；]\s*/u)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const separator = part.indexOf("=");
      if (separator < 0) {
        return { label: "", value: part };
      }
      const rawLabel = part.slice(0, separator).trim();
      return {
        label: keyNumberLabels[rawLabel.toLowerCase()] ?? rawLabel,
        value: part.slice(separator + 1).trim(),
      };
    });
}

function parseStructuredAnswer(answer: string): StructuredAnswer | null {
  const sections: Partial<Record<StructuredAnswerSection, string[]>> = {};
  let currentSection: StructuredAnswerSection | null = null;

  for (const line of answer.split(/\r?\n/u)) {
    const match = line.match(/^(结论|关键数字|证据|口径边界|下一步)[：:]\s*(.*)$/u);
    if (match) {
      currentSection = structuredSectionLabels[match[1]];
      sections[currentSection] = [match[2] ?? ""];
      continue;
    }
    if (currentSection) {
      sections[currentSection]?.push(line);
    }
  }

  const readSection = (section: StructuredAnswerSection) => (sections[section] ?? []).join("\n").trim();
  const conclusion = readSection("conclusion");
  const evidence = readSection("evidence");
  const boundary = readSection("boundary");
  if (!conclusion || (!evidence && !boundary)) {
    return null;
  }

  return {
    conclusion,
    keyNumbers: parseKeyNumbers(readSection("keyNumbers")),
    evidence,
    boundary,
    nextStep: readSection("nextStep"),
  };
}

function StructuredAnswerView({ structured }: { structured: StructuredAnswer }) {
  return (
    <div className="agent-answer-structured" data-testid="agent-structured-answer">
      <section className="agent-answer-structured__conclusion" aria-label="查询结论">
        <div className="agent-answer-structured__label">结论</div>
        <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
          {structured.conclusion}
        </Markdown>
      </section>

      {structured.keyNumbers.length > 0 ? (
        <section className="agent-answer-structured__numbers" aria-label="关键数字">
          <div className="agent-answer-structured__label">关键数字</div>
          <dl>
            {structured.keyNumbers.map(({ label, value }, index) => (
              <div
                key={`${label || "value"}-${index}`}
                className={`agent-answer-structured__number${label ? "" : " agent-answer-structured__number--plain"}`}
              >
                {label ? <dt>{label}</dt> : null}
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {structured.nextStep ? (
        <section className="agent-answer-structured__next-step" aria-label="下一步">
          <span className="agent-answer-structured__label">下一步</span>
          <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
            {structured.nextStep}
          </Markdown>
        </section>
      ) : null}

      <details className="agent-answer-structured__details">
        <summary>查看数据依据与口径</summary>
        <div className="agent-answer-structured__details-body">
          {structured.evidence ? (
            <section>
              <div className="agent-answer-structured__label">证据</div>
              <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
                {structured.evidence}
              </Markdown>
            </section>
          ) : null}
          {structured.boundary ? (
            <section>
              <div className="agent-answer-structured__label">口径边界</div>
              <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
                {structured.boundary}
              </Markdown>
            </section>
          ) : null}
        </div>
      </details>
    </div>
  );
}

export function AgentAnswerPanel({ answer, testId }: { answer: string; testId?: string }) {
  const visibleAnswer = stripFragmentedHermesToolsetWarning(answer).trim();
  if (!visibleAnswer) {
    return null;
  }

  const structuredAnswer = parseStructuredAnswer(visibleAnswer);

  return (
    <div data-testid={testId} className="agent-answer-panel agent-answer-panel--markdown">
      {structuredAnswer ? (
        <StructuredAnswerView structured={structuredAnswer} />
      ) : (
        <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
          {visibleAnswer}
        </Markdown>
      )}
    </div>
  );
}

function stripFragmentedHermesToolsetWarning(answer: string) {
  let cursor = 0;
  for (const expected of HERMES_UNKNOWN_TOOLSETS_WARNING) {
    if (/\s/.test(expected)) {
      continue;
    }
    while (cursor < answer.length && /\s/.test(answer[cursor] ?? "")) {
      cursor += 1;
    }
    if (cursor >= answer.length || answer[cursor] !== expected) {
      return answer;
    }
    cursor += 1;
  }
  const bannerSuffix = answer.slice(cursor).replace(/^[\t ]*/, "");
  if (bannerSuffix && !bannerSuffix.startsWith("\r") && !bannerSuffix.startsWith("\n")) {
    return answer;
  }
  return bannerSuffix.trimStart();
}
