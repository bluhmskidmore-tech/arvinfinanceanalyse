import type {
  DecimalLike,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlRow,
} from "../../../api/contracts";
import {
  formatProductCategoryValue,
  selectProductCategoryClosureErrorSignal,
} from "./productCategoryPnlPageModel";

type ProductCategoryFormalReadinessBandProps = {
  reportDate: string;
  selectedView: string;
  scenarioApplied: boolean;
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
  attribution?: ProductCategoryAttributionPayload;
};

export function ProductCategoryFormalReadinessBand(
  props: ProductCategoryFormalReadinessBandProps,
) {
  const scenarioStateLabel = props.scenarioApplied
    ? "已应用情景预览"
    : "正式基线";
  const attributionHeadline =
    props.selectedView === "monthly" && props.attribution?.state === "complete"
      ? props.attribution.totals?.grand_total
      : undefined;
  const attributionEffects = attributionHeadline?.effects;
  const attributionCompareLabel =
    props.attribution?.compare === "yoy" ? "同比变动" : "环比变动";
  const deltaValue = attributionEffects?.delta_business_net_income;
  const closureValue = attributionEffects?.closure_error;
  const parsedDelta = Number(deltaValue);
  const closureAvailable =
    closureValue !== null &&
    closureValue !== undefined &&
    Number.isFinite(Number(closureValue));
  const deltaTone = Number.isFinite(parsedDelta)
    ? parsedDelta < 0
      ? "is-negative"
      : parsedDelta > 0
        ? "is-positive"
        : "is-neutral"
    : "is-neutral";
  const closureSignal = selectProductCategoryClosureErrorSignal(closureValue);
  const headlineCopy = attributionHeadline
    ? `本期合计经营净收入 ${formatProductCategoryValue(
        props.grandTotal?.business_net_income,
      )} 亿元；${attributionCompareLabel} ${formatProductCategoryValue(
        deltaValue,
      )} 亿元；闭合误差 ${formatProductCategoryValue(closureValue)} 亿元${
        !closureAvailable
          ? "，状态待返回。"
          : closureSignal.hasMaterialGap
            ? "，需复核。"
            : "，已闭合。"
      }`
    : `本期合计经营净收入 ${formatProductCategoryValue(
        props.grandTotal?.business_net_income,
      )} 亿元，当前展示${scenarioStateLabel}。`;
  const attributionDrivers = attributionEffects
    ? [
        ["rate_effect", "利率因素"],
        ["day_effect", "天数因素"],
        ["direct_effect", "直接因素"],
        ["scale_effect", "规模因素"],
        ["ftp_effect", "FTP 因素"],
      ]
        .map(([key, label]) => {
          const rawValue = attributionEffects[
            key as keyof typeof attributionEffects
          ] as DecimalLike;
          const parsedValue = Number(rawValue ?? 0);
          return {
            key,
            label,
            rawValue,
            value: Number.isFinite(parsedValue) ? parsedValue : 0,
          };
        })
        .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
        .slice(0, 3)
    : [];
  const dominantDriver = attributionDrivers.find(
    (driver) => Math.abs(driver.value) > 0,
  );

  return (
    <section
      data-testid="product-category-formal-readiness-band"
      className="product-category-formal-readiness"
      aria-label="产品分类损益正式主链首屏摘要"
    >
      <div className="product-category-formal-readiness__header">
        <div className="product-category-formal-readiness__copy">
          <h2 className="product-category-formal-readiness__title">
            本期经营结果
          </h2>
          <p
            data-testid="product-category-formal-headline-copy"
            className="product-category-formal-readiness__description"
          >
            {headlineCopy}
          </p>
        </div>
        <div className="product-category-formal-readiness__headline-meta">
          <span>{props.reportDate || "待选报告日"}</span>
          <strong>{scenarioStateLabel}</strong>
        </div>
      </div>

      <div
        data-testid="product-category-decision-canvas"
        className="product-category-formal-readiness__decision-canvas"
      >
        <div
          data-testid="product-category-formal-headline-totals"
          className="product-category-formal-readiness__totals product-category-formal-readiness__totals--attribution"
        >
          <div
            data-testid="product-category-core-metric"
            className="product-category-formal-readiness__metric product-category-formal-readiness__metric--primary"
          >
            <span>FTP后经营净收入（亿元）</span>
            <strong>
              {formatProductCategoryValue(
                props.grandTotal?.business_net_income,
              )}
            </strong>
            <small>MTR-PCP-003</small>
          </div>
          <div
            data-testid="product-category-core-metric"
            className="product-category-formal-readiness__metric product-category-formal-readiness__metric--change"
          >
            <span>{attributionCompareLabel}（亿元）</span>
            <strong className={deltaTone}>
              {formatProductCategoryValue(deltaValue)}
            </strong>
            <small>
              对比期{" "}
              {formatProductCategoryValue(
                attributionHeadline?.prior?.business_net_income,
              )}
            </small>
          </div>
          <div
            data-testid="product-category-core-metric"
            className="product-category-formal-readiness__metric"
          >
            <span>资产端（亿元）</span>
            <strong>
              {formatProductCategoryValue(
                props.assetTotal?.business_net_income,
              )}
            </strong>
            <small>MTR-PCP-001</small>
          </div>
          <div
            data-testid="product-category-core-metric"
            className="product-category-formal-readiness__metric"
          >
            <span>负债端（亿元）</span>
            <strong>
              {formatProductCategoryValue(
                props.liabilityTotal?.business_net_income,
              )}
            </strong>
            <small>MTR-PCP-002</small>
          </div>
          <div
            data-testid="product-category-core-metric"
            className="product-category-formal-readiness__metric product-category-formal-readiness__metric--closure"
          >
            <span>闭合误差（亿元）</span>
            <strong
              className={
                !closureAvailable
                  ? "is-neutral"
                  : closureSignal.hasMaterialGap
                    ? "is-warning"
                    : "is-ready"
              }
            >
              {formatProductCategoryValue(closureValue)}
            </strong>
            <small>
              已解释{" "}
              {formatProductCategoryValue(attributionEffects?.explained_effect)}
            </small>
          </div>
        </div>

        <section
          data-testid="product-category-formal-driver-readout"
          className="product-category-formal-readiness__driver-readout"
          aria-label={`${attributionCompareLabel}关键驱动与风险`}
        >
          <div className="product-category-formal-readiness__driver-header">
            <div>
              <strong>关键驱动与风险</strong>
              <span>仅展示绝对影响最大的 3 项</span>
            </div>
            <small>单位：亿元</small>
          </div>
          {attributionDrivers.length > 0 ? (
            <div className="product-category-formal-readiness__driver-list">
              {attributionDrivers.map((driver) => (
                <div
                  data-testid="product-category-driver-item"
                  className="product-category-formal-readiness__driver-row"
                  key={driver.key}
                >
                  <span>{driver.label}</span>
                  <strong
                    className={
                      driver.value < 0
                        ? "is-negative"
                        : driver.value > 0
                          ? "is-positive"
                          : "is-neutral"
                    }
                  >
                    {formatProductCategoryValue(driver.rawValue)}
                  </strong>
                  <small>
                    {driver.key === dominantDriver?.key
                      ? "最大影响来源"
                      : "次要影响来源"}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <p className="product-category-formal-readiness__driver-empty">
              {props.selectedView === "monthly"
                ? "归因数据加载中，正式FTP后经营净收入仍按当前口径展示。"
                : "关键驱动仅支持月度视图，汇总视图继续展示正式FTP后经营净收入。"}
            </p>
          )}
        </section>
      </div>
    </section>
  );
}
