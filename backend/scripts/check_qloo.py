"""Checks your Qloo key against the real API and prints the response shapes the app depends on.

Run from backend/:  python scripts/check_qloo.py
Prints field names and a few entity names only. It never prints your key.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import Settings  # noqa: E402
from app.qloo import CATEGORY_TYPES  # noqa: E402

SAMPLES = {"music": "Tame Impala", "movies": "Parasite", "tv": "Severance", "books": "Dune", "brands": "Nike",
           "games": "Hades", "podcasts": "Radiolab", "places": "pizza", "destinations": "Kyoto"}


def show(label, response):
    print(f"\n== {label}: HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        print("   (not JSON)", response.text[:120].replace("\n", " "))
        return None
    print("   top-level keys:", list(data)[:8] if isinstance(data, dict) else type(data).__name__)
    results = data.get("results") if isinstance(data, dict) else None
    items = results.get("entities") if isinstance(results, dict) else results
    print("   results is:", "dict with 'entities'" if isinstance(results, dict) else type(results).__name__,
          "| count:", len(items) if isinstance(items, list) else "n/a")
    if isinstance(items, list) and items:
        first = items[0]
        print("   first item keys:", sorted(first)[:15])
        print("   first item:", {k: first.get(k) for k in ("entity_id", "id", "name", "types", "type") if k in first})
        print("   query field:", first.get("query"))
        return items
    return items


def main():
    cfg = Settings.from_env()
    if not cfg.qloo_api_key:
        sys.exit("QLOO_API_KEY is empty. Put it in backend/.env first.")
    http = httpx.Client(base_url=cfg.qloo_base_url, headers={"X-Api-Key": cfg.qloo_api_key}, timeout=20)
    print("Base URL:", cfg.qloo_base_url)

    items = show("search artist 'Tame Impala'", http.get("/search", params={"query": "Tame Impala", "types": CATEGORY_TYPES["music"], "take": 3}))
    ids = [i.get("entity_id") or i.get("id") for i in (items or []) if isinstance(i, dict)]
    if ids:
        signal = ids[0]
        got = show("insights: artists like the first hit", http.get("/v2/insights", params={
            "filter.type": CATEGORY_TYPES["music"], "signal.interests.entities": signal, "take": 3}))
        cand = [i.get("entity_id") or i.get("id") for i in (got or []) if isinstance(i, dict)][:2]
        if cand:
            show("insights scoring given candidates (filter.results.entities)", http.get("/v2/insights", params={
                "filter.type": CATEGORY_TYPES["music"], "signal.interests.entities": signal,
                "filter.results.entities": ",".join(cand), "take": 2}))

    print("\n== search per category (checks the type URNs)")
    for category, urn in CATEGORY_TYPES.items():
        r = http.get("/search", params={"query": SAMPLES[category], "types": urn, "take": 2})
        count = "?"
        try:
            data = r.json()
            res = data.get("results")
            res = res.get("entities") if isinstance(res, dict) else res
            count = len(res) if isinstance(res, list) else "?"
        except ValueError:
            pass
        verdict = "OK " if r.status_code == 200 and count not in (0, "?") else "CHECK"
        print(f"   {verdict} {category:<13} {urn:<26} HTTP {r.status_code} results={count}")


if __name__ == "__main__":
    main()
