"""Derive text from retained HTML only; no source acquisition."""

from html.parser import HTMLParser

from acquire_d8 import OUT


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.out = []

    def handle_starttag(self, t, a):
        if t in ["script", "style"]:
            self.skip += 1

    def handle_endtag(self, t):
        if t in ["script", "style"]:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, d):
        if not self.skip and d.strip():
            self.out.append(d.strip())


for path in (OUT / "raw").glob("*.raw"):
    if path.read_bytes()[:100].lstrip().startswith((b"<!", b"<html")):
        p = Text()
        p.feed(path.read_text())
        path.with_suffix(".text").write_text("\n".join(p.out))
