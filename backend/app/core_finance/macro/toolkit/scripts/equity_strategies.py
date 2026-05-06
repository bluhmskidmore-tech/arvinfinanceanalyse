from __future__ import annotations

import numpy as np
import pandas as pd
from backend.app.core_finance.macro.equity_strategies import (
    generate_random_prices,
    mean_reversion_momentum_strategy,
    moving_average_strategy,
    multi_factor_selection,
)


def main() -> None:
    prices = generate_random_prices(num_stocks=4, num_days=180, seed=20260506)
    ma_portfolio = moving_average_strategy(prices)
    mr_portfolio = mean_reversion_momentum_strategy(prices)

    financials = _sample_financials()
    selected = multi_factor_selection(
        financials,
        top_pct=0.2,
        industries_focus=["technology", "ai", "consumer"],
    )

    print(f"moving_average_final_value={ma_portfolio.iloc[-1]:.6f}")
    print(f"mean_reversion_momentum_final_value={mr_portfolio.iloc[-1]:.6f}")
    print(f"multi_factor_selected_count={len(selected)}")
    if not selected.empty:
        print(f"multi_factor_top_symbol={selected.index[0]}")


def _sample_financials() -> pd.DataFrame:
    rng = np.random.default_rng(20260506)
    symbols = [f"Stock{i:03d}" for i in range(40)]
    return pd.DataFrame(
        {
            "pe": rng.uniform(5, 50, size=len(symbols)),
            "pb": rng.uniform(0.5, 5, size=len(symbols)),
            "ps": rng.uniform(0.5, 10, size=len(symbols)),
            "roe": rng.uniform(0, 0.3, size=len(symbols)),
            "gross_margin": rng.uniform(0, 0.5, size=len(symbols)),
            "three_month_return": rng.uniform(-0.2, 0.5, size=len(symbols)),
            "twelve_month_return": rng.uniform(-0.5, 1.0, size=len(symbols)),
            "volatility": rng.uniform(0.1, 0.5, size=len(symbols)),
            "dividend_yield": rng.uniform(0, 0.1, size=len(symbols)),
            "industry": rng.choice(["technology", "ai", "consumer", "financial", "other"], size=len(symbols)),
        },
        index=symbols,
    )


if __name__ == "__main__":
    main()
