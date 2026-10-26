"""Gemini client (HTTPX) for the agent. Works with the free tier.

The agent keeps its messages in a simple block format (text / tool_use / tool_result); this module
translates that to and from Gemini's generateContent API.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import httpx


class AgentError(Exception):
    """Safe-to-show failure of the agent or its LLM. Never carries keys or provider payloads."""

    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _role(role: str) -> str:
    return "user" if role == "user" else "model"


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return {"text": text}


def to_gemini_contents(messages: list[dict]) -> list[dict]:
    tool_names: dict[str, str] = {}  # tool_use id -> tool name, needed for functionResponse
    contents = []
    for message in messages:
        if isinstance(message["content"], str):
            contents.append({"role": _role(message["role"]), "parts": [{"text": message["content"]}]})
            continue
        parts = []
        for block in message["content"]:
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                parts.append({"text": block["text"]})
            elif kind == "tool_use":
                tool_names[block["id"]] = block["name"]
                part: dict[str, Any] = {"functionCall": {"name": block["name"], "args": block.get("input") or {}}}
                if block.get("thought_signature"):
                    part["thoughtSignature"] = block["thought_signature"]
                parts.append(part)
            elif kind == "tool_result":
                payload = _parse_json(block.get("content", ""))
                if block.get("is_error"):
                    response = {"error": payload.get("error", "failed") if isinstance(payload, dict) else str(payload)}
                else:
                    response = {"result": payload}
                parts.append({"functionResponse": {"name": tool_names.get(block.get("tool_use_id", ""), "unknown"), "response": response}})
        if parts:
            contents.append({"role": _role(message["role"]), "parts": parts})
    return contents


def to_gemini_tools(tools: list[dict]) -> list[dict]:
    declarations = []
    for tool in tools:
        declaration = {"name": tool["name"], "description": tool["description"]}
        schema = tool.get("input_schema") or {}
        if schema.get("properties"):  # Gemini rejects an empty parameters object
            declaration["parameters"] = schema
        declarations.append(declaration)
    return [{"functionDeclarations": declarations}]


def from_gemini_parts(parts: list[dict], model: str = "") -> list[dict]:
    blocks = []
    for index, part in enumerate(parts):
        if part.get("thought"):
            continue
        call = part.get("functionCall")
        if call:
            block = {"type": "tool_use", "id": f"call_{index}", "name": call.get("name", ""),
                     "input": call.get("args") or {}, "gemini_model": model}
            if part.get("thoughtSignature"):
                block["thought_signature"] = part["thoughtSignature"]
            blocks.append(block)
        elif part.get("text"):
            blocks.append({"type": "text", "text": part["text"]})
    return blocks


def retry_after_seconds(response: httpx.Response) -> Optional[float]:
    """How long Google asks us to wait on a 429 (Retry-After header, or retryDelay like '21s' in the body)."""
    header = response.headers.get("retry-after", "")
    if header.replace(".", "", 1).isdigit():
        return float(header)
    try:
        for detail in response.json().get("error", {}).get("details", []):
            delay = detail.get("retryDelay") if isinstance(detail, dict) else None
            if isinstance(delay, str) and delay.endswith("s"):
                return float(delay[:-1])
    except (ValueError, AttributeError):
        pass
    return None


def pinned_model(messages: list[dict]) -> Optional[str]:
    """The model that wrote earlier tool calls. Its thought signatures only work with that model."""
    for message in reversed(messages):
        if isinstance(message["content"], list):
            for block in message["content"]:
                if block.get("type") == "tool_use" and block.get("gemini_model"):
                    return block["gemini_model"]
    return None


class GeminiClient:
    """`model` may be a comma-separated list: later models are fallbacks if earlier ones are gone or overloaded."""

    def __init__(self, api_key: str, model: str, timeout: float = 30.0, retry_delay: float = 3.0, attempts: int = 3,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        self.models = [m.strip().removeprefix("models/") for m in model.split(",") if m.strip()]
        self.model = self.models[0]
        self._retry_delay = retry_delay
        self._attempts = attempts
        self._http = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com", timeout=timeout, transport=transport,
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},  # key stays out of the URL
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _call_model(self, model: str, body: dict, pinned: bool = False) -> dict:
        """One model, with retries for temporary errors. Raises AgentError with `retry_next=True` if another model may work."""
        last: Optional[AgentError] = None
        for attempt in range(self._attempts):
            if attempt:
                await asyncio.sleep(self._retry_delay * attempt)
            try:
                response = await self._http.post(f"/v1beta/models/{model}:generateContent", json=body)
            except httpx.TimeoutException:
                last = AgentError("agent_timeout", "The agent's language model did not respond in time.", 504)
                last.retry_next = True
                break  # a slow model rarely recovers by retrying; try the next one
            except httpx.HTTPError:
                raise AgentError("agent_unreachable", "Could not reach the agent's language model.", 502) from None
            code = response.status_code
            if code == 404:
                last = AgentError("agent_model_not_found", f"Gemini model '{model}' was not found. Set AGENT_MODEL to a current model "
                                  "(run python scripts/list_gemini_models.py).", 502)
                last.retry_next = True
                break
            if code == 429:
                last = AgentError("agent_rate_limited", "The agent is busy (free-tier limit). Try again in a minute.", 429)
                last.retry_next = True
                wait = retry_after_seconds(response)
                if pinned and wait is not None and wait <= 25 and attempt < self._attempts - 1:
                    await asyncio.sleep(wait)  # this run cannot switch models, so wait out the limit
                    continue
                break  # each model has its own free quota: go straight to the next one
            if code in (500, 502, 503, 504):
                last = AgentError("agent_overloaded", "Gemini is overloaded right now. Try again in a moment.", 503)
                last.retry_next = True
                continue
            if code in (401, 403) or (code == 400 and "API key" in response.text):
                raise AgentError("agent_auth_failed", "The server's Gemini API key was rejected.", 502)
            if code >= 400:
                raise AgentError("agent_error", f"The agent's language model returned an error (HTTP {code}).", 502)
            return self._parse(response, model)
        raise last or AgentError("agent_error", "The agent's language model failed.", 502)

    @staticmethod
    def _parse(response: httpx.Response, model: str) -> dict:
        try:
            data = response.json()
        except ValueError:
            raise AgentError("agent_bad_response", "The agent's language model returned an unreadable response.") from None
        if not isinstance(data, dict):
            raise AgentError("agent_bad_response", "The agent's language model returned an unreadable response.")
        if (data.get("promptFeedback") or {}).get("blockReason"):
            raise AgentError("agent_blocked", "The language model declined this request. Try rewording the goal.", 422)
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise AgentError("agent_bad_response", "The agent's language model returned no answer.")
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        finish = (candidates[0] or {}).get("finishReason")
        return {"content": from_gemini_parts([p for p in parts if isinstance(p, dict)], model), "model": model,
                "finish_reason": finish if isinstance(finish, str) else None}

    async def complete(self, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 8192) -> dict[str, Any]:
        """One model turn. Returns {"content": [blocks], "model": name_that_answered, "finish_reason": str|None}."""
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": to_gemini_contents(messages),
            "tools": to_gemini_tools(tools),
            "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},  # always answer with a tool call
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4},
        }
        pinned = pinned_model(messages)
        candidates = [pinned] if pinned else self.models
        last: Optional[AgentError] = None
        for model in candidates:
            try:
                return await self._call_model(model, body, pinned=bool(pinned))
            except AgentError as err:
                if not getattr(err, "retry_next", False):
                    raise
                last = err
        raise last or AgentError("agent_error", "The agent's language model failed.", 502)
