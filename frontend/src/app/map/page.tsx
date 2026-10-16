"use client";

import { useMemo, useState } from "react";
import { Info, Network } from "lucide-react";
import { useStore } from "../../lib/store";
import { groupByPair, first } from "../../lib/graph";
import ConnectionGraph, { Selection } from "../../components/ConnectionGraph";
import ConnectionCard from "../../components/ConnectionCard";
import { Badge, ButtonLink, Card, EmptyState, Spinner } from "../../components/ui";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "../../lib/types";

export default function MapPage() {
  const { team, ready, connData } = useStore();
  const [sel, setSel] = useState<Selection>(null);
  const edges = useMemo(() => groupByPair(connData?.connections ?? []), [connData]);

  if (!ready) return <Spinner label="Loading map..." />;
  if (!team || team.members.length === 0) {
    return (
      <EmptyState
        icon={Network}
        title="No team to map yet"
        body="Add at least two members with a cultural interest each to see your connection map."
        action={
          <ButtonLink href="/workspace">Open workspace</ButtonLink>
        }
      />
    );
  }

  const member = sel?.kind === "member" ? team.members.find((m) => m.id === sel.id) : undefined;
  const edge = sel?.kind === "edge" ? edges.find((e) => e.id === sel.id) : undefined;
  const nameOf = (id: string) => team.members.find((m) => m.id === id)?.name ?? "Unknown";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl text-ink">Cultural connection map</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Direct overlaps and Qloo-returned affinities across {team.name}. Select a person or a line to see exactly why it is shown.
        </p>
      </div>

      {edges.length === 0 ? (
        <EmptyState
          icon={Network}
          title="No connections yet"
          body="Connections appear when two members list the same interest or have interests in the same category. A missing connection means unknown, not unrelated."
          action={
            <ButtonLink href="/workspace">Add interests</ButtonLink>
          }
        />
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[1fr_360px]">
          <Card className="p-6">
            <ConnectionGraph team={team} edges={edges} selected={sel} onSelect={setSel} />
            <div className="mt-4 flex items-start gap-2 border-t border-line pt-4 text-xs text-ink-faint">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <p>
                {connData?.analysis
                  ? `Includes Qloo results from the analysis run (${connData.analysis.mode} mode).`
                  : "Showing locally calculated overlaps. Run the Qloo analysis on the Insights page to add Qloo affinities."}
              </p>
            </div>
          </Card>

          <div className="space-y-4">
            {member ? (
              <Card className="p-5">
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-lg text-ink">{member.name}</h2>
                  <Badge tone="accent">Member</Badge>
                </div>
                <p className="mt-1 text-xs text-ink-faint">
                  {edges.filter((e) => e.aId === member.id || e.bId === member.id).length} connected members
                </p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {member.interests.length === 0 ? (
                    <p className="text-sm text-ink-faint">No interests listed yet.</p>
                  ) : (
                    member.interests.map((i) => (
                      <span key={i.id} title={CATEGORY_LABELS[i.category]} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-ink">
                        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[i.category] }} aria-hidden="true" />
                        {i.name}
                      </span>
                    ))
                  )}
                </div>
              </Card>
            ) : edge ? (
              <>
                <h2 className="font-display text-lg text-ink">
                  {first(nameOf(edge.aId))} x {first(nameOf(edge.bId))}
                </h2>
                {edge.connections.map((c) => (
                  <ConnectionCard key={c.id} c={c} team={team} />
                ))}
              </>
            ) : (
              <Card className="p-5">
                <h2 className="font-display text-lg text-ink">Inspect</h2>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                  Select a person to see their interests, or a line to see the evidence, source, and caveats behind that connection.
                </p>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
