# -*- coding: utf-8 -*-
"""
credit_bond_data.py
信用债数据层：收益率曲线、信用利差、二永债利差、理财规模
数据源：Wind API（日频，收盘后跑）
输出：output/credit_bond_latest.csv
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

import warnings
warnings.filterwarnings("ignore")

try:
    from WindPy import w
    WIND_AVAILABLE = w.start() == 0
except Exception:
    WIND_AVAILABLE = False
    print("[WARNING] Wind not available, using mock data for development")

import pandas as pd
import numpy as np
from datetime import datetime, date
import time

# ── Wind 代码定义 ──────────────────────────────────────────────────────────────

# 中债估值收益率（城投债）
# 格式: 隐含评级_期限，如 AA_2Y 代表隐含评级AA、2年期
# 使用中债估值收益率代码（S00597xx 系列）
YIELD_CODES = {
    # 城投债
    "城投_AA_1Y":  "S0059767",  # 隐含AA 1年
    "城投_AA_2Y":  "S0059768",
    "城投_AA_3Y":  "S0059769",
    "城投_AA_4Y":  "S0059770",
    "城投_AA_5Y":  "S0059771",
    "城投_AA_7Y":  "S0059772",
    "城投_AA_10Y": "S0059773",
    "城投_AA(2)_1Y":  "S0059780",
    "城投_AA(2)_2Y":  "S0059781",
    "城投_AA(2)_3Y":  "S0059782",
    "城投_AA(2)_4Y":  "S0059783",
    "城投_AA(2)_5Y":  "S0059784",
    "城投_AA+_1Y": "S0059756",
    "城投_AA+_3Y": "S0059757",
    "城投_AA+_5Y": "S0059758",
    "城投_AA+_7Y": "S0059759",
    "城投_AAA_1Y": "S0059753",
    "城投_AAA_3Y": "S0059754",
    "城投_AAA_5Y": "S0059755",
    # 中短票
    "中短票_AAA_1Y": "S0059650",
    "中短票_AAA_3Y": "S0059651",
    "中短票_AAA_5Y": "S0059652",
    "中短票_AA+_1Y": "S0059653",
    "中短票_AA+_3Y": "S0059654",
    "中短票_AA+_5Y": "S0059655",
    "中短票_AA_1Y":  "S0059656",
    "中短票_AA_3Y":  "S0059657",
    "中短票_AA_5Y":  "S0059658",
    "中短票_AA-_1Y": "S0059659",
    "中短票_AA-_3Y": "S0059660",
    "中短票_AA-_5Y": "S0059661",
    # 信用利差（相对国债）
    "利差_城投_AA_3Y":  "S0059784",
    "利差_城投_AA+_3Y": "S0059785",
    "利差_中短票_AAA_3Y": "S0059670",
    "利差_中短票_AA+_3Y": "S0059671",
    "利差_中短票_AA_3Y":  "S0059672",
    # 二永债
    "二永债_大行二级资本债_2Y": "S0059900",
    "二永债_大行二级资本债_4Y": "S0059901",
    "二永债_大行二级资本债_5Y": "S0059902",
    "二永债_大行二级资本债_10Y": "S0059903",
    "二永债_股份行二级资本债_2Y": "S0059910",
    "二永债_股份行二级资本债_4Y": "S0059911",
    "二永债_股份行二级资本债_5Y": "S0059912",
    "二永债_城商行二级资本债_2Y": "S0059920",
    "二永债_城商行二级资本债_4Y": "S0059921",
    "二永债_大行永续债_2Y": "S0059930",
    "二永债_大行永续债_3Y": "S0059931",
    "二永债_大行永续债_5Y": "S0059932",
    "二永债_股份行永续债_2Y": "S0059935",
    "二永债_股份行永续债_3Y": "S0059936",
    "二永债_股份行永续债_5Y": "S0059937",
    "二永债_城商行永续债_2Y": "S0059940",
    "二永债_城商行永续债_3Y": "S0059941",
}

# 基准利率
BENCHMARK_CODES = {
    "国债1Y": "S0059743",
    "国债2Y": "S0059745",
    "国债3Y": "S0059746",
    "国债5Y": "S0059747",
    "国债7Y": "S0059748",
    "国债10Y": "S0059749",
    "国债20Y": "S0059751",
    "国债30Y": "S0059752",
    "DR007": "DR007.IB",
    "SHIBOR_3M": "M0041813",
}

# 永续债相对普通债的品种利差（单位：bp）
# 这些需要通过计算得到：永续债收益率 - 同期限同评级普通债收益率
PERPETUAL_CODES = {
    "永续_产业债_AAA_3Y":  "S0059800",
    "永续_产业债_AA+_3Y":  "S0059801",
    "永续_城投债_AA+_3Y":  "S0059810",
    "永续_城投债_AA_3Y":   "S0059811",
}


# ── Wind 数据拉取 ──────────────────────────────────────────────────────────────

def pull_wind_series(codes_dict, start_date, end_date):
    """批量拉取 Wind 时序数据"""
    results = {}
    if not WIND_AVAILABLE:
        return results

    for name, code in codes_dict.items():
        try:
            data = w.wsd(code, "close", start_date, end_date, "Fill=Previous")
            if data.ErrorCode == 0 and data.Data:
                dates = [d.strftime("%Y-%m-%d") for d in data.Times]
                values = [v if (v is not None and v == v) else np.nan for v in data.Data[0]]
                results[name] = pd.Series(values, index=pd.to_datetime(dates))
            time.sleep(0.05)  # Wind 频率限制
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
    return results


def compute_spread(series_dict, benchmark_name, target_name):
    """计算信用利差：目标收益率 - 基准利率（bp）"""
    if benchmark_name not in series_dict or target_name not in series_dict:
        return None
    spread = (series_dict[target_name] - series_dict[benchmark_name]) * 100  # 转 bp
    return spread


# ── 主函数 ────────────────────────────────────────────────────────────────────

def fetch_credit_bond_data():
    today = date.today()
    start = (today - pd.DateOffset(days=250)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching credit bond data...")
    print(f"  Period: {start} → {end}")

    # 1. 拉取收益率数据
    yield_series = pull_wind_series(YIELD_CODES, start, end)
    benchmark_series = pull_wind_series(BENCHMARK_CODES, start, end)

    # 合并所有 series
    all_series = {**yield_series, **benchmark_series}

    # 2. 计算信用利差（最新值）
    credit_spreads = {}
    # 城投债利差：vs 国债
    for key in yield_series:
        if key.startswith("城投_"):
            tenor = key.split("_")[-1]  # e.g. "3Y"
            tenor_code = {"1Y": "国债1Y", "2Y": "国债2Y", "3Y": "国债3Y",
                          "4Y": "国债5Y", "5Y": "国债5Y", "7Y": "国债7Y", "10Y": "国债10Y"}.get(tenor)
            if tenor_code and tenor_code in benchmark_series:
                spread = compute_spread(benchmark_series, tenor_code, key)
                if spread is not None:
                    credit_spreads[f"利差_{key}"] = spread

    # 3. 拉取二永债数据
    eternal_codes = {**PERPETUAL_CODES}
    perpetual_series = pull_wind_series(eternal_codes, start, end)

    # 合并永续数据
    all_series.update(perpetual_series)

    # 4. 构建最新截面数据
    records = []

    # 收益率最新值
    for name, series in yield_series.items():
        if len(series) > 0:
            latest_val = series.dropna().iloc[-1] if not series.dropna().empty else np.nan
            latest_date = series.dropna().index[-1] if not series.dropna().empty else None
            records.append({
                "日期": latest_date,
                "指标类型": "收益率",
                "品种": name,
                "最新值": latest_val,
                "单位": "%",
            })

    # 信用利差最新值
    for name, series in credit_spreads.items():
        if len(series) > 0:
            latest_val = series.dropna().iloc[-1] if not series.dropna().empty else np.nan
            latest_date = series.dropna().index[-1] if not series.dropna().empty else None
            records.append({
                "日期": latest_date,
                "指标类型": "信用利差",
                "品种": name,
                "最新值": latest_val,
                "单位": "bp",
            })

    # 二永债利差（vs 同期限中短票）
    for name, series in perpetual_series.items():
        if len(series) > 0:
            latest_val = series.dropna().iloc[-1] if not series.dropna().empty else np.nan
            latest_date = series.dropna().index[-1] if not series.dropna().empty else None
            records.append({
                "日期": latest_date,
                "指标类型": "品种利差",
                "品种": name,
                "最新值": latest_val,
                "单位": "bp",
            })

    # 基准利率
    for name, series in benchmark_series.items():
        if len(series) > 0:
            latest_val = series.dropna().iloc[-1] if not series.dropna().empty else np.nan
            latest_date = series.dropna().index[-1] if not series.dropna().empty else None
            records.append({
                "日期": latest_date,
                "指标类型": "基准利率",
                "品种": name,
                "最新值": latest_val,
                "单位": "%",
            })

    # 5. 保存
    df = pd.DataFrame(records)
    out_path = paths.OUTPUT_DIR / "credit_bond_latest.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  Saved {len(df)} records to {out_path}")

    # 打印摘要
    if not df.empty:
        latest = df.iloc[-1]["日期"]
        print(f"\n  最新数据日期: {latest}")
        print(df[df["指标类型"] == "收益率"].to_string(index=False))

    return df


# ── 持有期收益率计算（3个月骑乘收益）────────────────────────────────────────────

def calc_roll_yield(yield_curve: pd.Series, tenor_from: str, tenor_to: str,
                    hold_months: int = 3) -> float:
    """
    估算持有期收益率（骑乘收益）
    yield_curve: pd.Series(index=期限标签, values=收益率%)
    hold_months: 持有月数
    """
    y0 = yield_curve.get(tenor_from)
    y1 = yield_curve.get(tenor_to)
    if y0 is None or y1 is None or np.isnan(y0) or np.isnan(y1):
        return np.nan
    # 简化：持有期收益 ≈ (y0 - y1) * hold_months/12 + y0 * hold_months/12
    # 即持有至更长期限，曲线陡峭带来骑乘收益
    roll = (y1 - y0) * hold_months / 12
    carry = y0 * hold_months / 12
    return carry + roll


if __name__ == "__main__":
    fetch_credit_bond_data()
