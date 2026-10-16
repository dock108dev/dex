"""Maintained documentation must resolve from the checked-out project files."""

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


def test_missing_local_reports_cannot_satisfy_documentation_links(docs):
    docs.write_text("[Local report](reports/local/report.md)\n")
    with pytest.raises(ValueError, match="reports/local/report.md"):
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
def test_missing_or_nonportable_links_are_rejected(docs, target):
    docs.write_text(f"[Invalid]({target})\n")
    with pytest.raises(ValueError):
        source.check_document_links()


def test_escaped_paths_and_external_links(docs):
    (docs.parent / "setup notes.md").write_text("# Install\n")
    docs.write_text(
        '# Local\n[Setup](setup%20notes.md#install "Setup")\n'
        "[External](https://example.invalid/docs)\n[Section](#local)\n"
    )
    source.check_document_links()


@pytest.mark.parametrize("target", ["#missing", "guide.md#missing"])
def test_missing_section_is_rejected_even_when_file_exists(docs, target):
    (docs.parent / "guide.md").write_text("# Current guide\n")
    docs.write_text(f"# Current readme\n[Missing]({target})\n")
    with pytest.raises(ValueError, match="missing section"):
        source.check_document_links()


def test_heading_anchors_preserve_unicode_punctuation_and_duplicate_order(docs):
    docs.write_text(
        "# Pokémon and `cards`\n## Manual bulk — installed locally\n"
        "## Repeated\n## Repeated\n## Repeated-1\n"
        "```markdown\n# Example only\n```\n"
        "~~~\n# Another example\n~~~\n"
        "[Unicode](#pok%C3%A9mon-and-cards)\n"
        "[Current](#manual-bulk--installed-locally)\n"
        "[Duplicate](#repeated-1)\n[Collision](#repeated-1-1)\n"
    )
    source.check_document_links()
    assert "example-only" not in source.heading_anchors(docs)
    assert "another-example" not in source.heading_anchors(docs)


def test_code_example_heading_cannot_satisfy_section_link(docs):
    docs.write_text("```markdown\n# Missing\n```\n[Missing](#missing)\n")
    with pytest.raises(ValueError, match="missing section"):
        source.check_document_links()


def test_explicit_compatibility_anchors_remain_valid(docs):
    docs.write_text(
        '<a id="old-section"></a>\n## Current section\n'
        "<a name='retained-section'></a>\n"
        "[Historical](#old-section)\n[Retained](#retained-section)\n"
        '```html\n<a id="example-only"></a>\n```\n'
    )
    source.check_document_links()
    assert "example-only" not in source.heading_anchors(docs)
