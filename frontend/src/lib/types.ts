// Mirrors backend/app/schemas.py. Keep in sync.

export type Category = "music" | "movies" | "tv" | "books" | "brands" | "games" | "podcasts" | "places" | "destinations";

export const CATEGORIES: Category[] = ["music", "movies", "tv", "books", "brands", "games", "podcasts", "places", "destinations"];

export const CATEGORY_LABELS: Record<Category, string> = {
  music: "Music",
  movies: "Movies",
  tv: "TV shows",
  books: "Books",
  brands: "Brands",
  games: "Video games",
  podcasts: "Podcasts",
  places: "Dining & places",
  destinations: "Travel",
};

export const CATEGORY_COLORS: Record<Category, string> = {
  music: "#EA580C",
  movies: "#3B82F6",
  tv: "#06B6D4",
  books: "#22C55E",
  brands: "#8B5CF6",
  games: "#EC4899",
  podcasts: "#F59E0B",
  places: "#EF4444",
  destinations: "#14B8A6",
};

export type QlooMode = "live" | "mock";

export interface Meta {
  source: "local" | "qloo";
  mode: QlooMode;
}

export interface EntityRef {
  id: string;
  name: string;
  types: string[];
  affinity: number | null;
}

export interface Interest {
  id: string;
  name: string;
  category: Category;
  entity_id: string | null;
  entity_name: string | null;
  source: "manual" | "qloo";
}

export interface InterestInput {
  name: string;
  category: Category;
  entity_id?: string | null;
  entity_name?: string | null;
}

export interface Member {
  id: string;
  name: string;
  interests: Interest[];
}

export interface Team {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  members: Member[];
}

export type ConnectionKind = "shared_interest" | "same_category" | "qloo_affinity";

export interface ConnectionEntity {
  role: "shared" | "listed" | "signal" | "result";
  member_id: string;
  name: string;
  category: Category;
  entity_id: string | null;
  affinity: number | null;
}

export interface Connection {
  id: string;
  kind: ConnectionKind;
  source: "local" | "qloo";
  member_ids: string[];
  entities: ConnectionEntity[];
  evidence: string;
  basis: "entity_id" | "name" | null;
  caveat: string | null;
}

export interface Resolution {
  member_id: string;
  interest_id: string;
  name: string;
  entity: EntityRef;
}

export interface Suggestion {
  category: Category;
  signal_entities: EntityRef[];
  entities: EntityRef[];
}

export interface AnalysisInfo {
  ran_at: string;
  mode: QlooMode;
  qloo_calls: number;
  truncated: boolean;
}

export interface ConnectionsData {
  connections: Connection[];
  suggestions: Suggestion[];
  resolutions: Resolution[];
  analysis: AnalysisInfo | null;
  analysis_stale: boolean;
  limitations: string[];
}

export interface Activity {
  id: string;
  title: string;
  objective: string;
  prompts: string[];
  connection_ids: string[];
  member_ids: string[];
  basis: "application_template";
  created_at: string;
}

export interface Idea {
  id: string;
  text: string;
  activity_id: string | null;
  created_at: string;
}

export interface Health {
  status: "ok";
  service: string;
  qloo_configured: boolean;
  mode: QlooMode;
  agent_configured: boolean;
  qloo_reachable: boolean | null;
  qloo_error: string | null;
}

export type ApiMode = "checking" | "live" | "mock" | "offline";

export interface AgentStep {
  tool: string;
  summary: string;
  ok: boolean;
}

export interface AgentRecommendation {
  entity_id: string;
  title: string;
  category: string | null;
  affinity: number | null;
  why: string;
  supported_by: string[];
}

export interface AgentRun {
  id: string;
  goal: string;
  summary: string;
  recommendations: AgentRecommendation[];
  caveats: string[];
  dropped_ungrounded: number;
  steps: AgentStep[];
  qloo_calls: number;
  model: string;
  created_at: string;
}

export type AgentEvent =
  | { type: "start"; mode: QlooMode }
  | ({ type: "step" } & AgentStep)
  | { type: "result"; data: AgentRun }
  | { type: "error"; code: string; message: string };
