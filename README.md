# CULTURESYNC: Team Culture Agent

**An AI agent that decides things for a whole team, using only what Qloo's taste data supports.**

**Live demo:**[ `https://culturesync.onrender.com/`](https://culturesync.onrender.com/)  |  **License:** MIT (see `LICENSE`)

## The problem
Teams constantly decide things together: where to hold an offsite, where to eat, what music to play, where to travel. Everyone likes different things, and a normal AI just guesses what is popular.

## What it does
1. You create a team and add each person's tastes (artists, movies, TV, books, brands, games, podcasts, restaurants and places, travel destinations). Each one is matched to a real item in Qloo's database.
2. You ask the **Team Culture Agent** for something, such as "Plan a team offsite everyone will enjoy".
3. The agent searches Qloo step by step, and you watch each step live. It asks Qloo what fits the whole team's tastes.
4. You get recommendations. Only items Qloo actually returned are kept. Anything the AI made up is removed, and the app shows how many it removed.

The app also has a **Map** and **Insights** page that show shared interests and Qloo-found links between team members, and a **Collaborate** page that turns a shared interest into a brainstorming activity.

## Why Qloo matters here
Without Qloo the agent has nothing to recommend from. Qloo supplies the items and the affinity scores. The AI plans and explains, but it cannot add recommendations of its own. The AI's "why" sentences are labeled as AI-written; the items and scores are Qloo's.

## What it does not do
It does not judge anyone's personality or how well people will work together. Shared tastes are conversation starters only.

## Built with
Next.js (static export) and FastAPI served as **one Render service**, SQLite, the Qloo API and Google Gemini. A longer project description is in `SUBMISSION.md`.

```
backend/   FastAPI, SQLite, Qloo client (app/qloo.py), agent (app/agent.py), tests
frontend/  Next.js 15 + Tailwind (exported to frontend/out, served by FastAPI)
Dockerfile, render.yaml
```

## Try it in 2 minutes (for judges)

1. Open the live demo, go to **Workspace**, and click **Load a sample demo team** (or create a team and add members).
2. On **Workspace**, add an interest and pick a result from the search list. That links it to a real Qloo entity.
3. Open **Agent**, click an example goal such as "Plan a team offsite everyone will enjoy", and press **Run agent**. Watch it call Qloo step by step.
4. Open **Insights** and press **Run Qloo analysis** to see Qloo affinities between members, then **Map** to see them as a graph.
5. **Settings** shows whether the live Qloo key and the agent are connected.

## Keys you need

| Variable | Where to get it | Required |
| --- | --- | --- |
| `QLOO_API_KEY` | Qloo hackathon developer guide | Yes (without it the app runs on a small mock sample, clearly labeled) |
| `QLOO_BASE_URL` | Given with the hackathon key; default `https://hackathon.api.qloo.com` | Yes |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (free tier) | For the Agent page |

Copy `backend/.env.example` to `backend/.env` and fill them in. `.env` is git-ignored.

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

## Hackathon requirements

| Requirement | Where |
| --- | --- |
| Agentic tool using Qloo | Team Culture Agent: an LLM tool-use loop over Qloo search, insights and scoring (`backend/app/agent.py`) |
| Functional hosted demo | Live demo link at the top of this README (Render) |
| Public repository with run instructions | This repository; see "Run locally" |
| Text description | `SUBMISSION.md` |
| Open-source license | `LICENSE` (MIT) |

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
| GET | `/entities/search?q=&category=` | Qloo `/search`; category: music, movies, tv, books, brands, games, podcasts, places, destinations |
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

## What is tested

- **Automated:** 74 backend tests with mocked HTTP (the agent runs against a scripted fake LLM), a frontend typecheck and production build, and a headless-browser run over every page (dark/light/system theme, Settings buttons, demo team, analysis, map, activities and ideas, interest search).
- **Run live by the author:** Qloo search, recommendations and scoring, and Gemini tool calling, in local runs.
- **Not independently confirmed:** the Docker image build on Render, the Qloo type names for TV, games, podcasts, places and travel (`CATEGORY_TYPES` in `backend/app/qloo.py` is the one place to fix them; `python scripts/check_qloo.py` checks them), and behavior under many users at once on the free Gemini tier.
- The Gemini client retries temporary errors and falls back through the models in `AGENT_MODEL` (a comma-separated list). `python scripts/list_gemini_models.py` shows the names your key can use.

## Security / access limits

- Key only in env (`QLOO_API_KEY`), never in responses, logs, or the browser bundle.
- **No authentication.** Team ids are unguessable (128-bit) and act as access links: anyone with a link can read and edit that team. Before real use on a public host add auth, and a data-retention/delete path.
- Input is length-limited; Qloo-backed endpoints are rate-limited per IP (30/min, in-memory); each analysis is capped at 40 Qloo calls; errors are mapped to safe messages (no raw upstream payloads).
- Interests are voluntary cultural picks. The app does not infer personality, ethnicity, or workplace behavior, and says so in the UI.
