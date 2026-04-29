from __future__ import annotations

from decimal import Decimal

import pytest

from tests.helpers import load_module


class _ChoiceResult:
    Codes = [
        "EMM00166492",
        "EMM00166494",
        "EMM00166495",
        "EMM00166496",
        "EMM00166498",
        "EMM00166502",
        "EMM00166504",
    ]
    Dates = ["2026-04-10"]
    Data = {
        "EMM00166492": [[Decimal("1.10")]],
        "EMM00166494": [[Decimal("1.20")]],
        "EMM00166495": [[Decimal("1.30")]],
        "EMM00166496": [[Decimal("1.40")]],
        "EMM00166498": [[Decimal("1.50")]],
        "EMM00166502": [[Decimal("1.80")]],
        "EMM00166504": [[Decimal("2.10")]],
    }


class _TreasuryChoiceResult:
    Codes = [
        "EMM00166455",
        "EMM00166456",
        "EMM00166458",
        "EMM00588704",
        "EMM00166460",
        "EMM00166462",
        "EMM00166464",
        "EMM00166466",
        "EMM00166468",
        "EMM00166469",
    ]
    Dates = ["2026-04-10"]
    Data = {
        "EMM00166455": [[Decimal("1.01")]],
        "EMM00166456": [[Decimal("1.02")]],
        "EMM00166458": [[Decimal("1.10")]],
        "EMM00588704": [[Decimal("1.20")]],
        "EMM00166460": [[Decimal("1.30")]],
        "EMM00166462": [[Decimal("1.40")]],
        "EMM00166464": [[Decimal("1.50")]],
        "EMM00166466": [[Decimal("1.60")]],
        "EMM00166468": [[Decimal("1.80")]],
        "EMM00166469": [[Decimal("1.90")]],
    }


class _AaaCreditChoiceResult:
    Codes = [
        "EMM00166654",
        "EMM00166655",
        "EMM00166656",
        "EMM00166657",
        "EMM00166659",
        "EMM00168470",
        "EMM00166661",
    ]
    Dates = ["2026-04-10"]
    Data = {
        "EMM00166654": [[Decimal("1.20")]],
        "EMM00166655": [[Decimal("1.30")]],
        "EMM00166656": [[Decimal("1.40")]],
        "EMM00166657": [[Decimal("1.50")]],
        "EMM00166659": [[Decimal("1.70")]],
        "EMM00168470": [[Decimal("1.80")]],
        "EMM00166661": [[Decimal("2.00")]],
    }


class _CreditChoiceResult:
    Dates = ["2026-04-10"]

    def __init__(self, code_map):
        tenor_values = {
            "6M": Decimal("1.00"),
            "1Y": Decimal("1.10"),
            "2Y": Decimal("1.20"),
            "3Y": Decimal("1.30"),
            "4Y": Decimal("1.40"),
            "5Y": Decimal("1.50"),
            "6Y": Decimal("1.60"),
            "7Y": Decimal("1.70"),
            "8Y": Decimal("1.80"),
            "10Y": Decimal("2.00"),
        }
        self.Codes = list(code_map.values())
        self.Data = {
            vendor_code: [[tenor_values[tenor]]]
            for tenor, vendor_code in code_map.items()
            if tenor in tenor_values
        }


def test_treasury_choice_fallback_returns_normalized_snapshot(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(module.VendorAdapter, "_fetch_akshare_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _TreasuryChoiceResult())

    snapshot = module.VendorAdapter().fetch_yield_curve("treasury", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "choice"
    assert tenor_map["3M"] == Decimal("1.01")
    assert tenor_map["30Y"] == Decimal("1.90")


def test_treasury_akshare_primary_returns_normalized_snapshot(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *args, **kwargs: module._snapshot_from_points(
            curve_type="treasury",
            trade_date="2026-04-10",
            vendor_name="akshare",
            points=[
                module.YieldCurvePoint("3M", Decimal("1.01")),
                module.YieldCurvePoint("6M", Decimal("1.02")),
                module.YieldCurvePoint("1Y", Decimal("1.10")),
                module.YieldCurvePoint("2Y", Decimal("1.20")),
                module.YieldCurvePoint("3Y", Decimal("1.30")),
                module.YieldCurvePoint("5Y", Decimal("1.40")),
                module.YieldCurvePoint("7Y", Decimal("1.50")),
                module.YieldCurvePoint("10Y", Decimal("1.60")),
                module.YieldCurvePoint("20Y", Decimal("1.80")),
                module.YieldCurvePoint("30Y", Decimal("1.90")),
            ],
        ),
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("treasury", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "akshare"
    assert tenor_map["3M"] == Decimal("1.01")
    assert tenor_map["30Y"] == Decimal("1.90")


def test_cdb_choice_fallback_synthesizes_30y_point(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(module.VendorAdapter, "_fetch_akshare_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _ChoiceResult())

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "choice"
    assert tenor_map["20Y"] == Decimal("2.10")
    assert tenor_map["30Y"] == Decimal("2.40")


def test_cdb_akshare_primary_synthesizes_30y_point(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [
            {
                "曲线名称": "中债政策性金融债收益率曲线(国开行)",
                "日期": "2026-04-10",
                "6月": Decimal("1.10"),
                "1年": Decimal("1.20"),
                "2年": Decimal("1.30"),
                "3年": Decimal("1.40"),
                "5年": Decimal("1.50"),
                "10年": Decimal("1.80"),
                "20年": Decimal("2.10"),
            }
        ],
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "akshare"
    assert tenor_map["20Y"] == Decimal("2.10")
    assert tenor_map["30Y"] == Decimal("2.40")


def test_partial_choice_curve_falls_back_to_gkh(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _Response:
        status_code = 200

        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    html = """
    <html>
      <body>
        <table id="conter">
          <tr>
            <th>曲线名称</th><th>关键期限(年)</th><th>查询日收益率(%)</th>
            <th>5日均值收益率(%)</th><th>10日均值收益率(%)</th>
            <th>15日均值收益率(%)</th><th>20日均值收益率(%)</th><th>上一年日均值收益率(%)</th>
          </tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>1</td><td>1.42</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>3</td><td>1.58</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>5</td><td>1.68</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>7</td><td>1.81</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>10</td><td>1.91</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
        </table>
      </body>
    </html>
    """

    class _PartialChoiceResult:
        Codes = ["EMM00166494"]
        Dates = ["2026-04-10"]
        Data = {"EMM00166494": [[Decimal("1.20")]]}

    monkeypatch.setattr(module.VendorAdapter, "_fetch_akshare_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _PartialChoiceResult())
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: _Response(html))

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    assert snapshot.vendor_name == "chinabond_gkh"


def test_cdb_gkh_fallback_returns_normalized_snapshot(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _Response:
        status_code = 200

        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    html = """
    <html>
      <body>
        <table id="conter">
          <tr>
            <th>曲线名称</th><th>关键期限(年)</th><th>查询日收益率(%)</th>
            <th>5日均值收益率(%)</th><th>10日均值收益率(%)</th>
            <th>15日均值收益率(%)</th><th>20日均值收益率(%)</th><th>上一年日均值收益率(%)</th>
          </tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>1</td><td>1.42</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>3</td><td>1.58</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>5</td><td>1.68</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>7</td><td>1.81</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>10</td><td>1.91</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
        </table>
      </body>
    </html>
    """

    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [{"曲线名称": "中债国债收益率曲线", "日期": "2026-04-10", "1年": Decimal("1.10")}],
    )

    class _ChoiceFailure:
        def edb(self, *args, **kwargs):
            raise RuntimeError("choice unavailable")

    monkeypatch.setattr(module, "ChoiceClient", lambda: _ChoiceFailure())
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: _Response(html))

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "chinabond_gkh"
    assert tenor_map["1Y"] == Decimal("1.42")
    assert tenor_map["2Y"] == Decimal("1.50")
    assert tenor_map["20Y"] > tenor_map["10Y"]
    assert tenor_map["30Y"] > tenor_map["20Y"]


def test_cdb_prefers_choice_before_gkh_when_akshare_has_no_match(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [{"曲线名称": "中债国债收益率曲线", "日期": "2026-04-10", "1年": Decimal("1.10")}],
    )
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _ChoiceResult())
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("gkh should not be called")),
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    assert snapshot.vendor_name == "choice"


def test_aaa_credit_prefers_choice_primary(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _AaaCreditChoiceResult())
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("akshare should not be called when choice succeeds")),
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("aaa_credit", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "choice"
    assert tenor_map["2Y"] == Decimal("1.40")
    assert tenor_map["7Y"] > tenor_map["6Y"]


@pytest.mark.parametrize("curve_type", ["aa_plus_credit", "aa_credit"])
def test_choice_only_credit_prefers_choice_primary(monkeypatch, curve_type):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(
        module.ChoiceClient,
        "edb",
        lambda *args, **kwargs: _CreditChoiceResult(module.CHOICE_CURVE_CODES[curve_type]),
    )
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("akshare should not be called for Choice-only credit curves")),
    )

    snapshot = module.VendorAdapter().fetch_yield_curve(curve_type, "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "choice"
    assert snapshot.curve_type == curve_type
    assert tenor_map["3Y"] == Decimal("1.30")
    assert tenor_map["7Y"] == Decimal("1.70")


@pytest.mark.parametrize("curve_type", ["aa_plus_credit", "aa_credit"])
def test_choice_only_credit_fails_closed_without_akshare_substitution(monkeypatch, curve_type):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _ChoiceFailure:
        def edb(self, *args, **kwargs):
            raise RuntimeError("choice unavailable")

    monkeypatch.setattr(module, "ChoiceClient", lambda: _ChoiceFailure())
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("akshare should not be called for Choice-only credit curves")),
    )

    with pytest.raises(RuntimeError, match="Choice failed: choice unavailable"):
        module.VendorAdapter().fetch_yield_curve(curve_type, "2026-04-10")


def test_aaa_credit_fails_closed_when_choice_unavailable_and_akshare_has_no_exact_family(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _ChoiceFailure:
        def edb(self, *args, **kwargs):
            raise RuntimeError("choice unavailable")

    monkeypatch.setattr(module, "ChoiceClient", lambda: _ChoiceFailure())
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [
            {
                "曲线名称": "中债中短期票据收益率曲线(AAA)",
                "日期": "2026-04-10",
                "1年": Decimal("1.20"),
                "3年": Decimal("1.40"),
                "5年": Decimal("1.60"),
                "10年": Decimal("1.90"),
            }
        ],
    )

    with pytest.raises(RuntimeError):
        module.VendorAdapter().fetch_yield_curve("aaa_credit", "2026-04-10")


def test_aaa_credit_uses_exact_family_akshare_fallback(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _ChoiceFailure:
        def edb(self, *args, **kwargs):
            raise RuntimeError("choice unavailable")

    monkeypatch.setattr(module, "ChoiceClient", lambda: _ChoiceFailure())
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [
            {
                "曲线名称": module.AKSHARE_CURVE_NAME_BY_TYPE["aaa_credit"],
                "日期": "2026-04-10",
                "1年": Decimal("1.20"),
                "3年": Decimal("1.40"),
                "5年": Decimal("1.60"),
                "10年": Decimal("1.90"),
            }
        ],
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("aaa_credit", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "akshare"
    assert tenor_map["2Y"] == Decimal("1.30")
    assert tenor_map["7Y"] > tenor_map["5Y"]


def test_cdb_uses_gkh_after_invalid_akshare_and_failed_choice(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _Response:
        status_code = 200

        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    html = """
    <html>
      <body>
        <table id="conter">
          <tr>
            <th>曲线名称</th><th>关键期限(年)</th><th>查询日收益率(%)</th>
            <th>5日均值收益率(%)</th><th>10日均值收益率(%)</th>
            <th>15日均值收益率(%)</th><th>20日均值收益率(%)</th><th>上一年日均值收益率(%)</th>
          </tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>1</td><td>1.42</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>3</td><td>1.58</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>5</td><td>1.68</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>7</td><td>1.81</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
          <tr><td>中债国开债收益率曲线（到期）</td><td>10</td><td>1.91</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
        </table>
      </body>
    </html>
    """

    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [
            {
                "曲线名称": module.AKSHARE_CURVE_NAME_BY_TYPE["cdb"],
                "日期": "2026-04-10",
                "1年": Decimal("1.10"),
            }
        ],
    )

    class _ChoiceFailure:
        def edb(self, *args, **kwargs):
            raise RuntimeError("choice unavailable")

    monkeypatch.setattr(module, "ChoiceClient", lambda: _ChoiceFailure())
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: _Response(html))

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    assert snapshot.vendor_name == "chinabond_gkh"
