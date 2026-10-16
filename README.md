# CULTURESYNC

**Team Culture Agent**: an LLM agent that plans team decisions using only entities Qloo returned (see SUBMISSION.md for the project description). Also maps cultural connections between team members. Built for the Qloo hackathon. Next.js frontend (static export) + FastAPI backend, deployed as **one Render service** (same origin, no CORS setup).

```
backend/   FastAPI, SQLite, Qloo client (app/qloo.py), tests
frontend/  Next.js 15 + Tailwind (exported to frontend/out, served by FastAPI)
Dockerfile, render.yaml
```

## Run locally

```bash
# backend (terminal 1)
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # add QLOO_API_KEY and GEMINI_API_KEY (empty = mock Qloo / agent off)
uvicorn app.main:app --reload --port 8000

# frontend (terminal 2)
cd frontend
npm install
npm run dev                                            # http://localhost:3000  (talks to :8000 via .env.development)
```

Single-process, production-like: `cd frontend && npm run build`, then run uvicorn from `backend/`; FastAPI serves `frontend/out` at http://localhost:8000.

Check your Qloo key and the response shapes the app relies on: `cd backend && python scripts/check_qloo.py` (prints field names only, never the key).

Tests: `cd backend && python -m pytest -q` (all Qloo HTTP is mocked; no key needed).

## Deploy on Render

1. Push to GitHub (`.env` is git-ignored).
2. Render: **New > Blueprint** > select the repo (uses `render.yaml` + `Dockerfile`).
3. Set `QLOO_API_KEY` and `GEMINI_API_KEY` in the dashboard (the agent is off without the second). Open `https://<service>.onrender.com`, go to **Settings > Test Qloo request**.

Free-tier caveats: the service sleeps when idle (first request is slow) and SQLite lives on an ephemeral disk, so data resets on redeploy/restart. For persistence attach a Render disk and set `DATABASE_URL=sqlite:////data/culturesync.db`.

## Theme

Light, Dark (#121212 background, #E0E0E0 text, #B0B0B0 secondary, #444444 borders, #888888 accent) and System. Toggle in the nav bar or Settings; saved in `localStorage`, applied before first paint. Colors are CSS variables in `frontend/src/app/globals.css`.

## Team Culture Agent

`POST /api/teams/{id}/agent` `{goal}` streams server-sent events (`start`, `step`..., then `result` or `error`). `GET /api/teams/{id}/agent/runs` returns the last 5 runs.

- Tools (Qloo-backed): `get_team`, `search_entities`, `get_recommendations`, `score_candidates`, plus `submit_plan`.
- Grounding: a recommendation survives only if its entity id was returned by a Qloo tool in the same run; the title and affinity come from Qloo, never from the model. `supported_by` names are kept only if they match real team interests or returned entities. Dropped suggestions are counted and shown.
- Limits: 8 model turns and 15 Qloo calls per run, 4 runs/min per IP, `AGENT_DAILY_LIMIT` runs/day for the whole server. Gemini free tier has tight per-minute limits (a run makes ~4-6 model calls), so the client retries a 429 once and otherwise shows a "busy, try again" message. Note: free-tier prompts may be used by Google to improve its products, so keep real personal data out of the demo.
- The agent does not run in mock Qloo mode with real quality: it still works, but over the small sample catalog and the UI says so.

## Hackathon checklist

| Requirement | Status |
| --- | --- |
| Agentic tool using Qloo | Team Culture Agent (LLM tool-use loop over Qloo search/insights) |
| Functional hosted demo | Deploy via `render.yaml`; set both keys; open the URL yourself before submitting |
| Public repo with instructions | Push this folder to a public GitHub repo (this README) |
| Text description | `SUBMISSION.md` |
| Open-source license visible in About | `LICENSE` (MIT) at repo root; GitHub shows it automatically |

## Modes

| Mode | When | Meaning |
| --- | --- | --- |
| `live` | `QLOO_API_KEY` set | Real calls to `QLOO_BASE_URL` (default `https://hackathon.api.qloo.com`). |
| `mock` | no key | Small built-in catalog, ids start `mock:`, **no affinities simulated**. Every response says `meta.mode: "mock"` and the UI shows a banner. |

## API (all under `/api`, JSON envelope `{data, meta:{source,mode}, error:{code,message}|null}`)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | `?probe=true` makes one real Qloo search to verify the key |
| POST | `/teams` | `{name, description?}` |
| GET / PATCH | `/teams/{id}` | team + members |
| POST | `/teams/{id}/members` | `{name, interests?[]}` |
| PATCH / DELETE | `/teams/{id}/members/{mid}` | PATCH `{name?, interests?}` (replaces interests) |
| GET | `/entities/search?q=&category=` | Qloo `/search`; category: music, movies, tv, books, brands, games, podcasts |
| POST | `/teams/{id}/insights` | runs Qloo analysis (resolve, affinities, suggestions), saves it |
| GET | `/teams/{id}/connections` | local connections + last Qloo analysis if still current |
| POST / GET | `/teams/{id}/activities` | `{connection_ids:[1..3]}`; deterministic template, not AI |
| DELETE | `/teams/{id}/activities/{aid}` | also deletes its ideas |
| POST / GET | `/teams/{id}/ideas` | `{text, activity_id?}` |
| DELETE | `/teams/{id}/ideas/{iid}` | |

Contract = `backend/app/schemas.py` (mirrored in `frontend/src/lib/types.ts`). Interactive docs: `/docs`.

```bash
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/teams -H 'content-type: application/json' -d '{"name":"Studio"}'
curl -s "localhost:8000/api/entities/search?q=tame&category=music"
curl -s -X POST localhost:8000/api/teams/$TEAM/insights -H 'content-type: application/json' -d '{}'
```

## Connection logic

- `shared_interest` (local): same Qloo entity id, or same category + normalized name when an interest has no entity id. Two different entity ids with the same name never match.
- `same_category` (local): both listed the category; no relationship claimed. Not usable for activities.
- `qloo_affinity` (Qloo): member X's picks as `signal.interests.entities`, member Y's picks scored via `filter.results.entities`. Only entities Qloo returns appear; absent = unknown. `affinity` is passed through exactly as returned, else `null`. No confidence scores are invented.
- Analysis auto-matches typed interests to the top Qloo search hit for that run only (shown in the UI, never saved).

## Verification status (be honest in your demo)

- **Tested:** 65 backend tests with mocked HTTP (the agent is tested with a scripted fake LLM); frontend typecheck + production build; headless-Chromium run (Playwright) over every page: dark/light/system theme, all Settings buttons, demo team, analysis, map, activity + idea flow, interest search; no hydration or JS errors.
- **NOT verified live:** the Gemini call (request/response translation is tested with mocked HTTP; `AGENT_MODEL` default `gemini-2.5-flash` may have been renamed or retired, so change it if Google returns an error) and the agent's real-world answer quality.
- **NOT verified against real Qloo** (no key was available; the docs site blocks automated fetching): response field names (`results`, `results.entities`, `entity_id`, `query.affinity`), type URNs for `tv_show`/`videogame`/`podcast`/`place`/`destination` (places may also need a location filter), and `filter.results.entities` behaviour. Parsing is defensive and isolated in `backend/app/qloo.py`; `CATEGORY_TYPES` is the one dict to fix if a URN is wrong. First thing to do with a key: Settings > Test Qloo request, then add an interest via search.
- Dockerfile / `render.yaml` were written but not built in the authoring sandbox.

## Security / access limits

- Key only in env (`QLOO_API_KEY`), never in responses, logs, or the browser bundle.
- **No authentication.** Team ids are unguessable (128-bit) and act as access links: anyone with a link can read and edit that team. Before real use on a public host add auth, and a data-retention/delete path.
- Input is length-limited; Qloo-backed endpoints are rate-limited per IP (30/min, in-memory); each analysis is capped at 40 Qloo calls; errors are mapped to safe messages (no raw upstream payloads).
- Interests are voluntary cultural picks. The app does not infer personality, ethnicity, or workplace behavior, and says so in the UI.
