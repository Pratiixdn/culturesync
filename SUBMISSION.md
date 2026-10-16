# CULTURESYNC: Team Culture Agent

**An agent that plans for a whole team, grounded in Qloo's taste graph.**

Teams constantly decide things together: an offsite, a dinner, a playlist, a retreat destination. A language model alone guesses, and tends to
recommend whatever is popular. CULTURESYNC lets each person list the music, films, brands, restaurants and destinations they love, links them
to real Qloo entities, and then asks an agent to plan around what the *whole team* likes.

## What the agent does
You type a goal, for example "Plan a team offsite everyone will enjoy". The agent (Google Gemini with function calling) then, visibly and step by step:
1. reads the team's interests,
2. calls **Qloo search** to link typed interests to Qloo entities,
3. calls **Qloo insights** to get recommendations that fit the combined picks, and **scores** specific candidates against them,
4. submits a plan.

## Why it is Qloo-powered (and fails without Qloo)
- Every recommendation must be an entity that **Qloo returned during that run**. The server checks this and **drops anything the model
  invented** (the UI shows how many were removed). Titles and affinities shown are Qloo's, not the model's.
- Tools reject entity ids the agent never received, so it cannot pass made-up ids to Qloo.
- Without Qloo the agent has nothing to recommend from.
- Beyond the agent: a team map and insights page that use Qloo cross-category affinities between members' picks, always labeled with their source
  (Qloo / locally calculated / app template) and caveats. Missing relationships stay "unknown", never "negative".

## Categories
Music, movies, TV, books, brands, video games, podcasts, dining and places, travel destinations.

## Responsible by design
Interests are voluntary cultural picks. The app never infers personality, ethnicity, health or workplace behavior, and says so. The
language model's reasoning text is labeled as generated; only the entity and its affinity are Qloo data.

## Stack
FastAPI + HTTPX (Qloo and Gemini APIs), SQLite, Next.js static export served by FastAPI, deployed as one Render service. 65 backend tests.
Code: see README. License: MIT.
