"""
memory.py — MongoDB-backed persistent memory for Zone Governor Agents.

Each zone's AI governor writes a structured memory document after every tick,
capturing what it observed, what it planned, what was executed, and what the
outcome was.  On the next tick, recent memories are retrieved and injected into
the Situation Awareness prompt so the agent can learn from its own history.

Schema (one document per zone per tick):
  {
    "zone_id":          str,          # "alpha" | "beta" | "gamma"
    "tick":             int,          # Engine tick number
    "timestamp":        datetime,     # UTC wall-clock time
    "stability":        str,          # stability_state at time of writing
    "budget":           float,        # budget remaining after actions
    "storage_fill_pct": float,        # storage % at end of tick
    "active_crises":    [str],        # list of crisis type strings
    "actions_taken":    [str],        # list of action_type strings executed
    "action_count":     int,          # total actions executed
    "total_cost":       float,        # total budget spent this tick
    "situation_summary": str,         # first 400 chars of situation_report
    "risk_decision":    str,          # "approved" | "rejected" | "forced_empty" | "skipped"
    "tick_report":      str,          # AI narrative (first 600 chars)
  }

Usage:
    from agents.memory import ZoneMemory

    # Initialise once at startup (or per-zone)
    mem = ZoneMemory(zone_id="alpha")

    # After each tick's report node:
    mem.save(tick_record)

    # At the start of each tick's situation_awareness node:
    context_str = mem.load_context(n=5)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MONGO_URI    = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME      = os.environ.get("MONGO_DB",  "crisis_simulation")
COLLECTION   = "zone_memories"
DEFAULT_N    = 5          # Default number of recent ticks to include in context
MAX_SUMMARY  = 400        # Characters of situation_report to store
MAX_REPORT   = 600        # Characters of tick_report to store

class ZoneMemory:
    """
    Persistent memory store for one zone's Governor Agent.

    Gracefully degrades: if MongoDB is unavailable, all operations become
    no-ops and the agent simply runs without memory (same as before).

    Args:
        zone_id:    Zone this memory instance belongs to.
        mongo_uri:  MongoDB connection string (default: $MONGO_URI or localhost).
        db_name:    Database name (default: $MONGO_DB or 'crisis_simulation').
    """

    def __init__(
        self,
        zone_id: str,
        mongo_uri: str = MONGO_URI,
        db_name:   str = DB_NAME,
    ):
        self.zone_id   = zone_id
        self._client   = None
        self._col      = None
        self._enabled  = False

        try:
            from pymongo import MongoClient, DESCENDING  # noqa: F401
            self._MongoClient = MongoClient
            self._DESCENDING  = DESCENDING
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            # Force a connection attempt to surface errors early
            client.admin.command("ping")
            col = client[db_name][COLLECTION]
            # Ensure index for fast per-zone queries
            col.create_index([("zone_id", 1), ("tick", -1)])
            self._client  = client
            self._col     = col
            self._enabled = True
            logger.info(
                f"[Memory | Zone {zone_id}] Connected to MongoDB "
                f"({mongo_uri}) → {db_name}.{COLLECTION}"
            )
            print(f"  [Memory | Zone {zone_id}] ✓ MongoDB connected — "
                  f"persistent memory enabled.")
        except ImportError:
            logger.warning(
                "[Memory] pymongo not installed — memory disabled. "
                "Install with: pip install pymongo"
            )
            print(f"  [Memory | Zone {zone_id}] ⚠ pymongo not found — "
                  "memory disabled (run without history).")
        except Exception as exc:
            logger.warning(f"[Memory | Zone {zone_id}] MongoDB unavailable: {exc}")
            print(f"  [Memory | Zone {zone_id}] ⚠ MongoDB unavailable ({exc}) — "
                  "memory disabled (run without history).")

    def save(self, record: dict[str, Any]) -> None:
        """
        Persist a tick memory document.

        Args:
            record: dict with keys matching the schema at module top.  Unknown
                    keys are stored as-is; missing keys are tolerated.
        """
        if not self._enabled:
            return
        try:
            doc = {
                "zone_id":           self.zone_id,
                "tick":              record.get("tick", 0),
                "timestamp":         datetime.now(timezone.utc),
                "stability":         record.get("stability", "unknown"),
                "budget":            record.get("budget", 0.0),
                "storage_fill_pct":  record.get("storage_fill_pct", 0.0),
                "active_crises":     record.get("active_crises", []),
                "actions_taken":     record.get("actions_taken", []),
                "action_count":      record.get("action_count", 0),
                "total_cost":        record.get("total_cost", 0.0),
                "situation_summary": record.get("situation_summary", "")[:MAX_SUMMARY],
                "risk_decision":     record.get("risk_decision", "unknown"),
                "tick_report":       record.get("tick_report", "")[:MAX_REPORT],
            }
            self._col.insert_one(doc)
            logger.debug(
                f"[Memory | Zone {self.zone_id}] Saved tick {doc['tick']}"
            )
        except Exception as exc:
            logger.warning(
                f"[Memory | Zone {self.zone_id}] Save failed (tick "
                f"{record.get('tick', '?')}): {exc}"
            )

    def load_context(self, n: int = DEFAULT_N) -> str:
        """
        Retrieve the most recent `n` tick memories and format them into a
        compact context string suitable for injection into LLM prompts.

        Returns an empty string if memory is disabled or no history exists.

        Args:
            n: Number of recent ticks to retrieve (default: 5).
        """
        if not self._enabled:
            return ""
        try:
            docs = list(
                self._col.find(
                    {"zone_id": self.zone_id},
                    sort=[("tick", self._DESCENDING)],
                    limit=n,
                )
            )
        except Exception as exc:
            logger.warning(
                f"[Memory | Zone {self.zone_id}] Load failed: {exc}"
            )
            return ""

        if not docs:
            return ""

        docs = list(reversed(docs))

        lines = [
            f"HISTORICAL MEMORY — last {len(docs)} tick(s) for zone "
            f"'{self.zone_id}' (oldest → newest):",
            "─" * 60,
        ]
        for doc in docs:
            crises   = ", ".join(doc.get("active_crises", [])) or "none"
            actions  = ", ".join(doc.get("actions_taken", [])) or "none"
            lines += [
                f"Tick {doc['tick']:>3}  |  stability={doc.get('stability','?')}  "
                f"budget={doc.get('budget', 0):.0f}  "
                f"storage={doc.get('storage_fill_pct', 0):.0f}%  "
                f"risk={doc.get('risk_decision','?')}",
                f"  Crises:  {crises}",
                f"  Actions: {actions} (cost={doc.get('total_cost', 0):.0f})",
            ]
            summary = doc.get("situation_summary", "").strip()
            if summary:
                # First line of the situation summary as a one-liner
                first_line = summary.splitlines()[0].strip()
                lines.append(f"  Situation: {first_line[:120]}")
            lines.append("")  # blank separator between ticks

        lines.append("─" * 60)
        lines.append(
            "Use this history to avoid repeating failed strategies and "
            "to anticipate recurring patterns."
        )
        return "\n".join(lines)

    def close(self) -> None:
        """Close the MongoDB connection (call at simulation shutdown)."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._enabled = False
