"use client";

import { FormEvent, useState } from "react";
import { Lightbulb, Trash2 } from "lucide-react";
import { useStore } from "../../lib/store";
import { first } from "../../lib/graph";
import { Activity } from "../../lib/types";
import { Badge, Button, ButtonLink, Card, EmptyState, Input, Spinner } from "../../components/ui";

export default function CollabPage() {
  const { team, ready, connData, activities, createActivity } = useStore();
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  if (!ready) return <Spinner label="Loading..." />;
  if (!team) {
    return (
      <EmptyState
        icon={Lightbulb}
        title="Create a team first"
        body="Brainstorming activities are built from your team's verified cultural connections."
        action={<ButtonLink href="/workspace">Open workspace</ButtonLink>}
      />
    );
  }

  const nameOf = (id: string) => team.members.find((m) => m.id === id)?.name ?? "Unknown member";
  const usable = (connData?.connections ?? []).filter((c) => c.kind !== "same_category");
  const selected = picked.filter((id) => usable.some((c) => c.id === id));

  const toggle = (id: string) =>
    setPicked((current) => (current.includes(id) ? current.filter((x) => x !== id) : current.length >= 3 ? current : [...current, id]));

  const generate = async () => {
    setBusy(true);
    const created = await createActivity(selected);
    setBusy(false);
    if (created) setPicked([]);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl text-ink">Creative collaboration</h1>
        <p className="mt-1 text-sm text-ink-soft">Turn a verified connection into a small, concrete brainstorming activity.</p>
      </div>

      {usable.length === 0 ? (
        <EmptyState
          icon={Lightbulb}
          title="No verified connections yet"
          body="Activities need a shared interest or a Qloo affinity. A shared category alone is not enough. Add interests in the workspace, or run the Qloo analysis."
          action={<ButtonLink href="/workspace">Open workspace</ButtonLink>}
        />
      ) : (
        <Card className="p-5">
          <fieldset>
            <legend className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-soft">Pick up to 3 connections</legend>
            <div className="space-y-2">
              {usable.map((c) => (
                <label key={c.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-line bg-surface px-3 py-2.5 text-sm hover:border-ink-faint">
                  <input
                    type="checkbox"
                    className="mt-1 accent-[rgb(var(--accent))]"
                    checked={selected.includes(c.id)}
                    onChange={() => toggle(c.id)}
                    disabled={!selected.includes(c.id) && selected.length >= 3}
                  />
                  <span className="flex-1 text-ink">
                    {nameOf(c.member_ids[0])} {c.kind === "qloo_affinity" ? "to" : "x"} {nameOf(c.member_ids[1])}
                    <span className="block text-xs text-ink-soft">{c.evidence}</span>
                  </span>
                  <Badge tone={c.source === "qloo" ? "blue" : "stone"}>{c.source === "qloo" ? "From Qloo" : "Local"}</Badge>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={() => void generate()} disabled={selected.length === 0} loading={busy}>
              Generate activity
            </Button>
            <p className="text-xs text-ink-faint">Generated from fixed templates (no AI). Conversation starters, not psychological advice.</p>
          </div>
        </Card>
      )}

      {activities.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {activities.map((a) => (
            <ActivityCard key={a.id} activity={a} />
          ))}
        </div>
      ) : usable.length > 0 ? (
        <EmptyState icon={Lightbulb} title="No activities yet" body="Pick a connection above to generate your first brainstorming activity." />
      ) : null}
    </div>
  );
}

function ActivityCard({ activity }: { activity: Activity }) {
  const { team, ideas, addIdea, removeIdea, removeActivity } = useStore();
  const [idea, setIdea] = useState("");
  const mine = ideas.filter((i) => i.activity_id === activity.id);
  const nameOf = (id: string) => team?.members.find((m) => m.id === id)?.name ?? "Unknown member";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (await addIdea(idea, activity.id)) setIdea("");
  };

  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-display text-lg text-ink">{activity.title}</h2>
        <button
          type="button"
          onClick={() => void removeActivity(activity.id)}
          aria-label={`Delete activity ${activity.title}`}
          className="rounded-md p-1.5 text-ink-faint hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40 dark:hover:text-red-400"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink-soft">{activity.objective}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {activity.member_ids.map((id) => (
          <Badge key={id} tone="accent">
            {first(nameOf(id))}
          </Badge>
        ))}
        <Badge>App template</Badge>
      </div>

      <h3 className="mt-5 text-xs font-medium uppercase tracking-wide text-ink-soft">Prompts</h3>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-ink">
        {activity.prompts.map((p, i) => (
          <li key={i}>{p}</li>
        ))}
      </ol>

      <h3 className="mt-5 text-xs font-medium uppercase tracking-wide text-ink-soft">Ideas</h3>
      {mine.length === 0 ? (
        <p className="mt-2 text-sm text-ink-faint">No ideas captured yet.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {mine.map((x) => (
            <li key={x.id} className="flex items-start justify-between gap-2 rounded-lg border border-line bg-paper px-3 py-2">
              <span className="text-sm text-ink">{x.text}</span>
              <button
                type="button"
                aria-label="Delete idea"
                onClick={() => void removeIdea(x.id)}
                className="shrink-0 rounded p-1 text-ink-faint hover:text-red-700 dark:hover:text-red-400"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="mt-3 flex gap-2">
        <Input value={idea} onChange={(e) => setIdea(e.target.value)} maxLength={500} placeholder="Capture an idea..." aria-label="New idea" />
        <Button type="submit">Add</Button>
      </form>
    </Card>
  );
}
