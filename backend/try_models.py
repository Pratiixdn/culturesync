import time, httpx
from app.main import Settings

key = Settings.from_env().gemini_api_key
models = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
          "gemini-3.5-flash", "gemini-2.5-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"]
body = {
    "contents": [{"role": "user", "parts": [{"text": "Call the get_team tool."}]}],
    "tools": [{"functionDeclarations": [{"name": "get_team", "description": "Returns the team."}]}],
    "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
}
for m in models:
    start = time.time()
    try:
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                       headers={"x-goog-api-key": key}, json=body, timeout=40)
        took = round(time.time() - start, 1)
        ok = "functionCall" in r.text
        note = "TOOL CALL OK" if ok else r.text[:90].replace("\n", " ")
        print(f"{m:28} HTTP {r.status_code}  {took:>5}s  {note}")
    except Exception as e:
        print(f"{m:28} {type(e).__name__} after {round(time.time() - start, 1)}s")
