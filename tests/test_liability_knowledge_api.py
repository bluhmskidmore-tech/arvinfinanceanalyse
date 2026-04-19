from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers import load_module


def _build_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "liability-knowledge.duckdb"))
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_mod.app)


def test_liability_business_context_reads_obsidian_note_matches(
    tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "同业负债、流动性与金融市场业务传导链.md").write_text(
        "# 同业负债、流动性与金融市场业务传导链\n\n"
        "> 把流动性环境、负债成本和配置动作串成一条主线。\n\n"
        "## 一句话结论\n\n"
        "同业负债先重定价资金成本，再传导到资产配置与交易边界。\n\n"
        "## 先问哪 8 个问题\n\n"
        "### 1. 当前流动性变化是总量变化还是结构变化\n"
        "### 2. 银行缺的是头寸还是稳定负债\n",
        encoding="utf-8",
    )
    (vault / "债券投资、久期与利率风险传导链.md").write_text(
        "# 债券投资、久期与利率风险传导链\n\n"
        "> 先问负债稳定性，再看久期与会计承受力。\n\n"
        "## 一句话结论\n\n"
        "久期不是观点问题，而是负债可持续性与报表承受力问题。\n",
        encoding="utf-8",
    )
    (vault / "金融市场条线经营分析标准提纲.md").write_text(
        "# 金融市场条线经营分析标准提纲\n\n"
        "> 把收益、风险、报表和管理层语言串成一条翻译链。\n\n"
        "## 一句话结论\n\n"
        "经营分析要把收益来源、风险结果和报表落点说成闭环。\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_OBSIDIAN_VAULT_PATH", str(vault))

    client = _build_client(tmp_path, monkeypatch)
    response = client.get("/ui/liability/business-context")

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["result_kind"] == "liability.page_knowledge"
    assert body["result"]["available"] is True
    assert body["result"]["vault_path"] == str(vault)
    assert [note["title"] for note in body["result"]["notes"]] == [
        "同业负债、流动性与金融市场业务传导链",
        "债券投资、久期与利率风险传导链",
        "金融市场条线经营分析标准提纲",
    ]
    assert body["result"]["notes"][0]["key_questions"] == [
        "当前流动性变化是总量变化还是结构变化",
        "银行缺的是头寸还是稳定负债",
    ]
