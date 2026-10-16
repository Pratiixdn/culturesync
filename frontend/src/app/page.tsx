"use client";

import { ArrowRight, Bot, ShieldCheck, Share2, Users } from "lucide-react";
import { Badge, ButtonLink, Card } from "../components/ui";

const previewEdges = [
  { d: "M 120 70 Q 220 20 320 55", kind: "shared" },
  { d: "M 320 55 Q 280 110 210 150", kind: "qloo" },
  { d: "M 120 70 Q 150 120 210 150", kind: "cat" },
  { d: "M 210 150 Q 140 180 90 190", kind: "shared" },
  { d: "M 320 55 Q 340 130 330 190", kind: "cat" },
];

const previewNodes = [
  { x: 120, y: 70, label: "Amara" },
  { x: 320, y: 55, label: "Diego" },
  { x: 210, y: 150, label: "Yuki" },
  { x: 90, y: 190, label: "Sofia" },
  { x: 330, y: 190, label: "Noah" },
];

const edgeStyle = {
  shared: { stroke: "rgb(var(--edge-shared))", w: 2, dash: undefined as string | undefined },
  qloo: { stroke: "rgb(var(--edge-qloo))", w: 2, dash: "2 5" as string | undefined },
  cat: { stroke: "rgb(var(--edge-category))", w: 1.5, dash: "4 5" as string | undefined },
};

function PreviewGraph() {
  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-ink">Team culture map</h2>
        <Badge tone="stone">Illustrative sample</Badge>
      </div>
      <svg viewBox="0 0 420 240" className="w-full" role="img" aria-label="Sample cultural connection map">
        {previewEdges.map((e, i) => {
          const s = edgeStyle[e.kind as keyof typeof edgeStyle];
          return <path key={i} d={e.d} fill="none" style={{ stroke: s.stroke }} strokeWidth={s.w} strokeDasharray={s.dash} strokeOpacity={0.75} />;
        })}
        {previewNodes.map((node) => (
          <g key={node.label} transform={`translate(${node.x} ${node.y})`}>
            <circle r={20} className="fill-surface stroke-line" strokeWidth={1.5} />
            <text textAnchor="middle" dy={3.5} className="fill-ink text-[10px] font-semibold">
              {node.label.slice(0, 1)}
            </text>
            <text textAnchor="middle" y={36} className="fill-ink-soft text-[10px]">
              {node.label}
            </text>
          </g>
        ))}
      </svg>
      <p className="mt-4 border-t border-line pt-4 text-xs leading-relaxed text-ink-faint">
        Solid line: a shared interest. Dotted blue: an affinity returned by Qloo. Grey dashed: same category only, with no relationship claimed.
      </p>
    </Card>
  );
}

const steps = [
  {
    icon: Users,
    title: "Add your team",
    body: "Create a workspace and let each member share cultural interests they are happy to list - music, movies, TV, books, brands, games, podcasts. Search finds the exact entity in Qloo.",
  },
  {
    icon: Share2,
    title: "Map the overlap",
    body: "See direct overlaps and Qloo-returned affinities between members, each with its evidence, source, and any caveat.",
  },
  {
    icon: Bot,
    title: "Ask the agent",
    body: "Tell the Team Culture Agent what you need to decide. It searches Qloo with your team's interests and returns only picks Qloo actually surfaced.",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-16">
      <section className="grid items-center gap-10 pt-6 lg:grid-cols-2">
        <div>
          <Badge tone="accent" className="mb-5">Cultural intelligence for teams</Badge>
          <h1 className="font-display text-4xl leading-tight text-ink sm:text-5xl">
            Find the overlap.
            <br />
            Start the conversation.
          </h1>
          <p className="mt-5 max-w-md text-base leading-relaxed text-ink-soft">
            CULTURESYNC is an agent grounded in Qloo&apos;s taste graph. It maps the interests your team chooses to share, then plans offsites,
            dinners, playlists and trips around what the whole team actually likes.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <ButtonLink href="/workspace">Build your team
                <ArrowRight className="h-4 w-4" aria-hidden="true" /></ButtonLink>
            <ButtonLink href="#how" variant="secondary">See how it works</ButtonLink>
          </div>
          <p className="mt-6 flex items-center gap-2 text-xs text-ink-faint">
            <ShieldCheck className="h-4 w-4 text-ink-soft" aria-hidden="true" />
            No personality tests. No assessments. Only what people choose to share.
          </p>
        </div>
        <PreviewGraph />
      </section>

      <section id="how" className="scroll-mt-20">
        <h2 className="font-display text-2xl text-ink">How it works</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {steps.map((s, i) => (
            <Card key={s.title} className="p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-tint">
                  <s.icon className="h-4 w-4 text-accent-deep" aria-hidden="true" />
                </span>
                <span className="text-xs font-medium text-ink-faint">Step {i + 1}</span>
              </div>
              <h3 className="mt-4 font-display text-lg text-ink">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">{s.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-line bg-surface p-6 shadow-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-tint">
            <ShieldCheck className="h-5 w-5 text-accent-deep" aria-hidden="true" />
          </span>
          <div>
            <h2 className="font-display text-lg text-ink">What this is - and what it is not</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-soft">
              Connections come from cultural interests people voluntarily list. They are conversation starters and discovery opportunities -
              never conclusions about anyone&apos;s personality, intelligence, communication ability, ethnicity, or workplace behavior. A missing
              connection means unknown, not &ldquo;unrelated&rdquo;.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
