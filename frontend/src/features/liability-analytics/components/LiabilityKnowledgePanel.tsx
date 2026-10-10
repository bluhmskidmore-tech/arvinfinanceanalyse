import type { LiabilityKnowledgeNote } from "../../../api/liabilityAdbContracts";

type LiabilityKnowledgePanelProps = {
  notes: LiabilityKnowledgeNote[];
  loading: boolean;
  errorText: string | null;
  statusNote?: string | null;
};

/** 业务资料正文：分区帧（编号 + 「业务资料」标题 + 状态位）由页面持有。 */
export function LiabilityKnowledgePanel({
  notes,
  loading,
  errorText,
}: LiabilityKnowledgePanelProps) {
  if (loading) {
    return (
      <p
        data-testid="liability-knowledge-panel"
        className="liability-analytics-page__surface liability-analytics-page__surface--loading"
      >
        业务资料读取中…
      </p>
    );
  }

  if (errorText) {
    return (
      <div data-testid="liability-knowledge-panel" className="liability-notice liability-notice--warning">
        <strong className="liability-notice__title">业务资料加载失败</strong>
        <span className="liability-notice__description">{errorText}</span>
      </div>
    );
  }

  if (notes.length === 0) {
    return null;
  }

  /*
   * 整区默认折叠：笔记正文约 1.5 屏，属参考资料不属首屏判断链路；
   * 来源绝对路径只保留在 title（证据引用），不在正文暴露本机路径。
   */
  return (
    <div data-testid="liability-knowledge-panel" className="liability-knowledge">
      <details className="liability-knowledge__details">
        <summary>{`业务笔记 ${notes.length} 篇（来自本机 Obsidian 金融市场笔记）`}</summary>
        <div className="liability-knowledge__body">
          <p className="liability-caption">
            这些材料帮助把当前页的负债结构、流动性约束和管理层解释口径对齐。
          </p>
          <div className="liability-analytics-page__grid liability-analytics-page__grid--2">
            {notes.map((note, index) => (
              <article
                key={`${note.id || note.source_path || note.title}-${index}`}
                className="liability-panel liability-knowledge-note"
              >
                <h3 className="liability-panel__title">{note.title}</h3>
                <p className="liability-knowledge-note__summary">{note.summary}</p>
                <p className="liability-caption">{note.why_it_matters}</p>
                {note.key_questions.length > 0 ? (
                  <div className="liability-knowledge-note__questions">
                    <strong>关键追问</strong>
                    <ul>
                      {note.key_questions.map((question, questionIndex) => (
                        <li key={`${question}-${questionIndex}`}>{question}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <p className="liability-caption liability-knowledge-note__source" title={note.source_path}>
                  来源：本机 Obsidian 笔记
                </p>
              </article>
            ))}
          </div>
        </div>
      </details>
    </div>
  );
}
