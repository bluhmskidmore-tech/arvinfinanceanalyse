"""Boundary tests for the H/A/T suffix heuristic in ``infer_invest_type``.

Caliber rule ``hat_mapping`` (canonical callable
``backend.app.core_finance.config.classification_rules.infer_invest_type``).

Background
----------
The last-character heuristic used to fire for *any* upper-cased text ending in
``A`` / ``T`` / ``H`` and ran *before* the explicit accounting-label substring
rules. That made plain English words classifiable (``CHINA`` -> ``A``,
``REIT`` -> ``T``) and let the weakest rule outrank the strongest one.

The heuristic is now restricted to coded forms (the character in front of the
tag must be a separator or a non-ASCII/CJK character) and demoted below the
substring rules.

Production value domain
-----------------------
``_PRODUCTION_DOMAIN_EXPECTED`` is the observed distinct value domain of every
column that reaches ``infer_invest_type`` (``asset_class``,
``account_category``, ``product_type``, ``account_type``, ``invest_type_std``,
``invest_type_raw``, ``portfolio_name`` / ``portfolio``) across
``zqtz_bond_daily_snapshot``, ``tyw_interbank_daily_snapshot``,
``fact_formal_zqtz_balance_daily``, ``fact_formal_tyw_balance_daily``,
``fact_formal_pnl_fi``, ``fact_formal_bond_analytics_daily``,
``fact_nonstd_pnl_bridge``, ``position_snapshot`` and the ``phase1_*`` preview
tables. Expected values are the pre-fix outputs, except for the three portfolio
codes covered by ``_PORTFOLIO_CODE_DELTAS``.
"""

from __future__ import annotations

import pytest

from backend.app.core_finance.config.classification_rules import (
    _match_invest_type_by_code_suffix,
    infer_invest_type,
)

# --- negative samples: English words must not be classified by the suffix rule ---


@pytest.mark.parametrize("word", ["CHINA", "REIT", "MATH", "DELTA", "ASSET", "BETA", "SOUTH"])
def test_plain_english_words_are_not_classified(word: str) -> None:
    assert _match_invest_type_by_code_suffix(word.upper()) is None
    assert infer_invest_type(None, word, None) is None
    assert infer_invest_type(word, None, None) is None
    assert infer_invest_type(None, None, word) is None


@pytest.mark.parametrize("word", ["china", "Reit", "mAtH"])
def test_plain_english_words_are_not_classified_case_insensitively(word: str) -> None:
    assert infer_invest_type(None, word, None) is None


def test_digit_boundary_is_not_treated_as_a_code_separator() -> None:
    """Conservative boundary: only separators / non-ASCII qualify, not digits."""
    assert _match_invest_type_by_code_suffix("PORT1A") is None
    assert infer_invest_type(None, "PORT1A", None) is None


# --- positive regression: legitimate coded forms keep their pre-fix behavior ---


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("组合A", "A"),
        ("交易T", "T"),
        ("持有至到期H", "H"),
        ("账户-A", "A"),
        ("账户_T", "T"),
        ("组合 H", "H"),
        ("-A", "A"),
        ("_T", "T"),
        ("asset_T", "T"),
        ("账户/A", "A"),
        ("A", "A"),
        ("T", "T"),
        ("H", "H"),
        ("  h  ", "H"),
    ],
)
def test_coded_forms_still_classify(value: str, expected: str) -> None:
    assert infer_invest_type(None, value, None) == expected
    assert infer_invest_type(value, None, None) == expected


def test_bare_token_still_wins_over_asset_class_substring() -> None:
    """``invest_type_std`` is already canonical; it outranks a label re-derivation."""
    assert infer_invest_type(None, "A", "交易性资产") == "A"
    assert infer_invest_type(None, "T", "持有至到期类资产") == "T"


def test_asset_type_suffix_still_wins_over_portfolio_suffix() -> None:
    assert infer_invest_type("portfolio-H", "asset_T", None) == "T"


# --- rule ordering: explicit substring rules outrank the suffix heuristic ---


@pytest.mark.parametrize(
    ("value", "expected_substring_result", "suffix_only_result"),
    [
        ("可供出售组合T", "A", "T"),
        ("持有至到期-A", "H", "A"),
        ("交易性资产_H", "T", "H"),
        ("HTM_T", "H", "T"),
        ("FVOCI-T", "A", "T"),
        ("摊余成本 A", "H", "A"),
    ],
)
def test_substring_rules_run_before_suffix_heuristic(
    value: str,
    expected_substring_result: str,
    suffix_only_result: str,
) -> None:
    assert _match_invest_type_by_code_suffix(value.upper()) == suffix_only_result
    assert expected_substring_result != suffix_only_result
    assert infer_invest_type(None, value, None) == expected_substring_result


def test_asset_class_substring_outranks_portfolio_suffix() -> None:
    """A real accounting label beats a coded portfolio tag from a weaker slot."""
    assert infer_invest_type("组合T", None, "可供出售类资产") == "A"


# --- production value-domain regression anchors ---

# value -> expected result, identical to the pre-fix output.
_PRODUCTION_DOMAIN_EXPECTED: dict[str, str | None] = {
    # zqtz_bond_daily_snapshot / fact_formal_zqtz_balance_daily .asset_class
    "持有至到期类资产": "H",
    "可供出售类资产": "A",
    "交易性资产": "T",
    "发行类债劵": "H",
    "应收投资款项": "H",
    # .account_category
    "银行账户": None,
    "交易账户": "T",
    # tyw_interbank_daily_snapshot / fact_formal_tyw_balance_daily .product_type
    "卖出回购票据": "H",
    "同业存放": "H",
    "存放同业": "H",
    "拆放同业": "H",
    "买入返售证券": "H",
    "卖出回购证券": "H",
    "同业拆入": "H",
    # .account_type
    "投融资类": None,
    "清算类": None,
    # invest_type_std / invest_type_raw
    "H": "H",
    "A": "A",
    "T": "T",
    # fact_formal_pnl_fi.asset_class
    "企业债": None,
    "资产支持证券": None,
    "中期票据": None,
    "大额存单": None,
    "地方政府债券": None,
    "政策性金融债": None,
    "商业银行债": None,
    "国债": None,
    "非银行金融债": None,
    "次级债": None,
    "短期融资券": None,
    "铁道债": None,
    # phase1_nonstd_pnl_preview_rows.product_type
    "证券投资基金": None,
    "投资券商资管计划以及受益权（结构化融资）": None,
    "投资券商资管计划以及受益权（非结构化融资）": None,
    "投资信托计划及受益权（结构化融资）": None,
    "投资信托计划及受益权（非结构化融资）": None,
    "投资其它资管计划（结构化融资）": None,
    "投资其它资管计划（非结构化融资）": None,
    "投资基金资管计划（非结构化融资）": None,
    # portfolio_name / portfolio codes that were already unclassified
    "FI19": None,
    "RI19": None,
    "FICD": None,
    "FIIS": None,
    "FIAB": None,
    "FITF": None,
    "D000": None,
    "__NULL__": None,
}

# The only production values whose classification changes: ASCII portfolio codes
# that the old suffix heuristic mis-hit. No live call path feeds a portfolio
# code into ``infer_invest_type`` today, so no persisted fact row is affected.
_PORTFOLIO_CODE_DELTAS: dict[str, tuple[str, None]] = {
    "FIOA": ("A", None),
    "RIOA": ("A", None),
    "PORT": ("T", None),
}


@pytest.mark.parametrize(
    ("value", "expected"),
    sorted(_PRODUCTION_DOMAIN_EXPECTED.items()),
)
def test_production_domain_classification_is_unchanged(value: str, expected: str | None) -> None:
    assert infer_invest_type(None, value, None) == expected
    assert infer_invest_type(value, None, None) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    sorted(_PRODUCTION_DOMAIN_EXPECTED.items()),
)
def test_production_domain_asset_class_slot_is_unchanged(value: str, expected: str | None) -> None:
    # The ``asset_class`` slot never had a bare-token or suffix branch, so bare
    # ``A`` / ``H`` stay unclassified there exactly as before the change.
    expected_asset_class_slot = None if value in ("A", "H") else expected
    assert infer_invest_type(None, None, value) == expected_asset_class_slot


@pytest.mark.parametrize(("code", "before_after"), sorted(_PORTFOLIO_CODE_DELTAS.items()))
def test_production_portfolio_codes_are_no_longer_mis_hit(
    code: str,
    before_after: tuple[str, None],
) -> None:
    _before, after = before_after
    assert infer_invest_type(None, code, None) is after
    assert infer_invest_type(code, None, None) is after
    assert infer_invest_type(None, None, code) is after
