const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
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
