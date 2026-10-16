"""API routes. Every route returns the {data, meta, error} envelope."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from . import services
from .agent import run_agent
from .llm import AgentError
from .qloo import QlooError
from .schemas import (ActivityCreate, AgentRequest, AgentRunsOut, ActivityOut, Category, Connection, ConnectionsOut, EntitySearchOut, Envelope,
                      HealthOut, IdeaCreate, IdeaOut, InsightsRequest, MemberCreate, MemberOut, MemberUpdate, TeamCreate,
                      TeamOut, TeamUpdate)
from .storage import Storage

router = APIRouter(prefix="/api")
log = logging.getLogger("culturesync")


# ---------- dependencies ----------
def get_store(request: Request) -> Storage:
    return request.app.state.store


def get_client(request: Request):
    return request.app.state.qloo


class RateLimiter:
    """Per-IP sliding window (in memory) for endpoints that call Qloo."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self.hits[ip]
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= self.per_minute:
            raise QlooError("rate_limited", "Too many requests. Wait a minute and try again.", 429)
        window.append(now)


def rate_limit(request: Request) -> None:
    request.app.state.limiter(request)


class DailyCap:
    """Caps total agent runs per UTC day, so a public demo cannot burn the LLM budget."""

    def __init__(self, limit: int):
        self.limit, self.day, self.used = limit, date.today(), 0

    def take(self) -> None:
        if self.day != date.today():
            self.day, self.used = date.today(), 0
        if self.used >= self.limit:
            raise AgentError("agent_daily_limit", "The demo's daily agent limit is reached. Try again tomorrow.", 429)
        self.used += 1


def ok(request: Request, data: Any, source: str = "local") -> dict:
    return {"data": data, "meta": {"source": source, "mode": request.app.state.qloo.mode}, "error": None}


def load_team(store: Storage, team_id: str) -> dict:
    team = store.get_team(team_id)
    if not team:
        raise HTTPException(404, "Team not found.")
    return team


def team_json(store: Storage, team_id: str) -> dict:
    return TeamOut.model_validate(load_team(store, team_id)).model_dump()


def member_json(store: Storage, team_id: str, member_id: str) -> dict:
    member = next(m for m in load_team(store, team_id)["members"] if m["id"] == member_id)
    return MemberOut.model_validate(member).model_dump()


def connections_payload(store: Storage, team: dict) -> dict:
    """Local connections, or the saved Qloo analysis if it still matches the team."""
    saved = store.get_analysis(team["id"])
    if saved and saved[0] == services.team_signature(team):
        return {**saved[1], "analysis_stale": False}
    limitations = list(services.LIMITATIONS)
    if saved:
        limitations.append("Interests changed since the last Qloo analysis. Run it again for current Qloo results.")
    return {
        "connections": [c.model_dump() for c in services.local_connections(team)],
        "suggestions": [], "resolutions": [], "analysis": None,
        "analysis_stale": saved is not None, "limitations": limitations,
    }


# ---------- health ----------
@router.get("/health", response_model=Envelope[HealthOut])
async def health(request: Request, probe: bool = False, client=Depends(get_client)):
    out = HealthOut(qloo_configured=client.mode == "live", mode=client.mode, agent_configured=request.app.state.llm is not None)
    if probe and client.mode == "live":
        rate_limit(request)
        try:
            await client.search("test", take=1)
            out.qloo_reachable = True
        except QlooError as err:
            out.qloo_reachable, out.qloo_error = False, err.code
    return ok(request, out.model_dump())


# ---------- teams and members ----------
@router.post("/teams", response_model=Envelope[TeamOut], status_code=201)
def create_team(request: Request, body: TeamCreate, store: Storage = Depends(get_store)):
    team_id = store.create_team(body.name, body.description)
    return ok(request, team_json(store, team_id))


@router.get("/teams/{team_id}", response_model=Envelope[TeamOut])
def get_team(request: Request, team_id: str, store: Storage = Depends(get_store)):
    return ok(request, team_json(store, team_id))


@router.patch("/teams/{team_id}", response_model=Envelope[TeamOut])
def update_team(request: Request, team_id: str, body: TeamUpdate, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    store.update_team(team_id, body.name, body.description)
    return ok(request, team_json(store, team_id))


@router.post("/teams/{team_id}/members", response_model=Envelope[MemberOut], status_code=201)
def add_member(request: Request, team_id: str, body: MemberCreate, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    interests = services.prepare_interests([i.model_dump() for i in body.interests])
    member_id = store.add_member(team_id, body.name, interests)
    return ok(request, member_json(store, team_id, member_id))


@router.patch("/teams/{team_id}/members/{member_id}", response_model=Envelope[MemberOut])
def update_member(request: Request, team_id: str, member_id: str, body: MemberUpdate,
                  store: Storage = Depends(get_store)):
    team = load_team(store, team_id)
    interests: Optional[list[dict]] = None
    if body.interests is not None:
        interests = services.prepare_interests([i.model_dump() for i in body.interests])
        current = next((m for m in team["members"] if m["id"] == member_id), None)
        existing = {(i["category"], services.norm(i["name"]), i.get("entity_id")): i["id"]
                    for i in (current["interests"] if current else [])}
        for interest in interests:  # unchanged interests keep their ids
            key = (interest["category"], services.norm(interest["name"]), interest.get("entity_id"))
            interest["id"] = existing.get(key, interest["id"])
    if not store.update_member(team_id, member_id, body.name, interests):
        raise HTTPException(404, "Member not found.")
    return ok(request, member_json(store, team_id, member_id))


@router.delete("/teams/{team_id}/members/{member_id}", response_model=Envelope[TeamOut])
def delete_member(request: Request, team_id: str, member_id: str, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    if not store.delete_member(team_id, member_id):
        raise HTTPException(404, "Member not found.")
    return ok(request, team_json(store, team_id))


# ---------- Qloo ----------
@router.get("/entities/search", response_model=Envelope[EntitySearchOut], dependencies=[Depends(rate_limit)])
async def search_entities(request: Request, q: str = Query(min_length=2, max_length=80),
                          category: Optional[Category] = None, client=Depends(get_client)):
    query = q.strip()
    results = await client.search(query, category, take=8)
    data = {"query": query, "category": category, "results": [r.model_dump() for r in results]}
    return ok(request, data, "qloo")


@router.post("/teams/{team_id}/insights", response_model=Envelope[ConnectionsOut], dependencies=[Depends(rate_limit)])
async def run_insights(request: Request, team_id: str, body: Optional[InsightsRequest] = None,
                       store: Storage = Depends(get_store), client=Depends(get_client)):
    body = body or InsightsRequest()
    team = load_team(store, team_id)
    result = await services.analyze(team, client, body.include_suggestions, body.suggest_categories,
                                    request.app.state.max_qloo_calls)
    store.save_analysis(team_id, services.team_signature(team), result)
    return ok(request, {**result, "analysis_stale": False}, "qloo")


@router.get("/teams/{team_id}/connections", response_model=Envelope[ConnectionsOut])
def get_connections(request: Request, team_id: str, store: Storage = Depends(get_store)):
    payload = connections_payload(store, load_team(store, team_id))
    return ok(request, payload, "qloo" if payload["analysis"] else "local")


# ---------- activities and ideas ----------
@router.post("/teams/{team_id}/activities", response_model=Envelope[ActivityOut], status_code=201)
def create_activity(request: Request, team_id: str, body: ActivityCreate, store: Storage = Depends(get_store)):
    team = load_team(store, team_id)
    available = {c["id"]: c for c in connections_payload(store, team)["connections"]}
    chosen = []
    for connection_id in body.connection_ids:
        connection = available.get(connection_id)
        if not connection:
            raise HTTPException(404, "Connection not found. Refresh and try again.")
        if connection["kind"] == "same_category":
            raise HTTPException(422, "Activities need a shared interest or a Qloo affinity, not just a shared category.")
        chosen.append(Connection.model_validate(connection))
    activity = services.build_activity(team, chosen)
    store.save_activity(team_id, activity)
    return ok(request, activity)


@router.get("/teams/{team_id}/activities", response_model=Envelope[list[ActivityOut]])
def list_activities(request: Request, team_id: str, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    return ok(request, store.list_activities(team_id))


@router.delete("/teams/{team_id}/activities/{activity_id}", response_model=Envelope[dict])
def delete_activity(request: Request, team_id: str, activity_id: str, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    if not store.delete_activity(team_id, activity_id):
        raise HTTPException(404, "Activity not found.")
    return ok(request, {"deleted": activity_id})


@router.post("/teams/{team_id}/ideas", response_model=Envelope[IdeaOut], status_code=201)
def create_idea(request: Request, team_id: str, body: IdeaCreate, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    return ok(request, store.add_idea(team_id, body.text, body.activity_id))


@router.get("/teams/{team_id}/ideas", response_model=Envelope[list[IdeaOut]])
def list_ideas(request: Request, team_id: str, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    return ok(request, store.list_ideas(team_id))


@router.delete("/teams/{team_id}/ideas/{idea_id}", response_model=Envelope[dict])
def delete_idea(request: Request, team_id: str, idea_id: str, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    if not store.delete_idea(team_id, idea_id):
        raise HTTPException(404, "Idea not found.")
    return ok(request, {"deleted": idea_id})


# ---------- agent ----------
def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/teams/{team_id}/agent")
async def ask_agent(request: Request, team_id: str, body: AgentRequest, store: Storage = Depends(get_store),
                    client=Depends(get_client)):
    """Streams server-sent events: step events while the agent works, then one result (or error) event."""
    team = load_team(store, team_id)
    llm = request.app.state.llm
    if llm is None:
        raise AgentError("agent_not_configured", "The agent needs GEMINI_API_KEY set on the server.", 503)
    if not any(m["interests"] for m in team["members"]):
        raise HTTPException(422, "Add at least one member with interests before asking the agent.")
    request.app.state.agent_limiter(request)
    request.app.state.agent_cap.take()

    async def events():
        yield sse({"type": "start", "mode": client.mode})
        try:
            async for event in run_agent(team, body.goal, client, llm, max_qloo_calls=request.app.state.max_agent_qloo_calls):
                if event["type"] == "result":
                    store.save_agent_run(team_id, event["data"])
                yield sse(event)
        except AgentError as err:
            yield sse({"type": "error", "code": err.code, "message": err.message})
        except Exception as err:  # noqa: BLE001 - last resort inside a stream
            log.error("agent failed: %s", type(err).__name__)
            yield sse({"type": "error", "code": "internal_error", "message": "The agent failed unexpectedly."})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


@router.get("/teams/{team_id}/agent/runs", response_model=Envelope[AgentRunsOut])
def list_agent_runs(request: Request, team_id: str, store: Storage = Depends(get_store)):
    load_team(store, team_id)
    return ok(request, {"runs": store.list_agent_runs(team_id)})
