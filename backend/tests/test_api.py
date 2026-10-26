import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import Settings, create_app
from app.qloo import QlooClient, QlooError

SECRET = "sk-test-SECRET-123"


def settings(**kw):
    return Settings(database_url=":memory:", static_dir="/nonexistent", **kw)


def mock_client(handler=None):
    """TestClient on the mock Qloo adapter (no key)."""
    return TestClient(create_app(settings()))


def live_client(handler, **kw):
    q = QlooClient(SECRET, transport=httpx.MockTransport(handler), **kw)
    return TestClient(create_app(settings(qloo_api_key=SECRET), qloo_client=q))


def mk_team(c, name="Studio"):
    return c.post("/api/teams", json={"name": name}).json()["data"]["id"]


def mk_member(c, tid, name, interests=()):
    r = c.post(f"/api/teams/{tid}/members", json={"name": name, "interests": list(interests)})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def I(name, category="music", entity_id=None):
    d = {"name": name, "category": category}
    if entity_id:
        d["entity_id"], d["entity_name"] = entity_id, name
    return d


# ---------------- health / mode / credentials ----------------
def test_health_mock_mode():
    with mock_client() as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"] == {"status": "ok", "service": "culturesync-api", "qloo_configured": False,
                                "mode": "mock", "agent_configured": False, "qloo_reachable": None, "qloo_error": None}
        assert body["meta"]["mode"] == "mock"


def test_health_live_configured_never_leaks_key():
    with live_client(lambda req: httpx.Response(200, json={"results": []})) as c:
        r = c.get("/api/health")
        assert r.json()["data"]["qloo_configured"] is True
        assert r.json()["data"]["mode"] == "live"
        assert SECRET not in r.text


def test_health_probe_live_ok_and_failure():
    with live_client(lambda req: httpx.Response(200, json={"results": []})) as c:
        assert c.get("/api/health?probe=true").json()["data"]["qloo_reachable"] is True
    with live_client(lambda req: httpx.Response(401, json={"message": SECRET})) as c:
        d = c.get("/api/health?probe=true").json()["data"]
        assert d["qloo_reachable"] is False and d["qloo_error"] == "qloo_auth_failed"


def test_missing_key_means_mock_never_live():
    with mock_client() as c:
        r = c.get("/api/entities/search", params={"q": "tame", "category": "music"})
        assert r.status_code == 200
        assert r.json()["meta"]["mode"] == "mock"
        assert r.json()["data"]["results"][0]["id"].startswith("mock:")


# ---------------- validation ----------------
@pytest.mark.parametrize("path,body", [
    ("/api/teams", {"name": ""}),
    ("/api/teams", {"name": "   "}),
    ("/api/teams", {"name": "x" * 81}),
    ("/api/teams", {}),
])
def test_team_validation(path, body):
    with mock_client() as c:
        r = c.post(path, json=body)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"
        assert r.json()["data"] is None


def test_member_and_interest_validation():
    with mock_client() as c:
        tid = mk_team(c)
        bad = [
            {"name": "", "interests": []},
            {"name": "A", "interests": [{"name": "X", "category": "food"}]},  # unsupported category
            {"name": "A", "interests": [{"name": "", "category": "music"}]},
            {"name": "A", "interests": [I(f"n{i}") for i in range(31)]},
        ]
        for b in bad:
            assert c.post(f"/api/teams/{tid}/members", json=b).status_code == 422


def test_search_validation():
    with mock_client() as c:
        assert c.get("/api/entities/search", params={"q": "a"}).status_code == 422
        assert c.get("/api/entities/search", params={"q": "abc", "category": "nope"}).status_code == 422


# ---------------- team + member CRUD ----------------
def test_team_member_crud_and_dedupe():
    with mock_client() as c:
        tid = mk_team(c, "  Studio   North ")
        t = c.get(f"/api/teams/{tid}").json()["data"]
        assert t["name"] == "Studio North" and t["members"] == []
        m = mk_member(c, tid, "Amara Okafor", [I("Tame Impala"), I("tame  impala"), I("Ramen", "brands")])
        assert [i["name"] for i in m["interests"]] == ["Tame Impala", "Ramen"]  # deduped
        assert m["interests"][0]["source"] == "manual"

        r = c.patch(f"/api/teams/{tid}/members/{m['id']}",
                    json={"name": "Amara O.", "interests": [I("Tame Impala"), I("SZA")]})
        assert r.status_code == 200
        upd = r.json()["data"]
        assert upd["name"] == "Amara O." and [i["name"] for i in upd["interests"]] == ["Tame Impala", "SZA"]
        assert upd["interests"][0]["id"] == m["interests"][0]["id"]  # stable id for unchanged interest

        assert c.patch(f"/api/teams/{tid}", json={"name": "Renamed", "description": "d"}).json()["data"]["name"] == "Renamed"

        r = c.delete(f"/api/teams/{tid}/members/{m['id']}")
        assert r.status_code == 200 and r.json()["data"]["members"] == []
        assert c.delete(f"/api/teams/{tid}/members/{m['id']}").status_code == 404
        assert c.patch(f"/api/teams/{tid}/members/nope", json={"name": "x"}).status_code == 404


def test_unknown_team_is_safe_404():
    with mock_client() as c:
        r = c.get("/api/teams/does-not-exist")
        assert r.status_code == 404
        assert r.json() == {"data": None, "meta": {"source": "local", "mode": "mock"},
                            "error": {"code": "not_found", "message": "Team not found."}}
        assert c.get("/api/nope").status_code == 404


def test_member_limit():
    with mock_client() as c:
        tid = mk_team(c)
        for i in range(12):
            mk_member(c, tid, f"M{i}")
        r = c.post(f"/api/teams/{tid}/members", json={"name": "extra"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "limit_reached"


def test_data_persists_in_storage_layer():
    with mock_client() as c:
        tid = mk_team(c)
        mk_member(c, tid, "A", [I("Radiohead")])
        assert c.get(f"/api/teams/{tid}").json()["data"]["members"][0]["interests"][0]["name"] == "Radiohead"


# ---------------- connection logic ----------------
def connections(c, tid):
    r = c.get(f"/api/teams/{tid}/connections")
    assert r.status_code == 200
    return r.json()["data"]


def test_insufficient_data_states():
    with mock_client() as c:
        tid = mk_team(c)
        d = connections(c, tid)
        assert d["connections"] == [] and d["analysis"] is None and d["limitations"]
        mk_member(c, tid, "Solo", [I("Radiohead")])
        assert connections(c, tid)["connections"] == []
        mk_member(c, tid, "Empty")
        assert connections(c, tid)["connections"] == []


def test_shared_interest_by_name_and_category_bridge():
    with mock_client() as c:
        tid = mk_team(c)
        a = mk_member(c, tid, "Amara Okafor", [I("Tame Impala"), I("Radiohead"), I("Dune", "movies")])
        b = mk_member(c, tid, "Yuki Tanaka", [I("tame impala"), I("Daft Punk"), I("Dune", "books")])
        conns = connections(c, tid)["connections"]
        shared = [x for x in conns if x["kind"] == "shared_interest"]
        assert len(shared) == 1
        assert shared[0]["basis"] == "name" and shared[0]["source"] == "local"
        assert shared[0]["caveat"] and set(shared[0]["member_ids"]) == {a["id"], b["id"]}
        # "Dune" the movie vs "Dune" the book must NOT match; no shared movie/book category either
        assert not any("Dune" in x["evidence"] and x["kind"] == "shared_interest" for x in conns)
        # music is a shared category via an exact match, so no extra same_category row for it
        assert not any(x["kind"] == "same_category" and x["entities"][0]["category"] == "music" for x in conns)


def test_same_category_is_not_a_relationship_claim():
    with mock_client() as c:
        tid = mk_team(c)
        mk_member(c, tid, "A", [I("Radiohead")])
        mk_member(c, tid, "B", [I("SZA")])
        conn = connections(c, tid)["connections"][0]
        assert conn["kind"] == "same_category"
        assert "No relationship" in conn["caveat"]


def test_same_name_different_entity_ids_do_not_match():
    with mock_client() as c:
        tid = mk_team(c)
        mk_member(c, tid, "A", [I("Phoenix", "music", "id-1")])
        mk_member(c, tid, "B", [I("Phoenix", "music", "id-2")])
        kinds = [x["kind"] for x in connections(c, tid)["connections"]]
        assert "shared_interest" not in kinds
        mk_member(c, tid, "C", [I("Phoenix (band)", "music", "id-1")])
        shared = [x for x in connections(c, tid)["connections"] if x["kind"] == "shared_interest"]
        assert len(shared) == 1 and shared[0]["basis"] == "entity_id"


# ---------------- Qloo error mapping ----------------
@pytest.mark.parametrize("handler,status,code", [
    (lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=req)), 504, "qloo_timeout"),
    (lambda req: (_ for _ in ()).throw(httpx.ConnectError("down", request=req)), 502, "qloo_unreachable"),
    (lambda req: httpx.Response(429, text="slow down"), 429, "qloo_rate_limited"),
    (lambda req: httpx.Response(401, json={"echo": SECRET}), 502, "qloo_auth_failed"),
    (lambda req: httpx.Response(500, text=f"boom {SECRET}"), 502, "qloo_error"),
    (lambda req: httpx.Response(200, text="<html>not json</html>"), 502, "qloo_bad_response"),
    (lambda req: httpx.Response(200, json=["weird"]), 502, "qloo_bad_response"),
])
def test_qloo_failures_are_safe(handler, status, code):
    with live_client(handler) as c:
        r = c.get("/api/entities/search", params={"q": "tame", "category": "music"})
        assert r.status_code == status
        body = r.json()
        assert body["error"]["code"] == code and body["data"] is None
        assert SECRET not in r.text and "boom" not in r.text and "html" not in r.text.lower()


def test_search_404_is_empty_and_both_result_shapes_parse():
    with live_client(lambda req: httpx.Response(404, json={"message": "No results"})) as c:
        assert c.get("/api/entities/search", params={"q": "zzz"}).json()["data"]["results"] == []
    shapes = [
        {"results": [{"entity_id": "E1", "name": "Tame Impala", "types": ["urn:entity:artist"]}]},
        {"results": {"entities": [{"entity_id": "E1", "name": "Tame Impala", "types": ["urn:entity:artist"]}]}},
    ]
    for payload in shapes:
        with live_client(lambda req, p=payload: httpx.Response(200, json=p)) as c:
            res = c.get("/api/entities/search", params={"q": "tame"}).json()
            assert res["meta"] == {"source": "qloo", "mode": "live"}
            assert res["data"]["results"][0]["id"] == "E1"


def test_live_request_shape_and_cache():
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        return httpx.Response(200, json={"results": [{"entity_id": "E1", "name": "Tame Impala"}]})

    with live_client(handler) as c:
        c.get("/api/entities/search", params={"q": "tame", "category": "music"})
        c.get("/api/entities/search", params={"q": "tame", "category": "music"})
    assert len(seen) == 1  # second call served from cache
    assert seen[0].headers["x-api-key"] == SECRET
    assert seen[0].url.path == "/search"
    assert seen[0].url.params["types"] == "urn:entity:artist" and seen[0].url.params["query"] == "tame"
    assert str(seen[0].url).startswith("https://hackathon.api.qloo.com/search")


def test_rate_limit_on_qloo_endpoints():
    app = create_app(Settings(database_url=":memory:", static_dir="/nonexistent", qloo_rpm=2))
    with TestClient(app) as c:
        codes = [c.get("/api/entities/search", params={"q": "tame"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------------- analysis ----------------
def qloo_handler(req: httpx.Request):
    p = req.url.path
    q = req.url.params
    if p == "/search":
        name = q["query"]
        table = {"Tame Impala": ("A1", "urn:entity:artist"), "Parasite": ("M1", "urn:entity:movie"),
                 "Whiplash": ("M2", "urn:entity:movie")}
        eid, typ = table[name]
        return httpx.Response(200, json={"results": [{"entity_id": eid, "name": name, "types": [typ]}]})
    if p == "/v2/insights":
        if "filter.results.entities" in q:
            asked = q["filter.results.entities"].split(",")
            # Qloo scores only Parasite; Whiplash is left out => unknown
            hits = [{"entity_id": "M1", "name": "Parasite", "query": {"affinity": 0.83}}] if "M1" in asked else []
            return httpx.Response(200, json={"results": {"entities": hits}})
        return httpx.Response(200, json={"results": {"entities": [{"entity_id": "S1", "name": "Suggested Thing"}]}})
    return httpx.Response(404)


def test_live_analysis_provenance_and_unknowns():
    calls = []

    def handler(req):
        calls.append(req)
        return qloo_handler(req)

    with live_client(handler) as c:
        tid = mk_team(c)
        a = mk_member(c, tid, "Amara", [I("Tame Impala", "music", "A1")])
        b = mk_member(c, tid, "Diego", [I("Parasite", "movies"), I("Whiplash", "movies")])  # unresolved -> auto-resolved
        r = c.post(f"/api/teams/{tid}/insights", json={"suggest_categories": ["movies"]})
        assert r.status_code == 200, r.text
        assert r.json()["meta"] == {"source": "qloo", "mode": "live"}
        d = r.json()["data"]
        assert d["analysis"]["mode"] == "live" and d["analysis"]["qloo_calls"] == len(calls)
        assert {x["name"] for x in d["resolutions"]} == {"Parasite", "Whiplash"}  # shown to the user, not persisted
        q = [x for x in d["connections"] if x["kind"] == "qloo_affinity"]
        assert len(q) == 1  # Whiplash was not scored => unknown, not a negative
        conn = q[0]
        assert conn["source"] == "qloo" and conn["member_ids"] == [a["id"], b["id"]]
        res = [e for e in conn["entities"] if e["role"] == "result"][0]
        sig = [e for e in conn["entities"] if e["role"] == "signal"][0]
        assert res["name"] == "Parasite" and res["affinity"] == 0.83 and sig["name"] == "Tame Impala"
        assert d["suggestions"][0]["entities"][0]["name"] == "Suggested Thing"
        assert d["suggestions"][0]["signal_entities"]  # provenance of the suggestion
        # persisted interests were NOT silently rewritten by auto-resolution
        t = c.get(f"/api/teams/{tid}").json()["data"]
        assert all(i["entity_id"] is None for i in t["members"][1]["interests"])
        # GET connections returns the saved analysis while fresh...
        g = c.get(f"/api/teams/{tid}/connections").json()["data"]
        assert g["analysis"] and any(x["kind"] == "qloo_affinity" for x in g["connections"])
        # ...and drops Qloo results (flagged stale) once the team changes
        c.post(f"/api/teams/{tid}/members", json={"name": "New"})
        g = c.get(f"/api/teams/{tid}/connections").json()["data"]
        assert g["analysis"] is None and g["analysis_stale"] is True
        assert not any(x["kind"] == "qloo_affinity" for x in g["connections"])


def test_analysis_fails_safely_when_qloo_down():
    with live_client(lambda req: httpx.Response(429, text="x")) as c:
        tid = mk_team(c)
        mk_member(c, tid, "A", [I("Tame Impala", "music", "A1")])
        mk_member(c, tid, "B", [I("Parasite", "movies", "M1")])
        r = c.post(f"/api/teams/{tid}/insights", json={})
        assert r.status_code == 429 and r.json()["error"]["code"] == "qloo_rate_limited"


def test_budget_cap_marks_truncated():
    import asyncio
    from app import services
    from app.qloo import MockQlooClient

    class Live(MockQlooClient):
        mode = "live"

        async def insights(self, *a, **k):
            return []

    team = {"members": [{"id": f"m{n}", "name": f"M{n}", "interests": [
        {"id": f"i{n}", "name": f"X{n}", "category": "music", "entity_id": f"e{n}"},
        {"id": f"j{n}", "name": f"Y{n}", "category": "movies", "entity_id": f"f{n}"}]} for n in range(5)]}
    out = asyncio.run(services.analyze(team, Live(), True, ["music"], max_calls=5))
    assert out["analysis"]["truncated"] is True and out["analysis"]["qloo_calls"] == 5
    assert any("budget" in x for x in out["limitations"])


def test_mock_mode_analysis_is_labeled_and_invents_nothing():
    with mock_client() as c:
        tid = mk_team(c)
        mk_member(c, tid, "A", [I("Radiohead")])
        mk_member(c, tid, "B", [I("Tame Impala")])
        r = c.post(f"/api/teams/{tid}/insights", json={})
        assert r.status_code == 200
        assert r.json()["meta"]["mode"] == "mock" and r.json()["data"]["analysis"]["mode"] == "mock"
        d = r.json()["data"]
        assert not any(x["kind"] == "qloo_affinity" for x in d["connections"])
        assert any("Mock mode" in x for x in d["limitations"])
        assert all(e["affinity"] is None for s in d["suggestions"] for e in s["entities"])
        assert all(e["id"].startswith("mock:") for s in d["suggestions"] for e in s["entities"])


# ---------------- activities + ideas ----------------
def test_activities_and_ideas_flow():
    with mock_client() as c:
        tid = mk_team(c)
        mk_member(c, tid, "Amara Okafor", [I("Tame Impala"), I("Nike", "brands")])
        mk_member(c, tid, "Yuki Tanaka", [I("Tame Impala"), I("Muji", "brands")])
        conns = connections(c, tid)["connections"]
        shared = next(x for x in conns if x["kind"] == "shared_interest")
        cat = next(x for x in conns if x["kind"] == "same_category")

        assert c.post(f"/api/teams/{tid}/activities", json={"connection_ids": [cat["id"]]}).status_code == 422
        assert c.post(f"/api/teams/{tid}/activities", json={"connection_ids": ["nope"]}).status_code == 404
        assert c.post(f"/api/teams/{tid}/activities", json={"connection_ids": []}).status_code == 422

        r = c.post(f"/api/teams/{tid}/activities", json={"connection_ids": [shared["id"]]})
        assert r.status_code == 201
        act = r.json()["data"]
        assert act["basis"] == "application_template" and "Tame Impala" in " ".join(act["prompts"] + [act["objective"]])
        again = c.post(f"/api/teams/{tid}/activities", json={"connection_ids": [shared["id"]]}).json()["data"]
        assert again["id"] == act["id"] and again["prompts"] == act["prompts"]  # deterministic
        assert len(c.get(f"/api/teams/{tid}/activities").json()["data"]) == 1

        i = c.post(f"/api/teams/{tid}/ideas", json={"text": "  Listening party  ", "activity_id": act["id"]})
        assert i.status_code == 201 and i.json()["data"]["text"] == "Listening party"
        assert c.post(f"/api/teams/{tid}/ideas", json={"text": "   "}).status_code == 422
        assert c.post(f"/api/teams/{tid}/ideas", json={"text": "x" * 501}).status_code == 422
        assert len(c.get(f"/api/teams/{tid}/ideas").json()["data"]) == 1
        assert c.delete(f"/api/teams/{tid}/ideas/{i.json()['data']['id']}").status_code == 200
        assert c.delete(f"/api/teams/{tid}/ideas/nope").status_code == 404

        c.post(f"/api/teams/{tid}/ideas", json={"text": "keep?", "activity_id": act["id"]})
        assert c.delete(f"/api/teams/{tid}/activities/{act['id']}").status_code == 200
        assert c.get(f"/api/teams/{tid}/ideas").json()["data"] == []  # ideas of a deleted activity go too


# ---------------- safety ----------------
def test_unhandled_error_is_generic_and_credential_free():
    app = create_app(settings(qloo_api_key=SECRET), qloo_client=QlooClient(SECRET, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))))

    @app.get("/boom")
    def boom():
        raise RuntimeError(f"db password {SECRET}")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
        assert r.status_code == 500
        assert r.json()["error"] == {"code": "internal_error", "message": "Something went wrong on the server."}
        assert SECRET not in r.text and "password" not in r.text


def test_no_endpoint_response_contains_the_key():
    with live_client(qloo_handler) as c:
        tid = mk_team(c)
        mk_member(c, tid, "A", [I("Tame Impala", "music", "A1")])
        mk_member(c, tid, "B", [I("Parasite", "movies", "M1")])
        texts = [
            c.get("/api/health").text, c.get(f"/api/teams/{tid}").text, c.get(f"/api/teams/{tid}/connections").text,
            c.post(f"/api/teams/{tid}/insights", json={}).text, c.get("/api/entities/search", params={"q": "Parasite"}).text,
            c.get("/openapi.json").text,
        ]
        assert all(SECRET not in t for t in texts)


def test_cors_uses_frontend_origin():
    app = create_app(Settings(database_url=":memory:", static_dir="/nonexistent", frontend_origin="https://app.example.com"))
    with TestClient(app) as c:
        ok = c.get("/api/health", headers={"Origin": "https://app.example.com"})
        bad = c.get("/api/health", headers={"Origin": "https://evil.example.com"})
        assert ok.headers.get("access-control-allow-origin") == "https://app.example.com"
        assert "access-control-allow-origin" not in bad.headers


# ---------------- audit regressions ----------------
def test_entity_id_must_be_a_plain_identifier():
    with mock_client() as c:
        tid = mk_team(c)
        for bad in ["a,b", "id with space", "x&take=999", ""]:
            body = {"name": "A", "interests": [{"name": "X", "category": "music", "entity_id": bad}]}
            assert c.post(f"/api/teams/{tid}/members", json=body).status_code == 422


def test_member_order_is_stable_after_delete():
    with mock_client() as c:
        tid = mk_team(c)
        ids = [mk_member(c, tid, n)["id"] for n in ("A", "B", "C")]
        c.delete(f"/api/teams/{tid}/members/{ids[1]}")
        mk_member(c, tid, "D")
        names = [m["name"] for m in c.get(f"/api/teams/{tid}").json()["data"]["members"]]
        assert names == ["A", "C", "D"]


def test_oversized_body_is_rejected():
    with mock_client() as c:
        r = c.post("/api/teams", content=b"x" * 70_000, headers={"content-type": "application/json"})
        assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_long_qloo_titles_are_accepted_up_to_200_chars():
    long_title = ("A Very Long Book Title: " + "and the subtitle goes on " * 5).strip()  # ~150 chars
    with mock_client() as c:
        tid = mk_team(c)
        m = mk_member(c, tid, "A", [I(long_title, "books", "book-1")])
        assert m["interests"][0]["name"] == long_title
        assert c.post(f"/api/teams/{tid}/members", json={"name": "B", "interests": [I("x" * 201)]}).status_code == 422
