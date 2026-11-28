"""Local durable attempt ledger, not a shared GitHub runner quota store.

Use only a private persistent directory shared by all local callers.
No upstream content or API credentials are stored.
"""
import json
import os
import sqlite3
from datetime import timedelta, timezone
from pathlib import Path
from scripts.revid_research_core import quota_remaining


class LocalQuota:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("absolute private ledger path required")
        root = Path(__file__).resolve().parents[1]
        if self.path.resolve().is_relative_to(root):
            raise ValueError("ledger must be outside repository")

    def initialize(self):
        """Explicit one-time initialization; never silently reset a lost ledger."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), attempts TEXT NOT NULL, blocked_until TEXT)")
            db.execute("INSERT INTO state VALUES (1, '[]', NULL)")

    def _connect(self):
        return sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)

    def reserve(self, now):
        if now.tzinfo is None:
            return False
        now = now.astimezone(timezone.utc)
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT attempts, blocked_until FROM state WHERE id=1").fetchone()
                if not row:
                    return False
                attempts = json.loads(row[0])
                if not isinstance(attempts, list) or not quota_remaining(attempts, now):
                    return False
                from scripts.revid_research_core import parse_time
                if row[1] is not None:
                    blocked = parse_time(row[1])
                    if blocked is None or blocked > now:
                        return False
                attempts = [v for v in attempts if parse_time(v) > now - timedelta(hours=24)]
                attempts.append(now.isoformat())
                db.execute("UPDATE state SET attempts=? WHERE id=1", (json.dumps(attempts),))
                return True
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return False

    def cool_down(self, now):
        """Conservative 24h halt after a provider 429. Persist before next call."""
        if now.tzinfo is None:
            raise ValueError("aware time required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT blocked_until FROM state WHERE id=1").fetchone()
            if row is None:
                raise ValueError("missing ledger state")
            from scripts.revid_research_core import parse_time
            until = now.astimezone(timezone.utc) + timedelta(hours=24)
            if row[0] is not None:
                previous = parse_time(row[0])
                if previous is None:
                    raise ValueError("corrupt cooldown")
                until = max(until, previous)
            db.execute("UPDATE state SET blocked_until=? WHERE id=1", (until.isoformat(),))
