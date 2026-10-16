"""Connection logic, Qloo analysis and activity templates.

Keeps three kinds of output apart:
- Qloo data:      Connection.source == "qloo", plus suggestions
- local matches:  Connection.source == "local"
- app templates:  activities
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import unicodedata
from itertools import combinations
from typing import Optional

from .qloo import QlooError
from .schemas import CATEGORIES, Connection, ConnectionEntity, EntityRef, Resolution, Suggestion
from .storage import now, short_id

LIMITATIONS = [
    "Connections come only from interests people chose to list. They are conversation starters, "
    "not conclusions about personality, communication style, ethnicity, or workplace behavior.",
    "A missing relationship means unknown, not 'unrelated'.",
]


#interests
def norm(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", ascii_text).split())


def first_name(full_name: str) -> str:
    parts = full_name.split()
    return parts[0] if parts else full_name


def prepare_interests(raw: list[dict]) -> list[dict]:
    """Drops repeats (same entity id or same category + name) and adds server ids."""
    seen_ids: set[str] = set()
    seen_names: set[tuple[str, str]] = set()
    prepared = []
    for item in raw:
        name_key = (item["category"], norm(item["name"]))
        entity_id = item.get("entity_id")
        if name_key in seen_names or (entity_id and entity_id in seen_ids):
            continue
        seen_names.add(name_key)
        if entity_id:
            seen_ids.add(entity_id)
        prepared.append({
            "id": short_id(),
            "name": item["name"],
            "category": item["category"],
            "entity_id": entity_id or None,
            "entity_name": item.get("entity_name") if entity_id else None,
            "source": "qloo" if entity_id else "manual",
        })
    return prepared


def team_signature(team: dict) -> str:
    """Fingerprint of everyone's interests, used to detect a stale saved analysis."""
    parts = [
        (m["id"], sorted((i["category"], norm(i["name"]), i.get("entity_id") or "") for i in m["interests"]))
        for m in team["members"]
    ]
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def _hash_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


# local connections
def _entity_id(interest: dict, resolved: dict[str, EntityRef]) -> Optional[str]:
    if interest.get("entity_id"):
        return interest["entity_id"]
    match = resolved.get(interest["id"])
    return match.id if match else None


def _match_basis(a: dict, b: dict, resolved: dict[str, EntityRef]) -> Optional[str]:
    if a["category"] != b["category"]:
        return None
    id_a, id_b = _entity_id(a, resolved), _entity_id(b, resolved)
    if id_a and id_b:
        return "entity_id" if id_a == id_b else None 
    return "name" if norm(a["name"]) == norm(b["name"]) else None


def _entity(role: str, member: dict, interest: dict, resolved: dict[str, EntityRef]) -> ConnectionEntity:
    return ConnectionEntity(role=role, member_id=member["id"], name=interest["name"], category=interest["category"],
                            entity_id=_entity_id(interest, resolved))


def _shared_interest(a: dict, b: dict, ia: dict, ib: dict, basis: str, resolved: dict[str, EntityRef]) -> Connection:
    auto_matched = any(i["id"] in resolved and not i.get("entity_id") for i in (ia, ib))
    caveat = None
    if basis == "name":
        caveat = "Matched by name only; neither interest is linked to a specific Qloo entity."
    elif auto_matched:
        caveat = "At least one interest was auto-matched to the top Qloo search result."
    return Connection(
        id=_hash_id("shared", a["id"], b["id"], ia["id"], ib["id"]),
        kind="shared_interest", source="local", member_ids=[a["id"], b["id"]], basis=basis, caveat=caveat,
        evidence=f"{first_name(a['name'])} and {first_name(b['name'])} both listed {ia['name']}.",
        entities=[_entity("shared", a, ia, resolved), _entity("shared", b, ib, resolved)],
    )


def _same_category(a: dict, b: dict, category: str, list_a: list[dict], list_b: list[dict],
                   resolved: dict[str, EntityRef]) -> Connection:
    names_a = ", ".join(i["name"] for i in list_a)
    names_b = ", ".join(i["name"] for i in list_b)
    return Connection(
        id=_hash_id("category", a["id"], b["id"], category),
        kind="same_category", source="local", member_ids=[a["id"], b["id"]],
        evidence=f"Both listed {category} interests ({names_a} / {names_b}).",
        caveat="Same category only. No relationship between the specific items is claimed.",
        entities=[_entity("listed", m, i, resolved) for m, items in ((a, list_a), (b, list_b)) for i in items],
    )


def local_connections(team: dict, resolved: Optional[dict[str, EntityRef]] = None) -> list[Connection]:
    resolved = resolved or {}
    connections: list[Connection] = []
    for a, b in combinations(team["members"], 2):
        shared_categories: set[str] = set()
        for ia in a["interests"]:
            for ib in b["interests"]:
                basis = _match_basis(ia, ib, resolved)
                if basis:
                    shared_categories.add(ia["category"])
                    connections.append(_shared_interest(a, b, ia, ib, basis, resolved))
        for category in CATEGORIES:
            list_a = [i for i in a["interests"] if i["category"] == category]
            list_b = [i for i in b["interests"] if i["category"] == category]
            if list_a and list_b and category not in shared_categories:
                connections.append(_same_category(a, b, category, list_a, list_b, resolved))
    return connections


#  Qloo analysis
class CallBudget:
    """Caps how many Qloo requests one analysis may make."""

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.truncated = False

    def take(self) -> bool:
        if self.used >= self.limit:
            self.truncated = True
            return False
        self.used += 1
        return True


class QlooRun:
    """Runs budgeted, concurrency-limited Qloo calls and collects failures."""

    def __init__(self, client, max_calls: int):
        self.client = client
        self.budget = CallBudget(max_calls)
        self.errors: list[QlooError] = []
        self._slots = asyncio.Semaphore(4)

    async def call(self, make_request):
        if not self.budget.take():
            return None
        async with self._slots:
            try:
                return await make_request()
            except QlooError as err:
                self.errors.append(err)
                return None


async def _resolve_interests(team: dict, run: QlooRun) -> tuple[list[Resolution], dict[str, EntityRef]]:
    """Matches typed (unlinked) interests to the top Qloo search result."""
    pending = [(m, i) for m in team["members"] for i in m["interests"] if not i.get("entity_id")][:20]
    hits = await asyncio.gather(*[
        run.call(lambda i=i: run.client.search(i["name"], i["category"], take=1)) for _, i in pending
    ])
    resolutions, by_interest = [], {}
    for (member, interest), found in zip(pending, hits):
        if found:
            by_interest[interest["id"]] = found[0]
            resolutions.append(Resolution(member_id=member["id"], interest_id=interest["id"],
                                          name=interest["name"], entity=found[0]))
    return resolutions, by_interest


def _linked_interests(team: dict, resolved: dict[str, EntityRef]) -> dict[str, list[dict]]:
    """Per member: interests that have a Qloo entity id (picked or auto-matched), with it as '_eid'."""
    return {
        m["id"]: [{**i, "_eid": _entity_id(i, resolved)} for i in m["interests"] if _entity_id(i, resolved)]
        for m in team["members"]
    }


def _affinity_jobs(team: dict, linked: dict[str, list[dict]]) -> list[tuple]:
    """One job per ordered member pair and category: score Y's picks using X's picks as the signal."""
    jobs = []
    for a, b in combinations(team["members"], 2):
        for source, target in ((a, b), (b, a)):
            signal = linked[source["id"]]
            if not signal or not linked[target["id"]]:
                continue
            signal_ids = list(dict.fromkeys(i["_eid"] for i in signal))[:5]
            for category in CATEGORIES:
                picks = [i for i in linked[target["id"]] if i["category"] == category and i["_eid"] not in signal_ids]
                if picks:
                    jobs.append((source, target, signal, picks, signal_ids, category))
    return jobs


def _affinity_connections(job: tuple, scored: list[EntityRef]) -> list[Connection]:
    source, target, signal, picks, signal_ids, category = job
    by_id = {e.id: e for e in scored}
    signal_picks = [i for i in signal if i["_eid"] in signal_ids][:5]
    signal_names = ", ".join(i["name"] for i in signal_picks)
    connections = []
    for pick in picks:
        returned = by_id.get(pick["_eid"])
        if not returned:
            continue
        evidence = (f"Qloo returned {pick['name']} when scoring {first_name(target['name'])}'s {category} picks "
                    f"against {first_name(source['name'])}'s picks ({signal_names}).")
        entities = [
            ConnectionEntity(role="signal", member_id=source["id"], name=s["name"], category=s["category"], entity_id=s["_eid"])
            for s in signal_picks
        ] + [ConnectionEntity(role="result", member_id=target["id"], name=returned.name, category=category,
                              entity_id=returned.id, affinity=returned.affinity)]
        connections.append(Connection(
            id=_hash_id("qloo", source["id"], target["id"], pick["id"]),
            kind="qloo_affinity", source="qloo", member_ids=[source["id"], target["id"]], evidence=evidence,
            caveat="Affinity is shown exactly as Qloo returned it, if at all. It says nothing about how people will work together.",
            entities=entities,
        ))
    return connections


async def _pair_affinities(team: dict, linked: dict[str, list[dict]], run: QlooRun) -> list[Connection]:
    jobs = _affinity_jobs(team, linked)

    async def score(job):
        _, _, _, picks, signal_ids, category = job
        ids = list(dict.fromkeys(p["_eid"] for p in picks))[:10]
        return job, await run.call(lambda: run.client.insights(category, signal_ids, results_ids=ids, take=len(ids)))

    connections = []
    for job, scored in await asyncio.gather(*[score(j) for j in jobs]):
        if scored:
            connections.extend(_affinity_connections(job, scored))
    return connections


async def _team_suggestions(linked: dict[str, list[dict]], categories: list[str], run: QlooRun) -> list[Suggestion]:
    """Asks Qloo what fits the team's combined picks, most widely shared picks first."""
    picks = [i for items in linked.values() for i in items]
    counts: dict[str, int] = {}
    for pick in picks:
        counts[pick["_eid"]] = counts.get(pick["_eid"], 0) + 1
    signal_ids = sorted(counts, key=lambda k: -counts[k])[:8]
    if not signal_ids:
        return []
    names = {p["_eid"]: p["name"] for p in picks}
    signal_refs = [EntityRef(id=k, name=names[k]) for k in signal_ids]

    async def suggest(category):
        return category, await run.call(lambda: run.client.insights(category, signal_ids, exclude_ids=signal_ids, take=5))

    results = await asyncio.gather(*[suggest(c) for c in categories])
    return [Suggestion(category=c, signal_entities=signal_refs, entities=found) for c, found in results if found]


async def analyze(team: dict, client, include_suggestions: bool, suggest_categories: list[str],
                  max_calls: int = 40) -> dict:
    """Runs the full Qloo workflow. Raises only if every request failed."""
    run = QlooRun(client, max_calls)
    limitations = list(LIMITATIONS)

    resolutions, resolved = await _resolve_interests(team, run)
    connections = local_connections(team, resolved)
    linked = _linked_interests(team, resolved)

    if client.mode == "live":
        connections += await _pair_affinities(team, linked, run)
    else:
        limitations.append("Mock mode: affinities between members are not simulated, so none are shown. Set QLOO_API_KEY for live data.")

    suggestions = await _team_suggestions(linked, suggest_categories, run) if include_suggestions else []

    if not any(linked.values()):
        limitations.append("No interests could be linked to Qloo entities. Pick Qloo search results when adding interests.")
    if run.budget.truncated:
        limitations.append(f"Qloo request budget ({max_calls}) reached; some pairs were not analysed.")
    if run.errors and len(run.errors) == run.budget.used:
        raise run.errors[0]
    if run.errors:
        limitations.append(f"{len(run.errors)} Qloo request(s) failed ({run.errors[0].code}); results may be incomplete.")

    return {
        "connections": [c.model_dump() for c in connections],
        "suggestions": [s.model_dump() for s in suggestions],
        "resolutions": [r.model_dump() for r in resolutions],
        "analysis": {"ran_at": now(), "mode": client.mode, "qloo_calls": run.budget.used,
                     "truncated": run.budget.truncated},
        "limitations": limitations,
    }


# brainstorming templates
TEMPLATES = [
    ("The {category} exchange",
     "Use what {names} share around {topic} as raw material for one small, concrete team artifact this week.",
     ["Each person names three {category} picks the others have not tried. Circle the most surprising one.",
      "Start from {topic}: what would a mash-up of each person's take on it look like?",
      "Draft a recommendation trade: one pick from each person for each other person."]),
    ("Crossover brief",
     "Turn the overlap between {names} around {topic} into a short creative brief the team can react to.",
     ["In five minutes, sketch a concept that combines your perspectives on {topic}.",
      "Why does {topic} work for each of you? List two reasons each.",
      "Pitch the concept to the team in two sentences, as if it were a real project."]),
    ("Tiny tradition",
     "Design a low-effort, repeatable team ritual inspired by {topic}, shared by {names}.",
     ["Decide the ritual: how often, how long, who starts.",
      "Make {topic} part of the first session somehow.",
      "Write a one-line invitation the whole team would actually accept."]),
]


def build_activity(team: dict, connections: list[Connection]) -> dict:
    members = {m["id"]: m for m in team["members"]}
    connection_ids = [c.id for c in connections]
    member_ids = list(dict.fromkeys(mid for c in connections for mid in c.member_ids))

    topics: list[str] = []
    for c in connections:
        topics += [c.entities[0].name] if c.kind == "shared_interest" else [e.name for e in c.entities if e.role == "result"]

    values = {
        "category": connections[0].entities[0].category,
        "names": " and ".join(first_name(members[m]["name"]) for m in member_ids if m in members) or "the team",
        "topic": " / ".join(dict.fromkeys(topics)) or "your shared interests",
    }
    pick = int(hashlib.sha1("|".join(connection_ids).encode()).hexdigest(), 16) % len(TEMPLATES)
    title, objective, prompts = TEMPLATES[pick]
    return {
        "id": _hash_id("activity", *connection_ids),
        "title": title.format(**values).capitalize(),
        "objective": objective.format(**values),
        "prompts": [p.format(**values) for p in prompts],
        "connection_ids": connection_ids,
        "member_ids": member_ids,
        "basis": "application_template",
        "created_at": now(),
    }
