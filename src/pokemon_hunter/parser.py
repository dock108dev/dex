import re
import unicodedata
from html.parser import HTMLParser

from .models import Count


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean(text: str) -> str:
    parser = PlainText()
    parser.feed(text)
    text = unicodedata.normalize("NFKD", " ".join(parser.parts))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-")).strip()


# A range is one token: its second number must never be mistaken for the count.
NUMBER = r"(?<![\d.,/-])(\d{1,3}(?:,\d{3})+|\d+)(?:\s*-\s*(\d+))?\s*\+?"
MODIFIERS = r"(?:(?:vintage|random|old|english|wotc|pokemon|tcg|common|uncommon|commons|uncommons|played|damaged|mixed|bulk)[ /-]+){0,7}"


def lower(match):
    a = int(match.group(1).replace(",", ""))
    return min(a, int(match.group(2))) if match.group(2) else a


def extract_count(text: str) -> Count:
    text = clean(text)
    # Quantities in repacks, options, per-pack counts and set checklist numbers
    # cannot safely identify what one purchase buys.
    if re.search(
        r"\b(?:packs? of|per pack|each pack|choose|pick your|pick from|up to|complete set|master set|\d+\s*[x×]\s*\d+)\b",
        text,
    ):
        return Count(explanation="Pack, selection, maximum, or complete-set quantity is ambiguous")
    explicit = list(
        re.finditer(
            NUMBER + r"\s*pokemon\b(?!\s*tcg)(?!\s*(?:cards?\s*)?(?:sleeves?|binders?|pages?|holders?))", text
        )
    )
    found = list(
        re.finditer(
            NUMBER + r"\s*" + MODIFIERS + r"cards?\b(?!\s*(?:sleeves?|binders?|pages?|holders?|storage))",
            text,
        )
    )
    found += list(
        re.finditer(r"\blot\s+of\s+" + NUMBER + r"\b(?!\s*(?:packs?|sleeves?|binders?|pages?))", text)
    )
    if not found and explicit:
        found = explicit
    if not found:
        return Count()
    values = [lower(m) for m in found]
    # Reject year numbers and impossible/zero quantities, rather than deleting
    # them and then trusting a different, potentially unrelated number.
    if any(n <= 0 or 1995 <= n <= 2035 or n > 100000 for n in values):
        return Count(explanation="Card count resembles a year or invalid quantity")
    total = min(values)
    count = Count(
        total=total, confidence=0.7, explanation=f"{total}-card lower bound; species composition unknown"
    )
    for field, pattern in [("trainers", r"trainer"), ("energy", r"energ(?:y|ies)")]:
        matches = list(re.finditer(NUMBER + r"\s*" + pattern + r"s?\b", text))
        if matches:
            setattr(count, field, max(lower(m) for m in matches))
    no_nonpokemon = bool(re.search(r"no\s+trainers?\s*(?:or|and|/|,|&)\s*energ", text))
    no_nonpokemon |= bool(re.search(r"pokemon\s+only|only\s+pokemon", text))
    inclusion = bool(re.search(r"\b(?:including|includes?|of which|contains?|with|total)\b", text))
    additive = bool(re.search(r"\bplus\b|\+\s*\d+\s*(?:trainers?|energ)", text)) and not inclusion
    if explicit and (
        no_nonpokemon or (additive and (count.trainers is not None or count.energy is not None))
    ):
        count.pokemon = min(lower(m) for m in explicit)
        count.total = max(total, count.pokemon)
        count.confidence = 0.95
        count.explanation = f"{count.pokemon} explicitly stated Pokemon cards"
    elif no_nonpokemon:
        count.pokemon = total
        count.confidence = 0.95
        count.explanation = f"{total} cards; seller states no trainers or energy"
    elif count.trainers is not None or count.energy is not None:
        nonpokemon = (count.trainers or 0) + (count.energy or 0)
        # "100 cards + 25 energy" keeps the 100; "100 cards including 25
        # energy" subtracts them. Unspecified composition remains low confidence.
        if additive:
            count.explanation = f"{total} cards excluding stated extras; remaining composition unknown"
        else:
            count.total = max(0, total - nonpokemon)
            count.explanation = (
                f"{count.total}-card lower bound after stated trainers/energy; composition unknown"
            )
        count.confidence = 0.65
    if len(set(values)) > 1:
        count.confidence = min(count.confidence, 0.5)
        count.explanation += "; conflicting counts, using smallest"
    return count
