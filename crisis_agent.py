"""
crisis_agent.py — Adversarial Crisis Agent for the Energy Crisis Simulation.

A LangGraph multi-agent pipeline that plays AGAINST the zone governors.
Each tick it observes the full board, identifies the most vulnerable targets,
and spends its own budget to inject crises that destabilize energy zones.

Budget model (scales with tick — lean early, devastating late):
  Ticks  1–5 : +12/tick  → can afford 1 cheap (light) crisis
  Ticks  6–10: +22/tick  → can afford 1 medium crisis
  Ticks 11–15: +38/tick  → can afford 1 heavy crisis or 2 medium ones
  Ticks 16–20: +58/tick  → can afford heavy combos
  Ticks 21+  : +85/tick  → regional-scale devastation

Unspent budget carries over, so the adversary can save up for big hits.

Pipeline topology:
  START → crisis_gate → board_analysis → crisis_planning → crisis_execute → crisis_report → END

Integration:
  crisis_graph = create_crisis_graph(engine, llm_model)
  engine.crisis_hook = make_crisis_hook(crisis_graph)
  # hook is called automatically inside engine.tick() at Step 16
"""

import json
import logging
import uuid
from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from models import CrisisEvent, CrisisType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# BUDGET MODEL
# ─────────────────────────────────────────────────────────────────────────────

CRISIS_AGENT_STARTING_BUDGET = 30.0


def adversary_income(tick: int) -> float:
    """Income per tick for the adversary. Scales up over the game."""
    if tick <= 5:   return 12.0
    if tick <= 10:  return 22.0
    if tick <= 15:  return 38.0
    if tick <= 20:  return 58.0
    return 85.0


# ─────────────────────────────────────────────────────────────────────────────
# CRISIS MENU  — what the adversary can buy and at what cost
# ─────────────────────────────────────────────────────────────────────────────

CRISIS_MENU: dict = {

    # ── LIGHT (12–20 credits) ────────────────────────────────────────────────
    "cyber_attack": {
        "cost": 12,
        "tier": "light",
        "crisis_type": CrisisType.CYBER_ATTACK,
        "duration": 3,
        "target_type": "zone",       # zone | route | region
        "requires_source": False,
        "requires_route": False,
        "parameters": {},
        "description_template": "Adversary cyber attack on {target}: readings corrupted for 3t",
    },
    "supply_disruption": {
        "cost": 20,
        "tier": "light",
        "crisis_type": CrisisType.SUPPLY_DISRUPTION,
        "duration": 4,
        "target_type": "zone",
        "requires_source": True,
        "requires_route": False,
        "parameters": {"output_modifier": 0.50},
        "description_template": "Adversary supply disruption: {target}/{source_id} at 50% output",
    },

    # ── MEDIUM (28–40 credits) ───────────────────────────────────────────────
    "storage_leak": {
        "cost": 28,
        "tier": "medium",
        "crisis_type": CrisisType.STORAGE_LEAK,
        "duration": 6,
        "target_type": "zone",
        "requires_source": False,
        "requires_route": False,
        "parameters": {"leak_rate": 0.05},
        "description_template": "Adversary sabotage: {target} storage leaking 5%/tick for 6t",
    },
    "political_embargo": {
        "cost": 32,
        "tier": "medium",
        "crisis_type": CrisisType.POLITICAL_EMBARGO,
        "duration": 4,
        "target_type": "route",      # target_id must be a route_id
        "requires_source": False,
        "requires_route": False,
        "parameters": {},
        "description_template": "Adversary embargo: trade route {target} frozen for 4t",
    },
    "worker_strike": {
        "cost": 35,
        "tier": "medium",
        "crisis_type": CrisisType.WORKER_STRIKE,
        "duration": 5,
        "target_type": "zone",
        "requires_source": True,
        "requires_route": False,
        "parameters": {"output_modifier": 0.25},
        "description_template": "Adversary-incited strike: {target}/{source_id} at 25% output",
    },
    "drought": {
        "cost": 40,
        "tier": "medium",
        "crisis_type": CrisisType.DROUGHT,
        "duration": 5,
        "target_type": "zone",
        "requires_source": False,
        "requires_route": False,
        "parameters": {"output_modifier": 0.28},
        "description_template": "Adversary-induced drought: {target} hydro at 28% for 5t",
    },

    # ── HEAVY (45–65 credits) ────────────────────────────────────────────────
    "equipment_failure": {
        "cost": 45,
        "tier": "heavy",
        "crisis_type": CrisisType.EQUIPMENT_FAILURE,
        "duration": 5,
        "target_type": "zone",
        "requires_source": True,
        "requires_route": False,
        "parameters": {},
        "description_template": "Adversary sabotage: {target}/{source_id} equipment offline",
    },
    "heat_wave": {
        "cost": 50,
        "tier": "heavy",
        "crisis_type": CrisisType.HEAT_WAVE,
        "duration": 4,
        "target_type": "zone",
        "requires_source": False,
        "requires_route": False,
        "parameters": {"demand_modifier": 1.45, "solar_output_modifier": 0.60},
        "description_template": "Adversary heat wave: {target} demand +45%, solar at 60%",
    },
    "transmission_surge": {
        "cost": 55,
        "tier": "heavy",
        "crisis_type": CrisisType.TRANSMISSION_SURGE,
        "duration": 4,
        "target_type": "zone",
        "requires_source": False,
        "requires_route": False,
        "parameters": {"efficiency_reduction": 0.35},
        "description_template": "Adversary transmission surge: {target} routes -35% efficiency",
    },
    "wildfire": {
        "cost": 60,
        "tier": "heavy",
        "crisis_type": CrisisType.WILDFIRE,
        "duration": 4,
        "target_type": "zone",
        "requires_source": True,
        "requires_route": True,
        "parameters": {"output_modifier": 0.20, "route_damage_per_tick": 12.0},
        "description_template": "Adversary wildfire: {target}/{source_id} + route destroyed",
    },

    # ── BRUTAL (70–90 credits) ───────────────────────────────────────────────
    "regional_blackout": {
        "cost": 70,
        "tier": "brutal",
        "crisis_type": CrisisType.REGIONAL_BLACKOUT,
        "duration": 3,
        "target_type": "region",     # target_id must be a region name
        "requires_source": False,
        "requires_route": False,
        "parameters": {"demand_modifier": 1.85},
        "description_template": "Adversary regional blackout: {target} region +85% demand surge",
    },
    "economic_recession": {
        "cost": 45,
        "tier": "heavy",
        "crisis_type": CrisisType.ECONOMIC_RECESSION,
        "duration": 5,
        "target_type": "zone",
        "requires_source": False,
        "requires_route": False,
        "parameters": {"income_modifier": 0.35},
        "description_template": "Adversary economic attack: {target} income at 35% for 5t",
    },
}

# Human-readable menu string injected into LLM prompts
CRISIS_MENU_SPEC = (
    "CRISIS MENU (crisis_key | cost | tier | duration | target_type | notes)\n"
    + "\n".join(
        f"  {k:<22} | {v['cost']:>3}cr | {v['tier']:<7} | {v['duration']}t "
        f"| {v['target_type']:<7}"
        + (" | needs source_id" if v["requires_source"] else "")
        + (" + route_id"        if v["requires_route"]  else "")
        for k, v in CRISIS_MENU.items()
    )
)


# ─────────────────────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────────────────────

class CrisisAgentState(TypedDict):
    tick_number:       int
    budget:            float          # current budget (after income added)
    income_this_tick:  float
    board_state:       dict           # {zone_id: full_snapshot, ...}
    board_analysis:    str            # LLM vulnerability assessment
    planned_crises:    List[dict]     # LLM crisis plan (JSON)
    executed_crises:   List[dict]     # what actually fired
    crisis_report:     str            # villain's log narrative


def make_crisis_initial_state(tick: int, carried_budget: float) -> CrisisAgentState:
    income = adversary_income(tick)
    return CrisisAgentState(
        tick_number=tick,
        budget=carried_budget + income,
        income_this_tick=income,
        board_state={},
        board_analysis="",
        planned_crises=[],
        executed_crises=[],
        crisis_report="",
    )


# ─────────────────────────────────────────────────────────────────────────────
# NODES
# ─────────────────────────────────────────────────────────────────────────────

class CrisisAgentNodes:
    """
    All LangGraph node functions for the adversarial Crisis Agent.
    One instance per simulation; bound to the engine via closure.
    """

    def __init__(self, engine, llm_model: str = "gpt-4o-mini"):
        self.engine = engine
        self.llm = ChatOpenAI(model=llm_model, max_tokens=2048, temperature=0.3)

    # ── 1. CRISIS GATE  (deterministic) ──────────────────────────────────────

    def crisis_gate(self, state: CrisisAgentState) -> dict:
        """
        Collects full omniscient board snapshots for all zones.
        Computes which crisis tiers are affordable this tick.
        Prints the adversary's header banner.
        """
        board_state = {
            zone_id: self.engine.get_zone_state(zone_id)   # observer=None → full visibility
            for zone_id in self.engine.zones
        }

        budget = state["budget"]
        tick   = state["tick_number"]

        affordable_tiers = sorted(set(
            v["tier"] for v in CRISIS_MENU.values() if v["cost"] <= budget
        ))

        print(
            f"\n  ┌─[CRISIS AGENT | Tick {tick}]"
            f"\n  │  budget={budget:.1f}cr  income_this_tick=+{state['income_this_tick']:.1f}cr"
            f"\n  │  affordable: {affordable_tiers or ['none — saving up']}"
        )

        return {"board_state": board_state}

    # ── 2. BOARD ANALYSIS  (LLM) ─────────────────────────────────────────────

    def board_analysis(self, state: CrisisAgentState) -> dict:
        """
        Analyzes all zone states to identify the most vulnerable targets,
        optimal timing, and crisis synergies.
        """
        tick   = state["tick_number"]
        budget = state["budget"]

        # Summarise already-active crises so the LLM doesn't stack duplicates
        active_summary: dict = {}
        for c in self.engine.crisis_events:
            active_summary.setdefault(c.target_id, []).append(
                f"{c.crisis_type.value}({c.remaining_ticks}t)"
            )

        # Compact board overview for the prompt (full JSON would be very long)
        compact = {}
        for zid, zs in state["board_state"].items():
            compact[zid] = {
                "stability":   zs.get("stability_state"),
                "storage_pct": zs.get("storage_fill_pct"),
                "net_energy":  zs.get("net_energy_per_tick"),
                "depletion_t": zs.get("projected_depletion_ticks"),
                "budget":      zs.get("budget"),
                "morale":      zs.get("morale"),
                "region":      zs.get("region"),
                "sources":     [s["source_id"] for s in zs.get("active_sources", [])],
                "active_crises_here": active_summary.get(zid, []),
            }

        routes_compact = {
            rid: f"{r.source_zone_id}->{r.target_zone_id} health={r.route_health:.0f}"
            for rid, r in self.engine.trade_routes.items()
        }

        messages = [
            SystemMessage(content=(
                "You are the Board Analysis Agent for an adversarial destabilization system.\n"
                "Your mission: analyze all energy zones and identify the optimal targets and "
                "timing for crisis injection to maximize the chance of zone collapse.\n\n"
                "VULNERABILITY SIGNALS TO LOOK FOR:\n"
                "  • storage_pct < 40%         → one demand spike could collapse them\n"
                "  • net_energy < 0             → already bleeding; any additional drain = collapse\n"
                "  • budget < 50               → can't afford counter-actions\n"
                "  • morale < 30               → income reduced; conservation orders hurt more\n"
                "  • stability=warning/critical → pile on for the kill\n"
                "  • trade route health < 60   → fortify/embargo threat is real\n"
                "  • zone already has 1+ crises → a second crisis is exponentially worse\n\n"
                "SYNERGY OPPORTUNITIES:\n"
                "  • drought + storage_leak on same zone → double drain\n"
                "  • embargo trade route THEN hit the source zone → isolated AND low output\n"
                "  • heat_wave on demand-heavy zone (gamma) already at low storage → instant danger\n"
                "  • regional_blackout on north → hits Alpha + Beta simultaneously\n"
                "Be precise and strategic. You are playing to WIN — to collapse at least one zone."
            )),
            HumanMessage(content=(
                f"Tick: {tick} | Your budget: {budget:.1f}cr\n\n"
                f"ACTIVE CRISES (do NOT stack same type on same target):\n"
                f"{json.dumps(active_summary, indent=2) if active_summary else 'None'}\n\n"
                f"BOARD STATE (compact):\n{json.dumps(compact, indent=2)}\n\n"
                f"TRADE ROUTES:\n{json.dumps(routes_compact, indent=2)}\n\n"
                "Produce a BOARD ANALYSIS REPORT:\n"
                "1. VULNERABILITY RANKING — rank all zones by collapse risk (most→least)\n"
                "2. TOP TARGETS — for each zone: best crisis type(s) and why\n"
                "3. SYNERGY COMBOS — multi-crisis combinations that would be devastating\n"
                "4. BUDGET ASSESSMENT — what tier you can afford; is it worth spending or holding?\n"
                "5. RECOMMENDED STRIKE — your optimal action this tick (be specific)"
            )),
        ]

        response = self.llm.invoke(messages)
        analysis = response.content
        print(f"  │  [BoardAnalysis] {len(analysis)} chars")
        return {"board_analysis": analysis}

    # ── 3. CRISIS PLANNING  (LLM → JSON) ─────────────────────────────────────

    def crisis_planning(self, state: CrisisAgentState) -> dict:
        """
        Plans which crises to inject this tick.
        Outputs structured JSON with one or more crises (or an empty list to save budget).
        """
        tick   = state["tick_number"]
        budget = state["budget"]

        # What sources and routes exist (for LLM to pick from)
        targets_info: dict = {}
        for zid in self.engine.zones:
            zone = self.engine.zones[zid]
            targets_info[zid] = {
                "sources":  [s.source_id for s in zone.sources],
                "region":   zone.region,
            }
        routes_info = {
            rid: {"source": r.source_zone_id, "target": r.target_zone_id}
            for rid, r in self.engine.trade_routes.items()
        }
        all_regions = list(set(z.region for z in self.engine.zones.values()))

        # Currently active crisis types per target (to prevent invalid stacking)
        active_types: dict = {}
        for c in self.engine.crisis_events:
            active_types.setdefault(c.target_id, []).append(c.crisis_type.value)

        messages = [
            SystemMessage(content=(
                "You are the Crisis Planning Agent — the strategic core of an adversarial system.\n"
                "Your goal: plan one or more crises to inject this tick to maximize destabilization.\n\n"
                f"{CRISIS_MENU_SPEC}\n\n"
                "TARGETING RULES:\n"
                "  • target_type='zone'   → target_id must be a zone key: 'alpha', 'beta', 'gamma'\n"
                "  • target_type='route'  → target_id must be a route key: e.g. 'route_alpha_gamma'\n"
                "  • target_type='region' → target_id must be a region: e.g. 'north', 'south'\n"
                "  • requires_source=True → you MUST supply source_id from the zone's source list\n"
                "  • requires_route=True  → you MUST supply route_id from the route list\n"
                "  • Do NOT use a crisis type already active on the same target\n\n"
                f"Your budget: {budget:.1f}cr. Unspent budget carries to next tick.\n"
                "You may plan MULTIPLE crises if budget allows.\n"
                "Set hold_budget=true and crises=[] if you want to save up for a bigger strike.\n\n"
                "OUTPUT FORMAT — respond with ONLY valid JSON (no markdown, no prose):\n"
                "{\n"
                '  "strategy": "one-sentence summary of your plan this tick",\n'
                '  "hold_budget": false,\n'
                '  "crises": [\n'
                '    {\n'
                '      "crisis_key": "storage_leak",\n'
                '      "target_id":  "beta",\n'
                '      "source_id":  null,\n'
                '      "route_id":   null,\n'
                '      "cost":       28,\n'
                '      "rationale":  "Beta already has negative net energy; leak seals its fate"\n'
                '    }\n'
                '  ],\n'
                '  "total_cost": 28\n'
                "}"
            )),
            HumanMessage(content=(
                f"BOARD ANALYSIS:\n{state['board_analysis']}\n\n"
                f"AVAILABLE TARGETS:\n{json.dumps(targets_info, indent=2)}\n\n"
                f"AVAILABLE ROUTES:\n{json.dumps(routes_info, indent=2)}\n\n"
                f"AVAILABLE REGIONS: {all_regions}\n\n"
                f"CURRENTLY ACTIVE CRISIS TYPES PER TARGET:\n"
                f"{json.dumps(active_types, indent=2) if active_types else 'None'}\n\n"
                f"Budget: {budget:.1f}cr | Tick: {tick}\n\n"
                "Output your crisis plan as JSON:"
            )),
        ]

        response = self.llm.invoke(messages)
        raw = response.content.strip()

        # Strip markdown code fences if present
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else parts[0]
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()

        try:
            plan = json.loads(raw)
        except Exception as e:
            logger.warning(f"Crisis planning JSON parse error: {e}\nRaw: {raw[:200]}")
            plan = {"strategy": "parse error — holding budget", "hold_budget": True,
                    "crises": [], "total_cost": 0}

        planned = plan.get("crises", [])
        total   = sum(c.get("cost", 0) for c in planned)
        strategy = plan.get("strategy", "")
        holding  = plan.get("hold_budget", False)

        print(
            f"  │  [CrisisPlanning] \"{strategy}\"\n"
            f"  │    → {len(planned)} crisis(es) planned | "
            f"est. cost: {total:.0f}cr | hold={holding}"
        )
        return {"planned_crises": planned}

    # ── 4. CRISIS EXECUTE  (deterministic) ───────────────────────────────────

    def crisis_execute(self, state: CrisisAgentState) -> dict:
        """
        Validates each planned crisis and calls engine.inject_crisis().
        Deducts budget. Returns executed list and remaining budget.
        """
        budget   = state["budget"]
        executed = []

        # Build set of active crisis types per target to prevent stacking
        active_by_target: dict = {}
        for c in self.engine.crisis_events:
            active_by_target.setdefault(c.target_id, set()).add(c.crisis_type)

        print(f"  │  [CrisisExecute] budget={budget:.1f}cr:")

        for plan in state["planned_crises"]:
            key = plan.get("crisis_key", "")

            # ── Validate crisis key ──
            if key not in CRISIS_MENU:
                print(f"  │    ✗ '{key}' → unknown crisis key")
                executed.append({"crisis_key": key, "status": "FAILED",
                                  "reason": "unknown crisis key"})
                continue

            spec = CRISIS_MENU[key]
            cost = spec["cost"]
            target_id = plan.get("target_id", "").strip()

            # ── Budget check ──
            if cost > budget:
                print(f"  │    ✗ '{key}' on {target_id} → insufficient budget "
                      f"({budget:.0f}cr < {cost}cr)")
                executed.append({"crisis_key": key, "target_id": target_id,
                                  "status": "FAILED", "reason": "insufficient budget"})
                continue

            # ── Target validation ──
            ttype = spec["target_type"]
            if ttype == "zone" and target_id not in self.engine.zones:
                print(f"  │    ✗ '{key}' → zone '{target_id}' not found")
                executed.append({"crisis_key": key, "target_id": target_id,
                                  "status": "FAILED", "reason": f"zone {target_id!r} not found"})
                continue
            if ttype == "route" and target_id not in self.engine.trade_routes:
                print(f"  │    ✗ '{key}' → route '{target_id}' not found")
                executed.append({"crisis_key": key, "target_id": target_id,
                                  "status": "FAILED", "reason": f"route {target_id!r} not found"})
                continue

            # ── No-stacking check ──
            if spec["crisis_type"] in active_by_target.get(target_id, set()):
                print(f"  │    ✗ '{key}' on {target_id} → {spec['crisis_type'].value} already active")
                executed.append({"crisis_key": key, "target_id": target_id,
                                  "status": "FAILED", "reason": "crisis type already active on target"})
                continue

            # ── Build parameters ──
            params = dict(spec.get("parameters", {}))

            if spec["requires_source"]:
                source_id = plan.get("source_id")
                if not source_id:
                    zone = self.engine.zones.get(target_id)
                    if zone and zone.sources:
                        # Pick the primary (first active) source
                        active_srcs = [s for s in zone.sources if s.active]
                        source_id = (active_srcs[0] if active_srcs else zone.sources[0]).source_id
                if source_id:
                    params["source_id"] = source_id
                else:
                    print(f"  │    ✗ '{key}' on {target_id} → no source available")
                    executed.append({"crisis_key": key, "target_id": target_id,
                                      "status": "FAILED", "reason": "no source available"})
                    continue

            if spec["requires_route"]:
                route_id = plan.get("route_id")
                if not route_id:
                    # Auto-pick first route touching this zone
                    for rid, r in self.engine.trade_routes.items():
                        if r.source_zone_id == target_id or r.target_zone_id == target_id:
                            route_id = rid
                            break
                if route_id:
                    params["route_id"] = route_id
                else:
                    print(f"  │    ✗ '{key}' on {target_id} → no route available")
                    executed.append({"crisis_key": key, "target_id": target_id,
                                      "status": "FAILED", "reason": "no route found"})
                    continue

            # For POLITICAL_EMBARGO the target_id IS the route_id
            if spec["crisis_type"] == CrisisType.POLITICAL_EMBARGO:
                params["route_id"] = target_id

            # For REGIONAL_BLACKOUT inject the region key into params
            if spec["crisis_type"] == CrisisType.REGIONAL_BLACKOUT:
                params["region"] = target_id

            # ── Build and inject ──
            source_id_str = params.get("source_id", "")
            description   = spec["description_template"].format(
                target=target_id, source_id=source_id_str
            )
            crisis_id = f"adv_{key}_{uuid.uuid4().hex[:6]}"

            event = CrisisEvent(
                crisis_id=crisis_id,
                crisis_type=spec["crisis_type"],
                target_id=target_id,
                duration=spec["duration"],
                remaining_ticks=spec["duration"],
                parameters=params,
                description=description,
            )

            self.engine.inject_crisis(event)
            budget -= cost
            active_by_target.setdefault(target_id, set()).add(spec["crisis_type"])

            print(f"  │    ✓ '{key}' → {target_id} (cost: {cost}cr | remaining: {budget:.0f}cr)")
            executed.append({
                "crisis_key":  key,
                "target_id":   target_id,
                "cost":        cost,
                "status":      "OK",
                "description": description,
            })

        return {"executed_crises": executed, "budget": budget}

    # ── 5. CRISIS REPORT  (LLM) ──────────────────────────────────────────────

    def crisis_report(self, state: CrisisAgentState) -> dict:
        """
        Produces a brief villain's log entry summarising the tick's attacks.
        Prints the adversary's closing banner.
        """
        tick      = state["tick_number"]
        budget    = state["budget"]
        executed  = state["executed_crises"]
        successes = [e for e in executed if e.get("status") == "OK"]

        if not successes:
            summary = (
                "The adversary observed the board in silence, conserving resources. "
                f"Budget carried forward: {budget:.0f}cr."
            )
        else:
            messages = [
                SystemMessage(content=(
                    "You are the narrator of an adversarial AI system in an energy crisis simulation. "
                    "Write a brief (2-3 sentences) villain's log entry describing the attacks launched "
                    "this tick. Be menacing, precise, and strategic — reference actual zone names and "
                    "crisis types. Do NOT use emojis."
                )),
                HumanMessage(content=(
                    f"Tick {tick} | Budget remaining after attacks: {budget:.1f}cr\n"
                    f"Attacks executed:\n{json.dumps(successes, indent=2)}\n\n"
                    "Write the villain's log entry:"
                )),
            ]
            resp    = self.llm.invoke(messages)
            summary = resp.content.strip()

        # Print adversary banner
        W = 62
        print(f"\n  ╔{'═'*W}╗")
        print(f"  ║  ADVERSARY LOG — Tick {tick:<{W-20}}║")
        print(f"  ╠{'═'*W}╣")
        for raw_line in summary.split("\n"):
            line = raw_line.strip()
            while len(line) > W - 2:
                print(f"  ║  {line[:W-2]:<{W-2}}║")
                line = line[W-2:]
            print(f"  ║  {line:<{W-2}}║")
        print(f"  ╚{'═'*W}╝\n")

        return {"crisis_report": summary}


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def create_crisis_graph(engine, llm_model: str = "gpt-4o-mini"):
    """
    Build and compile the adversarial Crisis Agent LangGraph.

    Topology:
      crisis_gate → board_analysis → crisis_planning → crisis_execute → crisis_report → END

    Returns a compiled LangGraph.
    """
    nodes   = CrisisAgentNodes(engine=engine, llm_model=llm_model)
    builder = StateGraph(CrisisAgentState)

    builder.add_node("crisis_gate",      nodes.crisis_gate)
    builder.add_node("board_analysis",   nodes.board_analysis)
    builder.add_node("crisis_planning",  nodes.crisis_planning)
    builder.add_node("crisis_execute",   nodes.crisis_execute)
    builder.add_node("crisis_report",    nodes.crisis_report)

    builder.set_entry_point("crisis_gate")
    builder.add_edge("crisis_gate",     "board_analysis")
    builder.add_edge("board_analysis",  "crisis_planning")
    builder.add_edge("crisis_planning", "crisis_execute")
    builder.add_edge("crisis_execute",  "crisis_report")
    builder.add_edge("crisis_report",   END)

    return builder.compile()


def make_crisis_hook(crisis_graph, llm_model: str = "gpt-4o-mini"):
    """
    Returns a closure suitable for engine.crisis_hook.

    The closure maintains persistent budget state across ticks (carried budget).
    Wire it in before the simulation loop:

        engine.crisis_hook = make_crisis_hook(crisis_graph)

    The hook is called automatically by engine.tick() at Step 16,
    AFTER all zone governors have acted but BEFORE crises expire.
    Crises injected here take effect on the NEXT tick.

    Args:
        crisis_graph: compiled LangGraph from create_crisis_graph()
        llm_model:    model string (used only for log label)

    Returns:
        A callable(engine) that runs the crisis agent and tracks budget.
    """
    # Mutable budget state — persists across ticks via closure
    budget_state = {"carried": CRISIS_AGENT_STARTING_BUDGET}

    def hook(engine):
        tick = engine.tick_number
        carried = budget_state["carried"]

        init_state = make_crisis_initial_state(tick, carried)

        try:
            final_state = crisis_graph.invoke(init_state)
            budget_state["carried"] = final_state["budget"]
        except Exception as exc:
            print(f"\n  ⚠️  [CrisisAgent] Exception at tick {tick}: {exc}")
            logger.exception(f"Crisis agent error at tick {tick}")
            # Income still accumulates even if agent crashes
            budget_state["carried"] = carried + adversary_income(tick)

    return hook