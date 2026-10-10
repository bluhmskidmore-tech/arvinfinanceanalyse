import type { AssetStructurePayload } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import { nocturneTokens } from "../../../theme/designSystem";
import type { BondSectionDataState } from "../sectionStatus";
import { formatRatePercent, formatYi, nativeToNumber } from "../utils/format";
import { BondSectionSurface } from "./BondSectionSurface";

const RATING_ORDER = [
  "AAA",
  "AA+",
  "AA",
  "AA-",
  "A+",
  "A",
  "A-",
  "BBB+",
  "BBB",
  "BBB-",
  "BB+",
  "BB",
  "B",
  "C",
  "D",
];

/*
 * 评级色阶（Nocturne 常量，禁止新增 hex）：高评级沿 accent 紫系渐进
 * （AAA 最深），AA- 落中性过渡；A 档进入琥珀警戒。评级恶化是警戒语义
 * （琥珀/红），不占用涨跌绿/红。
 */
const RATING_COLORS: Record<string, string> = {
  AAA: nocturneTokens.color.blue,
  "AA+": nocturneTokens.color.accent400,
  AA: nocturneTokens.color.accent300,
  "AA-": nocturneTokens.color.inkSoft,
  "A+": nocturneTokens.color.amber,
  A: nocturneTokens.color.amber,
  "A-": nocturneTokens.color.amber,
};

/**
 * 色带最小高度：载入骨架的防重排下限与 CSS 里的 `.rating-strip` 同值，
 * 数据到达时不产生高度跳变（DESIGN.md §11.10）。
 */
const RATING_STRIP_MIN_HEIGHT = 132;

function ratingRank(name: string): number {
  const i = RATING_ORDER.indexOf(name.trim().toUpperCase());
  return i >= 0 ? i : 500;
}

function ratingColor(category: string): string {
  const key = category.trim().toUpperCase();
  if (RATING_COLORS[key]) {
    return RATING_COLORS[key];
  }
  // BBB 及以下（B/C/D 开头）统一红警戒；其余含 A 变体琥珀兜底。
  if (/^[BCD]/.test(key)) {
    return nocturneTokens.color.red;
  }
  if (key.includes("A")) {
    return nocturneTokens.color.amber;
  }
  // 未评级/未知类目走中性灰，不伪装成任何评级档位。
  return nocturneTokens.color.inkMuted;
}

/*
 * 本组件刻意不走 DataTable：色块按市值占比分配 flex 权重，「面积即占比」是
 * 核心视觉编码，塞进 <table> 会丢掉这层信息（DESIGN.md §12 第 13 条同源纪律）。
 */
export function CreditRatingBlocks({
  data,
  state,
}: {
  data: AssetStructurePayload | undefined;
  state: BondSectionDataState;
}) {
  const items = [...(data?.items ?? [])].sort(
    (a, b) => ratingRank(a.category) - ratingRank(b.category),
  );
  const total =
    items.reduce((s, i) => {
      const raw = nativeToNumber(i.total_market_value);
      return raw === null ? s : s + raw;
    }, 0) || 1;

  return (
    <div className="bond-dashboard-page__panel">
      <div className="bond-dashboard-page__panel-head">
        <h3 className="bond-dashboard-page__panel-head-title">信用等级分布</h3>
      </div>
      {/*
       * 重构前这里有第三条分支：信封未到达时渲染一条 EM_DASH 色带骨架。分区状态
       * 接进来后，「信封未到达」已经由 loading / error 明确表达，ready 必然带数据，
       * 那条分支不再可达，随之删除（对应 CSS 的 __rating-empty 同步删除）。
       */}
      <BondSectionSurface
        state={state}
        isEmpty={items.length === 0}
        loadingMinHeight={RATING_STRIP_MIN_HEIGHT}
      >
        <div className="bond-dashboard-charts__rating-strip bond-dashboard-page__panel-body">
          {items.map((it) => {
            const rawMarketValue = nativeToNumber(it.total_market_value);
            const w = rawMarketValue === null ? 6 : (rawMarketValue / total) * 100;
            const percentage = formatRatePercent(it.percentage);
            const percentageText = percentage === EM_DASH ? EM_DASH : `${percentage}%`;
            return (
              <div
                key={it.category}
                className="bond-dashboard-charts__rating-block"
                /* 占比 <0.1% 的尾档最小权重收 2（原 6 视觉超配）；读数入 title 防窄块截断。 */
                title={`${it.category || EM_DASH} ${formatYi(it.total_market_value)} 亿 ${percentageText} ${it.bond_count} 只`}
                /* flex 权重与背景色是逐块真动态值（市值占比 + 评级档位）。 */
                style={{
                  flex: `${Math.max(w, 2)} 1 0`,
                  background: ratingColor(it.category),
                }}
              >
                <div className="bond-dashboard-charts__rating-category">
                  {it.category || EM_DASH}
                </div>
                <div className="bond-dashboard-charts__rating-amount">
                  {formatYi(it.total_market_value)} 亿
                </div>
                <div className="bond-dashboard-charts__rating-pct">
                  {percentageText}
                  {/* 只数放独立节点：测试对百分比文本做精确匹配。 */}
                  <span className="bond-dashboard-charts__rating-count">{it.bond_count} 只</span>
                </div>
              </div>
            );
          })}
        </div>
      </BondSectionSurface>
    </div>
  );
}
