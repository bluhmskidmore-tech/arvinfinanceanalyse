import "./StockAnalysisDeepResearchSkeleton.css";

function SkeletonBar({ variant = "wide" }: { variant?: "title" | "wide" | "mid" | "short" }) {
  return <div className={`sa-deep-research-skeleton__bar sa-deep-research-skeleton__bar--${variant}`} />;
}

export function StockAnalysisDeepResearchSkeleton() {
  return (
    <div
      className="stock-analysis-page__workspace sa-deep-research-skeleton"
      role="status"
      aria-label="正在加载深度研究"
    >
      <section className="sa-deep-research-skeleton__block sa-deep-research-skeleton__block--header">
        <SkeletonBar variant="title" />
        <SkeletonBar variant="mid" />
      </section>
      <section className="sa-deep-research-skeleton__block sa-deep-research-skeleton__block--review">
        <SkeletonBar variant="title" />
        <SkeletonBar />
        <SkeletonBar variant="mid" />
        <div className="sa-deep-research-skeleton__row">
          <SkeletonBar />
          <SkeletonBar variant="short" />
        </div>
        <SkeletonBar />
        <SkeletonBar variant="mid" />
        <SkeletonBar variant="short" />
      </section>
      <section className="sa-deep-research-skeleton__block sa-deep-research-skeleton__block--analytics">
        <SkeletonBar variant="title" />
        <SkeletonBar />
        <SkeletonBar variant="mid" />
        <SkeletonBar />
        <SkeletonBar variant="short" />
      </section>
      <section className="sa-deep-research-skeleton__block sa-deep-research-skeleton__block--sector">
        <SkeletonBar variant="title" />
        <div className="sa-deep-research-skeleton__row">
          <SkeletonBar />
          <SkeletonBar />
        </div>
        <SkeletonBar variant="mid" />
        <SkeletonBar />
      </section>
      <section className="sa-deep-research-skeleton__block sa-deep-research-skeleton__block--modules">
        <SkeletonBar variant="title" />
        <SkeletonBar />
        <SkeletonBar variant="mid" />
        <div className="sa-deep-research-skeleton__row">
          <SkeletonBar />
          <SkeletonBar variant="short" />
        </div>
        <SkeletonBar />
      </section>
      <section className="sa-deep-research-skeleton__block sa-deep-research-skeleton__block--pools">
        <SkeletonBar variant="title" />
        <SkeletonBar variant="mid" />
        <SkeletonBar />
        <SkeletonBar variant="short" />
      </section>
    </div>
  );
}
