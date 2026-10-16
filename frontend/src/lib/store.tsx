"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { DEMO_MEMBERS, DEMO_TEAM } from "./demo";
import type {
  Activity,
  AgentRun,
  AgentStep,
  ApiMode,
  Category,
  ConnectionsData,
  Health,
  Idea,
  InterestInput,
  Member,
  Team,
} from "./types";

export interface ToastMsg {
  id: number;
  kind: "success" | "error" | "info";
  text: string;
}

export interface HealthInfo extends Partial<Health> {
  ok: boolean;
  latencyMs?: number;
  error?: string;
  checkedAt: string;
}

interface StoreValue {
  ready: boolean;
  team: Team | null;
  mode: ApiMode;
  health: HealthInfo | null;
  toasts: ToastMsg[];
  connData: ConnectionsData | null;
  activities: Activity[];
  ideas: Idea[];
  analyzing: boolean;
  agentRuns: AgentRun[];
  agentSteps: AgentStep[];
  agentRunning: boolean;
  agentError: string | null;
  runAgent: (goal: string) => Promise<void>;
  notify: (kind: ToastMsg["kind"], text: string) => void;
  dismissToast: (id: number) => void;
  checkHealth: (probe?: boolean) => Promise<HealthInfo>;
  createTeam: (name: string, description?: string) => Promise<boolean>;
  renameTeam: (name: string, description?: string) => Promise<void>;
  forgetTeam: () => void;
  loadDemo: () => Promise<void>;
  addMember: (name: string) => Promise<Member | null>;
  renameMember: (id: string, name: string) => Promise<void>;
  removeMember: (id: string) => Promise<void>;
  addInterest: (memberId: string, input: InterestInput) => Promise<boolean>;
  removeInterest: (memberId: string, interestId: string) => Promise<void>;
  runAnalysis: (suggestCategories?: Category[]) => Promise<void>;
  createActivity: (connectionIds: string[]) => Promise<Activity | null>;
  removeActivity: (id: string) => Promise<void>;
  addIdea: (text: string, activityId?: string) => Promise<boolean>;
  removeIdea: (id: string) => Promise<void>;
}

const StoreContext = createContext<StoreValue | null>(null);

export function useStore(): StoreValue {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used inside StoreProvider");
  return ctx;
}

const LS_TEAM = "culturesync.teamId.v2";

const toInput = (i: Member["interests"][number]): InterestInput => ({
  name: i.name,
  category: i.category,
  entity_id: i.entity_id,
  entity_name: i.entity_name,
});

const msg = (err: unknown): string => (err instanceof ApiError ? err.message : "Something went wrong.");

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [team, setTeam] = useState<Team | null>(null);
  const [connData, setConnData] = useState<ConnectionsData | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [mode, setMode] = useState<ApiMode>("checking");
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const toastId = useRef(0);
  const teamRef = useRef<Team | null>(null);
  teamRef.current = team;

  const notify = useCallback((kind: ToastMsg["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const checkHealth = useCallback(async (probe = false): Promise<HealthInfo> => {
    const started = performance.now();
    const elapsed = () => Math.round(performance.now() - started);
    let info: HealthInfo;
    try {
      const { data } = await api.health(probe);
      info = { ...data, ok: true, latencyMs: elapsed(), checkedAt: new Date().toISOString() };
      setMode(data.mode);
    } catch (err) {
      info = { ok: false, error: msg(err), latencyMs: elapsed(), checkedAt: new Date().toISOString() };
      setMode("offline");
    }
    setHealth(info);
    return info;
  }, []);

  const forgetTeam = useCallback(() => {
    window.localStorage.removeItem(LS_TEAM);
    setTeam(null);
    setConnData(null);
    setActivities([]);
    setIdeas([]);
    setAgentRuns([]);
    setAgentSteps([]);
    setAgentError(null);
  }, []);

  const loadAll = useCallback(
    async (id: string): Promise<boolean> => {
      try {
        const [t, c, a, i, r] = await Promise.all([api.getTeam(id), api.connections(id), api.listActivities(id), api.listIdeas(id), api.listAgentRuns(id)]);
        setTeam(t.data);
        setConnData(c.data);
        setActivities(a.data);
        setIdeas(i.data);
        setAgentRuns(r.data.runs);
        window.localStorage.setItem(LS_TEAM, id);
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          forgetTeam();
          notify("info", "That team no longer exists on the server. Create a new one.");
        } else {
          notify("error", msg(err));
        }
        return false;
      }
    },
    [forgetTeam, notify]
  );

  // Initial load: health, then the team from ?team=<id> (share link) or localStorage.
  useEffect(() => {
    (async () => {
      await checkHealth();
      const fromUrl = new URLSearchParams(window.location.search).get("team");
      const id = fromUrl || window.localStorage.getItem(LS_TEAM);
      if (id) await loadAll(id);
      setReady(true);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready || mode !== "offline") return;
    const timer = window.setInterval(async () => {
      const info = await checkHealth();
      const savedId = window.localStorage.getItem(LS_TEAM);
      if (info.ok && savedId && !teamRef.current) await loadAll(savedId);
    }, 8000);
    return () => window.clearInterval(timer);
  }, [ready, mode, checkHealth, loadAll]);

  const refreshConnections = useCallback(async (id: string) => {
    try {
      setConnData((await api.connections(id)).data);
    } catch {
      // non-fatal: keep previous connections
    }
  }, []);

  const replaceMember = useCallback((m: Member) => {
    setTeam((t) => (t ? { ...t, members: t.members.map((x) => (x.id === m.id ? m : x)) } : t));
  }, []);

  const createTeam = useCallback(
    async (name: string, description?: string) => {
      try {
        const { data } = await api.createTeam(name.trim(), description?.trim());
        forgetTeam();
        setTeam(data);
        window.localStorage.setItem(LS_TEAM, data.id);
        await refreshConnections(data.id);
        notify("success", "Team created.");
        return true;
      } catch (err) {
        notify("error", msg(err));
        return false;
      }
    },
    [forgetTeam, notify, refreshConnections]
  );

  const renameTeam = useCallback(
    async (name: string, description?: string) => {
      const t = teamRef.current;
      if (!t) return;
      try {
        setTeam((await api.updateTeam(t.id, { name: name.trim(), description: description?.trim() ?? "" })).data);
      } catch (err) {
        notify("error", msg(err));
      }
    },
    [notify]
  );

  const loadDemo = useCallback(async () => {
    try {
      const { data } = await api.createTeam(DEMO_TEAM.name, DEMO_TEAM.description);
      for (const m of DEMO_MEMBERS) await api.addMember(data.id, m.name, m.interests);
      await loadAll(data.id);
      notify("info", "Demo team loaded. It is sample data, not Qloo results.");
    } catch (err) {
      notify("error", msg(err));
    }
  }, [loadAll, notify]);

  const addMember = useCallback(
    async (name: string): Promise<Member | null> => {
      const t = teamRef.current;
      const trimmed = name.trim();
      if (!t) return null;
      if (!trimmed) {
        notify("error", "Please enter a member name.");
        return null;
      }
      if (t.members.some((m) => m.name.toLowerCase() === trimmed.toLowerCase())) {
        notify("error", `${trimmed} is already on the team.`);
        return null;
      }
      try {
        const { data } = await api.addMember(t.id, trimmed);
        setTeam((cur) => (cur ? { ...cur, members: [...cur.members, data] } : cur));
        void refreshConnections(t.id);
        return data;
      } catch (err) {
        notify("error", msg(err));
        return null;
      }
    },
    [notify, refreshConnections]
  );

  const renameMember = useCallback(
    async (id: string, name: string) => {
      const t = teamRef.current;
      if (!t) return;
      try {
        replaceMember((await api.updateMember(t.id, id, { name })).data);
      } catch (err) {
        notify("error", msg(err));
      }
    },
    [notify, replaceMember]
  );

  const removeMember = useCallback(
    async (id: string) => {
      const t = teamRef.current;
      if (!t) return;
      try {
        setTeam((await api.removeMember(t.id, id)).data);
        void refreshConnections(t.id);
      } catch (err) {
        notify("error", msg(err));
      }
    },
    [notify, refreshConnections]
  );

  const addInterest = useCallback(
    async (memberId: string, input: InterestInput): Promise<boolean> => {
      const t = teamRef.current;
      const member = t?.members.find((m) => m.id === memberId);
      if (!t || !member) return false;
      const name = input.name.trim();
      if (!name) {
        notify("error", "Please enter an interest.");
        return false;
      }
      if (member.interests.some((i) => i.category === input.category && i.name.toLowerCase() === name.toLowerCase())) {
        notify("error", `${name} is already on ${member.name.split(" ")[0]}'s list.`);
        return false;
      }
      try {
        const interests = [...member.interests.map(toInput), { ...input, name }];
        replaceMember((await api.updateMember(t.id, memberId, { interests })).data);
        void refreshConnections(t.id);
        return true;
      } catch (err) {
        notify("error", msg(err));
        return false;
      }
    },
    [notify, refreshConnections, replaceMember]
  );

  const removeInterest = useCallback(
    async (memberId: string, interestId: string) => {
      const t = teamRef.current;
      const member = t?.members.find((m) => m.id === memberId);
      if (!t || !member) return;
      try {
        const interests = member.interests.filter((i) => i.id !== interestId).map(toInput);
        replaceMember((await api.updateMember(t.id, memberId, { interests })).data);
        void refreshConnections(t.id);
      } catch (err) {
        notify("error", msg(err));
      }
    },
    [notify, refreshConnections, replaceMember]
  );

  const runAnalysis = useCallback(
    async (suggestCategories?: Category[]) => {
      const t = teamRef.current;
      if (!t) return;
      setAnalyzing(true);
      try {
        setConnData((await api.runInsights(t.id, suggestCategories)).data);
      } catch (err) {
        notify("error", msg(err));
      } finally {
        setAnalyzing(false);
      }
    },
    [notify]
  );

  const runAgent = useCallback(
    async (goal: string) => {
      const t = teamRef.current;
      if (!t) return;
      setAgentRunning(true);
      setAgentSteps([]);
      setAgentError(null);
      let finished = false;
      try {
        await api.streamAgent(t.id, goal, (event) => {
          if (event.type === "step") setAgentSteps((s) => [...s, { tool: event.tool, summary: event.summary, ok: event.ok }]);
          if (event.type === "result") {
            finished = true;
            setAgentRuns((runs) => [event.data, ...runs.filter((r) => r.id !== event.data.id)].slice(0, 5));
          }
          if (event.type === "error") {
            finished = true;
            setAgentError(event.message);
          }
        });
        if (!finished) setAgentError("The agent connection closed before it finished. Try again.");
      } catch (err) {
        setAgentError(msg(err));
      } finally {
        setAgentRunning(false);
      }
    },
    []
  );

  const createActivity = useCallback(
    async (connectionIds: string[]): Promise<Activity | null> => {
      const t = teamRef.current;
      if (!t) return null;
      try {
        const { data } = await api.createActivity(t.id, connectionIds);
        setActivities((list) => [data, ...list.filter((a) => a.id !== data.id)]);
        return data;
      } catch (err) {
        notify("error", msg(err));
        return null;
      }
    },
    [notify]
  );

  const removeActivity = useCallback(
    async (id: string) => {
      const t = teamRef.current;
      if (!t) return;
      try {
        await api.deleteActivity(t.id, id);
        setActivities((l) => l.filter((a) => a.id !== id));
        setIdeas((l) => l.filter((i) => i.activity_id !== id));
      } catch (err) {
        notify("error", msg(err));
      }
    },
    [notify]
  );

  const addIdea = useCallback(
    async (text: string, activityId?: string): Promise<boolean> => {
      const t = teamRef.current;
      if (!t) return false;
      if (!text.trim()) {
        notify("error", "Write an idea first.");
        return false;
      }
      try {
        const { data } = await api.addIdea(t.id, text.trim(), activityId);
        setIdeas((l) => [...l, data]);
        return true;
      } catch (err) {
        notify("error", msg(err));
        return false;
      }
    },
    [notify]
  );

  const removeIdea = useCallback(
    async (id: string) => {
      const t = teamRef.current;
      if (!t) return;
      try {
        await api.deleteIdea(t.id, id);
        setIdeas((l) => l.filter((i) => i.id !== id));
      } catch (err) {
        notify("error", msg(err));
      }
    },
    [notify]
  );

  const value = useMemo<StoreValue>(
    () => ({
      ready, team, mode, health, toasts, connData, activities, ideas, analyzing,
      agentRuns, agentSteps, agentRunning, agentError, runAgent,
      notify, dismissToast, checkHealth, createTeam, renameTeam, forgetTeam, loadDemo,
      addMember, renameMember, removeMember, addInterest, removeInterest, runAnalysis,
      createActivity, removeActivity, addIdea, removeIdea,
    }),
    [
      ready, team, mode, health, toasts, connData, activities, ideas, analyzing,
      agentRuns, agentSteps, agentRunning, agentError, runAgent,
      notify, dismissToast, checkHealth, createTeam, renameTeam, forgetTeam, loadDemo,
      addMember, renameMember, removeMember, addInterest, removeInterest, runAnalysis,
      createActivity, removeActivity, addIdea, removeIdea,
    ]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}
