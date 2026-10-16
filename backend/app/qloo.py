"""All Qloo communication lives here.

Endpoints used (confirmed from public hackathon projects that call the hackathon API; the official
docs site blocks automated fetches, so response field names are parsed DEFENSIVELY):
  GET {base}/search            ?query=&types=&take=
  GET {base}/v2/insights       ?filter.type=&signal.interests.entities=&filter.results.entities=
                               &filter.exclude.entities=&take=
  Auth header: X-Api-Key

UNVERIFIED until run with a real key: exact response shape (see _entities_from), the type URNs in
CATEGORY_TYPES (esp. tv_show / videogame / podcast / place / destination), and filter.results.entities behaviour.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

import httpx

from .schemas import EntityRef

CATEGORY_TYPES: dict[str, str] = {
    "music": "urn:entity:artist",
    "movies": "urn:entity:movie",
    "tv": "urn:entity:tv_show",
    "books": "urn:entity:book",
    "brands": "urn:entity:brand",
    "games": "urn:entity:videogame",
    "podcasts": "urn:entity:podcast",
    "places": "urn:entity:place",  # restaurants, cafes, venues
    "destinations": "urn:entity:destination",  # travel
}
TYPE_CATEGORIES = {v: k for k, v in CATEGORY_TYPES.items()}


class QlooError(Exception):
    """Safe-to-show upstream failure. Never carries headers, keys, or raw provider payloads."""

    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _entities_from(payload: Any) -> list[dict]:
    """Accepts {"results": [..]} or {"results": {"entities": [..]}} (both seen in the wild)."""
    if not isinstance(payload, dict):
        raise QlooError("qloo_bad_response", "Qloo returned an unexpected response.")
    results = payload.get("results")
    if isinstance(results, dict):
        results = results.get("entities")
    if results is None:
        return []
    if not isinstance(results, list):
        raise QlooError("qloo_bad_response", "Qloo returned an unexpected response.")
    return [r for r in results if isinstance(r, dict)]


def _to_ref(item: dict) -> Optional[EntityRef]:
    eid = item.get("entity_id") or item.get("id")
    name = item.get("name")
    if not eid or not name:
        return None
    types = item.get("types") or ([item["type"]] if item.get("type") else [])
    affinity = None
    q = item.get("query")
    if isinstance(q, dict) and isinstance(q.get("affinity"), (int, float)):
        affinity = float(q["affinity"])
    return EntityRef(id=str(eid), name=str(name), types=[str(t) for t in types if t], affinity=affinity)


class QlooClient:
    mode = "live"

    def __init__(self, api_key: str, base_url: str = "https://hackathon.api.qloo.com", timeout: float = 10.0,
                 transport: Optional[httpx.AsyncBaseTransport] = None, cache_ttl: float = 600.0):
        self._key = api_key
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport,
                                       headers={"X-Api-Key": api_key, "Accept": "application/json"})
        self._cache: dict[tuple, tuple[float, list[EntityRef]]] = {}
        self._ttl = cache_ttl

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> list[EntityRef]:
        ck = (path, tuple(sorted(params.items())))
        hit = self._cache.get(ck)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        try:
            r = await self._http.get(path, params=params)
        except httpx.TimeoutException:
            raise QlooError("qloo_timeout", "Qloo did not respond in time. Try again.", 504) from None
        except httpx.HTTPError:
            raise QlooError("qloo_unreachable", "Could not reach Qloo.", 502) from None
        if r.status_code == 404:  # Qloo search documents "404 No results"
            refs: list[EntityRef] = []
        elif r.status_code == 429:
            raise QlooError("qloo_rate_limited", "Qloo rate limit reached. Wait a moment and retry.", 429)
        elif r.status_code in (401, 403):
            raise QlooError("qloo_auth_failed", "Qloo rejected the API key. Check QLOO_API_KEY.", 502)
        elif r.status_code >= 400:
            raise QlooError("qloo_error", f"Qloo returned an error (HTTP {r.status_code}).", 502)
        else:
            try:
                payload = r.json()
            except ValueError:
                raise QlooError("qloo_bad_response", "Qloo returned an unreadable response.") from None
            refs = [x for x in (_to_ref(i) for i in _entities_from(payload)) if x]
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[ck] = (time.monotonic() + self._ttl, refs)
        return refs

    async def search(self, query: str, category: Optional[str] = None, take: int = 8) -> list[EntityRef]:
        params: dict[str, Any] = {"query": query, "take": take}
        if category:
            params["types"] = CATEGORY_TYPES[category]
        return await self._get("/search", params)

    async def insights(self, category: str, signal_ids: list[str], results_ids: Optional[list[str]] = None,
                       exclude_ids: Optional[list[str]] = None, take: int = 10) -> list[EntityRef]:
        params: dict[str, Any] = {
            "filter.type": CATEGORY_TYPES[category],
            "signal.interests.entities": ",".join(signal_ids),
            "take": take,
        }
        if results_ids:
            params["filter.results.entities"] = ",".join(results_ids)
        if exclude_ids:
            params["filter.exclude.entities"] = ",".join(exclude_ids)
        return await self._get("/v2/insights", params)


# ---------------- mock adapter (local dev only; NEVER live Qloo data) ----------------
_MOCK_CATALOG: dict[str, list[str]] = {
    "music": ["Tame Impala", "Kendrick Lamar", "Beyonce", "Radiohead", "SZA", "Fleetwood Mac", "Bad Bunny", "Daft Punk", "Burna Boy"],
    "movies": ["Spirited Away", "Parasite", "Everything Everywhere All at Once", "Interstellar", "Amelie", "Dune", "Whiplash", "La La Land"],
    "tv": ["Severance", "The Bear", "Arcane", "Succession", "Fleabag"],
    "books": ["Piranesi", "Dune", "Circe", "Klara and the Sun"],
    "brands": ["Nike", "Patagonia", "Aesop", "IKEA", "LEGO", "Muji", "Sonos", "New Balance"],
    "games": ["Hades", "Celeste", "Stardew Valley", "Disco Elysium"],
    "podcasts": ["Radiolab", "99% Invisible", "Hardcore History"],
    "places": ["Din Tai Fung", "Blue Bottle Coffee", "Shake Shack", "Sweetgreen"],
    "destinations": ["Kyoto", "Lisbon", "Mexico City", "Reykjavik"],
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class MockQlooClient:
    """Deterministic stand-in. Ids start with 'mock:'. Returns NO affinity scores and never
    evaluates filter.results.entities (relationships stay unknown rather than invented)."""

    mode = "mock"

    async def aclose(self) -> None:
        return None

    def _ref(self, category: str, name: str) -> EntityRef:
        return EntityRef(id=f"mock:{category}:{_slug(name)}", name=name, types=[CATEGORY_TYPES[category]])

    async def search(self, query: str, category: Optional[str] = None, take: int = 8) -> list[EntityRef]:
        q = query.strip().lower()
        cats = [category] if category else list(_MOCK_CATALOG)
        out = [self._ref(c, n) for c in cats for n in _MOCK_CATALOG[c] if q in n.lower()]
        return out[:take]

    async def insights(self, category: str, signal_ids: list[str], results_ids: Optional[list[str]] = None,
                       exclude_ids: Optional[list[str]] = None, take: int = 10) -> list[EntityRef]:
        if results_ids:  # scoring a given list is not simulated
            return []
        skip = set(signal_ids) | set(exclude_ids or [])
        names = [self._ref(category, n) for n in _MOCK_CATALOG[category]]
        return [e for e in names if e.id not in skip][: min(take, 3)]
