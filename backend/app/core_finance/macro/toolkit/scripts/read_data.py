import pandas as pd
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

# Read GARCH results
garch = pd.read_csv(OUTPUT_DIR / "garch_results.csv", encoding="utf-8-sig")
print("=== GARCH ===")
print(garch[['资产', '当前日波动率%', '年化波动率%', '波动率状态', '操作建议']].to_string())

# Read CTA results
cta = pd.read_csv(OUTPUT_DIR / "cta_results.csv", encoding="utf-8-sig")
print("\n=== CTA ===")
print(cta.tail(5).to_string())

# Read regime results
regime = pd.read_csv(OUTPUT_DIR / "regime_results.csv", encoding="utf-8-sig")
print("\n=== Regime ===")
print(regime.tail(5).to_string())

# Read crisis score
crisis = pd.read_csv(OUTPUT_DIR / "crisis_score_latest.csv", encoding="utf-8-sig")
print("\n=== Crisis ===")
print(crisis.to_string())
