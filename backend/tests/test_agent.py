import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.llm import AgentError, GeminiClient, from_gemini_parts, to_gemini_contents, to_gemini_tools
from app.main import Settings, create_app

SECRET = "AIza-SECRET-999"


class FakeLlm:
    """Plays back scripted model turns and records what the agent sent."""

    model = "fake-model"

    def __init__(self, turns):
        self.turns, self.calls = list(turns), []

    async def complete(self, system, messages, tools, max_tokens=1500):
        self.calls.append(json.loads(json.dumps(messages)))
        if not self.turns:
            raise AssertionError("agent asked for more turns than scripted")
        return {"content": self.turns.pop(0), "stop_reason": "tool_use"}

    async def aclose(self):
        return None


def use(name, tool_id="t1", **args):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": args}


def make(llm, **settings):
    app = create_app(Settings(database_url=":memory:", static_dir="/nonexistent", **settings), llm_client=llm)
    return TestClient(app)


def team_with_interests(c):
    tid = c.post("/api/teams", json={"name": "Studio"}).json()["data"]["id"]
    c.post(f"/api/teams/{tid}/members", json={"name": "Amara", "interests": [{"name": "Tame Impala", "category": "music"}]})
    c.post(f"/api/teams/{tid}/members", json={"name": "Yuki", "interests": [{"name": "Daft Punk", "category": "music"}]})
    return tid


def events(response):
    return [json.loads(line[6:]) for line in response.text.split("\n\n") if line.startswith("data: ")]


def ask(c, tid, goal="Pick music for our team offsite playlist"):
    return c.post(f"/api/teams/{tid}/agent", json={"goal": goal})


HAPPY = [
    [use("get_team")],
    [use("search_entities", query="Tame Impala", category="music")],
    [use("get_recommendations", category="music", signal_entity_ids=["mock:music:tame-impala"])],
    [use("submit_plan", summary="Go with Kendrick Lamar.", caveats=["Small sample."], recommendations=[
        {"entity_id": "mock:music:kendrick-lamar", "why": "Fits Tame Impala fans.", "supported_by": ["Tame Impala", "Imaginary Band"]},
        {"entity_id": "made-up-id", "why": "Invented by the model."},
    ])],
]


def test_agent_streams_steps_and_returns_only_qloo_grounded_picks():
    with make(FakeLlm(HAPPY)) as c:
        tid = team_with_interests(c)
        r = ask(c, tid)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        ev = events(r)
        assert [e["type"] for e in ev] == ["start", "step", "step", "step", "result"]
        assert [e["tool"] for e in ev[1:4]] == ["get_team", "search_entities", "get_recommendations"]
        result = ev[-1]["data"]
        assert [x["title"] for x in result["recommendations"]] == ["Kendrick Lamar"]  # Qloo's name, not the model's
        assert result["dropped_ungrounded"] == 1
        assert result["recommendations"][0]["supported_by"] == ["Tame Impala"]  # invented support removed
        assert result["qloo_calls"] == 2 and result["model"] == "fake-model" and result["caveats"] == ["Small sample."]
        runs = c.get(f"/api/teams/{tid}/agent/runs").json()["data"]["runs"]
        assert len(runs) == 1 and runs[0]["id"] == result["id"]


def test_agent_rejects_ids_it_never_received_and_continues():
    turns = [
        [use("get_recommendations", category="music", signal_entity_ids=["invented-id"])],
        [use("search_entities", query="Tame Impala", category="music")],
        [use("submit_plan", summary="s", recommendations=[{"entity_id": "mock:music:tame-impala", "why": "w"}])],
    ]
    llm = FakeLlm(turns)
    with make(llm) as c:
        tid = team_with_interests(c)
        ev = events(ask(c, tid))
        assert ev[1]["ok"] is False and "rejected" in ev[1]["summary"]
        error_result = llm.calls[1][-1]["content"][0]
        assert error_result["is_error"] is True and "Unknown entity ids" in error_result["content"]
        assert ev[-1]["type"] == "result"


def test_agent_never_recommends_what_the_team_already_listed():
    turns = [
        [use("get_team")],
        [use("search_entities", query="Tame Impala", category="music")],
        [use("submit_plan", summary="s", recommendations=[{"entity_id": "mock:music:tame-impala", "why": "w"}])],
    ]
    with make(FakeLlm(turns + [[use("submit_plan", summary="s", recommendations=[{"entity_id": "mock:music:tame-impala", "why": "w"}])]])) as c:
        tid = c.post("/api/teams", json={"name": "T"}).json()["data"]["id"]
        c.post(f"/api/teams/{tid}/members", json={"name": "A", "interests": [
            {"name": "Tame Impala", "category": "music", "entity_id": "mock:music:tame-impala"}]})
        ev = events(ask(c, tid))
        assert ev[-1] == {"type": "error", "code": "agent_ungrounded",
                          "message": "The agent could not produce recommendations backed by Qloo results."}


def test_fully_ungrounded_plan_gets_one_retry():
    bad = [use("submit_plan", summary="s", recommendations=[{"entity_id": "nope", "why": "w"}])]
    turns = [[use("search_entities", query="Daft Punk", category="music")], bad,
             [use("submit_plan", summary="s", recommendations=[{"entity_id": "mock:music:daft-punk", "why": "w"}])]]
    with make(FakeLlm(turns)) as c:
        tid = team_with_interests(c)
        assert events(ask(c, tid))[-1]["type"] == "result"


def test_agent_without_submit_plan_is_nudged_then_fails_safely():
    llm = FakeLlm([[{"type": "text", "text": "Here is my answer in prose."}]] * 2)
    with make(llm) as c:
        tid = team_with_interests(c)
        last = events(ask(c, tid))[-1]
        assert last["type"] == "error" and last["code"] == "agent_no_plan"
        assert "submit_plan" in llm.calls[1][-1]["content"]


def test_agent_step_limit():
    turns = [[use("get_team")]] * 8
    with make(FakeLlm(turns)) as c:
        tid = team_with_interests(c)
        assert events(ask(c, tid))[-1]["code"] == "agent_step_limit"


def test_qloo_budget_is_enforced_inside_tools():
    turns = [[use("search_entities", query="Tame Impala", category="music")]] * 3 + [[use("submit_plan", summary="s", recommendations=[{"entity_id": "mock:music:tame-impala", "why": "w"}])]]
    with make(FakeLlm(turns), max_agent_qloo_calls=2) as c:
        tid = team_with_interests(c)
        ev = events(ask(c, tid))
        assert ev[3]["ok"] is False and "budget" in ev[3]["summary"]


# ---------------- request-level guards ----------------
def test_not_configured_is_a_safe_503():
    with make(None) as c:
        tid = team_with_interests(c)
        r = ask(c, tid)
        assert r.status_code == 503 and r.json()["error"]["code"] == "agent_not_configured"
        assert c.get("/api/health").json()["data"]["agent_configured"] is False


def test_agent_needs_interests_and_a_valid_goal():
    with make(FakeLlm([])) as c:
        tid = c.post("/api/teams", json={"name": "Empty"}).json()["data"]["id"]
        assert ask(c, tid).status_code == 422
        assert ask(c, "missing").status_code == 404
        tid2 = team_with_interests(c)
        assert ask(c, tid2, "short").status_code == 422
        assert ask(c, tid2, "x" * 401).status_code == 422
        assert c.get("/api/health").json()["data"]["agent_configured"] is True


def test_daily_cap_and_per_ip_limit():
    with make(FakeLlm(HAPPY * 3), agent_daily_limit=1) as c:
        tid = team_with_interests(c)
        assert ask(c, tid).status_code == 200
        r = ask(c, tid)
        assert r.status_code == 429 and r.json()["error"]["code"] == "agent_daily_limit"
    with make(FakeLlm(HAPPY * 3), agent_rpm=1) as c:
        tid = team_with_interests(c)
        assert ask(c, tid).status_code == 200
        assert ask(c, tid).status_code == 429


def test_only_the_last_five_runs_are_kept():
    one = [[use("search_entities", query="Daft Punk", category="music")],
           [use("submit_plan", summary="s", recommendations=[{"entity_id": "mock:music:daft-punk", "why": "w"}])]]
    with make(FakeLlm(one * 7), agent_rpm=100) as c:
        tid = team_with_interests(c)
        for _ in range(7):
            assert events(ask(c, tid))[-1]["type"] == "result"
        assert len(c.get(f"/api/teams/{tid}/agent/runs").json()["data"]["runs"]) == 5


# ---------------- real Gemini client (mocked HTTP) ----------------
def client_with(handler, **kw):
    return GeminiClient(SECRET, "gemini-test", retry_delay=0, transport=httpx.MockTransport(handler), **kw)


def gemini_reply(*parts):
    return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": list(parts)}}]})


def test_gemini_request_shape_and_parsing():
    import asyncio
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(req.url), req.headers, json.loads(req.content)
        return gemini_reply({"thought": True, "text": "private reasoning"},
                            {"functionCall": {"name": "get_team", "args": {}}, "thoughtSignature": "sig-1"},
                            {"text": "calling"})

    tools = [{"name": "get_team", "description": "d", "input_schema": {"type": "object", "properties": {}}},
             {"name": "search_entities", "description": "d", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}}]
    out = asyncio.run(client_with(handler).complete("sys", [{"role": "user", "content": "hi"}], tools))
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    assert SECRET not in seen["url"] and seen["headers"]["x-goog-api-key"] == SECRET
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "sys"
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    assert body["toolConfig"]["functionCallingConfig"]["mode"] == "ANY"
    declarations = body["tools"][0]["functionDeclarations"]
    assert "parameters" not in declarations[0] and "parameters" in declarations[1]  # empty params omitted
    assert out["content"] == [
        {"type": "tool_use", "id": "call_1", "name": "get_team", "input": {}, "thought_signature": "sig-1"},
        {"type": "text", "text": "calling"},
    ]


def test_message_translation_round_trips_tool_calls_and_signatures():
    messages = [
        {"role": "user", "content": "Team goal: x"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "call_0", "name": "search_entities",
                                           "input": {"query": "q"}, "thought_signature": "sig"}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_0", "is_error": False, "content": json.dumps([{"entity_id": "e1"}])}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "call_0", "name": "get_recommendations", "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_0", "is_error": True, "content": json.dumps({"error": "bad id"})}]},
    ]
    contents = to_gemini_contents(messages)
    assert [c["role"] for c in contents] == ["user", "model", "user", "model", "user"]
    assert contents[1]["parts"][0] == {"functionCall": {"name": "search_entities", "args": {"query": "q"}}, "thoughtSignature": "sig"}
    assert contents[2]["parts"][0]["functionResponse"] == {"name": "search_entities", "response": {"result": [{"entity_id": "e1"}]}}
    assert contents[4]["parts"][0]["functionResponse"] == {"name": "get_recommendations", "response": {"error": "bad id"}}
    assert from_gemini_parts([{"text": ""}, {"functionCall": {"name": "x"}}])[0]["input"] == {}
    assert to_gemini_tools([])[0] == {"functionDeclarations": []}


def test_gemini_retries_once_on_free_tier_rate_limit():
    import asyncio
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, text="quota") if len(calls) == 1 else gemini_reply({"functionCall": {"name": "get_team", "args": {}}})

    out = asyncio.run(client_with(handler).complete("s", [{"role": "user", "content": "x"}], []))
    assert len(calls) == 2 and out["content"][0]["name"] == "get_team"


@pytest.mark.parametrize("handler,code", [
    (lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=req)), "agent_timeout"),
    (lambda req: (_ for _ in ()).throw(httpx.ConnectError("down", request=req)), "agent_unreachable"),
    (lambda req: httpx.Response(429, text="slow"), "agent_rate_limited"),
    (lambda req: httpx.Response(403, json={"echo": SECRET}), "agent_auth_failed"),
    (lambda req: httpx.Response(400, json={"error": {"message": f"API key not valid {SECRET}"}}), "agent_auth_failed"),
    (lambda req: httpx.Response(400, text=f"bad request {SECRET}"), "agent_error"),
    (lambda req: httpx.Response(500, text=f"boom {SECRET}"), "agent_error"),
    (lambda req: httpx.Response(200, text="<html>"), "agent_bad_response"),
    (lambda req: httpx.Response(200, json={"candidates": []}), "agent_bad_response"),
    (lambda req: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}), "agent_blocked"),
])
def test_llm_failures_are_safe_error_events(handler, code):
    app = create_app(Settings(database_url=":memory:", static_dir="/nonexistent"), llm_client=client_with(handler))
    with TestClient(app) as c:
        tid = team_with_interests(c)
        r = ask(c, tid)
        last = events(r)[-1]
        assert last["type"] == "error" and last["code"] == code
        assert SECRET not in r.text and "boom" not in r.text and "bad request" not in r.text
        assert c.get(f"/api/teams/{tid}/agent/runs").json()["data"]["runs"] == []


def test_agent_works_end_to_end_through_the_gemini_client():
    """Full loop: real GeminiClient + scripted HTTP answers + mock Qloo."""
    replies = iter([
        [{"functionCall": {"name": "search_entities", "args": {"query": "Daft Punk", "category": "music"}}}],
        [{"functionCall": {"name": "get_recommendations", "args": {"category": "music", "signal_entity_ids": ["mock:music:daft-punk"]}}}],
        [{"functionCall": {"name": "submit_plan", "args": {"summary": "Go with Kendrick Lamar.", "recommendations": [
            {"entity_id": "mock:music:kendrick-lamar", "why": "Close to Daft Punk.", "supported_by": ["Daft Punk"]}]}}}],
    ])
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return gemini_reply(*next(replies))

    app = create_app(Settings(database_url=":memory:", static_dir="/nonexistent"), llm_client=client_with(handler))
    with TestClient(app) as c:
        tid = team_with_interests(c)
        ev = events(ask(c, tid))
        assert [e["type"] for e in ev] == ["start", "step", "step", "result"]
        assert ev[-1]["data"]["recommendations"][0]["title"] == "Kendrick Lamar"
        sent_back = bodies[1]["contents"][-1]["parts"][0]["functionResponse"]
        assert sent_back["name"] == "search_entities" and sent_back["response"]["result"][0]["entity_id"] == "mock:music:daft-punk"


def test_agent_error_class_has_no_secret():
    assert SECRET not in str(AgentError("agent_error", "safe", 502))
