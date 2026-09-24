import "./AgentRepoMemoryPanel.css";

type AgentRepoMemoryPanelProps = {
  pinnedRepoPaths: string[];
  recentUnpinnedRepoPaths: string[];
  onApplyRecentRepoPath: (path: string) => void;
  onMovePinnedRepoPath: (path: string, direction: "up" | "down") => void;
  onUnpinRepo: (path: string) => void;
  onPinRepoPath: (path: string) => void;
};

export function AgentRepoMemoryPanel({
  pinnedRepoPaths,
  recentUnpinnedRepoPaths,
  onApplyRecentRepoPath,
  onMovePinnedRepoPath,
  onUnpinRepo,
  onPinRepoPath,
}: AgentRepoMemoryPanelProps) {
  if (!pinnedRepoPaths.length && !recentUnpinnedRepoPaths.length) {
    return null;
  }

  return (
    <div className="agent-repo-memory">
      {pinnedRepoPaths.length > 0 ? (
        <div className="agent-repo-memory__group">
          <div className="agent-repo-memory__title">固定仓库</div>
          <div className="agent-repo-memory__list">
            {pinnedRepoPaths.map((path) => (
              <div key={`pinned-${path}`} className="agent-repo-memory__item">
                <button
                  type="button"
                  className="agent-repo-memory__path"
                  onClick={() => onApplyRecentRepoPath(path)}
                >
                  {path}
                </button>
                <button
                  type="button"
                  className="agent-repo-memory__action"
                  onClick={() => onMovePinnedRepoPath(path, "up")}
                  aria-label={`上移固定仓库 ${path}`}
                >
                  上移
                </button>
                <button
                  type="button"
                  className="agent-repo-memory__action"
                  onClick={() => onMovePinnedRepoPath(path, "down")}
                  aria-label={`下移固定仓库 ${path}`}
                >
                  下移
                </button>
                <button
                  type="button"
                  className="agent-repo-memory__action"
                  onClick={() => onUnpinRepo(path)}
                  aria-label={`取消固定 ${path}`}
                >
                  取消固定
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {recentUnpinnedRepoPaths.length > 0 ? (
        <div className="agent-repo-memory__group">
          <div className="agent-repo-memory__title">最近仓库</div>
          <div className="agent-repo-memory__list">
            {recentUnpinnedRepoPaths.map((path) => (
              <div key={path} className="agent-repo-memory__item">
                <button
                  type="button"
                  className="agent-repo-memory__path"
                  onClick={() => onApplyRecentRepoPath(path)}
                >
                  {path}
                </button>
                <button
                  type="button"
                  className="agent-repo-memory__action"
                  onClick={() => onPinRepoPath(path)}
                  aria-label={`固定仓库 ${path}`}
                >
                  固定
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
