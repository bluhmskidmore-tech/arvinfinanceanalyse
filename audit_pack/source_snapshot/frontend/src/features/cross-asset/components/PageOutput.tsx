import { SectionCard } from "../../../components/SectionCard";
import { designTokens } from "../../../theme/designSystem";
import type { EnvironmentTags } from "../lib/crossAssetDriversModel";

const t = designTokens;

export type PageOutputProps = {
  envTags?: EnvironmentTags;
  signalPreview?: string | null;
  linkageWarnings?: readonly string[];
  topCorrelationSummary?: string | null;
};

export function PageOutput({
  envTags,
  signalPreview,
  linkageWarnings = [],
  topCorrelationSummary,
}: PageOutputProps = {}) {
  const envBody = envTags
    ? `${envTags.primary} / ${envTags.secondary} / ${envTags.style}`
    : "联动评分就绪后将汇总主导因子、次要扰动与风格判断。";

  const directionBody =
    signalPreview?.trim() ||
    "暂无摘要文本：请结合上方「市场判断」与 KPI；摘要来自联动分析的环境评分。";

  const riskBody =
    linkageWarnings.length > 0
      ? linkageWarnings.slice(0, 4).join("；")
      : "当前无管线级告警（仍须结合正式风控流程）。";

  const watchBody =
    topCorrelationSummary ??
    "优先关注右侧「宏观—债市相关性」表中排名靠前的序列对。";

  const items: { label: string; body: string }[] = [
    { label: "环境标签", body: envBody },
    { label: "方向判断", body: directionBody },
    { label: "主要风险 / 告警", body: riskBody },
    { label: "关注窗口", body: watchBody },
  ];

  return (
    <SectionCard title="页面输出">
      <dl
        style={{
          margin: 0,
          fontSize: t.fontSize[13],
          color: t.color.neutral[700],
          lineHeight: t.lineHeight.normal,
        }}
      >
        {items.map((item) => (
          <div key={item.label} style={{ marginBottom: item.label === "关注窗口" ? 0 : t.space[4] }}>
            <dt style={{ fontWeight: 700, color: t.color.neutral[800], margin: 0 }}>{item.label}</dt>
            <dd style={{ margin: `${t.space[2]}px 0 0` }}>{item.body}</dd>
          </div>
        ))}
      </dl>
    </SectionCard>
  );
}
