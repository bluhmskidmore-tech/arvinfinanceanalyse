"""
多资产 GARCH 波动率参数估计工具
=================================
资产池: 沪深300、中证500、黄金期货、铜期货、原油期货
流程: 拉数据 → 拟合4种GARCH变体 → 样本外验证 → 输出最优参数 + 每日预测波动率
"""

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import akshare as ak
from arch import arch_model
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

# ============================================================
# 1. 数据获取
# ============================================================

def fetch_index(symbol: str, name: str) -> pd.DataFrame:
    """拉A股指数日线"""
    df = ak.stock_zh_index_daily(symbol=symbol)
    df = df[['date', 'close']].copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df.columns = [name]
    return df

def fetch_futures(symbol: str, name: str) -> pd.DataFrame:
    """拉期货主力合约日线"""
    df = ak.futures_main_sina(
        symbol=symbol,
        start_date='20150101',
        end_date=datetime.now().strftime('%Y%m%d')
    )
    df = df[['日期', '收盘价']].copy()
    df.columns = ['date', name]
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df[name] = pd.to_numeric(df[name], errors='coerce')
    return df


def load_all_assets() -> pd.DataFrame:
    """拉取全部资产价格，合并为一张表"""
    print("正在拉取数据...")

    assets = {}

    # A股指数
    print("  沪深300...", end="", flush=True)
    assets['hs300'] = fetch_index('sh000300', 'hs300')
    print("OK")

    print("  中证500...", end="", flush=True)
    assets['csi500'] = fetch_index('sh000905', 'csi500')
    print("OK")

    # 期货
    futures_map = {
        'AU0': 'gold',
        'CU0': 'copper',
        'SC0': 'crude_oil',
    }
    for code, name in futures_map.items():
        print(f"  {name}...", end="", flush=True)
        try:
            assets[name] = fetch_futures(code, name)
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")

    # 合并
    prices = pd.concat(assets.values(), axis=1, join='inner')
    prices = prices.dropna()

    # 只保留最近5年数据（足够估计，又不会太老）
    cutoff = prices.index.max() - pd.DateOffset(years=5)
    prices = prices[prices.index >= cutoff]

    print(f"\n数据范围: {prices.index[0].date()} ~ {prices.index[-1].date()}")
    print(f"交易日数: {len(prices)}")
    print(f"资产列表: {list(prices.columns)}")
    return prices


# ============================================================
# 2. GARCH 模型拟合与选择
# ============================================================

MODELS = {
    'GARCH':     dict(vol='Garch', p=1, o=0, q=1),
    'GJR-GARCH': dict(vol='Garch', p=1, o=1, q=1),
    'EGARCH':    dict(vol='EGARCH', p=1, o=1, q=1),
    'TARCH':     dict(vol='Garch', p=1, o=1, q=1),  # 同GJR，换t分布对比
}

DISTS = ['t', 'normal', 'skewt']


def fit_single_asset(returns: pd.Series, asset_name: str) -> dict:
    """
    对单个资产拟合多种 GARCH 变体，返回最优模型信息。
    returns: 百分比对数收益率序列
    """
    print(f"\n{'='*60}")
    print(f"  {asset_name}")
    print(f"{'='*60}")
    print(f"  样本量: {len(returns)}, 均值: {returns.mean():.4f}%, 标准差: {returns.std():.4f}%")
    print(f"  偏度: {returns.skew():.3f}, 峰度: {returns.kurtosis():.3f}")

    best_bic = np.inf
    best_result = None
    all_results = []

    for vol_name, vol_params in MODELS.items():
        for dist in DISTS:
            label = f"{vol_name} / {dist}"
            try:
                model = arch_model(
                    returns,
                    mean='Constant',
                    vol=vol_params['vol'],
                    p=vol_params['p'],
                    o=vol_params['o'],
                    q=vol_params['q'],
                    dist=dist
                )
                res = model.fit(disp='off', show_warning=False)

                row = {
                    'model': vol_name,
                    'dist': dist,
                    'label': label,
                    'aic': res.aic,
                    'bic': res.bic,
                    'loglik': res.loglikelihood,
                    'params': dict(res.params),
                    'result_obj': res,
                }
                all_results.append(row)

                if res.bic < best_bic:
                    best_bic = res.bic
                    best_result = row

            except Exception:
                pass

    if best_result is None:
        print("  所有模型拟合失败!")
        return None

    # 打印前5名
    ranking = sorted(all_results, key=lambda x: x['bic'])[:5]
    print(f"\n  BIC 排名 Top 5:")
    print(f"  {'模型':<25} {'AIC':>10} {'BIC':>10}")
    print(f"  {'-'*47}")
    for r in ranking:
        marker = " <-- BEST" if r['label'] == best_result['label'] else ""
        print(f"  {r['label']:<25} {r['aic']:>10.1f} {r['bic']:>10.1f}{marker}")

    # 提取关键参数
    params = best_result['params']
    print(f"\n  最优模型参数:")
    for k, v in params.items():
        print(f"    {k}: {v:.6f}")

    # 计算 alpha+beta 持久性
    alpha = params.get('alpha[1]', 0)
    beta = params.get('beta[1]', 0)
    gamma = params.get('gamma[1]', 0)
    persistence = alpha + beta + 0.5 * gamma  # GJR调整
    print(f"  持久性 (alpha+beta+0.5*gamma): {persistence:.4f}")

    return best_result


# ============================================================
# 3. 样本外验证
# ============================================================

def out_of_sample_test(returns: pd.Series, best_result: dict,
                       asset_name: str, train_ratio: float = 0.7) -> dict:
    """
    滚动窗口样本外预测，评估预测波动率与实现波动率的相关性。
    """
    split = int(len(returns) * train_ratio)
    test_returns = returns.iloc[split:]

    vol_params = None
    for name, params in MODELS.items():
        if name == best_result['model']:
            vol_params = params
            break

    dist = best_result['dist']

    print(f"\n  样本外验证 ({asset_name}):")
    print(f"  训练集: {split} 天, 测试集: {len(test_returns)} 天")

    # 滚动预测（每20天重新拟合一次以加速）
    predicted_var = []
    refit_every = 20
    cached_res = None

    for i in range(len(test_returns)):
        if i % refit_every == 0:
            data = returns.iloc[:split + i]
            try:
                m = arch_model(
                    data,
                    mean='Constant',
                    vol=vol_params['vol'],
                    p=vol_params['p'],
                    o=vol_params['o'],
                    q=vol_params['q'],
                    dist=dist
                )
                cached_res = m.fit(disp='off', show_warning=False)
            except Exception:
                pass

        if cached_res is not None:
            fcast = cached_res.forecast(horizon=1)
            predicted_var.append(fcast.variance.values[-1, 0])
        else:
            predicted_var.append(np.nan)

    # 实现波动率: 20日滚动标准差的平方
    realized_var = test_returns.rolling(20).var()

    eval_df = pd.DataFrame({
        'realized_var': realized_var.values,
        'predicted_var': predicted_var,
    }, index=test_returns.index).dropna()

    if len(eval_df) < 20:
        print("  数据不足，跳过验证")
        return {'corr': np.nan, 'mse': np.nan}

    corr = eval_df['realized_var'].corr(eval_df['predicted_var'])
    mse = ((eval_df['realized_var'] - eval_df['predicted_var']) ** 2).mean()

    print(f"  预测方差 vs 实现方差 相关性: {corr:.4f}")
    print(f"  MSE: {mse:.6f}")

    quality = "优秀" if corr > 0.7 else "可用" if corr > 0.5 else "较弱，建议换模型"
    print(f"  评价: {quality}")

    return {'corr': corr, 'mse': mse}


# ============================================================
# 4. 当前波动率预测 + 阈值判断
# ============================================================

def current_forecast(returns: pd.Series, best_result: dict,
                     asset_name: str) -> dict:
    """用全量数据拟合，预测明日波动率，并与历史分位数比较。"""
    vol_params = None
    for name, params in MODELS.items():
        if name == best_result['model']:
            vol_params = params
            break

    model = arch_model(
        returns,
        mean='Constant',
        vol=vol_params['vol'],
        p=vol_params['p'],
        o=vol_params['o'],
        q=vol_params['q'],
        dist=best_result['dist']
    )
    res = model.fit(disp='off', show_warning=False)
    try:
        fcast = res.forecast(horizon=1)
    except Exception:
        # EGARCH等模型可能不支持解析预测，用simulation
        fcast = res.forecast(horizon=1, method='simulation', simulations=1000)

    # 明日预测波动率（年化）
    daily_vol = np.sqrt(fcast.variance.values[-1, 0])
    annual_vol = daily_vol * np.sqrt(252)

    # 历史条件波动率分位数
    cond_vol = res.conditional_volatility
    pct_25 = cond_vol.quantile(0.25)
    pct_50 = cond_vol.quantile(0.50)
    pct_75 = cond_vol.quantile(0.75)
    pct_90 = cond_vol.quantile(0.90)
    current = cond_vol.iloc[-1]

    # 判断当前处于什么水平
    if current < pct_25:
        regime = "低波动"
        action = "可适当加仓"
    elif current < pct_75:
        regime = "中波动"
        action = "维持当前仓位"
    elif current < pct_90:
        regime = "高波动"
        action = "考虑降仓"
    else:
        regime = "极端波动"
        action = "必须降仓防御"

    print(f"\n  {asset_name} 当前波动率状态:")
    print(f"    明日预测日波动率: {daily_vol:.4f}% (年化 {annual_vol:.2f}%)")
    print(f"    历史分位数: 25%={pct_25:.4f} | 50%={pct_50:.4f} | 75%={pct_75:.4f} | 90%={pct_90:.4f}")
    print(f"    当前条件波动率: {current:.4f}")
    print(f"    状态判断: {regime} → {action}")

    return {
        'daily_vol': daily_vol,
        'annual_vol': annual_vol,
        'regime': regime,
        'action': action,
        'pct_25': pct_25,
        'pct_50': pct_50,
        'pct_75': pct_75,
        'pct_90': pct_90,
        'current_cond_vol': current,
    }


# ============================================================
# 5. 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  多资产 GARCH 波动率参数估计工具")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 拉数据
    prices = load_all_assets()

    # 计算对数收益率（百分比）
    log_returns = np.log(prices / prices.shift(1)).dropna() * 100

    # 存储结果
    summary_rows = []

    for asset in log_returns.columns:
        returns = log_returns[asset].dropna()

        # Step 1: 拟合
        best = fit_single_asset(returns, asset)
        if best is None:
            continue

        # Step 2: 样本外验证
        oos = out_of_sample_test(returns, best, asset)

        # Step 3: 当前预测
        forecast = current_forecast(returns, best, asset)

        # 汇总
        params = best['params']
        summary_rows.append({
            '资产': asset,
            '最优模型': f"{best['model']} / {best['dist']}",
            'omega': params.get('omega', params.get('mu', 0)),
            'alpha': params.get('alpha[1]', 0),
            'beta': params.get('beta[1]', 0),
            'gamma': params.get('gamma[1]', 0),
            '持久性': params.get('alpha[1]', 0) + params.get('beta[1]', 0) + 0.5 * params.get('gamma[1]', 0),
            'BIC': best['bic'],
            '样本外相关性': oos['corr'],
            '当前日波动率%': forecast['daily_vol'],
            '年化波动率%': forecast['annual_vol'],
            '波动率状态': forecast['regime'],
            '操作建议': forecast['action'],
        })

    # 输出汇总表
    summary = pd.DataFrame(summary_rows)

    print("\n")
    print("=" * 60)
    print("  汇总结果")
    print("=" * 60)

    # 参数表
    param_cols = ['资产', '最优模型', 'alpha', 'beta', 'gamma', '持久性', 'BIC', '样本外相关性']
    print("\n参数估计:")
    print(summary[param_cols].to_string(index=False, float_format='%.4f'))

    # 当前状态表
    state_cols = ['资产', '当前日波动率%', '年化波动率%', '波动率状态', '操作建议']
    print("\n当前波动率状态:")
    print(summary[state_cols].to_string(index=False, float_format='%.2f'))

    # 保存到CSV（与 toolkit output 目录一致）
    output_path = OUTPUT_DIR / "garch_results.csv"
    summary.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存到: {output_path}")

    # 和笔记里的默认参数对比
    print("\n" + "=" * 60)
    print("  与尽调笔记默认参数对比")
    print("=" * 60)
    print("  笔记默认: alpha=0.10, beta=0.85 (股票), alpha=0.15, beta=0.80 (商品)")
    print()
    for _, row in summary.iterrows():
        a = row['alpha']
        b = row['beta']
        g = row['gamma']
        note_a = 0.10 if row['资产'] in ('hs300', 'csi500') else 0.15
        note_b = 0.85 if row['资产'] in ('hs300', 'csi500') else 0.80
        print(f"  {row['资产']:>10}: 实际 alpha={a:.4f} beta={b:.4f} gamma={g:.4f}"
              f"  vs 笔记 alpha={note_a:.2f} beta={note_b:.2f}"
              f"  → alpha偏差{a-note_a:+.4f}, beta偏差{b-note_b:+.4f}")

    print("\n完成。")


if __name__ == '__main__':
    main()
