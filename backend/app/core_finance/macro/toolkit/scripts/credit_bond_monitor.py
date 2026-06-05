# -*- coding: utf-8 -*-
"""
credit_bond_monitor.py
信用债风控层：
1. 固收+赎回风险监控（MA5 阈值报警）
2. 城投区域风险评分（弱省份预警）
3. 每日截面利差分位数（距离历史底部空间）

依赖：第三方固收+申赎数据（需接入）、Wind 区域城投数据
输出：output/credit_monitor.csv / risk_alert.csv
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path

# ── 阈值定义 ──────────────────────────────────────────────────────────────────

FIXED_INCOME_PLUS_WARNING   = -1.0   # MA5 < -1 → 提示谨慎
FIXED_INCOME_PLUS_DANGER     = -2.0   # MA5 < -2 → 强烈预警（二永债降仓）
SPREAD_NEAR_FLOOR_BP         = 6      # 利差距底部空间 < 6bp → 防守为主
HIST_250D_NEAR_FLOOR_BP      = 5      # 滚动250日均值-2σ空间 < 5bp → 极低性价比

# 城投区域风险（弱省份列表）
WEAK_PROVINCES = ["贵州", "云南", "天津", "内蒙古", "甘肃", "吉林", "黑龙江"]

# ── 固收+申赎数据（示例）───────────────────────────────────────────────────────
# 实际应从第三方数据源（私募排排网/济安金信/自建）接入
# 此处用模拟数据演示格式

FIXED_INCOME_PLUS_HISTORY = [
    # 日期, 净申赎强度, MA5
    {"日期": "2026-03-20", "净申赎强度": -0.31, "MA5": -0.28},
    {"日期": "2026-03-21", "净申赎强度": -0.35, "MA5": -0.30},
    {"日期": "2026-03-22", "净申赎强度": -0.42, "MA5": -0.33},
    {"日期": "2026-03-23", "净申赎强度": -0.48, "MA5": -0.38},
    {"日期": "2026-03-24", "净申赎强度": -0.51, "MA5": -0.41},  # 当前 MA5=-0.51
    {"日期": "2026-03-25", "净申赎强度": -0.44, "MA5": -0.44},
    {"日期": "2026-03-26", "净申赎强度": -0.38, "MA5": -0.43},
    {"日期": "2026-03-27", "净申赎强度": -0.29, "MA5": -0.40},
]

# 城投区域风险评分（示例）
PROVINCE_RISK_SCORE = {
    "广东":   {"净融资亿": 291, "收益率下行bp": 8,  "风险评分": 1},
    "天津":   {"净融资亿": 60,  "收益率下行bp": 12, "风险评分": 2},
    "河南":   {"净融资亿": 60,  "收益率下行bp": 9,  "风险评分": 2},
    "云南":   {"净融资亿": 60,  "收益率下行bp": 11, "风险评分": 3},
    "重庆":   {"净融资亿": 60,  "收益率下行bp": 9,  "风险评分": 2},
    "湖北":   {"净融资亿": -79, "收益率下行bp": 7,  "风险评分": 3},
    "四川":   {"净融资亿": -30, "收益率下行bp": 8,  "风险评分": 2},
    "江西":   {"净融资亿": -30, "收益率下行bp": 8,  "风险评分": 2},
    "山东":   {"净融资亿": -30, "收益率下行bp": 7,  "风险评分": 2},
    "浙江":   {"净融资亿": 20,  "收益率下行bp": 7,  "风险评分": 1},
    "江苏":   {"净融资亿": 15,  "收益率下行bp": 8,  "风险评分": 1},
    "北京":   {"净融资亿": 10,  "收益率下行bp": 6,  "风险评分": 1},
    "贵州":   {"净融资亿": 5,   "收益率下行bp": 12, "风险评分": 4},
    "内蒙古": {"净融资亿": 3,   "收益率下行bp": 12, "风险评分": 4},
    "甘肃":   {"净融资亿": 2,   "收益率下行bp": 11, "风险评分": 4},
    "吉林":   {"净融资亿": 1,   "收益率下行bp": 10, "风险评分": 4},
    "黑龙江": {"净融资亿": 0,   "收益率下行bp": 10, "风险评分": 4},
}


# ── 监控函数 ──────────────────────────────────────────────────────────────────

def monitor_fixed_income_plus():
    """
    监控固收+申赎风险
    返回: (MA5值, 风险等级, 建议)
    """
    df = pd.DataFrame(FIXED_INCOME_PLUS_HISTORY)
    latest = df.iloc[-1]
    ma5 = latest["MA5"]

    if ma5 < FIXED_INCOME_PLUS_DANGER:
        level = "🚨 危险"
        advice = "二永债强制降仓，禁止新增买入"
        action = "大幅减仓二永债"
    elif ma5 < FIXED_INCOME_PLUS_WARNING:
        level = "⚠️ 警示"
        advice = "二永债利差承压，适度减仓，关注赎回动态"
        action = "减仓二永债10-20%"
    else:
        level = "✅ 正常"
        advice = "赎回压力可控，可正常配置二永债"
        action = "正常配置"

    return {
        "指标": "固收+申赎强度MA5",
        "当前值": round(ma5, 2),
        "阈值_警示": FIXED_INCOME_PLUS_WARNING,
        "阈值_危险": FIXED_INCOME_PLUS_DANGER,
        "风险等级": level,
        "建议": advice,
        "操作": action,
    }


def monitor_province_risk():
    """
    城投区域风险监控
    返回: 各省份风险 DataFrame
    """
    records = []
    for province, data in PROVINCE_RISK_SCORE.items():
        if data["净融资亿"] < 0:
            funding_status = "净流出"
        elif data["净融资亿"] < 30:
            funding_status = "偏低"
        else:
            funding_status = "正常"

        records.append({
            "省份": province,
            "净融资_亿": data["净融资亿"],
            "收益率变动_bp": data["收益率下行bp"],
            "风险评分": data["风险评分"],
            "资金面状态": funding_status,
            "预警": "⚠️" if data["风险评分"] >= 3 else ("⚠️弱省" if province in WEAK_PROVINCES else ""),
        })

    df = pd.DataFrame(records)
    df = df.sort_values("风险评分", ascending=False)
    return df


def monitor_spread_floor(df_credit: pd.DataFrame) -> pd.DataFrame:
    """
    利差底部空间监控
    df_credit: credit_bond_latest.csv 读取的 DataFrame
    返回: 各品种距历史底部空间
    """
    spreads = df_credit[df_credit["指标类型"] == "信用利差"].copy()
    if spreads.empty:
        return pd.DataFrame()

    # 各品种利差最新值 vs 区间最小值（2025年7月18日以来）
    # 模拟区间最小值（实际应从历史数据计算）
    floor_data = {
        "城投_AA_1Y": 30,
        "城投_AA_3Y": 35,
        "城投_AA_5Y": 40,
        "城投_AA+_3Y": 25,
        "城投_AA+_5Y": 30,
        "中短票_AAA_1Y": 20,
        "中短票_AAA_3Y": 22,
        "中短票_AA+_3Y": 30,
        "中短票_AA_3Y": 40,
    }

    records = []
    for _, row in spreads.iterrows():
        name = row["品种"].replace("利差_", "")
        latest = row["最新值"]
        if name in floor_data and latest is not None:
            floor = floor_data[name]
            dist = latest - floor
            records.append({
                "品种": name,
                "最新利差_bp": round(latest, 1),
                "区间最小_bp": floor,
                "距底部空间_bp": round(dist, 1),
                "状态": "🟢 充裕" if dist > SPREAD_NEAR_FLOOR_BP else ("🟡 偏低" if dist > 3 else "🔴 极低"),
            })

    return pd.DataFrame(records)


def generate_monitor_report():
    """
    生成每日监控报告
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating credit bond monitor report...")

    # 1. 读取信用债数据
    credit_path = paths.OUTPUT_DIR / "credit_bond_latest.csv"
    if credit_path.exists():
        credit_df = pd.read_csv(credit_path, encoding="utf-8-sig")
    else:
        credit_df = pd.DataFrame()
        print("  [WARNING] credit_bond_latest.csv not found, using mock data")

    # 2. 固收+风险
    fi_plus = monitor_fixed_income_plus()
    print(f"\n  固收+赎回风险: {fi_plus['风险等级']} MA5={fi_plus['当前值']}")
    print(f"  建议: {fi_plus['建议']}")

    # 3. 城投区域风险
    province_risk = monitor_province_risk()
    print(f"\n  城投区域风险 TOP5（高风险省份）:")
    print(province_risk.head(5).to_string(index=False))

    # 4. 利差底部空间
    if not credit_df.empty:
        spread_floor = monitor_spread_floor(credit_df)
        if not spread_floor.empty:
            print(f"\n  利差底部空间（距区间最小值）:")
            print(spread_floor.to_string(index=False))

    # 5. 生成预警记录
    alerts = []

    # 固收+预警
    alerts.append(fi_plus)

    # 弱省份预警
    weak_provinces = province_risk[province_risk["省份"].isin(WEAK_PROVINCES)]
    if not weak_provinces.empty:
        for _, row in weak_provinces.iterrows():
            alerts.append({
                "指标": "城投区域风险",
                "当前值": row["省份"],
                "风险评分": row["风险评分"],
                "风险等级": "⚠️ 弱省",
                "建议": f"{row['省份']}净融资{row['资金面状态']}，关注估值调整风险",
                "操作": "低配或回避",
            })

    # 利差极低预警
    if not credit_df.empty:
        spread_floor = monitor_spread_floor(credit_df)
        if not spread_floor.empty:
            low_spread = spread_floor[spread_floor["距底部空间_bp"] <= SPREAD_NEAR_FLOOR_BP]
            for _, row in low_spread.iterrows():
                alerts.append({
                    "指标": "利差底部预警",
                    "当前值": f"{row['品种']} {row['最新利差_bp']}bp",
                    "距底部空间_bp": row["距底部空间_bp"],
                    "风险等级": row["状态"],
                    "建议": "利差偏低，性价比有限，防守为主",
                    "操作": "维持现有仓位，不追涨",
                })

    # 保存预警
    alert_df = pd.DataFrame(alerts)
    alert_out = paths.OUTPUT_DIR / "risk_alert.csv"
    alert_df.to_csv(alert_out, index=False, encoding="utf-8-sig")
    print(f"\n  Risk alerts saved to {alert_out}")

    # 保存监控快照
    monitor_snapshot = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "固收+MA5": fi_plus["当前值"],
        "固收+风险等级": fi_plus["风险等级"],
        "二永债操作": fi_plus["操作"],
        "高风险省份数": len(weak_provinces),
        "利差极低品种数": len(low_spread) if not credit_df.empty else 0,
    }
    snap_df = pd.DataFrame([monitor_snapshot])
    snap_out = paths.OUTPUT_DIR / "credit_monitor.csv"
    snap_df.to_csv(snap_out, index=False, encoding="utf-8-sig")
    print(f"  Monitor snapshot saved to {snap_out}")

    return alert_df


# ── 主函数 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    generate_monitor_report()
