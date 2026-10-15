"""Strict public sealed-catalog package schemas, independent of publication writes."""

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import catalog_imports as cat


def instant(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("A timezone-aware source time is required")
    return dt.astimezone(timezone.utc)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Record(Model):
    id: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    sources: list[str] = Field(min_length=1)


class Source(Model):
    id: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    provider: str
    url: str
    retrieved_at: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    language: str | None
    market: str | None
    authority: Literal["official-species", "official-card", "official-product", "provider", "retailer"]
    status: Literal["usable", "access-denied", "unusable", "search-only"]
    subjects: list[str]
    supports: list[
        Literal[
            "species-identity",
            "printing-identity",
            "booster-membership",
            "distribution-membership",
            "product-identity",
            "product-contents",
            "offer-observation",
            "universe",
        ]
    ]
    rights: str
    note: str

    @field_validator("url")
    @classmethod
    def url_https(cls, value):
        if not re.fullmatch(r"https://[^\s]+", value):
            raise ValueError("Public HTTPS URL required")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def dated(cls, value):
        instant(value)
        return value


class Species(Record):
    dex: int = Field(ge=1, le=100000)
    name: str = Field(min_length=1)


class Expansion(Record):
    name: str
    language: str
    series: str | None
    medium: Literal["physical", "digital", "unknown"]
    expected_printings: int | None = Field(ge=0)


class Printing(Record):
    expansion_id: str
    species_id: str | None
    name: str
    number: str
    language: str
    rarity: str | None
    finish: str | None
    variant: str | None
    category: Literal["pokemon", "trainer", "energy", "unknown"]


class Membership(Record):
    printing_id: str
    expansion_id: str
    status: Literal["booster", "promo", "deck-only", "unknown"]


class IncludedCard(Model):
    """Documented inclusion with unresolved exact printing; never target coverage."""

    name: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    canonical_dex: int | None = Field(default=None, ge=1)
    exact_printing: Literal["unresolved"]
    sources: list[str] = Field(min_length=1)


class Product(Record):
    name: str
    sku: str | None
    version: str = Field(min_length=1)
    market: str
    language: str
    product_type: str
    contents: Literal["complete", "mixed-known", "unknown"]
    total_packs: int | None = Field(ge=0)
    guaranteed_cards_known: bool
    included_cards: list[IncludedCard] = Field(default_factory=list)


class Pack(Record):
    product_id: str
    expansion_id: str | None
    quantity: int | None = Field(ge=1)


class Guaranteed(Record):
    product_id: str
    printing_id: str
    quantity: int = Field(ge=1)


class Offer(Record):
    product_id: str
    retailer: str
    seller: str | None
    seller_kind: Literal["direct", "marketplace", "unknown"]
    market: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    url: str

    _url = field_validator("url")(Source.url_https.__func__)


class Observation(Record):
    offer_id: str
    checked_at: str | None
    stock: Literal["in-stock", "out-of-stock", "preorder", "unknown"]
    price_minor: int | None = Field(ge=0)
    shipping_minor: int | None = Field(ge=0)
    note: str

    @field_validator("checked_at")
    @classmethod
    def observation_time(cls, value):
        if value is not None:
            instant(value)
        return value


class Mapping(Model):
    provider: str = Field(min_length=1)
    language: str = Field(min_length=2)
    kind: Literal["species", "expansions", "printings", "products", "offers"]
    external_id: str = Field(min_length=1)
    internal_id: str


class Coverage(Record):
    language: str
    market: str
    intended_expansions: list[str]
    species_count: int = Field(ge=1)
    gaps: list[str]


class Correction(Model):
    kind: str
    id: str
    before_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1)


class BridgeLink(Model):
    printing_id: str
    external_id: str


class Bridge(Model):
    expansion_id: str
    package: cat.Package
    links: list[BridgeLink]


class Package(Model):
    schema_version: Literal["dex-sealed-v1"]
    provider: str = Field(min_length=1)
    version: str = Field(min_length=1)
    sources: list[Source]
    species: list[Species]
    expansions: list[Expansion]
    printings: list[Printing]
    memberships: list[Membership]
    products: list[Product]
    packs: list[Pack]
    guaranteed: list[Guaranteed]
    offers: list[Offer]
    observations: list[Observation]
    coverage: list[Coverage]
    mappings: list[Mapping]
    corrections: list[Correction] = Field(default_factory=list)
    bridges: list[Bridge] = Field(default_factory=list)
