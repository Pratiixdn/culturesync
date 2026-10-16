"use client";

import { Info, Sparkles, Users } from "lucide-react";
import { useStore } from "../../lib/store";
import ConnectionCard from "../../components/ConnectionCard";
import { Badge, Button, Card, EmptyState, Spinner, ButtonLink } from "../../components/ui";
import { CATEGORY_COLORS, CATEGORY_LABELS, Category } from "../../lib/types";

export default function InsightsPage() {
  const { team, ready, mode, connData, analyzing, runAnalysis } = useStore();

  if (!ready) return <Spinner label="Loading insights..." />;
  if (!team) {
    return (
      <EmptyState
        icon={Users}
        title="No insights yet"
        body="Create a team and add member interests to unlock shared ground and Qloo-powered discoveries."
        action={
          <ButtonLink href="/workspace">Open workspace</ButtonLink>
        }
      />
    );
  }

  const conns = connData?.connections ?? [];
  const shared = conns.filter((c) => c.kind === "shared_interest");
  const qloo = conns.filter((c) => c.kind === "qloo_affinity");
  const cats = conns.filter((c) => c.kind === "same_category");
  const analysis = connData?.analysis ?? null;
  const total = team.members.reduce((n, m) => n + m.interests.length, 0);

  // interests listed by exactly one member (computed locally from the team data)
  const byName = new Map<string, { name: string; category: Category; member: string; count: number }>();
  team.members.forEach((m) =>
    m.interests.forEach((i) => {
      const key = `${i.category}:${i.name.trim().toLowerCase()}`;
      const cur = byName.get(key);
      byName.set(key, cur ? { ...cur, count: cur.count + 1 } : { name: i.name, category: i.category, member: m.name, count: 1 });
    })
  );
  const uncommon = [...byName.values()].filter((v) => v.count === 1);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl text-ink">Cultural insights</h1>
          <p className="mt-1 max-w-xl text-sm text-ink-soft">
            Shared ground, Qloo-returned affinities, and discoveries for {team.name}. Every item shows where it came from.
          </p>
        </div>
        <Button onClick={() => void runAnalysis()} loading={analyzing} disabled={total === 0 || mode === "offline"}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {analysis ? "Re-run Qloo analysis" : "Run Qloo analysis"}
        </Button>
      </div>

      {mode === "mock" ? (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>Mock mode: the analysis runs against a built-in sample list, not Qloo. Qloo affinities between members are not simulated.</p>
        </div>
      ) : null}
      {connData?.analysis_stale ? (
        <div className="rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink-soft">
          Team interests changed since the last Qloo analysis. Re-run it for current Qloo results.
        </div>
      ) : null}

      {total === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="Not enough data yet"
          body="Add interests for at least two members. Insights are only shown where the data supports them."
          action={
            <ButtonLink href="/workspace">Add interests</ButtonLink>
          }
        />
      ) : (
        <>
          <section>
            <div className="mb-3 flex items-center gap-2">
              <h2 className="font-display text-lg text-ink">Shared ground</h2>
              <Badge>Locally calculated</Badge>
            </div>
            {shared.length === 0 ? (
              <Card className="p-5 text-sm text-ink-soft">No exact shared interests yet. That means unknown, not unrelated.</Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {shared.map((c) => (
                  <ConnectionCard key={c.id} c={c} team={team} />
                ))}
              </div>
            )}
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <h2 className="font-display text-lg text-ink">Qloo affinities between members</h2>
              <Badge tone="blue">From Qloo</Badge>
            </div>
            {!analysis ? (
              <Card className="p-5 text-sm text-ink-soft">Run the Qloo analysis to look for affinities between members&apos; picks.</Card>
            ) : qloo.length === 0 ? (
              <Card className="p-5 text-sm text-ink-soft">
                Qloo returned no affinities between members&apos; picks for this run. Interests linked to a Qloo entity (pick a search result when adding) give Qloo more to work with.
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {qloo.map((c) => (
                  <ConnectionCard key={c.id} c={c} team={team} />
                ))}
              </div>
            )}
          </section>

          {connData && connData.suggestions.length > 0 ? (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <h2 className="font-display text-lg text-ink">Discoveries for the team</h2>
                <Badge tone="blue">{analysis?.mode === "mock" ? "Mock sample" : "From Qloo"}</Badge>
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                {connData.suggestions.map((s) => (
                  <Card key={s.category} className="p-5">
                    <h3 className="text-sm font-semibold text-ink">{CATEGORY_LABELS[s.category]}</h3>
                    <ul className="mt-3 space-y-1.5 text-sm text-ink">
                      {s.entities.map((e) => (
                        <li key={e.id} className="flex items-center justify-between gap-2">
                          <span>{e.name}</span>
                          {e.affinity !== null ? <span className="font-mono text-xs text-ink-faint">{e.affinity.toFixed(2)}</span> : null}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-ink-faint">
                      Based on: {s.signal_entities.map((x) => x.name).join(", ")}
                    </p>
                  </Card>
                ))}
              </div>
            </section>
          ) : null}

          {connData && connData.resolutions.length > 0 ? (
            <section>
              <h2 className="mb-3 font-display text-lg text-ink">Auto-matched interests</h2>
              <Card className="p-5">
                <p className="text-sm text-ink-soft">
                  These typed interests were matched to the top Qloo search result for this run only. Check they are right; pick the exact result in the workspace to pin one.
                </p>
                <ul className="mt-3 flex flex-wrap gap-1.5">
                  {connData.resolutions.map((r) => (
                    <li key={r.interest_id} className="rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-ink">
                      {r.name} <span className="text-ink-faint">to</span> {r.entity.name}
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ) : null}

          {cats.length > 0 ? (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <h2 className="font-display text-lg text-ink">Same category</h2>
                <Badge>Locally calculated</Badge>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {cats.map((c) => (
                  <ConnectionCard key={c.id} c={c} team={team} />
                ))}
              </div>
            </section>
          ) : null}

          {uncommon.length > 0 ? (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <h2 className="font-display text-lg text-ink">Uncommon angles</h2>
                <Badge>Locally calculated</Badge>
              </div>
              <Card className="p-5">
                <p className="text-sm leading-relaxed text-ink-soft">Interests listed by exactly one member - a chance to discover something new:</p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {uncommon.map((v) => (
                    <span key={`${v.category}:${v.name}`} title={`Only ${v.member} listed this`} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-ink">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[v.category] }} aria-hidden="true" />
                      {v.name} <span className="text-ink-faint">- {v.member.split(" ")[0]}</span>
                    </span>
                  ))}
                </div>
              </Card>
            </section>
          ) : null}

          {analysis ? (
            <p className="text-xs text-ink-faint">
              Last Qloo analysis: {new Date(analysis.ran_at).toLocaleString()} - {analysis.qloo_calls} requests ({analysis.mode} mode)
              {analysis.truncated ? " - request budget reached, some pairs skipped" : ""}.
            </p>
          ) : null}
          <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-ink-faint">
            {(connData?.limitations ?? []).map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
