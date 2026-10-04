import { Link, useLocation } from "react-router-dom";
import { readMarketSourceContext } from "./marketSourceContext";
import "./marketSourceContext.css";

export default function MarketSourceContextBanner() {
  const location = useLocation();
  const source = readMarketSourceContext(location.search);
  if (!source) return null;
  const labels: Record<string, string> = { indicator_id: "指标", indicator_period: "来源期次", published_at: "发布时间", market_observation_date: "市场观察日", topic_code: "专题", received_from: "接收起点", received_to: "接收终点" };
  return <aside className="market-source-context" aria-label="市场总览来源">
    <div><strong>来自市场总览</strong><p>{Object.entries(labels).filter(([key]) => source.params.has(key)).map(([key, label]) => `${label}：${source.params.get(key)}`).join(" · ") || "保留首页观察上下文"}</p>
    <small>来源日期用于核对；本页分析仍以接口返回的实际日期为准。</small></div>
    <Link to={source.returnTo}>返回市场总览</Link>
  </aside>;
}
