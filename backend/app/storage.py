"""SQLite persistence. One shared connection guarded by a lock."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .schemas import MAX_INTERESTS, MAX_MEMBERS

MAX_TEAMS = 2000
MAX_IDEAS = 200
MAX_ACTIVITIES = 50
KEEP_AGENT_RUNS = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members (
  id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  name TEXT NOT NULL, interests TEXT NOT NULL DEFAULT '[]', position INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  text TEXT NOT NULL, activity_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activities (
  id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS analyses (
  team_id TEXT PRIMARY KEY REFERENCES teams(id) ON DELETE CASCADE,
  signature TEXT NOT NULL, body TEXT NOT NULL);
"""


class LimitError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def short_id() -> str:
    return uuid.uuid4().hex[:12]


class Storage:
    def __init__(self, database_url: str = "sqlite:///./culturesync.db"):
        path = database_url.removeprefix("sqlite:///")
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    def _all(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return self._run(sql, args).fetchall()

    def _count(self, table: str, team_id: Optional[str] = None) -> int:
        if team_id is None:
            return self._all(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]
        return self._all(f"SELECT COUNT(*) AS n FROM {table} WHERE team_id=?", (team_id,))[0]["n"]

    # teams
    def create_team(self, name: str, description: Optional[str]) -> str:
        if self._count("teams") >= MAX_TEAMS:
            raise LimitError("This server has reached its team limit.")
        team_id = uuid.uuid4().hex  # unguessable, doubles as the access link
        self._run("INSERT INTO teams VALUES (?,?,?,?)", (team_id, name, description or None, now()))
        return team_id

    def get_team(self, team_id: str) -> Optional[dict[str, Any]]:
        rows = self._all("SELECT * FROM teams WHERE id=?", (team_id,))
        if not rows:
            return None
        members = self._all("SELECT * FROM members WHERE team_id=? ORDER BY position, rowid", (team_id,))
        return {
            **dict(rows[0]),
            "members": [{"id": m["id"], "name": m["name"], "interests": json.loads(m["interests"])} for m in members],
        }

    def update_team(self, team_id: str, name: Optional[str], description: Optional[str]) -> None:
        if name is not None:
            self._run("UPDATE teams SET name=? WHERE id=?", (name, team_id))
        if description is not None:
            self._run("UPDATE teams SET description=? WHERE id=?", (description or None, team_id))

    # members
    def add_member(self, team_id: str, name: str, interests: list[dict]) -> str:
        if self._count("members", team_id) >= MAX_MEMBERS:
            raise LimitError(f"A team can have at most {MAX_MEMBERS} members.")
        last = self._all("SELECT MAX(position) AS p FROM members WHERE team_id=?", (team_id,))[0]["p"]
        member_id = short_id()
        self._run("INSERT INTO members VALUES (?,?,?,?,?)",
                  (member_id, team_id, name, json.dumps(interests[:MAX_INTERESTS]), 0 if last is None else last + 1))
        return member_id

    def update_member(self, team_id: str, member_id: str, name: Optional[str], interests: Optional[list[dict]]) -> bool:
        if not self._all("SELECT 1 FROM members WHERE id=? AND team_id=?", (member_id, team_id)):
            return False
        if name is not None:
            self._run("UPDATE members SET name=? WHERE id=?", (name, member_id))
        if interests is not None:
            self._run("UPDATE members SET interests=? WHERE id=?", (json.dumps(interests), member_id))
        return True

    def delete_member(self, team_id: str, member_id: str) -> bool:
        return self._run("DELETE FROM members WHERE id=? AND team_id=?", (member_id, team_id)).rowcount > 0

    # ideas
    def add_idea(self, team_id: str, text: str, activity_id: Optional[str]) -> dict:
        if self._count("ideas", team_id) >= MAX_IDEAS:
            raise LimitError("This team has reached its idea limit.")
        idea = {"id": short_id(), "text": text, "activity_id": activity_id, "created_at": now()}
        self._run("INSERT INTO ideas VALUES (?,?,?,?,?)", (idea["id"], team_id, text, activity_id, idea["created_at"]))
        return idea

    def list_ideas(self, team_id: str) -> list[dict]:
        rows = self._all("SELECT id, text, activity_id, created_at FROM ideas WHERE team_id=? ORDER BY rowid", (team_id,))
        return [dict(r) for r in rows]

    def delete_idea(self, team_id: str, idea_id: str) -> bool:
        return self._run("DELETE FROM ideas WHERE id=? AND team_id=?", (idea_id, team_id)).rowcount > 0

    # activities
    def save_activity(self, team_id: str, activity: dict) -> None:
        exists = self._all("SELECT 1 FROM activities WHERE id=?", (activity["id"],))
        if not exists and self._count("activities", team_id) >= MAX_ACTIVITIES:
            raise LimitError("This team has reached its activity limit.")
        self._run("INSERT OR REPLACE INTO activities VALUES (?,?,?,?)",
                  (activity["id"], team_id, json.dumps(activity), activity["created_at"]))

    def list_activities(self, team_id: str) -> list[dict]:
        rows = self._all("SELECT body FROM activities WHERE team_id=? ORDER BY rowid DESC", (team_id,))
        return [json.loads(r["body"]) for r in rows]

    def delete_activity(self, team_id: str, activity_id: str) -> bool:
        self._run("DELETE FROM ideas WHERE team_id=? AND activity_id=?", (team_id, activity_id))
        return self._run("DELETE FROM activities WHERE id=? AND team_id=?", (activity_id, team_id)).rowcount > 0

    # last Qloo analysis per team
    def save_analysis(self, team_id: str, signature: str, body: dict) -> None:
        self._run("INSERT OR REPLACE INTO analyses VALUES (?,?,?)", (team_id, signature, json.dumps(body)))

    def get_analysis(self, team_id: str) -> Optional[tuple[str, dict]]:
        rows = self._all("SELECT signature, body FROM analyses WHERE team_id=?", (team_id,))
        return (rows[0]["signature"], json.loads(rows[0]["body"])) if rows else None

    # agent runs (newest first, last few kept)
    def save_agent_run(self, team_id: str, run: dict) -> None:
        self._run("INSERT OR REPLACE INTO agent_runs VALUES (?,?,?,?)", (run["id"], team_id, json.dumps(run), run["created_at"]))
        self._run("DELETE FROM agent_runs WHERE team_id=? AND id NOT IN "
                  "(SELECT id FROM agent_runs WHERE team_id=? ORDER BY rowid DESC LIMIT ?)", (team_id, team_id, KEEP_AGENT_RUNS))

    def list_agent_runs(self, team_id: str) -> list[dict]:
        rows = self._all("SELECT body FROM agent_runs WHERE team_id=? ORDER BY rowid DESC", (team_id,))
        return [json.loads(r["body"]) for r in rows]
