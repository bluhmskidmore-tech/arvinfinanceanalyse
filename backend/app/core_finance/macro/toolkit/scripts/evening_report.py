# -*- coding: utf-8 -*-
"""
evening_report.py
每日宏观晚间综合报告
一键生成，串联所有模块：
1. AlphaEar 新闻（宏观舆情）
2. Polymarket 预测市场
3. Crisis Score / CTA / 美林时钟信号
4. Monte Carlo 风险统计
5. 信用债监控
输出：output/evening_report_YYYYMMDD.md
"""
import os, sys

SKILL_PATH = os.environ.get(
    "ALPHAEAR_NEWS_SKILL_PATH",
    r"C:\Users\arvin\AppData\Roaming\npm\node_modules\openclaw\skills\alphaear-news",
)
TOOLKIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_PATH)
sys.path.insert(0, TOOLKIT_ROOT)

import paths

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from datetime import datetime, date
from scripts.database_manager import DatabaseManager
from scripts.news_tools import NewsNowTools, PolymarketTools

# ──────────────────────────────────────────────────────────────────────────────

MACRO_SOURCES = {
    "cls": "财联社",
    "wallstreetcn": "华尔街见闻",
    "xueqiu": "雪球热榜",
}

MACRO_KEYWORDS = [
    "央行", "降息", "加息", "降准", "存款准备金",
    "美联储", "Fed", "利率", "汇率", "人民币", "美元", "美债",
    "MLF", "SLF", "LPR", "逆回购",
    "PMI", "CPI", "PPI", "GDP", "社融", "M2", "出口", "进口",
    "工业增加值", "零售", "消费", "房地产", "房价",
    "原油", "油价", "黄金", "铜", "大宗商品",
    "中东", "俄乌", "伊朗", "红海", "胡塞",
    "关税", "制裁",
    "Crisis", "风险", "流动性", "信用债", "城投", "二永",
    "危机", "宽松", "收紧", "量化", "北向", "外资",
]

POLYMARKET_MACRO_KEYWORDS = [
    "china", "russia", "iran", "oil", "war", "tariff", "inflation",
    "rate", "fed", "gold", "bitcoin", "dollar", "trade", "military",
    "conflict", "energy", "sanction", "invade", "ceasefire",
]


def is_macro(title):
    t = str(title).lower()
    return any(kw.lower() in t for kw in MACRO_KEYWORDS)


def parse_json_field(val):
    if val is None:
        return None
    if isinstance(val, str):
        import json as _json
        try:
            return _json.loads(val)
        except (ValueError, TypeError):
            return val
    return val


def fetch_news():
    """抓取并筛选宏观舆情"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching macro news...")
    db = DatabaseManager(db_path=str(paths.OUTPUT_DIR / "alphaear_news.db"))
    tools = NewsNowTools(db)

    all_news = []
    for src, name in MACRO_SOURCES.items():
        try:
            news = tools.fetch_hot_news(src, count=20)
            if isinstance(news, list):
                for item in news:
                    item["source_name"] = name
                    item["is_macro"] = is_macro(item.get("title", ""))
                all_news.extend(news)
        except Exception as e:
            print(f"  [{src}] ERROR: {e}")

    df_all = pd.DataFrame(all_news)
    df_macro = df_all[df_all["is_macro"] == True].copy()
    df_all.to_csv(paths.OUTPUT_DIR / "alphaear_news_latest.csv", index=False, encoding="utf-8-sig")
    df_macro.to_csv(paths.OUTPUT_DIR / "alphaear_macro_news.csv", index=False, encoding="utf-8-sig")
    print(f"  Total: {len(df_all)} | Macro: {len(df_macro)}")
    return df_all, df_macro


def fetch_polymarket():
    """抓取宏观相关预测市场"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching Polymarket...")
    db = DatabaseManager(db_path=str(paths.OUTPUT_DIR / "alphaear_news.db"))
    pm = PolymarketTools(db)
    markets = pm.get_active_markets(limit=100)

    macro = []
    for m in markets:
        q = str(m.get("question", ""))
        q_lower = q.lower()
        if any(k in q_lower for k in POLYMARKET_MACRO_KEYWORDS):
            prices = parse_json_field(m.get("outcomePrices"))
            vol = float(parse_json_field(m.get("volume")) or 0)
            prob = None
            if isinstance(prices, list) and len(prices) >= 2:
                try:
                    prob = round(float(prices[0]) * 100, 1)
                except (ValueError, TypeError):
                    pass
            macro.append({
                "question": q,
                "yes_prob_pct": prob,
                "volume_usd": vol,
            })

    df = pd.DataFrame(macro)
    if not df.empty:
        df = df.sort_values("volume_usd", ascending=False)
    df.to_csv(paths.OUTPUT_DIR / "polymarket_macro.csv", index=False, encoding="utf-8-sig")
    print(f"  Polymarket macro: {len(df)} items")
    return df


def load_signals():
    """加载所有量化信号"""
    files = {
        "Crisis Score": paths.OUTPUT_DIR / "crisis_score_latest.csv",
        "CTA": paths.OUTPUT_DIR / "cta_results.csv",
        "美林时钟": paths.OUTPUT_DIR / "merrill_clock_latest.csv",
        "信用债信号": paths.OUTPUT_DIR / "credit_signal.csv",
        "Monte Carlo": paths.OUTPUT_DIR / "mc_simulation_results.csv",
        "风控": paths.OUTPUT_DIR / "credit_monitor.csv",
        "Final Signal": paths.OUTPUT_DIR / "final_signal.csv",
    }
    data = {}
    for key, path in files.items():
        if path.exists():
            try:
                data[key] = pd.read_csv(path, encoding="utf-8-sig")
            except UnicodeDecodeError:
                try:
                    data[key] = pd.read_csv(path)
                except (OSError, pd.errors.ParserError) as e:
                    print(f"  [{key}] WARNING: could not load {path}: {e}")
            except (OSError, pd.errors.ParserError) as e:
                print(f"  [{key}] WARNING: could not load {path}: {e}")
    return data


def extract_value(df, col_hint, val_hint):
    """从信号CSV里提取数值"""
    if df is None or df.empty:
        return "N/A"
    row = df.iloc[-1]
    for col in df.columns:
        if col_hint.lower() in col.lower():
            v = row[col]
            if pd.notna(v):
                try:
                    return round(float(v), 3)
                except (ValueError, TypeError):
                    return v
    return "N/A"


def extract_str(df, col_hint):
    if df is None or df.empty:
        return "N/A"
    row = df.iloc[-1]
    for col in df.columns:
        if col_hint.lower() in col.lower():
            v = row[col]
            if pd.notna(v):
                return str(v)
    return "N/A"


# ──────────────────────────────────────────────────────────────────────────────

def build_report():
    today = date.today()
    print(f"\n{'='*60}")
    print(f"  Macro Toolkit 晚间综合报告 — {today.strftime('%Y年%m月%d日')}")
    print(f"{'='*60}\n")

    # 1. 新闻
    df_all, df_macro = fetch_news()

    # 2. Polymarket
    pm_df = fetch_polymarket()

    # 3. 信号
    sig = load_signals()

    # ── Crisis Score ───────────────────────────────────────────────
    cs_df = sig.get("Crisis Score")
    cs_score = extract_value(cs_df, "score", "")
    if cs_score == "N/A":
        for col in (cs_df.columns if cs_df is not None else []):
            if "crisis" in col.lower() or "score" in col.lower():
                cs_score = cs_df.iloc[-1][col] if cs_df is not None else "N/A"
                break
    cs_status = extract_str(cs_df, "status")

    # ── CTA ──────────────────────────────────────────────────────
    cta_df = sig.get("CTA")
    cta_sig = extract_str(cta_df, "signal")
    cta_str_val = extract_value(cta_df, "strength", "")

    # ── 美林时钟 ────────────────────────────────────────────────
    mc_df = sig.get("美林时钟")
    mc_quad = extract_str(mc_df, "quadrant")
    mc_bond = extract_str(mc_df, "bond")

    # ── Monte Carlo ───────────────────────────────────────────────
    mc_df2 = sig.get("Monte Carlo")
    var99 = extract_value(mc_df2, "VaR_99", "")
    sharpe = extract_value(mc_df2, "sharpe", "")

    # ── 信用债 ───────────────────────────────────────────────────
    mon_df = sig.get("风控")
    fi_risk = extract_str(mon_df, "风险等级")

    # ── 综合判断 ─────────────────────────────────────────────────
    try:
        cs_v = float(cs_score) if cs_score != "N/A" else None
    except (ValueError, TypeError):
        cs_v = None

    if cs_v is not None:
        if cs_v >= 2:
            risk_rating = "🔴 高风险"
            overall = "建议降低风险资产仓位，等待信号确认"
        elif cs_v >= 1:
            risk_rating = "🟡 警惕"
            overall = "谨慎加仓，关注趋势变化"
        else:
            risk_rating = "🟢 正常"
            overall = "可维持或适度加仓"
    else:
        risk_rating = "⚪ 未知"
        overall = "信号不足，建议补充数据"

    # ── 报告内容 ─────────────────────────────────────────────────
    lines = []
    lines.append(f"# 宏观量化晚间报告")
    lines.append(f"")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**报告日期**: {today.strftime('%Y年%m月%d日')}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 一句话
    lines.append(f"## 一句话总结")
    lines.append(f"")
    lines.append(f"**{risk_rating}** — {overall}")
    lines.append(f"")
    lines.append(f"Crisis Score: **{cs_score}** | CTA: **{cta_sig}** | 美林时钟: **{mc_quad}**")
    lines.append(f"")

    # 量化信号
    lines.append(f"## 量化信号面板")
    lines.append(f"")
    lines.append(f"| 指标 | 数值 | 含义 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| Crisis Score | {cs_score} | {cs_status} |")
    lines.append(f"| CTA信号 | {cta_sig} | 强度 {cta_str_val} |")
    lines.append(f"| 美林时钟 | {mc_quad} | 债券方向 {mc_bond} |")
    lines.append(f"| VaR(99%) | {var99} | Monte Carlo模拟 |")
    lines.append(f"| 夏普比率 | {sharpe} | 风险调整后收益 |")
    lines.append(f"| 固收+风险 | {fi_risk} | 赎回压力 |")
    lines.append(f"")

    # 宏观舆情
    lines.append(f"## 宏观舆情（今日热点）")
    lines.append(f"")
    if not df_macro.empty:
        for src, name in MACRO_SOURCES.items():
            subset = df_macro[df_macro["source"] == src].head(5)
            if subset.empty:
                continue
            lines.append(f"### {name}")
            for _, row in subset.iterrows():
                title = str(row.get("title", ""))[:60]
                lines.append(f"- {title}")
            lines.append(f"")
    else:
        lines.append("*今日无宏观相关热点*")
        lines.append(f"")

    # Polymarket
    lines.append(f"## 预测市场（聪明钱情绪）")
    lines.append(f"")
    if not pm_df.empty:
        lines.append(f"| 概率 | 交易量 | 预测问题 |")
        lines.append(f"|------|--------|----------|")
        for _, row in pm_df.head(10).iterrows():
            prob = f"{row['yes_prob_pct']:.1f}%" if pd.notna(row['yes_prob_pct']) else "N/A"
            vol = f"${row['volume_usd']/1e6:.1f}M" if row['volume_usd'] > 1e6 else f"${row['volume_usd']/1e3:.0f}K"
            q = str(row['question'])[:50]
            lines.append(f"| {prob} | {vol} | {q} |")
        lines.append(f"")
        lines.append(f"*来源：Polymarket | 概率为 YES 选项*")
        lines.append(f"")
    else:
        lines.append("*暂无宏观相关预测市场*")
        lines.append(f"")

    # 风险提示
    lines.append(f"## 风险提示")
    lines.append(f"")
    if fi_risk not in ("N/A", "正常", "✅ 正常"):
        lines.append(f"- ⚠️ **固收+赎回风险**: {fi_risk}")
    if cs_v is not None and cs_v >= 1:
        lines.append(f"- ⚠️ **Crisis Score偏高**: {cs_score}，建议关注")
    if var99 != "N/A":
        try:
            if float(var99) < -0.1:
                lines.append(f"- ⚠️ **VaR(99%)较低**: {var99}，尾部风险显著")
        except (ValueError, TypeError):
            pass
    if not lines[-1].startswith(f"- ⚠️"):
        lines.append(f"- ✅ 无重大风险预警")
    lines.append(f"")

    # 下一步
    lines.append(f"## 下一步建议")
    lines.append(f"")
    if cs_v is not None and cs_v >= 2:
        lines.append(f"1. **降低风险资产敞口**，等待CTA信号确认")
        lines.append(f"2. 关注明日宏观数据（PMI/CPI）是否验证当前判断")
        lines.append(f"3. 减少二永债仓位，防范固收+赎回传导")
    elif cs_v is not None and cs_v >= 1:
        lines.append(f"1. **维持现有配置**，不追高不加仓")
        lines.append(f"2. 关注Crisis Score每日变化，触发阈值时再调整")
        lines.append(f"3. 信用债注意弱省份城投风险")
    else:
        lines.append(f"1. **维持或适度加仓**，当前环境支持风险偏好")
        lines.append(f"2. 关注美元/黄金走势，持续跟踪宏观舆情")
        lines.append(f"3. 下个月理财规模增量可期，信用债仍有配置需求")

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*数据来源: Wind / AlphaEar / Polymarket | 仅供参考，不构成投资建议*")

    report_text = "\n".join(lines)

    # 保存
    out_path = paths.OUTPUT_DIR / f"evening_report_{today.strftime('%Y%m%d')}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\n{'='*60}")
    print(report_text)
    print(f"{'='*60}")
    print(f"\n✅ Report saved: {out_path}")
    return out_path


if __name__ == "__main__":
    build_report()
