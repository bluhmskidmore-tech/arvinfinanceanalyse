# -*- coding: utf-8 -*-
"""
alphaear_news_fetch.py
接入 alphaear-news skill，获取实时财经热点
数据源：财联社、华尔街见闻、雪球等
输出：output/alphaear_news_latest.csv
"""
import os, sys
SKILL_PATH = os.environ.get(
    "ALPHAEAR_NEWS_SKILL_PATH",
    r"C:\Users\arvin\AppData\Roaming\npm\node_modules\openclaw\skills\alphaear-news",
)
sys.path.insert(0, SKILL_PATH)
_toolkit_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _toolkit_root)

import paths

import warnings
warnings.filterwarnings("ignore")

from datetime import datetime
import pandas as pd

from scripts.database_manager import DatabaseManager
from scripts.news_tools import NewsNowTools

# 宏规定义
MACRO_SOURCES = {
    "cls":           "财联社",
    "wallstreetcn":  "华尔街见闻",
    "xueqiu":        "雪球热榜",
}

# 宏观关键词（用于筛选）
MACRO_KEYWORDS = [
    # 政策/利率/汇率
    "央行", "降息", "加息", "降准", "存款准备金",
    "美联储", "Fed", "利率", "汇率", "人民币", "美元", "美债",
    "MLF", "SLF", "LPR", "逆回购",
    # 宏观数据
    "PMI", "CPI", "PPI", "GDP", "社融", "M2", "出口", "进口",
    "工业增加值", "零售", "消费", "房地产", "房价",
    # 地缘/大宗
    "原油", "油价", "黄金", "铜", "大宗商品",
    "中东", "俄乌", "伊朗", "红海", "胡塞",
    "关税", "贸易战", "制裁",
    # 市场/风险
    "Crisis", "风险", "流动性", "信用债", "城投", "二永",
    "危机", "宽松", "收紧", "量化紧缩", "QE", "QT",
    # A股/基金
    "北向", "南向", "外资", "主力", "机构",
]


def is_macro_related(title: str) -> bool:
    t = title.lower()
    return any(kw.lower() in t for kw in MACRO_KEYWORDS)


def fetch_alphaear_news(sources=None, count=20):
    if sources is None:
        sources = list(MACRO_SOURCES.keys())

    db = DatabaseManager(db_path=str(paths.OUTPUT_DIR / "alphaear_news.db"))
    tools = NewsNowTools(db)

    all_news = []
    for source in sources:
        try:
            news = tools.fetch_hot_news(source, count=count)
            if isinstance(news, list):
                for item in news:
                    item["source_name"] = MACRO_SOURCES.get(source, source)
                    item["is_macro"] = is_macro_related(item.get("title", ""))
                all_news.extend(news)
            print(f"  [OK] {source} ({MACRO_SOURCES.get(source,'')}) fetched {len(news) if isinstance(news,list) else 0}")
        except Exception as e:
            print(f"  [FAIL] {source}: {e}")

    if not all_news:
        return pd.DataFrame()

    df = pd.DataFrame(all_news)

    # 全部保存
    all_out = paths.OUTPUT_DIR / "alphaear_news_latest.csv"
    df.to_csv(all_out, index=False, encoding="utf-8-sig")
    print(f"\n  Total: {len(df)} items saved to {all_out}")

    # 只筛选宏观相关的
    macro_df = df[df["is_macro"] == True].copy()
    macro_out = paths.OUTPUT_DIR / "alphaear_macro_news.csv"
    macro_df.to_csv(macro_out, index=False, encoding="utf-8-sig")
    print(f"  Macro: {len(macro_df)} items saved to {macro_out}")

    return df, macro_df


def print_macro_news(macro_df):
    """打印宏观相关新闻，按源分组"""
    print(f"\n{'='*60}")
    print(f" 宏观相关舆情 ({len(macro_df)} 条)")
    print(f"{'='*60}")

    for src, name in MACRO_SOURCES.items():
        subset = macro_df[macro_df["source"] == src].head(5)
        if subset.empty:
            continue
        print(f"\n--- {name} ---")
        for _, row in subset.iterrows():
            tag = "[MACRO]" if row["is_macro"] else ""
            print(f"  #{row['rank']} {row['title'][:50]}")

    # 没有宏规定的关键词但实际有用的
    other = macro_df[~macro_df["source"].isin(MACRO_SOURCES.keys())]
    if not other.empty:
        print(f"\n--- 其他 ---")
        for _, row in other.head(5).iterrows():
            print(f"  #{row['rank']} [{row.get('source_name','')}] {row['title'][:50]}")


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching macro news...")
    df, macro_df = fetch_alphaear_news(count=20)
    print_macro_news(macro_df)
