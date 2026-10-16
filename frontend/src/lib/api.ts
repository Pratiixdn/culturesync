// Typed client for the CULTURESYNC FastAPI backend. The browser never talks to Qloo.
// Production: same origin ("" base). Dev: NEXT_PUBLIC_API_BASE_URL in .env.development.
import type {
  Activity,
  AgentEvent,
  AgentRun,
  Category,
  ConnectionsData,
  EntityRef,
  Health,
  Idea,
  InterestInput,
  Member,
  Meta,
  QlooMode,
  Team,
} from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status?: number;
  code?: string;

  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

interface Envelope<T> {
  data: T | null;
  meta: Meta;
  error: { code: string; message: string } | null;
}

export interface Result<T> {
  data: T;
  meta: Meta;
}

async function request<T>(
  path: string,
  opts: { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: unknown; timeoutMs?: number } = {}
): Promise<Result<T>> {
  const { method = "GET", body, timeoutMs = 20000 } = opts;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("The server took too long to respond.", undefined, "timeout");
    }
    throw new ApiError("Cannot reach the server. Check your connection and try again.", undefined, "network");
  } finally {
    window.clearTimeout(timer);
  }
  let env: Envelope<T> | null = null;
  try {
    env = (await response.json()) as Envelope<T>;
  } catch {
    // fall through
  }
  if (!response.ok || !env || env.error || env.data === null) {
    throw new ApiError(env?.error?.message ?? `Server returned status ${response.status}.`, response.status, env?.error?.code);
  }
  return { data: env.data, meta: env.meta };
}

/** Reads the agent's server-sent events and hands each one to onEvent. */
async function streamAgent(teamId: string, goal: string, onEvent: (e: AgentEvent) => void): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api/teams/${encodeURIComponent(teamId)}/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }),
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", undefined, "network");
  }
  if (!response.ok || !response.body) {
    let message = `Server returned status ${response.status}.`;
    let code: string | undefined;
    try {
      const env = (await response.json()) as { error?: { code: string; message: string } };
      message = env.error?.message ?? message;
      code = env.error?.code;
    } catch {
      // keep the generic message
    }
    throw new ApiError(message, response.status, code);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      if (part.startsWith("data: ")) onEvent(JSON.parse(part.slice(6)) as AgentEvent);
    }
  }
}

const t = (id: string) => `/api/teams/${encodeURIComponent(id)}`;

export const api = {
  baseUrl: BASE_URL, // empty means same origin
  health: (probe = false) => request<Health>(`/api/health${probe ? "?probe=true" : ""}`, { timeoutMs: 45000 }),

  createTeam: (name: string, description?: string) =>
    request<Team>("/api/teams", { method: "POST", body: { name, description: description || null } }),
  getTeam: (id: string) => request<Team>(t(id)),
  updateTeam: (id: string, patch: { name?: string; description?: string }) =>
    request<Team>(t(id), { method: "PATCH", body: patch }),

  addMember: (id: string, name: string, interests: InterestInput[] = []) =>
    request<Member>(`${t(id)}/members`, { method: "POST", body: { name, interests } }),
  updateMember: (id: string, memberId: string, patch: { name?: string; interests?: InterestInput[] }) =>
    request<Member>(`${t(id)}/members/${encodeURIComponent(memberId)}`, { method: "PATCH", body: patch }),
  removeMember: (id: string, memberId: string) =>
    request<Team>(`${t(id)}/members/${encodeURIComponent(memberId)}`, { method: "DELETE" }),

  searchEntities: (q: string, category?: Category) =>
    request<{ query: string; category: Category | null; results: EntityRef[] }>(
      `/api/entities/search?q=${encodeURIComponent(q)}${category ? `&category=${category}` : ""}`
    ),
  connections: (id: string) => request<ConnectionsData>(`${t(id)}/connections`),
  runInsights: (id: string, suggestCategories?: Category[]) =>
    request<ConnectionsData>(`${t(id)}/insights`, {
      method: "POST",
      body: suggestCategories ? { suggest_categories: suggestCategories } : {},
      timeoutMs: 60000,
    }),

  streamAgent,
  listAgentRuns: (id: string) => request<{ runs: AgentRun[] }>(`${t(id)}/agent/runs`),

  createActivity: (id: string, connectionIds: string[]) =>
    request<Activity>(`${t(id)}/activities`, { method: "POST", body: { connection_ids: connectionIds } }),
  listActivities: (id: string) => request<Activity[]>(`${t(id)}/activities`),
  deleteActivity: (id: string, activityId: string) =>
    request<{ deleted: string }>(`${t(id)}/activities/${encodeURIComponent(activityId)}`, { method: "DELETE" }),

  addIdea: (id: string, text: string, activityId?: string) =>
    request<Idea>(`${t(id)}/ideas`, { method: "POST", body: { text, activity_id: activityId ?? null } }),
  listIdeas: (id: string) => request<Idea[]>(`${t(id)}/ideas`),
  deleteIdea: (id: string, ideaId: string) =>
    request<{ deleted: string }>(`${t(id)}/ideas/${encodeURIComponent(ideaId)}`, { method: "DELETE" }),
};

export type { QlooMode };
