"""Pin macro input-contract honesty for reverse-repo and PMI aliases."""

from __future__ import annotations

from backend.app.core_finance.macro.toolkit import system_sources
from backend.app.core_finance.macro.toolkit.system_sources import _candidate_aliases


def test_m0041653_candidates_prefer_populated_legacy_before_empty_choice_target() -> None:
    ordered = list(system_sources._LEGACY_ALIAS_CANDIDATES["m0041653"])
    candidates = _candidate_aliases("M0041653")

    assert ordered[0] == "legacy.wind_market_db.reverse_repo_7d"
    assert "EMM00088132" in ordered
    assert ordered.index("legacy.wind_market_db.reverse_repo_7d") < ordered.index("EMM00088132")
    assert system_sources._normalize_alias("legacy.wind_market_db.reverse_repo_7d") in candidates
    assert "emm00088132" in candidates


def test_pmi_aliases_resolve_through_legacy_candidate_table() -> None:
    expected = {
        system_sources._normalize_alias("M0017126"),
        system_sources._normalize_alias("制造业PMI"),
        system_sources._normalize_alias("cn_pmi"),
        system_sources._normalize_alias("pmi"),
    }
    for alias in ("M0017126", "制造业PMI", "cn_pmi"):
        assert expected <= _candidate_aliases(alias)


def test_us_gov_10y_alias_prefers_populated_e1003238() -> None:
    ordered = list(system_sources._LEGACY_ALIAS_CANDIDATES["ca.us-gov-10y"])
    candidates = _candidate_aliases("CA.US_GOV_10Y")

    assert ordered[0] == "E1003238"
    assert ordered.index("E1003238") < ordered.index("EMG00001310")
    assert "e1003238" in candidates
    assert "emg00001310" in candidates
