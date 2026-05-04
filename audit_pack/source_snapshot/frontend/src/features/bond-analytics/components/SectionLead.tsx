import { designTokens } from "../../../theme/designSystem";

const dt = designTokens;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: dt.space[2],
} as const;

const sectionEyebrowStyle = {
  fontSize: dt.fontSize[11],
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: dt.color.neutral[500],
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: dt.fontSize[18],
  fontWeight: 600,
  color: dt.color.primary[900],
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: dt.color.neutral[600],
  fontSize: dt.fontSize[13],
  lineHeight: dt.lineHeight.relaxed,
} as const;

type SectionLeadProps = {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
};

export function SectionLead({ eyebrow, title, description, testId }: SectionLeadProps) {
  return (
    <div data-testid={testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{eyebrow}</span>
      <h2 style={sectionTitleStyle}>{title}</h2>
      <p style={sectionDescriptionStyle}>{description}</p>
    </div>
  );
}
