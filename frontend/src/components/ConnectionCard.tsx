"use client";

import { ArrowRight } from "lucide-react";
import { KIND_LABEL } from "../lib/graph";
import { CATEGORY_LABELS, Connection, Team } from "../lib/types";
import { Badge } from "./ui";

/** One connection with its provenance: who, what, why, source, caveat. */
export default function ConnectionCard({ c, team }: { c: Connection; team: Team }) {
  const name = (id: string) => team.members.find((m) => m.id === id)?.name ?? "Unknown member";
  const signals = c.entities.filter((e) => e.role === "signal");
  const results = c.entities.filter((e) => e.role === "result");
  const kindTone = c.kind === "shared_interest" ? "accent" : c.kind === "qloo_affinity" ? "blue" : "stone";

  return (
    <div className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-ink">
          {c.kind === "qloo_affinity" ? (
            <>
              {name(c.member_ids[0])} <ArrowRight className="mx-1 inline h-3.5 w-3.5 text-ink-faint" aria-hidden="true" /> {name(c.member_ids[1])}
            </>
          ) : (
            <>
              {name(c.member_ids[0])} <span className="text-ink-faint">x</span> {name(c.member_ids[1])}
            </>
          )}
        </p>
        <span className="flex items-center gap-1.5">
          <Badge tone={kindTone}>{KIND_LABEL[c.kind]}</Badge>
          <Badge tone={c.source === "qloo" ? "blue" : "stone"}>{c.source === "qloo" ? "From Qloo" : "Locally calculated"}</Badge>
        </span>
      </div>

      {c.kind === "qloo_affinity" ? (
        <div className="mt-3 space-y-2 text-xs">
          <p className="text-ink-soft">
            Signal: <span className="text-ink">{signals.map((s) => s.name).join(", ")}</span>
          </p>
          {results.map((r) => (
            <p key={r.entity_id ?? r.name} className="text-ink-soft">
              Qloo returned: <span className="font-medium text-ink">{r.name}</span> ({CATEGORY_LABELS[r.category]})
              {r.affinity !== null ? <span className="ml-2 font-mono text-ink">affinity {r.affinity.toFixed(2)}</span> : null}
            </p>
          ))}
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {c.kind === "shared_interest" ? (
            <Badge tone="accent">{c.entities[0]?.name}</Badge>
          ) : (
            [...new Set(c.entities.map((e) => CATEGORY_LABELS[e.category]))].map((x) => <Badge key={x}>{x}</Badge>)
          )}
        </div>
      )}

      <p className="mt-3 text-xs leading-relaxed text-ink-soft">{c.evidence}</p>
      {c.caveat ? <p className="mt-2 text-xs leading-relaxed text-ink-faint">{c.caveat}</p> : null}
    </div>
  );
}
