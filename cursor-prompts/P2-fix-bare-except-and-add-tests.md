# P2 修复：bare except + 核心计算单元测试

## 任务 1：修复 bare except（`evening_report.py`）

**文件**：`backend/app/core_finance/macro/toolkit/scripts/evening_report.py`

该文件有 6 处 `except:` 裸异常捕获（第 74、123、158、174、240、334 行），
会吞掉 `SystemExit`、`KeyboardInterrupt` 等系统异常，导致夜间报告失败无法感知。

**修复要求**：
逐一检查每处 `except:` 的上下文，替换为合适的具体异常类型：

- JSON 解析失败（第 74 行附近）：改为 `except (json.JSONDecodeError, ValueError, TypeError):`
- 网络/IO 操作失败：改为 `except (OSError, IOError, ConnectionError, TimeoutError):`
- 数据处理失败：改为 `except (KeyError, AttributeError, ValueError, TypeError):`
- 通用兜底（如果确实需要）：改为 `except Exception:` 并加 `logger.exception(...)` 记录完整堆栈

**规则**：
- 每处替换后，确保 `except` 块内有日志记录（至少 `logger.warning` 或 `logger.exception`）
- 不要把所有地方都改成 `except Exception:`，要根据上下文选择最窄的异常类型
- 不改业务逻辑，只改异常捕获范围

---

## 任务 2：为核心计算添加单元测试

**目标文件**：
- `backend/app/core_finance/bond_four_effects.py`
- `backend/app/core_finance/bond_duration.py`
- `backend/app/core_finance/rate_units.py`

**测试文件位置**：
先检查 `backend/tests/` 目录结构，在对应位置创建测试文件：
- `backend/tests/core_finance/test_bond_four_effects.py`
- `backend/tests/core_finance/test_bond_duration.py`
- `backend/tests/core_finance/test_rate_units.py`

如果 `tests/core_finance/` 不存在，创建并加 `__init__.py`。

### `test_rate_units.py` 测试用例

```python
from backend.app.core_finance.rate_units import normalize_annual_rate_to_decimal

def test_decimal_input_unchanged():
    """小数格式输入不应被除以100"""
    assert normalize_annual_rate_to_decimal(0.0255) == pytest.approx(0.0255)

def test_small_decimal_unchanged():
    """0.5% 存为 0.005，不应被误判为百分数"""
    assert normalize_annual_rate_to_decimal(0.005) == pytest.approx(0.005)

def test_large_percent_corrected():
    """明显的百分数（>2）应被除以100"""
    assert normalize_annual_rate_to_decimal(2.55) == pytest.approx(0.0255)

def test_boundary_value_2():
    """边界值 2.0：视为百分数（2%），返回 0.02"""
    result = normalize_annual_rate_to_decimal(2.0)
    assert result == pytest.approx(0.02)

def test_dirty_data_above_20():
    """超过 20% 的值视为脏数据，返回 None"""
    assert normalize_annual_rate_to_decimal(25.0) is None

def test_negative_returns_none():
    assert normalize_annual_rate_to_decimal(-0.01) is None

def test_none_returns_none():
    assert normalize_annual_rate_to_decimal(None) is None

def test_string_input():
    assert normalize_annual_rate_to_decimal("0.0255") == pytest.approx(0.0255)
```

### `test_bond_four_effects.py` 测试用例

```python
from decimal import Decimal
from datetime import date
from backend.app.core_finance.bond_four_effects import compute_bond_four_effects

def _make_bond(**kwargs):
    base = {
        "bond_code": "TEST001",
        "coupon_rate": 0.03,          # 3%，小数格式
        "face_value": 1_000_000,
        "market_value_start": 1_000_000,
        "market_value_end": 1_005_000,
        "maturity_date": date(2027, 12, 31),
        "yield_to_maturity": 0.03,
        "asset_class": "TPL",
    }
    base.update(kwargs)
    return base

def test_basic_four_effects():
    bond = _make_bond()
    result = compute_bond_four_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0.001"),
        spread_change=Decimal("0"),
        report_date=date(2024, 1, 31),
    )
    assert result["income_return"] > Decimal("0")
    assert "diagnostics" in result
    assert isinstance(result["diagnostics"], list)

def test_missing_maturity_date():
    """到期日缺失时，mod_dur=0，treasury/spread=0，diagnostics 有标记"""
    bond = _make_bond(maturity_date=None)
    result = compute_bond_four_effects(
        bond, 30, Decimal("0.001"), Decimal("0"), date(2024, 1, 31)
    )
    assert result["mod_duration"] == Decimal("0")
    assert result["treasury_effect"] == Decimal("0")
    assert "mod_dur_fallback_zero" in result["diagnostics"]

def test_ac_class_zeroes_rate_effects():
    """AC 类资产：利率/利差/选券效应全为 0"""
    bond = _make_bond(asset_class="摊余成本")
    result = compute_bond_four_effects(
        bond, 30, Decimal("0.001"), Decimal("0.0005"), date(2024, 1, 31)
    )
    assert result["treasury_effect"] == Decimal("0")
    assert result["spread_effect"] == Decimal("0")
    assert result["selection_effect"] == Decimal("0")
    assert result["total_return"] == result["income_return"]

def test_accrued_interest_full_price():
    """有应计利息时，total_return 用全价变动"""
    bond = _make_bond(
        accrued_interest_start=5000,
        accrued_interest_end=5500,
    )
    result = compute_bond_four_effects(
        bond, 30, Decimal("0"), Decimal("0"), date(2024, 1, 31)
    )
    assert "accrued_interest_missing" not in result["diagnostics"]
    assert result["has_accrued_interest"] is True

def test_missing_accrued_interest_diagnostic():
    """缺少应计利息时，diagnostics 有标记"""
    bond = _make_bond()  # 无 accrued_interest 字段
    result = compute_bond_four_effects(
        bond, 30, Decimal("0"), Decimal("0"), date(2024, 1, 31)
    )
    assert "accrued_interest_missing" in result["diagnostics"]
```

### `test_bond_duration.py` 测试用例

```python
from decimal import Decimal
from datetime import date
from backend.app.core_finance.bond_duration import estimate_duration, infer_accounting_class

def test_estimate_duration_normal():
    """正常债券久期应在合理范围内"""
    dur = estimate_duration(
        maturity_date=date(2027, 12, 31),
        report_date=date(2024, 1, 31),
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.03"),
    )
    assert Decimal("1") < dur < Decimal("5")

def test_estimate_duration_none_maturity():
    """到期日为 None 时返回代理值（不崩溃）"""
    dur = estimate_duration(
        maturity_date=None,
        report_date=date(2024, 1, 31),
        coupon_rate=Decimal("0.03"),
    )
    assert dur >= Decimal("0")

def test_infer_accounting_class_ac():
    assert infer_accounting_class("摊余成本债权投资") == "AC"

def test_infer_accounting_class_oci():
    assert infer_accounting_class("其他债权投资OCI") == "OCI"

def test_infer_accounting_class_tpl():
    assert infer_accounting_class("交易性金融资产") == "TPL"

def test_infer_accounting_class_none():
    assert infer_accounting_class(None) == "TPL"
```

## 执行顺序

1. 先修复 `evening_report.py` 的 bare except（快，风险低）
2. 再创建测试文件（按上面的用例，可根据实际函数签名微调）
3. 运行测试确认通过：`python -m pytest backend/tests/core_finance/ -v`

## 注意

- 测试用例中的字段名（如 `accrued_interest_missing`）需与 P1 修复后的实际 diagnostics 字符串一致，
  如果 P1 还没做，先用 `"accrued_interest_fallback_to_zero"` 占位
- 如果 pytest 未安装，检查 `backend/requirements*.txt` 或 `pyproject.toml`
