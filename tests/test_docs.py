import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts" / "check_docs.py")
check_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_docs)


def test_process_docs_are_valid():
    assert check_docs.main() == 0


def test_checker_detects_missing_section_and_unknown_endpoint(tmp_path):
    doc = tmp_path / "malo.md"
    doc.write_text("# Bad\n\n## Purpose\nUses `POST /no-existe`.\n", encoding="utf-8")
    errs = check_docs.check(doc, check_docs.routes())
    assert any("missing section 'Flow'" in e for e in errs)
    assert any("no mermaid flow" in e for e in errs)
    assert any("/no-existe" in e for e in errs)
