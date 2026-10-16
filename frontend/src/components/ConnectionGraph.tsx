"use client";

import type { Team } from "../lib/types";
import type { PairEdge } from "../lib/graph";

export type Selection = { kind: "member" | "edge"; id: string } | null;

interface Props {
  team: Team;
  edges: PairEdge[];
  selected: Selection;
  onSelect: (sel: Selection) => void;
}

const W = 780;
const H = 520;
const R = 195;

const STYLE = {
  shared_interest: { stroke: "rgb(var(--edge-shared))", width: 2.2, dash: undefined as string | undefined },
  qloo_affinity: { stroke: "rgb(var(--edge-qloo))", width: 2, dash: "2 5" as string | undefined },
  same_category: { stroke: "rgb(var(--edge-category))", width: 1.5, dash: "5 6" as string | undefined },
};

export default function ConnectionGraph({ team, edges, selected, onSelect }: Props) {
  const n = team.members.length;
  const cx = W / 2;
  const cy = H / 2;

  const pos = (index: number): { x: number; y: number } => {
    if (n <= 1) return { x: cx, y: cy };
    const angle = (Math.PI * 2 * index) / n - Math.PI / 2;
    return { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
  };
  const indexOf = (id: string): number => team.members.findIndex((m) => m.id === id);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Cultural connection map">
        {edges.map((e) => {
          const ia = indexOf(e.aId);
          const ib = indexOf(e.bId);
          if (ia < 0 || ib < 0) return null;
          const p1 = pos(ia);
          const p2 = pos(ib);
          const mx = (p1.x + p2.x) / 2;
          const my = (p1.y + p2.y) / 2;
          const len = Math.hypot(mx - cx, my - cy) || 1;
          const qx = mx + ((mx - cx) / len) * 30;
          const qy = my + ((my - cy) / len) * 30;
          const d = `M ${p1.x} ${p1.y} Q ${qx} ${qy} ${p2.x} ${p2.y}`;
          const isSel = selected?.kind === "edge" && selected.id === e.id;
          const st = STYLE[e.kind];
          return (
            <g key={e.id}>
              <path d={d} fill="none" stroke="transparent" strokeWidth={18} className="cursor-pointer" onClick={() => onSelect({ kind: "edge", id: e.id })}>
                <title>{e.connections[0]?.evidence}</title>
              </path>
              <path
                d={d}
                fill="none"
                style={{ stroke: st.stroke }}
                strokeWidth={isSel ? st.width + 1.2 : st.width}
                strokeDasharray={st.dash}
                strokeOpacity={isSel ? 1 : 0.8}
                pointerEvents="none"
              />
            </g>
          );
        })}
        {team.members.map((m, i) => {
          const p = pos(i);
          const isSel = selected?.kind === "member" && selected.id === m.id;
          const initials = m.name
            .split(" ")
            .map((w) => w[0])
            .slice(0, 2)
            .join("")
            .toUpperCase();
          return (
            <g
              key={m.id}
              transform={`translate(${p.x} ${p.y})`}
              className="cursor-pointer outline-none"
              onClick={() => onSelect({ kind: "member", id: m.id })}
              role="button"
              tabIndex={0}
              aria-label={`Select ${m.name}`}
              onKeyDown={(ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                  ev.preventDefault();
                  onSelect({ kind: "member", id: m.id });
                }
              }}
            >
              {isSel ? <circle r={38} fill="none" className="stroke-accent" strokeOpacity={0.25} strokeWidth={7} /> : null}
              <circle r={30} className={isSel ? "fill-surface stroke-accent" : "fill-surface stroke-line"} strokeWidth={isSel ? 2.5 : 1.5} />
              <text textAnchor="middle" dy={4} className="fill-ink text-[13px] font-semibold" style={{ pointerEvents: "none" }}>
                {initials}
              </text>
              <text textAnchor="middle" y={52} className="fill-ink-soft text-[12px]" style={{ pointerEvents: "none" }}>
                {m.name}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-ink-soft">
        {(
          [
            ["shared_interest", "Shared interest (local)"],
            ["qloo_affinity", "Qloo affinity"],
            ["same_category", "Same category only"],
          ] as const
        ).map(([k, label]) => (
          <span key={k} className="inline-flex items-center gap-2">
            <svg width="28" height="8" aria-hidden="true">
              <path d="M1 4 H27" style={{ stroke: STYLE[k].stroke }} strokeWidth="2" strokeDasharray={STYLE[k].dash} />
            </svg>
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
