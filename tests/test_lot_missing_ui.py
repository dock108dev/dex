"""Run the shipped calculator against rendered templates and disposable browser state."""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.template import Context, Engine


class BrowserTree(HTMLParser):
    """Keep actual template elements/options while omitting browser layout concerns."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}

    def __init__(self):
        super().__init__()
        self.tree = {"tag": "document", "attrs": {}, "children": []}
        self.stack = [self.tree]

    def handle_starttag(self, tag, attrs):
        item = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(item)
        if tag not in self.VOID:
            self.stack.append(item)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1]["children"].append(data)


def test_current_missing_picker_and_existing_lot_draft_boundaries(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the shipped calculator checks")
    root = Path(__file__).resolve().parents[1]
    engine = Engine(dirs=[str(root / "src/pokemon_hunter/beta/templates")])
    template = engine.get_template("beta/lot_calculator.html")
    context = {
        "account_id": "engineering-account",
        "generation": 12,
        "kind": "all",
        "label": "All cards",
        "query": {},
        "current_present": None,
    }
    goal = {"id": "engineering-frozen", "name": "Retained engineering goal", "version": "a" * 64}
    variants = {}
    for name, goals, incoming in [
        ("default", [goal], context),
        ("no_goals", [], context),
        ("explicit_goal", [goal], {**context, "query": {"goal": goal["id"], "version": goal["version"]}}),
    ]:
        rendered = template.render(
            Context(
                {
                    "shopping_context": incoming,
                    "shopping_binding": "engineering-binding",
                    "missing_goals": goals,
                    "wants": [],
                    "items": [],
                    "research_enabled": True,
                    "csrf_token": "engineering-csrf",
                },
                use_l10n=False,
            )
        )
        tree = BrowserTree()
        tree.feed(rendered)
        variants[name] = tree.tree
    trees = tmp_path / "rendered-calculator-trees.json"
    trees.write_text(json.dumps(variants))
    result = subprocess.run(
        [
            node,
            str(root / "tests/lot_missing_ui_cases.cjs"),
            str(root / "src/pokemon_hunter/beta/static/lot_calculator.js"),
            str(trees),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report = json.loads(result.stdout)
    assert report["passed"] == len(report["cases"]) >= 7
    assert report["provider_calls"] == 0
    assert report["customer_data"] is False
