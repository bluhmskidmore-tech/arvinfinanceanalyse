import type { CampisiEnhancedPayload } from "../../../api/contracts";

export type MetricCard = {
  key: string;
  label: string;
  value: number | undefined;
  /**
   * bridge 路径未拆分该效应。数值仍是精确 0 并继续参与闭合求和，只是不得以数字
   * 形式发布——"0.00 亿"会被读成"观测到二阶贡献为零"。
   */
  notDecomposed?: boolean;
};

export function buildMetricCards(
  totals: CampisiEnhancedPayload["totals"] | undefined,
  secondOrderNotDecomposed = false,
): MetricCard[] {
  const hasBridgeDetails =
    totals?.realized_trading !== undefined ||
    totals?.manual_adjustment !== undefined ||
    totals?.fx_translation !== undefined;
  const cards: MetricCard[] = [
    { key: "income_return", label: "票息", value: totals?.income_return },
    { key: "treasury_effect", label: "国债曲线", value: totals?.treasury_effect },
    { key: "spread_effect", label: "利差", value: totals?.spread_effect },
  ];
  if (hasBridgeDetails) {
    cards.push(
      { key: "realized_trading", label: "已实现交易", value: totals?.realized_trading },
      { key: "manual_adjustment", label: "手工调整", value: totals?.manual_adjustment },
      { key: "fx_translation", label: "汇兑", value: totals?.fx_translation },
    );
  }
  cards.push(
    {
      key: "convexity_effect",
      label: "凸性",
      value: totals?.convexity_effect,
      notDecomposed: secondOrderNotDecomposed,
    },
    {
      key: "cross_effect",
      label: "交叉项",
      value: totals?.cross_effect,
      notDecomposed: secondOrderNotDecomposed,
    },
    {
      key: "reinvestment_effect",
      label: "再投资",
      value: totals?.reinvestment_effect,
      notDecomposed: secondOrderNotDecomposed,
    },
    { key: "selection_effect", label: "剩余/选券", value: totals?.selection_effect },
    { key: "total_return", label: "总收益", value: totals?.total_return },
  );
  return cards;
}

/**
 * 前端独立加总：展示分量（不含总收益）之和，供契约闭合断言。
 *
 * 未拆分的效应只影响展示，不退出求和——把它当成缺失会让闭合断言退化成 null，
 * 而 bridge 路径恰恰是靠这个和等于 `total_return` 才能证明没有分量被吞掉。
 */
export function sumCampisiEnhancedDisplayAmounts(
  totals: CampisiEnhancedPayload["totals"] | undefined,
): number | null {
  if (!totals) {
    return null;
  }
  const cards = buildMetricCards(totals).filter((card) => card.key !== "total_return");
  let sum = 0;
  for (const card of cards) {
    if (typeof card.value !== "number" || !Number.isFinite(card.value)) {
      return null;
    }
    sum += card.value;
  }
  return sum;
}
