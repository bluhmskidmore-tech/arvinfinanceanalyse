from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_document_authority_files_exist_after_bundle_merge():
    required_paths = [
        ROOT / "AGENTS.md",
        ROOT / "prd-moss-agent-analytics-os.md",
        ROOT / "docs" / "DOCUMENT_AUTHORITY.md",
        ROOT / "docs" / "CODEX_HANDOFF.md",
        ROOT / "docs" / "IMPLEMENTATION_PLAN.md",
        ROOT / "docs" / "CODEX_KICKOFF_PROMPT.md",
        ROOT / "docs" / "SYSTEM_STACK_SPEC_FOR_CODEX.md",
    ]

    missing = [str(path) for path in required_paths if not path.exists()]
    assert not missing, "Missing merged bundle files:\n" + "\n".join(missing)
