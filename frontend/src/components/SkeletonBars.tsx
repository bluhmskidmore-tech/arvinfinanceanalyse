import "./SkeletonBars.css";

type SkeletonBarStackProps = {
  bars?: number;
  className?: string;
};

export function SkeletonBarStack({ bars = 4, className }: SkeletonBarStackProps) {
  const stackClassName = ["moss-skeleton-bar-stack", className].filter(Boolean).join(" ");

  return (
    <div className={stackClassName}>
      {Array.from({ length: bars }).map((_, index) => (
        <div key={index} className="moss-skeleton-bar" />
      ))}
    </div>
  );
}
