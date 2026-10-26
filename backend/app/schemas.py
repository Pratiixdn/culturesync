"""Request and response models; this is the frontend contract."""
from __future__ import annotations

from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

Category = Literal["music", "movies", "tv", "books", "brands", "games", "podcasts", "places", "destinations"]
CATEGORIES: tuple[str, ...] = ("music", "movies", "tv", "books", "brands", "games", "podcasts", "places", "destinations")

MAX_MEMBERS = 12
MAX_INTERESTS = 30


def _clean(v: str) -> str:
    return " ".join(v.split())


# ---------- envelope ----------
T = TypeVar("T")


class Meta(BaseModel):
    source: Literal["local", "qloo"] = "local"
    mode: Literal["live", "mock"] = "mock"  # mock is never live Qloo data


class ErrorBody(BaseModel):
    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    data: Optional[T] = None
    meta: Meta
    error: Optional[ErrorBody] = None


# ---------- entities ----------
class EntityRef(BaseModel):
    id: str
    name: str
    types: list[str] = []
    affinity: Optional[float] = None  # as returned by Qloo, None if absent


class EntitySearchOut(BaseModel):
    query: str
    category: Optional[Category] = None
    results: list[EntityRef]


# ---------- teams / members ----------
class InterestIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Category
    entity_id: Optional[str] = Field(default=None, pattern=r"^[\w:.\-]{1,200}$")
    entity_name: Optional[str] = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def _n(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class InterestOut(BaseModel):
    id: str
    name: str
    category: Category
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    source: Literal["manual", "qloo"] = "manual"  # qloo: picked from Qloo search


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    interests: list[InterestIn] = Field(default_factory=list, max_length=MAX_INTERESTS)

    @field_validator("name")
    @classmethod
    def _n(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class MemberUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    interests: Optional[list[InterestIn]] = Field(default=None, max_length=MAX_INTERESTS)

    @field_validator("name")
    @classmethod
    def _n(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class MemberOut(BaseModel):
    id: str
    name: str
    interests: list[InterestOut]


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def _n(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def _n(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class TeamOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: str
    members: list[MemberOut]


# ---------- connections / insights ----------
ConnectionKind = Literal["shared_interest", "same_category", "qloo_affinity"]


class ConnectionEntity(BaseModel):
    role: Literal["shared", "listed", "signal", "result"]
    member_id: str
    name: str
    category: Category
    entity_id: Optional[str] = None
    affinity: Optional[float] = None  # only set on results, and only if Qloo returned it


class Connection(BaseModel):
    id: str
    kind: ConnectionKind
    source: Literal["local", "qloo"]
    member_ids: list[str]
    entities: list[ConnectionEntity]
    evidence: str
    basis: Optional[Literal["entity_id", "name"]] = None  # how a local overlap matched
    caveat: Optional[str] = None


class Resolution(BaseModel):
    """A typed interest matched to the top Qloo hit during one analysis run."""
    member_id: str
    interest_id: str
    name: str
    entity: EntityRef


class Suggestion(BaseModel):
    category: Category
    signal_entities: list[EntityRef]
    entities: list[EntityRef]


class InsightsRequest(BaseModel):
    suggest_categories: list[Category] = Field(default_factory=lambda: ["music", "movies", "brands"], max_length=4)
    include_suggestions: bool = True


class AnalysisInfo(BaseModel):
    ran_at: str
    mode: Literal["live", "mock"]
    qloo_calls: int
    truncated: bool = False


class ConnectionsOut(BaseModel):
    connections: list[Connection]
    suggestions: list[Suggestion] = []
    resolutions: list[Resolution] = []
    analysis: Optional[AnalysisInfo] = None  # None: not run yet, or stale after edits
    analysis_stale: bool = False
    limitations: list[str]


# ---------- activities / ideas ----------
class ActivityCreate(BaseModel):
    connection_ids: list[str] = Field(min_length=1, max_length=3)


class ActivityOut(BaseModel):
    id: str
    title: str
    objective: str
    prompts: list[str]
    connection_ids: list[str]
    member_ids: list[str]
    basis: Literal["application_template"] = "application_template"
    created_at: str


class IdeaCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    activity_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("text")
    @classmethod
    def _t(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class IdeaOut(BaseModel):
    id: str
    text: str
    activity_id: Optional[str] = None
    created_at: str


# ---------- health ----------
class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "culturesync-api"
    qloo_configured: bool
    mode: Literal["live", "mock"]
    agent_configured: bool = False
    qloo_reachable: Optional[bool] = None  # only set when ?probe=true
    qloo_error: Optional[str] = None


# ---------- agent ----------
class AgentRequest(BaseModel):
    goal: str = Field(min_length=8, max_length=400)

    @field_validator("goal")
    @classmethod
    def _g(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 8:
            raise ValueError("describe the goal in a few more words")
        return v


class AgentStepOut(BaseModel):
    tool: str
    summary: str
    ok: bool


class AgentRecommendation(BaseModel):
    entity_id: str  # a Qloo entity returned during the run
    title: str  # Qloo's name for it, not the model's
    category: Optional[str] = None
    affinity: Optional[float] = None  # as returned by Qloo, if any
    why: str  # generated by the language model; not a Qloo field
    supported_by: list[str] = []


class AgentRunOut(BaseModel):
    id: str
    goal: str
    summary: str
    recommendations: list[AgentRecommendation]
    actions: list[str] = []  # written by the language model; each names Qloo picks or team interests
    caveats: list[str]
    dropped_ungrounded: int  # model suggestions removed because Qloo never returned them
    steps: list[AgentStepOut]
    qloo_calls: int
    model: str
    created_at: str


class AgentRunsOut(BaseModel):
    runs: list[AgentRunOut]
