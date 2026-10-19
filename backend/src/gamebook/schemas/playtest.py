"""In-app player, bot batches, runs, coverage and jobs."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Discriminator, Field, Tag, model_validator

from gamebook.core.engine.events import ActionType
from gamebook.core.sim.bots import BotName
from gamebook.schemas.common import In, Out

# ── player ────────────────────────────────────────────────────────────────


class ActionInput(In):
    kind: Literal["action"]
    type: ActionType
    target: str | None = None


class JumpInput(In):
    """Debug: go straight to a node."""

    kind: Literal["jump"]
    node_id: str


class SetInput(In):
    """Debug: overwrite stats, item counts and codewords."""

    kind: Literal["set"]
    stats: dict[str, int] = Field(default_factory=dict)
    items: dict[str, Annotated[int, Field(ge=0, le=10_000)]] = Field(default_factory=dict)
    flags: dict[str, bool] = Field(default_factory=dict)


class ForceInput(In):
    """Debug: the next dice roll (not a combat round) comes out as ``total``."""

    kind: Literal["force"]
    total: int = Field(ge=-1000, le=1000)


PlayInput = Annotated[ActionInput | JumpInput | SetInput | ForceInput, Field(discriminator="kind")]


class PlayIn(In):
    tier: str
    seed: int = Field(default=1, ge=0, le=2**31 - 1)
    character_class: str | None = None
    fixed_stats: dict[str, int] | None = None
    #: Everything the reader has done, in order. The server replays it each time.
    inputs: list[PlayInput] = Field(default_factory=list, max_length=5_000)


class PlayNode(Out):
    id: str
    key: str
    title: str
    beat_notes: str
    #: Approved prose for the variant shown (None until written and approved).
    prose: str | None = None
    act_title: str | None
    variant_label: str | None
    ending_kind: str | None
    ending_grade: str | None


class PlayStat(Out):
    key: str
    label: str
    kind: str
    value: int
    effective: int
    max: int | None


class PlayItem(Out):
    key: str
    name: str
    category: str
    count: int
    slot: str | None
    equipped: bool


class PlayEnemy(Out):
    key: str
    name: str
    level: int
    stats: dict[str, int]


class PlayCombat(Out):
    round: int
    flee_allowed: bool
    enemies: list[PlayEnemy]


class PlayAction(Out):
    type: str
    target: str | None
    label: str
    enabled: bool
    reason: str | None


class PlayEvent(Out):
    type: str
    #: Plain-English line, or None when the event has nothing to say.
    text: str | None
    #: Index of the input that produced it (-1 = character creation).
    turn: int
    data: dict[str, Any]


class Option(Out):
    key: str
    label: str


class PlayOut(Out):
    tier: str
    seed: int
    #: How many inputs were replayed; less than sent when the book has changed.
    applied: int
    #: Why replay stopped early (the inputs after ``applied`` were dropped).
    error: str | None
    ended: str | None
    node: PlayNode | None
    stats: list[PlayStat]
    character_class: str | None
    skills: list[Option]
    items: list[PlayItem]
    flags: list[str]
    combat: PlayCombat | None
    actions: list[PlayAction]
    events: list[PlayEvent]
    classes: list[Option]
    steps: int
    #: Replays of LLM runs: the player's note for the choice made at this step.
    next_note: dict[str, Any] | None = None


# ── batches & runs ───────────────────────────────────────────────────────

#: Upper bound on runs times max_steps for one batch (≈ minutes of CPU, a few MB of picks).
MAX_BATCH_STEPS = 2_000_000


class BotOut(Out):
    name: BotName
    description: str


class BotPlayer(In):
    kind: Literal["bot"] = "bot"
    bot: BotName = "random"


Persona = Literal["cautious", "reckless", "completionist", "role-player"]


class LlmPlayer(In):
    """A model plays, seeing only what a reader sees (SPEC §5.4)."""

    kind: Literal["llm"]
    provider_id: str
    model: str = Field(min_length=1, max_length=200)
    persona: Persona = "cautious"
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=400, ge=64, le=4000)


#: Caps for LLM batches: every step is a paid model call.
MAX_LLM_RUNS = 200
MAX_LLM_STEPS = 400


def _player_kind(v: Any) -> str:
    """A player without ``kind`` is a bot (requests from before LLM players)."""
    kind = v.get("kind", "bot") if isinstance(v, dict) else getattr(v, "kind", "bot")
    return str(kind)


Player = Annotated[
    Annotated[BotPlayer, Tag("bot")] | Annotated[LlmPlayer, Tag("llm")],
    Discriminator(_player_kind),
]


class BatchIn(In):
    tier: str
    player: Player = Field(default_factory=BotPlayer)
    #: LLM players: stop starting new steps once spending reaches this.
    budget_usd: float | None = Field(default=None, ge=0)
    runs: int = Field(default=1000, ge=1, le=20_000)
    seed_base: int = Field(default=1, ge=0, le=2**31 - 1)
    max_steps: int = Field(default=500, ge=10, le=5_000)
    label: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _bounded(self) -> "BatchIn":
        if self.runs * self.max_steps > MAX_BATCH_STEPS:
            raise ValueError(
                f"Runs times max steps must be at most {MAX_BATCH_STEPS:,} "
                f"(lower one of them; {self.runs:,} x {self.max_steps:,} asked)"
            )
        if self.seed_base + self.runs > 2**31 - 1:
            raise ValueError("seed_base + runs must fit in 31 bits")
        if isinstance(self.player, LlmPlayer) and (
            self.runs > MAX_LLM_RUNS or self.max_steps > MAX_LLM_STEPS
        ):
            raise ValueError(
                f"LLM batches allow at most {MAX_LLM_RUNS} runs of {MAX_LLM_STEPS} steps"
            )
        return self


class ResumeIn(In):
    #: A new spending cap for the whole batch (keeps the old one when omitted).
    budget_usd: float | None = Field(default=None, ge=0)


class JobOut(Out):
    id: str
    kind: str
    status: str
    progress: int
    total: int
    label: str
    error: str | None
    result: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class BatchOut(Out):
    id: str
    book_id: str
    label: str
    tier: str
    player: dict[str, Any]
    n_runs: int
    seed_base: int
    max_steps: int
    content_hash: str
    status: str
    duration_s: float | None
    created_at: datetime
    job_id: str | None
    #: Headline numbers once done (the full summary is on the detail).
    win_rate: float | None = None
    cost_usd: float = 0.0
    #: The book or rules have changed since this batch ran.
    stale: bool = False


class BatchDetail(BatchOut):
    summary: dict[str, Any] | None
    job: JobOut | None
    #: Node, act, item and enemy names from the bundle the batch played.
    names: dict[str, dict[str, str]]


class RunOut(Out):
    index: int
    seed: int
    outcome: str
    ending_node_id: str | None
    last_node_id: str | None
    steps: int
    death_cause: str | None
    errors: int
    error_sample: str | None
    cost_usd: float = 0.0
    #: LLM runs: how many steps the player flagged as confusing.
    confused_steps: int = 0


class RunPage(Out):
    total: int
    runs: list[RunOut]


class CoverageIn(In):
    tier: str
    max_states: int = Field(default=20_000, ge=10, le=100_000)
    samples: int = Field(default=4, ge=1, le=12)
