import {
  CheckCircleOutlined,
  CopyOutlined,
  ExclamationCircleOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button } from "antd";
import { useCallback, useState, type ReactNode } from "react";

import type { MacroToolkitSignalCard } from "../../../api/macroToolkitClient";
import { MacroStatusIcon, compactText } from "../lib/macroToolkitPanelShared";

function clampScore(score: number | null | undefined) {
  if (score == null) {
    return 0;
  }
  return Math.min(100, Math.max(0, score));
}

export function ScoreTrack({ score }: { score: number | null | undefined }) {
  return <progress className="macro-toolkit-score-track" value={clampScore(score)} max={100} aria-hidden="true" />;
}

export function ReadinessTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon?: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: MacroToolkitSignalCard["tone"];
}) {
  const Icon = tone === "negative" || tone === "missing" ? ExclamationCircleOutlined : CheckCircleOutlined;
  return (
    <div className={`macro-toolkit-readiness-tile macro-toolkit-readiness-tile--${tone}`}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <Icon />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 28)}</small>
    </div>
  );
}

const MACRO_TOOLKIT_ANALYSIS_KIND = "macro_toolkit.analysis";
const MACRO_TOOLKIT_UI_RULE_VERSION = "rv_macro_toolkit_ui_v1";

export function MacroToolkitContractBoundary({
  formalUseAllowed,
  resultKind,
  ruleVersion,
  plainLanguage = false,
}: {
  formalUseAllowed?: boolean;
  resultKind?: string;
  ruleVersion?: string;
  plainLanguage?: boolean;
}) {
  const resultKindText = plainLanguage ? "宏观分析结果" : resultKind ?? MACRO_TOOLKIT_ANALYSIS_KIND;
  const versionText = plainLanguage ? "规则版本已记录" : ruleVersion ?? MACRO_TOOLKIT_UI_RULE_VERSION;
  return (
    <div
      className="macro-toolkit-contract-boundary"
      data-testid="macro-toolkit-contract-boundary"
      aria-label="宏观工具口径边界"
    >
      <span>
        <SafetyCertificateOutlined />
        分析/工具口径
      </span>
      <strong>{formalUseAllowed ? "正式可用" : "非正式口径"}</strong>
      <small>{resultKindText}</small>
      <small>{versionText}</small>
    </div>
  );
}

const MACRO_TOOLKIT_READ_SCOPE_REQUEST_TEXT = [
  "申请授予 macro_toolkit/read",
  "resource=macro_toolkit",
  "action=read",
  "页面=/macro-toolkit",
  "用途=读取宏观工具 core/full 分析、脚本注册表、策略摘要和 Crisis Score 证据面板",
  "授权后点击重试读取",
].join("\n");

export function MacroToolkitReadScopeBlocker() {
  const [copyStatus, setCopyStatus] = useState<"idle" | "success" | "error">("idle");

  const copyScopeRequest = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (typeof writeText !== "function") {
      setCopyStatus("error");
      return;
    }
    try {
      await writeText.call(clipboard, MACRO_TOOLKIT_READ_SCOPE_REQUEST_TEXT);
      setCopyStatus("success");
    } catch {
      setCopyStatus("error");
    }
  }, []);

  return (
    <div className="macro-toolkit-read-scope-blocker" aria-label="宏观工具读取权限缺口">
      <div>
        <span>缺少宏观工具读取权限</span>
        <strong>macro_toolkit/read</strong>
        <small>当前账号未被允许读取宏观工具；授权后点击重试读取。</small>
      </div>
      <div className="macro-toolkit-read-scope-blocker__actions">
        <Button
          aria-label="复制授权申请"
          icon={<CopyOutlined aria-hidden="true" />}
          size="small"
          type="default"
          onClick={() => void copyScopeRequest()}
        >
          {copyStatus === "success" ? "已复制" : copyStatus === "error" ? "复制失败" : "复制授权申请"}
        </Button>
        {copyStatus !== "idle" ? (
          <span
            aria-atomic="true"
            aria-live="polite"
            className={`macro-toolkit-read-scope-blocker__copy-status macro-toolkit-read-scope-blocker__copy-status--${copyStatus}`}
            role="status"
          >
            {copyStatus === "success" ? "授权申请已复制" : "复制失败，请手动选择授权信息"}
          </span>
        ) : null}
      </div>
    </div>
  );
}
