# -*- coding: utf-8 -*-
import warnings; warnings.filterwarnings("ignore")
import sys, os, numpy as np, pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import minimize

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR, ASSET_DIR

plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

COLORS = {"navy": "#0B1F33", "gold": "#C99A2E", "steel": "#4E6B8A", "teal": "#2E6F72", "orange": "#C76433"}

ASSETS = {
    "hs300":     {"name": "沪深300",  "type": "index",   "symbol": "sh000300"},
    "csi500":    {"name": "中证500",  "type": "index",   "symbol": "sh000905"},
    "gold":      {"name": "黄金期货", "type": "futures", "symbol": "AU0"},
    "copper":    {"name": "铜期货",   "type": "futures", "symbol": "CU0"},
    "crude_oil": {"name": "原油期货", "type": "futures", "symbol": "SC0"},
}

RP_CHART_DIR = str(ASSET_DIR)
CSV_OUT      = str(OUTPUT_DIR / "risk_parity_results.csv")
CLOCK_CSV    = str(OUTPUT_DIR / "merrill_clock_latest.csv")

BUDGET_MAP = {
    "复苏": {"hs300": 0.30, "csi500": 0.25, "gold": 0.15, "copper": 0.15, "crude_oil": 0.15},
    "过热": {"hs300": 0.20, "csi500": 0.15, "gold": 0.20, "copper": 0.15, "crude_oil": 0.30},
    "滞胀": {"hs300": 0.12, "csi500": 0.08, "gold": 0.30, "copper": 0.15, "crude_oil": 0.35},
    "衰退": {"hs300": 0.22, "csi500": 0.18, "gold": 0.30, "copper": 0.15, "crude_oil": 0.15},
}


def fetch_data():
    try:
        import akshare as ak
    except ImportError:
        print("[" + chr(38169) + chr(35823) + "] " + chr(35831) + chr(20808) + chr(23433) + chr(35013) + " akshare: pip install akshare")
        sys.exit(1)

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=730)
    end_str    = end_date.strftime("%Y%m%d")
    price_dict = {}

    for key, info in ASSETS.items():
        print("  " + chr(33719) + chr(21462) + " " + info["name"] + "...", end=" ", flush=True)
        try:
            if info["type"] == "index":
                df = ak.stock_zh_index_daily(symbol=info["symbol"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                mask = (df.index >= pd.Timestamp(start_date.date())) & (df.index <= pd.Timestamp(end_date.date()))
                price_dict[key] = df.loc[mask, "close"]
            else:
                df = ak.futures_main_sina(symbol=info["symbol"], start_date="20150101", end_date=end_str)
                date_col  = [c for c in df.columns if chr(26085) + chr(26399) in c or c.lower() == "date"][0]
                close_col = [c for c in df.columns if chr(25910) + chr(30424) in c or c.lower() == "close"][0]
                df["date"] = pd.to_datetime(df[date_col])
                df = df.set_index("date").sort_index()
                mask = (df.index >= pd.Timestamp(start_date.date())) & (df.index <= pd.Timestamp(end_date.date()))
                price_dict[key] = df.loc[mask, close_col].astype(float)
            print("OK (" + str(len(price_dict[key])) + " " + chr(26465) + ")")
        except Exception as e:
            print(chr(22833) + chr(36133) + ": " + str(e))
            return None

    prices = pd.DataFrame(price_dict).dropna()
    if len(prices) < 100:
        print("[" + chr(38169) + chr(35823) + "] " + chr(26377) + chr(25928) + chr(25968) + chr(25454) + chr(19981) + chr(36275) + chr(65288) + str(len(prices)) + " " + chr(34892) + chr(65289) + chr(65292) + chr(36864) + chr(20986))
        sys.exit(1)

    print("  " + chr(21512) + chr(24182) + chr(21518) + chr(26377) + chr(25928) + chr(20132) + chr(26131) + chr(26085) + ": " + str(len(prices)) + " " + chr(22825))
    return prices


def calc_cov(prices):
    log_ret = np.log(prices / prices.shift(1)).dropna()
    cov = log_ret.cov().values * 252
    vol = np.sqrt(np.diag(cov))
    return cov, log_ret, vol


def risk_contributions(w, cov):
    w   = np.array(w)
    sig = float(np.sqrt(w @ cov @ w))
    mrc = cov @ w / sig
    rc  = w * mrc
    return rc, sig


def solve_risk_parity(cov):
    n  = cov.shape[0]
    w0 = np.ones(n) / n
    def objective(w):
        rc, sig = risk_contributions(w, cov)
        return float(np.sum((rc - sig / n) ** 2))
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    bounds = [(1e-6, 1.0)] * n
    res = minimize(objective, w0, method="SLSQP", bounds=bounds,
                   constraints=constraints, options={"ftol": 1e-12, "maxiter": 2000})
    return res.x


def solve_risk_budget(cov, budget):
    n = cov.shape[0]
    b = np.array(budget, dtype=float); b = b / b.sum()
    def objective(w):
        rc, sig = risk_contributions(w, cov)
        return float(np.sum((rc / sig - b) ** 2))
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    bounds = [(1e-6, 1.0)] * n
    res = minimize(objective, b.copy(), method="SLSQP", bounds=bounds,
                   constraints=constraints, options={"ftol": 1e-12, "maxiter": 2000})
    return res.x


def get_clock_phase():
    shuaitui = chr(34928) + chr(36864)
    try:
        df = pd.read_csv(CLOCK_CSV, encoding="utf-8-sig")
        col = chr(20256) + chr(32479) + chr(35937) + chr(38480)
        phase = str(df[col].iloc[-1]).strip()
        print("  " + chr(24403) + chr(21069) + chr(32654) + chr(26519) + chr(26102) + chr(38047) + chr(35937) + chr(38480) + ": " + phase)
        return phase
    except Exception as e:
        print("[" + chr(35686) + chr(21578) + "] " + chr(35835) + chr(21462) + chr(32654) + chr(26519) + chr(26102) + chr(38047) + chr(22833) + chr(36133) + ": " + str(e))
        return shuaitui


def print_results(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, vol):
    print()
    print("=" * 74)
    hdr = "  {:<10} {:>10} {:>10} {:>9} {:>9} {:>10}"
    c1 = chr(36164) + chr(20135)
    c2 = chr(39118) + chr(38505) + chr(24179) + chr(20215) + chr(26435) + chr(37325)
    c3 = chr(39118) + chr(38505) + chr(39044) + chr(31639) + chr(26435) + chr(37325)
    c4 = "RP" + chr(36129) + chr(29486) + "%"
    c5 = "RB" + chr(36129) + chr(29486) + "%"
    c6 = chr(24180) + chr(21270) + chr(27874) + chr(21160) + chr(29575)
    print(hdr.format(c1, c2, c3, c4, c5, c6))
    print("-" * 74)
    fmt = "  {:<10} {:>9.2f}%  {:>9.2f}%  {:>8.2f}%  {:>8.2f}%  {:>9.2f}%"
    for i, name in enumerate(asset_names):
        print(fmt.format(name, w_rp[i]*100, w_rb[i]*100,
                         rc_rp[i]/sig_rp*100, rc_rb[i]/sig_rb*100, vol[i]*100))
    print("-" * 74)
    total_lbl = chr(21512) + chr(35745)
    print("  {:<10} {:>9.2f}%  {:>9.2f}%  {:>8}%  {:>8}%".format(
        total_lbl, sum(w_rp)*100, sum(w_rb)*100, "100.00", "100.00"))
    vol_lbl = chr(32452) + chr(21512) + chr(24180) + chr(21270) + chr(27874) + chr(21160) + chr(29575)
    rp_lbl = chr(39118) + chr(38505) + chr(24179) + chr(20215)
    rb_lbl = chr(39118) + chr(38505) + chr(39044) + chr(31639)
    print("  " + vol_lbl + " — " + rp_lbl + ": {:.2f}%   ".format(sig_rp*100) + rb_lbl + ": {:.2f}%".format(sig_rb*100))
    print("=" * 74)


def save_csv(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, vol):
    rows = []
    for i, name in enumerate(asset_names):
        rows.append({
            chr(36164)+chr(20135):         name,
            chr(39118)+chr(38505)+chr(24179)+chr(20215)+chr(26435)+chr(37325)+"%": round(w_rp[i]*100, 4),
            chr(39118)+chr(38505)+chr(39044)+chr(31639)+chr(26435)+chr(37325)+"%": round(w_rb[i]*100, 4),
            chr(39118)+chr(38505)+chr(24179)+chr(20215)+chr(36129)+chr(29486)+"%": round(rc_rp[i]/sig_rp*100, 4),
            chr(39118)+chr(38505)+chr(39044)+chr(31639)+chr(36129)+chr(29486)+"%": round(rc_rb[i]/sig_rb*100, 4),
            chr(24180)+chr(21270)+chr(27874)+chr(21160)+chr(29575)+"%":   round(vol[i]*100, 4),
        })
    pd.DataFrame(rows).to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    print("  " + chr(24050)+chr(20445)+chr(23384)+": " + CSV_OUT)


def plot_results(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, phase):
    os.makedirs(RP_CHART_DIR, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#F5F5F0")
    x = np.arange(len(asset_names))
    width = 0.35

    ax = axes[0]
    ax.set_facecolor("#F5F5F0")
    bars1 = ax.bar(x - width/2, [w*100 for w in w_rp], width,
                   label=chr(39118)+chr(38505)+chr(24179)+chr(20215), color=COLORS["navy"], alpha=0.85)
    bars2 = ax.bar(x + width/2, [w*100 for w in w_rb], width,
                   label=chr(39118)+chr(38505)+chr(39044)+chr(31639)+"("+phase+")", color=COLORS["gold"], alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(asset_names, fontsize=10)
    ax.set_ylabel(chr(26435)+chr(37325)+" (%)", fontsize=11)
    ax.set_title(chr(36164)+chr(20135)+chr(26435)+chr(37325)+chr(23545)+chr(27604), fontsize=13, fontweight="bold", color=COLORS["navy"])
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    for bar in bars1:
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                "{:.1f}%".format(bar.get_height()), ha="center", va="bottom", fontsize=8, color=COLORS["navy"])
    for bar in bars2:
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                "{:.1f}%".format(bar.get_height()), ha="center", va="bottom", fontsize=8, color=COLORS["gold"])

    ax2 = axes[1]
    ax2.set_facecolor("#F5F5F0")
    rc_rp_pct = [rc/sig_rp*100 for rc in rc_rp]
    rc_rb_pct = [rc/sig_rb*100 for rc in rc_rb]
    bars3 = ax2.bar(x - width/2, rc_rp_pct, width,
                    label=chr(39118)+chr(38505)+chr(24179)+chr(20215), color=COLORS["steel"], alpha=0.85)
    bars4 = ax2.bar(x + width/2, rc_rb_pct, width,
                    label=chr(39118)+chr(38505)+chr(39044)+chr(31639)+"("+phase+")", color=COLORS["teal"], alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels(asset_names, fontsize=10)
    ax2.set_ylabel(chr(39118)+chr(38505)+chr(36129)+chr(29486)+" (%)", fontsize=11)
    ax2.set_title(chr(39118)+chr(38505)+chr(36129)+chr(29486)+chr(23545)+chr(27604), fontsize=13, fontweight="bold", color=COLORS["navy"])
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", alpha=0.3)
    for bar in bars3:
        ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                 "{:.1f}%".format(bar.get_height()), ha="center", va="bottom", fontsize=8, color=COLORS["steel"])
    for bar in bars4:
        ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                 "{:.1f}%".format(bar.get_height()), ha="center", va="bottom", fontsize=8, color=COLORS["teal"])

    title = chr(39118)+chr(38505)+chr(24179)+chr(20215)+" vs "+chr(39118)+chr(38505)+chr(39044)+chr(31639)+chr(65288)+phase+chr(35937)+chr(38480)+chr(65289)
    plt.suptitle(title, fontsize=15, fontweight="bold", color=COLORS["navy"], y=1.01)
    plt.tight_layout()
    out_path = os.path.join(RP_CHART_DIR, "risk_parity.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("  " + chr(24050)+chr(20445)+chr(23384)+chr(22270)+chr(34920)+": " + out_path)


def main():
    print("")
    print("[" + chr(39118)+chr(38505)+chr(24179)+chr(20215)+" + "+chr(39118)+chr(38505)+chr(39044)+chr(31639)+"] " + chr(24320)+chr(22987)+chr(36816)+chr(34892))
    print("  " + chr(36816)+chr(34892)+chr(26102)+chr(38388)+": " + datetime.today().strftime("%Y-%m-%d %H:%M:%S"))

    print("")
    print("[1/4] " + chr(33719)+chr(21462)+chr(34892)+chr(24773)+chr(25968)+chr(25454)+"...")
    prices = fetch_data()
    if prices is None:
        print("[" + chr(38169)+chr(35823)+"] " + chr(25968)+chr(25454)+chr(33719)+chr(21462)+chr(22833)+chr(36133)+chr(65292)+chr(36864)+chr(20986))
        sys.exit(1)

    print("")
    print("[2/4] " + chr(35745)+chr(31639)+chr(21327)+chr(26041)+chr(24046)+"...")
    cov, log_ret, vol = calc_cov(prices)
    asset_keys  = list(ASSETS.keys())
    asset_names = [ASSETS[k]["name"] for k in asset_keys]
    print("  " + chr(21327)+chr(26041)+chr(24046)+chr(32500)+chr(24230)+": " + str(cov.shape))

    print("")
    print("[3/4] " + chr(27714)+chr(35299)+chr(20248)+chr(21270)+chr(26435)+chr(37325)+"...")
    w_rp = solve_risk_parity(cov)
    rc_rp, sig_rp = risk_contributions(w_rp, cov)
    print("  " + chr(39118)+chr(38505)+chr(24179)+chr(20215)+chr(27714)+chr(35299)+chr(23436)+chr(25104)+chr(65292)+chr(32452)+chr(21512)+chr(27874)+chr(21160)+chr(29575)+": {:.2f}%".format(sig_rp*100))

    phase      = get_clock_phase()
    budget_raw = BUDGET_MAP.get(phase, BUDGET_MAP[chr(34928)+chr(36864)])
    budget     = [budget_raw[k] for k in asset_keys]
    w_rb = solve_risk_budget(cov, budget)
    rc_rb, sig_rb = risk_contributions(w_rb, cov)
    print("  " + chr(39118)+chr(38505)+chr(39044)+chr(31639)+chr(27714)+chr(35299)+chr(23436)+chr(25104)+chr(65292)+chr(32452)+chr(21512)+chr(27874)+chr(21160)+chr(29575)+": {:.2f}%".format(sig_rb*100))
    bdesc = ", ".join(asset_names[i]+"="+str(int(budget[i]*100))+"%" for i in range(len(asset_keys)))
    print("  " + chr(39118)+chr(38505)+chr(39044)+chr(31639)+chr(30446)+chr(26631)+chr(65288)+phase+chr(65289)+": " + bdesc)

    print("")
    print("[4/4] " + chr(36755)+chr(20986)+chr(32467)+chr(26524)+"...")
    print_results(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, vol)
    save_csv(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, vol)
    plot_results(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, phase)

    print("")
    print("[" + chr(23436)+chr(25104)+"]")


if __name__ == "__main__":
    main()
