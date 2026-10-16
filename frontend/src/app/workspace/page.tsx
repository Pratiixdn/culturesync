"use client";

import { FormEvent, useState } from "react";
import { Check, Link2, Pencil, Plus, Sparkles, Trash2, Users, X } from "lucide-react";
import { useStore } from "../../lib/store";
import { CATEGORY_COLORS, CATEGORY_LABELS, Member } from "../../lib/types";
import { Badge, Button, Card, EmptyState, Field, Input, Spinner } from "../../components/ui";
import AddInterest from "../../components/AddInterest";

export default function WorkspacePage() {
  const { team, ready, mode } = useStore();
  if (!ready) return <Spinner label="Loading workspace..." />;
  if (mode === "offline" && !team) {
    return <EmptyState icon={Users} title="Server unreachable" body="The workspace needs the CULTURESYNC server. Check that it is running, then reload." />;
  }
  if (!team) return <CreateTeam />;
  return (
    <div className="space-y-6">
      <TeamHeader />
      <AddMember />
      {team.members.length === 0 ? (
        <EmptyState icon={Users} title="No members yet" body="Add your first team member, then let each person add cultural interests they are happy to share." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {team.members.map((m) => (
            <MemberCard key={m.id} member={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function CreateTeam() {
  const { createTeam, loadDemo } = useStore();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please give your team a name.");
      return;
    }
    setBusy(true);
    await createTeam(name, desc);
    setBusy(false);
  };

  return (
    <Card className="mx-auto max-w-lg p-6">
      <h1 className="font-display text-2xl text-ink">Create your team</h1>
      <p className="mt-1 text-sm text-ink-soft">A workspace for your team&apos;s shared cultural interests.</p>
      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        <Field label="Team name" error={error}>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setError(null);
            }}
            maxLength={80}
            placeholder="e.g. Product Design, Studio North"
            aria-invalid={error ? "true" : undefined}
          />
        </Field>
        <Field label="Description (optional)">
          <Input value={desc} onChange={(e) => setDesc(e.target.value)} maxLength={300} placeholder="What does this team work on?" />
        </Field>
        <Button type="submit" className="w-full" loading={busy}>
          Create team
        </Button>
      </form>
      <div className="mt-5 border-t border-line pt-5">
        <Button variant="secondary" className="w-full" onClick={() => void loadDemo()}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Or load a sample demo team
        </Button>
        <p className="mt-3 text-xs leading-relaxed text-ink-faint">The demo team is fictional sample data and is labeled as such. It is not Qloo output.</p>
      </div>
    </Card>
  );
}

function TeamHeader() {
  const { team, renameTeam, notify } = useStore();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(team?.name ?? "");
  const [desc, setDesc] = useState(team?.description ?? "");
  if (!team) return null;

  const copyLink = async () => {
    const url = `${window.location.origin}/workspace/?team=${team.id}`;
    try {
      await navigator.clipboard.writeText(url);
      notify("success", "Team link copied. Anyone with it can view and edit this team.");
    } catch {
      notify("info", url);
    }
  };

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl text-ink">{team.name}</h1>
        {team.description ? <p className="mt-1 text-sm text-ink-soft">{team.description}</p> : null}
        <p className="mt-2 text-xs text-ink-faint">
          {team.members.length} {team.members.length === 1 ? "member" : "members"}
        </p>
      </div>
      {editing ? (
        <form
          className="flex w-full max-w-sm flex-col gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!name.trim()) return;
            await renameTeam(name, desc);
            setEditing(false);
          }}
        >
          <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} aria-label="Team name" />
          <Input value={desc} onChange={(e) => setDesc(e.target.value)} maxLength={300} aria-label="Team description" />
          <div className="flex gap-2">
            <Button type="submit">Save</Button>
            <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void copyLink()}>
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Copy team link
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setName(team.name);
              setDesc(team.description ?? "");
              setEditing(true);
            }}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
            Edit team
          </Button>
        </div>
      )}
    </div>
  );
}

function AddMember() {
  const { addMember } = useStore();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter a member name.");
      return;
    }
    setBusy(true);
    const created = await addMember(name);
    setBusy(false);
    if (created) {
      setName("");
      setError(null);
    }
  };

  return (
    <Card className="p-4">
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-center" noValidate>
        <Field label="Add a member" className="flex-1" error={error}>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setError(null);
            }}
            maxLength={60}
            placeholder="Full name, e.g. Amara Okafor"
            aria-invalid={error ? "true" : undefined}
          />
        </Field>
        <Button type="submit" className="sm:mt-5" loading={busy}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add member
        </Button>
      </form>
    </Card>
  );
}

function MemberCard({ member }: { member: Member }) {
  const { renameMember, removeMember, addInterest, removeInterest } = useStore();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(member.name);
  const [adding, setAdding] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const submitName = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed) {
      setNameError("Name cannot be empty.");
      return;
    }
    await renameMember(member.id, trimmed);
    setEditing(false);
    setNameError(null);
  };

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        {editing ? (
          <form onSubmit={submitName} className="flex flex-1 flex-col gap-1">
            <div className="flex items-center gap-2">
              <Input value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={60} aria-label="Member name" autoFocus />
              <Button type="submit">
                <Check className="h-4 w-4" aria-hidden="true" />
                Save
              </Button>
            </div>
            {nameError ? <span role="alert" className="text-xs text-red-700 dark:text-red-400">{nameError}</span> : null}
          </form>
        ) : (
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm font-semibold text-ink">
              {member.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()}
            </span>
            <div>
              <h3 className="text-sm font-semibold text-ink">{member.name}</h3>
              <p className="text-xs text-ink-faint">{member.interests.length} interests shared</p>
            </div>
          </div>
        )}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              setDraft(member.name);
              setEditing((v) => !v);
            }}
            aria-label={`Edit ${member.name}`}
            className="rounded-md p-1.5 text-ink-faint hover:bg-muted hover:text-ink"
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => void removeMember(member.id)}
            aria-label={`Remove ${member.name}`}
            className="rounded-md p-1.5 text-ink-faint hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-700 dark:hover:text-red-400"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {member.interests.length === 0 ? (
          <p className="text-sm text-ink-faint">No interests added yet.</p>
        ) : (
          member.interests.map((i) => (
            <span
              key={i.id}
              title={CATEGORY_LABELS[i.category]}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface py-1 pl-2.5 pr-1 text-xs text-ink"
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[i.category] }} aria-hidden="true" />
              {i.name}
              {i.source === "qloo" ? <Badge tone="blue">Qloo</Badge> : null}
              <button
                type="button"
                onClick={() => void removeInterest(member.id, i.id)}
                aria-label={`Remove ${i.name}`}
                className="rounded-full p-0.5 text-ink-faint hover:bg-muted hover:text-ink"
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </span>
          ))
        )}
      </div>

      {adding ? (
        <AddInterest onAdd={(input) => addInterest(member.id, input)} onCancel={() => setAdding(false)} />
      ) : (
        <Button variant="ghost" className="mt-3 px-2" onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add interest
        </Button>
      )}
    </Card>
  );
}
