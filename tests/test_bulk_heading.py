"""The bulk task heading must not acquire global banner styles."""

from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "src/pokemon_hunter/beta"


class Heading(HTMLParser):
    def __init__(self):
        super().__init__()
        self.banner_count = 0
        self.heading_count = 0
        self.back_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.banner_count += tag == "header"
        self.heading_count += "bulk-page-heading" in attrs.get("class", "").split()
        self.back_count += tag == "a" and attrs.get("href") == "/add-card/"


def test_bulk_introduction_does_not_match_global_banner_selector():
    parser = Heading()
    parser.feed((BASE / "templates/beta/bulk_entry.html").read_text())
    assert parser.banner_count == 0
    assert parser.heading_count == 1
    assert parser.back_count == 1


def test_heading_link_has_scoped_visited_hover_and_keyboard_focus_rules():
    css = (BASE / "static/bulk_entry.css").read_text()
    for state in ("visited", "hover", "active", "focus-visible"):
        assert "#bulk-entry .bulk-page-heading a:" + state in css
    assert "outline: 3px solid #416ec8" in css
    assert "text-decoration: underline" in css
