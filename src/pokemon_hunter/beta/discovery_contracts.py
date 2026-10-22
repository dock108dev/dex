"""Validated Shopping choices and ephemeral run state shared with Hunter.

These types perform no storage, authentication or provider operations. The
orchestrator owns locks, deadlines, admission and terminal accounting.
"""

import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, StrictBool, StrictInt, field_validator, model_validator

MAX_BROWSE = 4


class Choices(BaseModel):
    model_config = {"extra": "forbid"}

    intent: Literal["deals", "missing"] = "deals"
    missing_basis: Literal["printing", "species"] = "species"
    goal_id: str | None = Field(default=None, min_length=1, max_length=64)
    focus: Literal["all", "kanto", "johto", "rares", "bulk"] = "all"
    budget: Decimal | None = Field(default=None, ge=0, le=10000)
    query: str = Field(default="", max_length=200)
    set_id: str | None = Field(default=None, min_length=1, max_length=100)
    species: StrictInt | None = Field(default=None, ge=1, le=251)
    group_id: str | None = Field(default=None, pattern=r"^dg1-[0-9a-f]{64}$")
    printing_id: str | None = Field(default=None, min_length=1, max_length=160)
    goal_version: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    generation: StrictInt | None = Field(default=None, ge=0, le=10**18)
    product_type: Literal["singles", "mixed_lots", "both"] = "mixed_lots"
    sort: Literal["best_match", "ending_soonest"] = "ending_soonest"
    english_vintage: StrictBool = False
    browse_requests: StrictInt = Field(default=1, ge=1, le=MAX_BROWSE)

    @field_validator("query")
    @classmethod
    def trim(cls, value):
        return value.strip()

    @model_validator(mode="after")
    def checked_context(self):
        if self.species is not None and self.group_id is not None:
            raise ValueError("Choose a Pokémon or a card group")
        if self.printing_id is not None and self.group_id is None:
            raise ValueError("An exact printing requires its checked card group")
        if self.goal_version and not self.goal_id:
            raise ValueError("A saved version requires its goal")
        if self.intent == "missing" and not self.goal_id and "focus" not in self.model_fields_set:
            self.focus = "kanto"
        return self


@dataclass
class Run:
    id: str
    owner: tuple
    choices: Choices
    scope: dict | None
    queries: list
    operation: str = "browse"
    identifier: str | None = None
    auth_session: str | None = None
    offset: int = 0
    named_pages: list | None = None
    named_count: int = 0
    action_counts: dict | None = None
    raws: list = field(default_factory=list)
    seen: set = field(default_factory=set)
    revealed: set = field(default_factory=set)
    state: str = "queued"
    error: str | None = None
    created: float = field(default_factory=time.monotonic)
    deadline: float | None = None
    acquired_at: float | None = None
    timed_out: bool = False
    counts: dict = field(default_factory=lambda: {"oauth": 0, "browse": 0, "total": 0, "summary_count": 0})
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)
