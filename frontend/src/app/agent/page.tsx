"use client";

import { FormEvent, useState } from "react";
import { Bot, CheckCircle2, ChevronDown, Search, ShieldCheck, Sparkles, XCircle } from "lucide-react";
import { useStore } from "../../lib/store";
import { AgentRun } from "../../lib/types";
import { Badge, Button, ButtonLink, Card, EmptyState, Spinner, cn } from "../../components/ui";

const EXAMPLES = [
  "Plan a team offsite everyone will enjoy",
  "Pick music for our team playlist",
  "Where should we go for a team dinner?",
  "Suggest a trip for our next retreat",
];

const TOOL_LABELS: Record<string, string> = {
  get_team: "Read team",
  search_entities: "Qloo search",
  get_recommendations: "Qloo recommendations",
  score_candidates: "Qloo scoring",
};

export default function AgentPage() {
  const { team, ready, health, agentRuns, agentSteps, agentRunning, agentError, runAgent } = useStore();
  const [goal, setGoal] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (!ready) return <Spinner label="Loading agent..." />;
  if (!team) {
    return (
      <EmptyState
        icon={Bot}
        title="Create a team first"
        body="The agent plans around your team's interests. Add a team and a few interests, then ask it anything."
        action={<ButtonLink href="/workspace">Open workspace</ButtonLink>}
      />
    );
  }

  const hasInterests = team.members.some((m) => m.interests.length > 0);
  const configured = health?.agent_configured !== false;
  const current: AgentRun | undefined = agentRuns.find((r) => r.id === selectedId) ?? agentRuns[0];

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (goal.trim().length < 8 || agentRunning) return;
    setSelectedId(null);
    await runAgent(goal.trim());
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl text-ink">Team Culture Agent</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-soft">
          Describe what your team needs to decide. The agent searches Qloo&apos;s taste graph with your team&apos;s interests, and only picks Qloo actually returned
          make it into the answer.
        </p>
      </div>

      {!configured ? (
        <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          The agent is switched off: the server has no <code className="font-mono">GEMINI_API_KEY</code>. Everything else in the app still works.
        </div>
      ) : null}

      <Card className="p-5">
        <form onSubmit={submit} className="space-y-3" noValidate>
          <label htmlFor="goal" className="text-xs font-medium uppercase tracking-wide text-ink-soft">
            What should the agent help with?
          </label>
          <textarea
            id="goal"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            maxLength={400}
            rows={2}
            placeholder="e.g. Plan a team offsite everyone will enjoy"
            className="w-full resize-none rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25"
          />
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setGoal(example)}
                className="rounded-full border border-line px-3 py-1 text-xs text-ink-soft transition-colors hover:border-ink-faint hover:text-ink"
              >
                {example}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={agentRunning} disabled={goal.trim().length < 8 || !hasInterests || !configured}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {agentRunning ? "Agent working..." : "Run agent"}
            </Button>
            {!hasInterests ? <p className="text-xs text-ink-faint">Add at least one member with interests first.</p> : null}
          </div>
        </form>
      </Card>

      {agentRunning || agentSteps.length > 0 ? <Trace steps={agentSteps} running={agentRunning} /> : null}

      {agentError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {agentError}
        </div>
      ) : null}

      {current && !agentRunning ? <RunView run={current} /> : null}

      {agentRuns.length > 1 ? (
        <section>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-soft">Earlier runs</h2>
          <ul className="space-y-1.5">
            {agentRuns.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(r.id)}
                  className={cn(
                    "w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                    current?.id === r.id ? "border-accent bg-muted text-ink" : "border-line text-ink-soft hover:text-ink"
                  )}
                >
                  {r.goal}
                  <span className="ml-2 text-xs text-ink-faint">{new Date(r.created_at).toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function Trace({ steps, running }: { steps: { tool: string; summary: string; ok: boolean }[]; running: boolean }) {
  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold text-ink">{running ? "Agent is working" : "What the agent did"}</h2>
      <ol className="mt-3 space-y-2" aria-live="polite">
        {steps.map((s, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm">
            {s.ok ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-red-400" aria-hidden="true" />
            )}
            <span className="text-ink">
              <Badge tone={s.tool === "get_team" ? "stone" : "blue"}>{TOOL_LABELS[s.tool] ?? s.tool}</Badge>
              <span className="ml-2 text-ink-soft">{s.summary}</span>
            </span>
          </li>
        ))}
        {running ? (
          <li className="flex items-center gap-2.5 text-sm text-ink-faint">
            <Spinner label="Thinking..." />
          </li>
        ) : null}
      </ol>
    </Card>
  );
}

function RunView({ run }: { run: AgentRun }) {
  const [showSteps, setShowSteps] = useState(false);
  return (
    <section className="space-y-4">
      <Card className="p-5">
        <p className="text-xs text-ink-faint">Goal: {run.goal}</p>
        <p className="mt-2 text-sm leading-relaxed text-ink">{run.summary}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
          <Badge tone="blue">{run.qloo_calls} Qloo requests</Badge>
          <span>{new Date(run.created_at).toLocaleString()}</span>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {run.recommendations.map((rec) => (
          <Card key={rec.entity_id} className="flex flex-col p-5">
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-display text-lg text-ink">{rec.title}</h3>
              <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                {rec.category ? <Badge>{rec.category}</Badge> : null}
                <Badge tone="blue">
                  <Search className="mr-1 h-3 w-3" aria-hidden="true" />
                  Qloo entity
                </Badge>
              </div>
            </div>
            {rec.affinity !== null ? <p className="mt-1 font-mono text-xs text-ink-faint">Qloo affinity {rec.affinity.toFixed(2)}</p> : null}
            <p className="mt-3 text-sm leading-relaxed text-ink-soft">{rec.why}</p>
            <p className="mt-2 text-xs text-ink-faint">Reasoning written by the agent&apos;s language model.</p>
            {rec.supported_by.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
                <span className="text-xs text-ink-faint">Supported by:</span>
                {rec.supported_by.map((name) => (
                  <Badge key={name} tone="accent">
                    {name}
                  </Badge>
                ))}
              </div>
            ) : null}
          </Card>
        ))}
      </div>

      {run.dropped_ungrounded > 0 ? (
        <p className="flex items-start gap-2 text-xs text-ink-faint">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {run.dropped_ungrounded} suggestion{run.dropped_ungrounded === 1 ? "" : "s"} from the language model {run.dropped_ungrounded === 1 ? "was" : "were"} removed because Qloo never returned
          {run.dropped_ungrounded === 1 ? " it" : " them"} during this run.
        </p>
      ) : null}

      {run.caveats.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-ink-faint">
          {run.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ) : null}

      <button type="button" onClick={() => setShowSteps((v) => !v)} aria-expanded={showSteps} className="inline-flex items-center gap-1.5 text-xs text-ink-soft hover:text-ink">
        <ChevronDown className={cn("h-4 w-4 transition-transform", showSteps && "rotate-180")} aria-hidden="true" />
        How the agent got here ({run.steps.length} steps, {run.model})
      </button>
      {showSteps ? <Trace steps={run.steps} running={false} /> : null}
    </section>
  );
}
