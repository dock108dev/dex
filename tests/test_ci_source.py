"""A clean source checkout must not require ignored qualification evidence."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "source_checks", Path(__file__).resolve().parents[1] / "scripts/ci/source.py"
)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


@pytest.fixture
def docs(monkeypatch, tmp_path):
    monkeypatch.setattr(source, "ROOT", tmp_path)
    monkeypatch.setattr(source, "DOCS", ("README.md",))
    return tmp_path / "README.md"


def test_ignored_reports_are_optional_in_clean_checkout(docs):
    docs.write_text("[Local-only closeout](reports/qualification/closeout.md)\n")
    source.check_document_links()
    assert not (docs.parent / "reports").exists()


def test_relative_source_link_remains_required(docs):
    docs.write_text("[Development](docs/local-development.md)\n")
    with pytest.raises(ValueError, match="docs/local-development.md"):
        source.check_document_links()
    (docs.parent / "docs").mkdir()
    (docs.parent / "docs/local-development.md").write_text("# Development\n")
    source.check_document_links()


@pytest.mark.parametrize(
    "target",
    ["reports/../missing.md", "reports/%2e%2e/missing.md", "/reports/closeout.md"],
)
def test_report_exception_does_not_hide_other_missing_or_nonportable_links(docs, target):
    docs.write_text(f"[Invalid]({target})\n")
    with pytest.raises(ValueError):
        source.check_document_links()


def test_escaped_paths_and_external_links(docs):
    (docs.parent / "setup notes.md").write_text("# Setup\n")
    docs.write_text(
        '[Setup](setup%20notes.md#install "Setup")\n'
        "[External](https://example.invalid/docs)\n[Section](#local)\n"
    )
    source.check_document_links()
