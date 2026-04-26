import { shellTokens as t } from "../../../theme/tokens";

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
    <div
      style={{
        display: "grid",
        gap: 10,
      }}
    >
      {pinnedRepoPaths.length > 0 ? (
        <div
          style={{
            display: "grid",
            gap: 8,
          }}
        >
          <div
            style={{
              color: t.colorTextMuted,
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
            }}
          >
            固定仓库
          </div>
          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            {pinnedRepoPaths.map((path) => (
              <div
                key={`pinned-${path}`}
                style={{
                  display: "flex",
                  gap: 6,
                  alignItems: "center",
                }}
              >
                <button
                  type="button"
                  onClick={() => onApplyRecentRepoPath(path)}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 999,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgSurface,
                    color: t.colorTextSecondary,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  {path}
                </button>
                <button
                  type="button"
                  onClick={() => onMovePinnedRepoPath(path, "up")}
                  aria-label={`上移固定仓库 ${path}`}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 999,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgCanvas,
                    color: t.colorTextMuted,
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  上移
                </button>
                <button
                  type="button"
                  onClick={() => onMovePinnedRepoPath(path, "down")}
                  aria-label={`下移固定仓库 ${path}`}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 999,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgCanvas,
                    color: t.colorTextMuted,
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  下移
                </button>
                <button
                  type="button"
                  onClick={() => onUnpinRepo(path)}
                  aria-label={`取消固定 ${path}`}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 999,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgCanvas,
                    color: t.colorTextMuted,
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  取消固定
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {recentUnpinnedRepoPaths.length > 0 ? (
        <div
          style={{
            display: "grid",
            gap: 8,
          }}
        >
          <div
            style={{
              color: t.colorTextMuted,
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
            }}
          >
            最近仓库
          </div>
          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            {recentUnpinnedRepoPaths.map((path) => (
              <div
                key={path}
                style={{
                  display: "flex",
                  gap: 6,
                  alignItems: "center",
                }}
              >
                <button
                  type="button"
                  onClick={() => onApplyRecentRepoPath(path)}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 999,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgSurface,
                    color: t.colorTextSecondary,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  {path}
                </button>
                <button
                  type="button"
                  onClick={() => onPinRepoPath(path)}
                  aria-label={`固定仓库 ${path}`}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 999,
                    border: `1px solid ${t.colorBorderSoft}`,
                    background: t.colorBgCanvas,
                    color: t.colorTextMuted,
                    fontSize: 11,
                    cursor: "pointer",
                  }}
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
