type ImprovementNotesProps = {
  notes: readonly string[];
};

function splitNote(note: string): { title: string; body: string } {
  const [title, ...rest] = note.split("：");
  return {
    title: title.trim(),
    body: rest.join("：").trim(),
  };
}

export function ImprovementNotes({ notes }: ImprovementNotesProps) {
  return (
    <aside
      data-testid="dashboard-improvement-notes"
      className="dashboard-cockpit-notes"
      aria-label="首页改造重点"
    >
      <div className="dashboard-cockpit-notes__head">
        <span className="dashboard-cockpit-notes__eyebrow">说明栏</span>
        <h2>首页改造重点</h2>
      </div>
      <div className="dashboard-cockpit-notes__list">
        {notes.map((note, index) => {
          const item = splitNote(note);
          return (
            <article key={note} className="dashboard-cockpit-notes__item">
              <span className="dashboard-cockpit-notes__index">{String(index + 1).padStart(2, "0")}</span>
              <div className="dashboard-cockpit-notes__copy">
                <strong>{item.title}</strong>
                <p>{item.body}</p>
              </div>
            </article>
          );
        })}
      </div>
    </aside>
  );
}
