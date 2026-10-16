"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { CATEGORIES, CATEGORY_LABELS, Category, EntityRef, InterestInput } from "../lib/types";
import { Badge, Button, Field, Input, Select, Spinner } from "./ui";
import { useStore } from "../lib/store";

/** Category + typeahead over Qloo entity search. Picking a result links the interest to a Qloo entity. */
export default function AddInterest({ onAdd, onCancel }: { onAdd: (i: InterestInput) => Promise<boolean>; onCancel: () => void }) {
  const { mode } = useStore();
  const [category, setCategory] = useState<Category>("music");
  const [text, setText] = useState("");
  const [results, setResults] = useState<EntityRef[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const q = text.trim();
    setSearchError(null);
    if (q.length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    const mine = ++seq.current;
    setSearching(true);
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await api.searchEntities(q, category);
        if (mine === seq.current) setResults(data.results);
      } catch (err) {
        if (mine === seq.current) {
          setResults([]);
          setSearchError(err instanceof ApiError ? err.message : "Search failed.");
        }
      } finally {
        if (mine === seq.current) setSearching(false);
      }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [text, category]);

  const add = async (input: InterestInput) => {
    setSaving(true);
    const ok = await onAdd(input);
    setSaving(false);
    if (ok) {
      setText("");
      setResults([]);
    }
  };

  const submitManual = (e: FormEvent) => {
    e.preventDefault();
    void add({ name: text, category });
  };

  return (
    <form onSubmit={submitManual} className="mt-4 space-y-3 rounded-lg border border-line bg-paper p-3" noValidate>
      <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
        <Field label="Category">
          <Select value={category} onChange={(e) => setCategory(e.target.value as Category)} aria-label="Interest category">
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Interest">
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Search Qloo, or type your own" autoFocus />
        </Field>
      </div>

      {searching ? <Spinner label="Searching..." /> : null}
      {searchError ? (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          {searchError} You can still add it as typed.
        </p>
      ) : null}
      {results.length > 0 ? (
        <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface" aria-label="Search results">
          {results.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                disabled={saving}
                onClick={() => void add({ name: r.name, category, entity_id: r.id, entity_name: r.name })}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-muted disabled:opacity-50"
              >
                <span className="flex items-center gap-2 text-ink">
                  <Search className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
                  {r.name}
                </span>
                <Badge tone={mode === "live" ? "blue" : "amber"}>{mode === "live" ? "Qloo match" : "Mock sample"}</Badge>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="secondary" loading={saving} disabled={!text.trim()}>
          Add &ldquo;{text.trim() || "..."}&rdquo; as typed
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <p className="text-xs text-ink-faint">Pick a search result to link the interest to a specific Qloo entity. Typed interests still count for direct overlaps (matched by name).</p>
    </form>
  );
}
