import type { Connection, ConnectionKind } from "./types";

export interface PairEdge {
  id: string;
  aId: string;
  bId: string;
  kind: ConnectionKind; // strongest evidence on the pair
  connections: Connection[];
}

const RANK: Record<ConnectionKind, number> = { shared_interest: 3, qloo_affinity: 2, same_category: 1 };

/** One visual edge per member pair; all underlying connections stay inspectable. */
export function groupByPair(connections: Connection[]): PairEdge[] {
  const map = new Map<string, PairEdge>();
  for (const c of connections) {
    const [a, b] = [...c.member_ids].sort();
    const key = `${a}::${b}`;
    const edge = map.get(key) ?? { id: key, aId: a, bId: b, kind: c.kind, connections: [] };
    edge.connections.push(c);
    if (RANK[c.kind] > RANK[edge.kind]) edge.kind = c.kind;
    map.set(key, edge);
  }
  return [...map.values()];
}

export const KIND_LABEL: Record<ConnectionKind, string> = {
  shared_interest: "Shared interest",
  qloo_affinity: "Qloo affinity",
  same_category: "Same category",
};

export const first = (name: string): string => name.split(" ")[0] ?? name;
