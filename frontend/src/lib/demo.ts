import type { InterestInput } from "./types";

// Sample team, created on the backend only when the user clicks "Load demo team".
// Interests are plain names (not linked to Qloo entities) - it is sample data, labeled as such in the team name.

const m = (name: string, category: InterestInput["category"]): InterestInput => ({ name, category });

export const DEMO_TEAM = { name: "Studio North (demo)", description: "Sample team - fictional people, sample interests." };

export const DEMO_MEMBERS: Array<{ name: string; interests: InterestInput[] }> = [
  { name: "Amara Okafor", interests: [m("Burna Boy", "music"), m("Tame Impala", "music"), m("Severance", "tv"), m("Patagonia", "brands")] },
  { name: "Diego Reyes", interests: [m("Parasite", "movies"), m("Everything Everywhere All at Once", "movies"), m("Hades", "games"), m("Patagonia", "brands")] },
  { name: "Yuki Tanaka", interests: [m("Tame Impala", "music"), m("Daft Punk", "music"), m("Celeste", "games"), m("Muji", "brands")] },
  { name: "Sofia Lindqvist", interests: [m("Amelie", "movies"), m("Parasite", "movies"), m("Piranesi", "books"), m("IKEA", "brands")] },
];
