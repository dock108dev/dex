from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Thresholds(StrictModel):
    fixed_price_per_card: Decimal = Field(default=Decimal("1"), gt=0)
    auction_per_card: Decimal = Field(default=Decimal(".5"), gt=0)


class MaximumPurchase(StrictModel):
    fixed_price: Decimal | None = Field(default=Decimal("60"), gt=0)
    auction: Decimal | None = Field(default=Decimal("75"), gt=0)


class Alerts(StrictModel):
    minimum_priority: Literal["low", "medium", "high"] = "medium"
    max_hits: int = Field(default=5, ge=1, le=25)
    material_price_change: Decimal = Field(default=Decimal(".2"), gt=0)
    macos_notification: bool = False


class Search(StrictModel):
    page_size: int = Field(default=100, ge=1, le=200)
    max_pages: int = Field(default=2, ge=1, le=10)
    detail_limit: int = Field(default=30, ge=0, le=100)


class PokedexBaseline(StrictModel):
    kanto_owned: int = Field(default=133, ge=0, le=151)
    johto_owned: int = Field(default=20, ge=0, le=100)


class Settings(StrictModel):
    marketplace: Literal["EBAY_US"] = "EBAY_US"
    currency: Literal["USD"] = "USD"
    environment: Literal["production", "sandbox"] = "production"
    delivery_country: Literal["US"] = "US"
    delivery_postal_code: str | None = Field(default=None, pattern=r"^\d{5}(?:-\d{4})?$")
    thresholds: Thresholds = Field(default_factory=Thresholds)
    minimum_cards: int = Field(default=25, ge=1)
    maximum_purchase: MaximumPurchase = Field(default_factory=MaximumPurchase)
    alerts: Alerts = Field(default_factory=Alerts)
    search: Search = Field(default_factory=Search)
    pokedex: PokedexBaseline = Field(default_factory=PokedexBaseline)


class Count(BaseModel):
    total: int | None = None
    pokemon: int | None = None
    trainers: int | None = None
    energy: int | None = None
    confidence: float = 0
    explanation: str = "No reliable card count"

    @property
    def denominator(self) -> int | None:
        return self.pokemon if self.pokemon is not None else self.total


class Listing(BaseModel):
    ebay_item_id: str
    title: str
    url: str
    listing_type: Literal["bin", "auction"]
    item_price: Decimal | None = None
    shipping_price: Decimal | None = None
    landed_price: Decimal | None = None
    cost_per_card: Decimal | None = None
    max_bid: Decimal | None = None
    bid_count: int | None = None
    end_time: datetime | None = None
    seller: str | None = None
    condition: str | None = None
    count: Count = Field(default_factory=Count)
    detected_sets: set[str] = Field(default_factory=set)
    excluded_sets: set[str] = Field(default_factory=set)
    purity: Literal["pure", "probably_pure", "mixed", "unknown"] = "unknown"
    pokedex_score: float = 0
    confidence: float = 0
    priority: Literal["low", "medium", "high"] = "low"
    qualifying: bool = False
    reasons: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    queries: set[str] = Field(default_factory=set)
