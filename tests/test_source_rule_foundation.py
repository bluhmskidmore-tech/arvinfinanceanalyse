from pathlib import Path

from tests.helpers import ROOT, load_module


def test_ingest_scan_enriches_manifest_with_source_family_and_report_date(tmp_path):
    ingest_module = load_module(
        "backend.app.services.ingest_service",
        "backend/app/services/ingest_service.py",
    )

    data_root = tmp_path / "data_input"
    zqtz_file = data_root / "ZQTZSHOW-20251231.xls"
    tyw_file = data_root / "TYWLSHOW-2025.06.01.xls"
    zqtz_file.parent.mkdir(parents=True, exist_ok=True)
    zqtz_file.write_bytes(b"zqtz")
    tyw_file.write_bytes(b"tyw")

    service = ingest_module.IngestService(data_root=data_root)
    rows = sorted(service.scan(), key=lambda row: row["file_name"])

    assert rows[0]["source_family"] == "tyw"
    assert rows[0]["report_date"] == "2025-06-01"
    assert rows[1]["source_family"] == "zqtz"
    assert rows[1]["report_date"] == "2025-12-31"


def test_source_rules_detect_family_and_date_from_supported_file_names():
    rules_module = load_module(
        "backend.app.services.source_rules",
        "backend/app/services/source_rules.py",
    )

    assert rules_module.detect_source_family("ZQTZSHOW-20251231.xls") == "zqtz"
    assert rules_module.detect_source_family("TYWLSHOW-2025.06.01.xls") == "tyw"
    assert rules_module.extract_report_date_from_name("ZQTZSHOW-20251231.xls") == "2025-12-31"
    assert rules_module.extract_report_date_from_name("TYWLSHOW-2025.06.01.xls") == "2025-06-01"


def test_zqtz_other_bond_prefix_rule_maps_to_expected_preview_group():
    rules_module = load_module(
        "backend.app.services.source_rules",
        "backend/app/services/source_rules.py",
    )

    row = {
        "业务种类1": "其他债券",
        "债券代号": "SA0001",
        "业务种类": "其他",
        "资产分类": "交易类资产",
        "账户类别": "银行账户",
    }

    result = rules_module.classify_zqtz_preview(row)

    assert result["business_type_primary"] == "其他债券"
    assert result["business_type_final"] == "公募基金"
    assert result["asset_group"] == "基金类"
    assert result["manual_review_needed"] is False
    assert result["trace_fields"] == ["业务种类1", "债券代号"]


def test_tyw_conflicting_confirmation_flags_manual_review():
    rules_module = load_module(
        "backend.app.services.source_rules",
        "backend/app/services/source_rules.py",
    )

    row = {
        "产品类型": "存放同业",
        "投资组合": "拆借自营",
        "会计类型_银保监会": "非银行金融机构",
        "会计类型_人行": "非银行金融机构",
        "核心客户类型": "基金",
        "账户类型": "清算类",
        "特殊账户类型": "托管账户",
        "托管账户名称": "测试托管专户",
    }

    result = rules_module.classify_tyw_preview(row)

    assert result["business_type_primary"] == "存放同业"
    assert result["product_group"] == "存放类"
    assert result["institution_category"] == "non-bank"
    assert result["special_nature"] == "托管清算"
    assert result["manual_review_needed"] is True
    assert result["trace_fields"] == [
        "产品类型",
        "投资组合",
        "会计类型_银保监会",
        "会计类型_人行",
        "核心客户类型",
        "账户类型",
        "特殊账户类型",
        "托管账户名称",
    ]
