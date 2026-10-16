"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Link2, Monitor, Moon, RefreshCw, ShieldCheck, Sun, Trash2, XCircle } from "lucide-react";
import { api } from "../../lib/api";
import { useStore } from "../../lib/store";
import { ThemeChoice, useTheme } from "../../lib/theme";
import { Badge, Button, Card, cn } from "../../components/ui";

const THEME_OPTIONS: Array<{ value: ThemeChoice; label: string; icon: typeof Sun }> = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-ink">{children}</dd>
    </div>
  );
}

export default function SettingsPage() {
  const { mode, health, team, checkHealth, forgetTeam, notify } = useStore();
  const { choice, setChoice } = useTheme();
  const [checking, setChecking] = useState<"server" | "qloo" | null>(null);
  const [origin, setOrigin] = useState("");

  useEffect(() => setOrigin(window.location.origin), []);

  const runCheck = async (probe: boolean) => {
    setChecking(probe ? "qloo" : "server");
    const info = await checkHealth(probe);
    setChecking(null);
    if (!info.ok) notify("error", info.error ?? "Server unreachable.");
    else if (probe) notify(info.qloo_reachable ? "success" : "error", info.qloo_reachable ? "Qloo request succeeded." : `Qloo request failed (${info.qloo_error ?? "unknown"}).`);
    else notify("success", "Server is reachable.");
  };

  const copyTeamLink = async () => {
    if (!team) return;
    const url = `${window.location.origin}/workspace/?team=${team.id}`;
    try {
      await navigator.clipboard.writeText(url);
      notify("success", "Team link copied. Anyone with it can view and edit this team.");
    } catch {
      notify("info", url);
    }
  };

  const forget = () => {
    forgetTeam();
    notify("info", "Team forgotten on this device. Use the team link to open it again.");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl text-ink">Settings &amp; API status</h1>
        <p className="mt-1 text-sm text-ink-soft">Appearance, server connectivity, and safe diagnostics.</p>
      </div>

      <Card className="p-6">
        <h2 className="text-sm font-semibold text-ink">Appearance</h2>
        <p className="mt-1 text-xs text-ink-faint">Applies to every page. System follows your device setting.</p>
        <div role="radiogroup" aria-label="Theme" className="mt-4 inline-flex rounded-lg border border-line bg-paper p-1">
          {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={choice === value}
              onClick={() => setChoice(value)}
              className={cn(
                "inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm transition-colors",
                choice === value ? "bg-accent text-accent-on" : "text-ink-soft hover:text-ink"
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {health?.ok ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            ) : (
              <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" aria-hidden="true" />
            )}
            <div>
              <h2 className="text-sm font-semibold text-ink">Server &amp; Qloo</h2>
              <p className="text-xs text-ink-faint">
                {mode === "live" ? "Live: the server has a Qloo API key." : mode === "mock" ? "Mock: no Qloo key, sample data only." : mode === "offline" ? "Server unreachable." : "Checking..."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => void runCheck(false)} loading={checking === "server"} disabled={checking !== null}>
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Check server
            </Button>
            <Button variant="secondary" onClick={() => void runCheck(true)} loading={checking === "qloo"} disabled={checking !== null || mode !== "live"}>
              Test Qloo request
            </Button>
          </div>
        </div>
        {mode === "mock" ? <p className="mt-3 text-xs text-ink-faint">Test Qloo request is available once QLOO_API_KEY is set on the server.</p> : null}

        <dl className="mt-6 grid gap-x-8 gap-y-3 border-t border-line pt-5 text-sm sm:grid-cols-2">
          <Row label="API base"><span className="font-mono text-xs">{api.baseUrl || origin || "-"}</span></Row>
          <Row label="Server">{health?.ok ? <Badge tone="green">Reachable</Badge> : <Badge tone="red">Unreachable</Badge>}</Row>
          <Row label="Mode">{mode === "live" ? <Badge tone="green">Live Qloo</Badge> : mode === "mock" ? <Badge tone="amber">Mock (not Qloo data)</Badge> : "-"}</Row>
          <Row label="Agent (language model)">{health?.agent_configured === undefined ? "-" : health.agent_configured ? <Badge tone="green">Configured</Badge> : <Badge tone="amber">Off (no GEMINI_API_KEY)</Badge>}</Row>
          <Row label="Qloo key configured">{health?.qloo_configured === undefined ? "-" : health.qloo_configured ? "Yes" : "No"}</Row>
          <Row label="Last Qloo test">
            {health?.qloo_reachable == null ? "Not run" : health.qloo_reachable ? <Badge tone="green">Request succeeded</Badge> : <Badge tone="red">Failed ({health.qloo_error})</Badge>}
          </Row>
          <Row label="Latency">{health?.latencyMs != null ? `${health.latencyMs} ms` : "-"}</Row>
          <Row label="Last checked">{health ? new Date(health.checkedAt).toLocaleString() : "-"}</Row>
        </dl>

        {health && !health.ok ? (
          <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
            {health.error}
          </div>
        ) : null}
      </Card>

      <Card className="p-6">
        <h2 className="text-sm font-semibold text-ink">Your team on this device</h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-faint">
          {team ? `Current team: ${team.name}. ` : "No team selected. "}
          This browser remembers the id of your current team. Forgetting it does not delete the team on the server.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" disabled={!team} onClick={() => void copyTeamLink()}>
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Copy team link
          </Button>
          <Button variant="secondary" disabled={!team} onClick={forget}>
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Forget team on this device
          </Button>
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 text-ink-soft" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold text-ink">Security notes</h2>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-xs leading-relaxed text-ink-soft">
              <li>The Qloo API key lives only on the server. The browser never sees it and never calls Qloo.</li>
              <li>There are no accounts. Whoever has a team link can view and edit that team, so share it only with the team.</li>
              <li>Avoid entering sensitive personal data. Interests are voluntary cultural picks, not assessments.</li>
              <li>This page shows only safe diagnostics: no secrets, stack traces, or environment details.</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
