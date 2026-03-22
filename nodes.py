"""
nodes.py — All six LangGraph agent node functions + conditional routing logic.
 
Agent roster:
  1. supervisor_gate        — Deterministic gatekeeper; reads zone state, sets routing.
  2. situation_awareness    — LLM analysis of telemetry, crises, messages, pending queue.
  3. planning               — LLM action plan drafting (JSON output); handles retries.
  4. risk_assessment        — LLM financial+strategic safeguard; enforces max_retries.
  5. supervisor_execute     — Deterministic executor; only agent that calls engine actions.
  6. report                 — LLM tick narrative: problems → plan → risk → execution.
  7. communication          — LLM diplomat; handles trade offers and info requests.
 
Routing functions (pure — no side effects):
  route_supervisor_gate     — "plan" | "communicate" | "skip"
  route_risk_assessment     — "approved" | "retry" | "forced_empty"
  route_communication       — "needs_planning" | "done"
 
Design principles:
  - Engine is accessed only through ZoneAgentNodes (closure pattern).
  - supervisor_execute is the ONLY node that calls engine action methods.
  - All LLM nodes emit structured JSON; parsing failures default to safe no-ops.
  - MAX_RETRIES prevents infinite planning loops.
"""
 
import json
import logging
import sys
import os
from typing import Optional
 
# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.prebuilt import create_react_agent 
from pydantic import BaseModel, Field
from valyu import Valyu 
from langchain.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model
 
# Local imports — resolve relative to project root
# Local imports — resolve relative to project root
sys.path.insert(0, os.path.dirname(__file__))
from models import EnergyType
 
from state import AgentState
from memory import ZoneMemory
 
logger = logging.getLogger(__name__)
 
# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
 
MAX_RETRIES = 2          # Max planning→risk loops before forcing an empty action list
BUDGET_RESERVE = 50.0    # Risk agent flags any plan that would drop budget below this
 
# Complete specification of valid engine actions — injected into Planning prompts.
# Complete specification of valid engine actions — injected into Planning prompts.
VALID_ACTIONS_SPEC = """
VALID ENGINE ACTIONS  (use these exact action_type strings)
===========================================================
IMMEDIATE (0-tick latency):
  sell_surplus          DISABLED — energy-cash conversion not allowed               cost: N/A
  emergency_broadcast   params: {zone_id, message: str}                            cost: 0
  monitor_zone          params: {observer_zone_id: str, target_zone_id: str, duration: int} cost: 20
  set_export_cap        params: {zone_id, route_id: str, max_rate: float|null}     cost: 5
  propose_trade         params: {from_zone_id: str, to_zone_id: str, energy_offered: float,
                                  budget_offered: float, energy_requested: float,
                                  budget_requested: float, expires_in_ticks: int,
                                  description: str}                                cost: 5
  reject_trade          params: {zone_id, offer_id: str}                           cost: 0
 
1-TICK LATENCY:
  ration_energy         params: {zone_id, reduction_pct: float (0.0-1.0)}         cost: 10
  close_trade_route     params: {zone_id, route_id: str}                           cost: 5
  boost_source          params: {zone_id, source_id: str, boost_factor: float (1-2.5)} cost: 50
  deploy_emergency_generator
                        params: {zone_id, output_rate: float, duration: int}       cost: 75
                        *ONLY VALID IF ZONE IS IN 'WARNING' OR 'CRITICAL' STATE*
  issue_conservation_order
                        params: {zone_id, reduction_pct: float (0.0-0.5)}         cost: 15
  settle_worker_strike  params: {zone_id, source_id: str}                         cost: 60
  request_aid           params: {requesting_zone_id: str, donor_zone_id: str, amount: float} cost: 0
  accept_trade          params: {zone_id, offer_id: str}                           cost: 0
 
2-TICK LATENCY:
  repair_route          params: {zone_id, route_id: str, repair_amount: float=20.0} cost: 30
  fortify_route         params: {zone_id, route_id: str}                           cost: 40
  repair_source         params: {zone_id, source_id: str}                         cost: 35
                        *ONLY VALID IF SOURCE IS COMPLETELY OFFLINE/INACTIVE*
  invest_in_efficiency  params: {zone_id, source_id: str, improvement_pct: float} cost: 80
  open_trade_route      params: {source_zone_id: str, target_zone_id: str, energy_type: str,
                                  transfer_rate: float, route_latency: int=2,
                                  transmission_efficiency: float=0.90}            cost: 20
 
3-TICK LATENCY:
  upgrade_storage       params: {zone_id, additional_capacity: float}             cost: 100
  build_new_route       params: {source_zone_id: str, target_zone_id: str, energy_type: str,
                                  transfer_rate: float, construction_ticks: int=4,
                                  transmission_efficiency: float=0.90}            cost: 150
 
NOTES:
  - energy_type values: "solar" | "hydro" | "wind" | "fossil" | "nuclear"
  - Budget is deducted immediately when an action is queued (even with latency)
  - sell_surplus is DISABLED — energy cannot be converted to cash directly
  - propose_trade uses from_zone_id (not zone_id); build_new_route uses source_zone_id
"""
 
 
# ─────────────────────────────────────────────────────────────────────────────
# NODE CONTAINER CLASS
# ─────────────────────────────────────────────────────────────────────────────
 
class ZoneAgentNodes:
    """
    Holds all LangGraph node functions for a single zone, bound to the
    simulation engine via closure. One instance = one zone's AI governor.
 
    Pass node methods directly to builder.add_node():
        nodes = ZoneAgentNodes(engine, "alpha")
        builder.add_node("supervisor_gate", nodes.supervisor_gate)
    """
 
    def __init__(self, engine, zone_id: str, llm_model: str = "gpt-4o"):
        self.engine = engine
        self.zone_id = zone_id
        self.llm = ChatOpenAI(
            model=llm_model,
            max_tokens=2048,
            temperature=0.2,
        )

        self.memory = ZoneMemory(zone_id=zone_id)
 
    # ─────────────────────────────────────────────────────────────────────────
    # 1. SUPERVISOR GATE  (deterministic — no LLM)
    # ─────────────────────────────────────────────────────────────────────────
 
    def supervisor_gate(self, state: AgentState) -> dict:
        """
        Central orchestrator entry point.
 
        Fetches the zone's current state from the engine and decides:
          - Is the zone stable enough to skip deep planning?
          - Are there incoming trade offers requiring the Communication Agent?
          - Should we trigger the full Situation Awareness → Planning → Risk pipeline?
 
        Resets all per-tick fields so each tick starts clean.
        """
        zone_state = self.engine.get_zone_state(self.zone_id)
 
        stability       = zone_state.get("stability_state", "stable")
        messages        = zone_state.get("messages", [])
        incoming_trades = zone_state.get("incoming_trade_offers", [])
        pending         = zone_state.get("pending_actions", [])
        active_crises   = zone_state.get("active_crises", [])
 
        # Urgency heuristics
        has_warning_msgs = any(
            any(kw in str(m).lower() for kw in ("alert", "warning", "crisis", "critical", "failure"))
            for m in messages
        )
 
        # Skip deep planning only if truly stable with nothing requiring attention
        skip = (
            stability == "stable"
            and not has_warning_msgs
            and len(incoming_trades) == 0
            and len(active_crises) == 0
            and len(pending) <= 2       # Small pending queue is fine
        )

        memory_context = self.memory.load_context(n=5)
        memory_flag    = "✓ memory loaded" if memory_context else "○ no memory"
 
 
        print(
            f"\n[SUPERVISOR | Zone {self.zone_id.upper()} | Tick {self.engine.tick_number}]"
            f"\n  stability={stability}  budget={zone_state.get('budget', 0):.0f}"
            f"  storage={zone_state.get('storage_fill_pct', 0):.0f}%"
            f"  crises={len(active_crises)}  pending={len(pending)}"
            f"  trades={len(incoming_trades)}"
            f"\n  Decision: {'SKIP (stable)' if skip else 'RUN PIPELINE'}"
        )
 
        return {
            # Zone snapshot
            "zone_state":            zone_state,
            "tick_number":           self.engine.tick_number,
            # Routing
            "skip_planning":         skip,
            # Reset per-tick fields
            "situation_report":      "",
            "planned_actions":       [],
            "estimated_cost":        0.0,
            "risk_decision":         "",
            "risk_critique":         "",
            "retry_count":           0,
            "approved_actions":      [],
            "executed_results":      [],
            "tick_report":           "",
            "comm_response_actions": [],
            "comm_needs_planning":   False,
            "memory_context": memory_context,
        }
 
    def route_supervisor_gate(self, state: AgentState) -> str:
        """
        Pure routing function for supervisor_gate conditional edges.
 
        Returns:
          "skip"        → Report Agent (stable, nothing to do)
          "communicate" → Communication Agent (stable but has trade offers)
          "plan"        → Situation Awareness (needs full planning cycle)
        """
        if state["skip_planning"]:
            # Even if skipping planning, route incoming trades to comm agent
            if state["zone_state"].get("incoming_trade_offers"):
                return "communicate"
            return "skip"
 
        # Stable zone with only trade offers: let Comm Agent handle diplomatically
        stability = state["zone_state"].get("stability_state", "stable")
        has_trades = bool(state["zone_state"].get("incoming_trade_offers"))
        has_crises = bool(state["zone_state"].get("active_crises"))
 
        if stability == "stable" and has_trades and not has_crises:
            return "communicate"
 
        return "plan"
 
    # ─────────────────────────────────────────────────────────────────────────
    # 2. SITUATION AWARENESS AGENT  (LLM)
    # ─────────────────────────────────────────────────────────────────────────
 
    def situation_awareness(self, state: AgentState) -> dict:
        """
        Analyzes the zone's current telemetry snapshot.
 
        Responsibilities:
          - Identify resource deficits (storage, net energy, projected depletion)
          - Spot active crises and their severity
          - Parse incoming early warning signals
          - Parse trade offers and messages
          - Scan the pending_actions queue (so the Planner doesn't re-order paid work)
          - If the Communication Agent already proposed responses, note them as context
 
        Outputs a structured natural-language situation report for the Planner.
        """
        zone_state   = state["zone_state"]
        comm_context = ""
 
        if state.get("comm_response_actions"):
            comm_context = (
                f"\n\nCOMMUNICATION AGENT PRE-PROPOSED RESPONSES (incorporate into plan):\n"
                + json.dumps(state["comm_response_actions"], indent=2)
            )

        memory_section = ""
        if state.get("memory_context"):
            memory_section = (
                f"\n\nAGENT HISTORICAL MEMORY (use to spot patterns & avoid past mistakes):\n"
                f"{state['memory_context']}\n"
            )
 
        messages = [
            SystemMessage(content=(
                "You are the Situation Awareness Agent for an energy zone management system.\n"
                "Role: Analyze zone telemetry, identify problems, and produce a structured Situation Report "
                "for the Planning Agent. Be precise with numbers. Flag anything that will become "
                "critical within 5 ticks. Do NOT suggest actions — that is the Planner's job."
            )),
            HumanMessage(content=(
                f"Analyze this zone state snapshot for Tick {state['tick_number']}:\n\n"
                f"{json.dumps(zone_state, indent=2)}"
                f"{comm_context}"
                f"{memory_section}\n\n"
                "Produce a Situation Report with EXACTLY these sections:\n\n"
                "RESOURCE STATUS\n"
                "  • Stored energy (absolute + % of capacity)\n"
                "  • Net energy per tick (positive = surplus, negative = deficit)\n"
                "  • Projected depletion (ticks until empty, or 'surplus')\n"
                "  • Storage fill trend\n\n"
                "FINANCIAL STATUS\n"
                "  • Current budget and income per tick\n"
                "  • Recent spending (total_spent) and remaining runway\n\n"
                "SOURCE HEALTH\n"
                "  • List each source: output, modifiers, degradation, active/inactive\n"
                "  • Flag any source with output_modifier < 0.7 or inactive=True\n\n"
                "ACTIVE CRISES  (each: type, ticks remaining, effect on zone)\n\n"
                "EARLY WARNINGS  (scheduled future threats)\n\n"
                "PENDING ACTIONS  (already paid for — do NOT re-queue these)\n\n"
                "INCOMING MESSAGES & TRADE OFFERS\n"
                "  • For each trade offer: offer_id, terms, my net gain/loss\n\n"
                "TRADE ROUTE STATUS\n"
                "  • Each route: direction, health, efficiency, embargoed?\n\n"
                "PRIORITY CONCERNS  (top 3, ranked by urgency, with specific numbers)\n"
            )),
        ]
 
        response          = self.llm.invoke(messages)
        situation_report  = response.content
 
        print(f"  [SitAwareness] Report: {len(situation_report)} chars")
 
        return {"situation_report": situation_report}
 
    # ─────────────────────────────────────────────────────────────────────────
    # 3. PLANNING AGENT  (LLM → JSON)
    # ─────────────────────────────────────────────────────────────────────────
 
    def planning(self, state: AgentState) -> dict:
        """
        Drafts a strategic action plan addressing the Situation Report.
 
        On first call: drafts freely.
        On retry: must read the Risk Assessment critique and produce a cheaper/safer plan.
        NEVER executes. Always outputs structured JSON.
 
        If the Communication Agent flagged responses requiring resource commitment
        (comm_needs_planning=True), those are folded into the plan here.
        """
        budget     = state["zone_state"].get("budget", 0)
        stability  = state["zone_state"].get("stability_state", "stable")
        retry_count = state["retry_count"]
 
        # Retry context: give the planner the specific critique
        retry_context = ""
        if retry_count > 0:
            retry_context = (
                f"\n\n⚠️  REVISION REQUIRED (attempt {retry_count}/{MAX_RETRIES})\n"
                f"Risk Assessment rejected your previous plan:\n"
                f"  \"{state['risk_critique']}\"\n\n"
                f"Previous rejected actions:\n"
                f"{json.dumps(state['planned_actions'], indent=2)}\n\n"
                f"You MUST produce a cheaper or safer alternative. "
                f"If no safe action exists, return an empty actions list []."
            )
 
        # Comm agent context
        comm_context = ""
        if state.get("comm_needs_planning") and state.get("comm_response_actions"):
            comm_context = (
                f"\n\nCOMMUNICATION RESPONSES TO INCLUDE IN PLAN:\n"
                f"{json.dumps(state['comm_response_actions'], indent=2)}\n"
                f"These responses were flagged as requiring budget. "
                f"Include them in your actions list (cost them correctly)."
            )
 
        messages = [
            SystemMessage(content=(
                f"You are the Planning Agent for energy zone '{state['zone_id']}'.\n"
                "Role: Draft a strategic action plan as a JSON action list.\n"
                "You NEVER execute actions. You ONLY plan.\n\n"
                f"Available budget this tick: {budget:.1f} credits\n"
                f"Current stability:          {stability}\n"
                f"Budget reserve floor:       {BUDGET_RESERVE:.0f} credits "
                f"(Risk Agent will reject plans dropping below this)\n\n"
                f"{VALID_ACTIONS_SPEC}\n"
                "OUTPUT FORMAT — respond with ONLY valid JSON, no prose:\n"
                "{\n"
                '  "strategic_rationale": "one-sentence explanation of overall strategy",\n'
                '  "actions": [\n'
                '    {\n'
                f'      "action_type": "...",\n'
                f'      "params": {{"zone_id": "{state["zone_id"]}", ...}},\n'
                '      "estimated_cost": 0.0,\n'
                '      "rationale": "why this specific action"\n'
                '    }\n'
                '  ],\n'
                '  "total_estimated_cost": 0.0\n'
                "}\n\n"
                "RULES:\n"
                f"  • zone_id in params must be '{state['zone_id']}' "
                "  (except propose_trade → from_zone_id; build_new_route & open_trade_route → source_zone_id; request_aid → requesting_zone_id; monitor_zone → observer_zone_id)\n"
                "  • EXACT IDs ONLY: For source_id and route_id, you MUST use the exact lowercase string from the snapshot (e.g., 'alpha_solar', 'route_alpha_gamma'). Do not capitalize!\n"
                "  • STRICT NO-DUPLICATES RULE: Check the 'pending_actions' array. Do NOT re-queue an action targeting the same resource if it is already pending. It takes time to apply. Do not double-spend!\n"
                f"  • Keep total_estimated_cost < {budget - BUDGET_RESERVE:.0f} "
                f"  (budget {budget:.0f} minus {BUDGET_RESERVE:.0f} reserve)\n"
                "  • An empty actions list [] is valid if no action is warranted\n"
                "  • Only take actions that directly address Priority Concerns"
            )),
            HumanMessage(content=(
                f"SITUATION REPORT:\n{state['situation_report']}\n\n"
                f"ZONE SNAPSHOT (key numbers):\n"
                f"  budget:                {budget:.1f}\n"
                f"  stability:             {stability}\n"
                f"  stored_energy:         {state['zone_state'].get('stored_energy', '?')}\n"
                f"  net_energy_per_tick:   {state['zone_state'].get('net_energy_per_tick', '?')}\n"
                f"  projected_depletion:   {state['zone_state'].get('projected_depletion_ticks', 'N/A')}\n"
                f"  pending_actions:       {json.dumps(state['zone_state'].get('pending_actions', []))}\n"
                f"{comm_context}"
                f"{retry_context}\n\n"
                "Draft your JSON action plan:"
            )),
        ]
 
        response = self.llm.invoke(messages)
 
        # ── JSON parsing with graceful fallback ───────────────────────────
        try:
            content = response.content.strip()
            # Strip markdown code fences if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
 
            plan             = json.loads(content)
            planned_actions  = plan.get("actions", [])
            total_cost       = float(plan.get(
                "total_estimated_cost",
                sum(float(a.get("estimated_cost", 0)) for a in planned_actions)
            ))
 
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(f"[Planning] JSON parse error (retry {retry_count}): {exc}")
            logger.debug(f"Raw response: {response.content[:400]}")
            planned_actions = []
            total_cost      = 0.0
 
        print(
            f"  [Planning] {len(planned_actions)} action(s) | "
            f"est. cost: {total_cost:.0f} | retry #{retry_count}"
        )
        for act in planned_actions:
            print(f"    -> {act.get('action_type', '?')} "
                  f"(cost: {act.get('estimated_cost', '?')})")
 
        return {
            "planned_actions": planned_actions,
            "estimated_cost":  total_cost,
        }
 
    # ─────────────────────────────────────────────────────────────────────────
    # 4. RISK ASSESSMENT AGENT  (LLM → JSON)
    # ─────────────────────────────────────────────────────────────────────────
 
    def risk_assessment(self, state: AgentState) -> dict:
        """
        Financial and strategic safeguard.
 
        Evaluates the Planner's draft against:
          • Available budget (hard constraint)
          • Budget reserve floor (soft constraint — {BUDGET_RESERVE} credits)
          • Zone stability requirements
          • Action validity (correct zone_id, no duplicate pending actions)
 
        Enforces MAX_RETRIES: if the planner has already failed MAX_RETRIES times,
        forces an empty action list rather than entering an infinite loop.
 
        Outputs one of:
          "approved"     → passes approved_actions to Supervisor for execution
          "rejected"     → loops back to Planning with specific critique
          "forced_empty" → planning limit reached; Supervisor executes nothing
        """
        # Hard-enforce retry limit before even calling the LLM
        if state["retry_count"] >= MAX_RETRIES:
            print(
                f"  [RiskAssessment] MAX RETRIES ({MAX_RETRIES}) reached -- "
                f"forcing empty action list"
            )
            return {
                "risk_decision":  "forced_empty",
                "risk_critique":  (
                    f"Planning retry limit ({MAX_RETRIES}) reached. "
                    "No safe plan was produced. Supervisor will do nothing this tick."
                ),
                "approved_actions": [],
            }
 
        budget        = state["zone_state"].get("budget", 0)
        stability     = state["zone_state"].get("stability_state", "stable")
        estimated_cost = state["estimated_cost"]
 
        messages = [
            SystemMessage(content=(
                f"You are the Risk Assessment Agent for energy zone '{state['zone_id']}'.\n"
                "Role: Financial and strategic safeguard. Approve or reject the proposed plan.\n\n"
                f"Zone available budget:    {budget:.1f} credits\n"
                f"Plan estimated cost:      {estimated_cost:.1f} credits\n"
                f"Budget reserve floor:     {BUDGET_RESERVE:.0f} credits\n"
                f"Zone stability:           {stability}\n\n"
                "OUTPUT FORMAT — respond with ONLY valid JSON:\n"
                "{\n"
                '  "decision": "approved" | "rejected",\n'
                '  "critique": "specific reason",\n'
                '  "concerns": ["optional list of non-blocking concerns"],\n'
                '  "approved_actions": [...]  // exact copy of actions if approved; [] if rejected\n'
                "}\n\n"
                "REJECTION CRITERIA (reject if ANY of these are true):\n"
                f"  1. estimated_cost > {budget - BUDGET_RESERVE:.0f} "
                f"     (would drop budget below {BUDGET_RESERVE:.0f} reserve)\n"
                f"  2. estimated_cost > {budget:.0f} (literally unaffordable)\n"
                f"  3. Zone is CRITICAL or COLLAPSED but plan has NO emergency actions\n"
                "  4. Any action targets wrong zone_id or invalid source/route ID\n\n"
                "APPROVAL: An empty actions list [] is ALWAYS approved.\n"
                "If you approve, copy the actions list verbatim into approved_actions."
            )),
            HumanMessage(content=(
                f"ZONE STATE:\n"
                f"  stability_state:      {stability}\n"
                f"  budget:               {budget:.1f}\n"
                f"  stored_energy:        {state['zone_state'].get('stored_energy', '?')}\n"
                f"  net_energy_per_tick:  {state['zone_state'].get('net_energy_per_tick', '?')}\n"
                f"  active_crises:        {json.dumps(state['zone_state'].get('active_crises', []))}\n\n"
                f"PROPOSED ACTIONS ({len(state['planned_actions'])}, est. cost {estimated_cost:.1f}):\n"
                f"{json.dumps(state['planned_actions'], indent=2)}\n\n"
                "Evaluate and respond with JSON:"
            )),
        ]
 
        response = self.llm.invoke(messages)
 
        # ── Parse JSON response ───────────────────────────────────────────
        try:
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
 
            result           = json.loads(content)
            decision         = result.get("decision", "rejected").lower().strip()
            critique         = result.get("critique", "No critique provided.")
            approved_actions = result.get("approved_actions", []) if decision == "approved" else []
 
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(f"[RiskAssessment] JSON parse error: {exc}")
            decision         = "rejected"
            critique         = f"Risk assessment response could not be parsed: {exc}"
            approved_actions = []
 
        # Increment retry counter on rejection
        new_retry_count = state["retry_count"] + (1 if decision == "rejected" else 0)
 
        icon = "✅" if decision == "approved" else "❌"
        print(
            f"  [RiskAssessment] {icon} {decision.upper()} "
            f"(retry_count -> {new_retry_count}) | {critique[:80]}"
        )
 
        return {
            "risk_decision":    decision,
            "risk_critique":    critique,
            "approved_actions": approved_actions,
            "retry_count":      new_retry_count,
        }
 
    def route_risk_assessment(self, state: AgentState) -> str:
        """
        Pure routing function for risk_assessment conditional edges.
 
        Returns:
          "approved"     → supervisor_execute
          "retry"        → planning  (with incremented retry_count)
          "forced_empty" → supervisor_execute  (with empty approved_actions)
        """
        decision    = state["risk_decision"]
        retry_count = state["retry_count"]
 
        if decision == "approved":
            return "approved"
        if decision == "forced_empty" or retry_count >= MAX_RETRIES:
            return "forced_empty"
        return "retry"
 
    # ─────────────────────────────────────────────────────────────────────────
    # 5. SUPERVISOR EXECUTE  (deterministic — no LLM)
    # ─────────────────────────────────────────────────────────────────────────
 
    def supervisor_execute(self, state: AgentState) -> dict:
        """
        The ONLY agent that physically calls engine action methods.
 
        Iterates over approved_actions and dispatches each to the engine.
        Budget deduction and latency queuing are handled inside the engine.
        Collects execution results for the Report Agent.
        """
        actions     = state.get("approved_actions", [])
        exec_results = []
 
        if not actions:
            print("  [Supervisor] No actions to execute this tick")
            return {"executed_results": []}
 
        print(f"  [Supervisor] Executing {len(actions)} approved action(s):")
 
        for action in actions:
            action_type = action.get("action_type", "")
            params      = dict(action.get("params", {}))
 
            result = self._dispatch_action(action_type, params)
            exec_results.append({
                "action_type": action_type,
                "params":      params,
                "success":     result["success"],
                "result":      result["result"],
            })
 
            icon = "✓" if result["success"] else "✗"
            print(f"    {icon} {action_type:<35} -> {result['result']}")
 
        return {"executed_results": exec_results}
 
    def _dispatch_action(self, action_type: str, params: dict) -> dict:
        """
        Map action_type string → engine method and execute it.
 
        Handles energy_type string → EnergyType enum conversion automatically.
        Returns {"success": bool, "result": str}.
        """
        # Convert energy_type string to EnergyType enum
        if "energy_type" in params:
            try:
                params["energy_type"] = EnergyType(params["energy_type"])
            except ValueError as exc:
                return {"success": False, "result": f"Invalid energy_type: {exc}"}
 
        # Remove None values that might break engine methods
        params = {k: v for k, v in params.items() if v is not None or k == "max_rate"}
 
        method_name = f"action_{action_type}"
        method      = getattr(self.engine, method_name, None)
 
        if method is None:
            return {"success": False, "result": f"Unknown action_type: '{action_type}'"}
 
        try:
            result = method(**params)
            # Engine action methods return bool (True=success) or a route_id string
            if isinstance(result, bool):
                return {"success": result, "result": "OK" if result else "FAILED (engine rejected)"}
            elif result is not None:
                # build_new_route, open_trade_route, propose_trade return string IDs
                return {"success": True, "result": str(result)}
            else:
                return {"success": False, "result": "None returned (budget insufficient?)"}
        except TypeError as exc:
            return {"success": False, "result": f"Parameter error: {exc}"}
        except Exception as exc:
            return {"success": False, "result": f"Exception: {type(exc).__name__}: {exc}"}
 
    # ─────────────────────────────────────────────────────────────────────────
    # 6. REPORT AGENT  (LLM)
    # ─────────────────────────────────────────────────────────────────────────
 
    def report(self, state: AgentState) -> dict:
        """
        Creates the tick's console readout, explaining the 'why' behind AI behavior.
 
        Covers: problems identified → plan proposed → risk decision → actions executed.
        Also handles the fast-path report when planning was skipped entirely.
        """
        tick    = state["tick_number"]
        zone    = state["zone_id"].upper()
 
        # Fast path: stable zone, nothing was done
        if state.get("skip_planning") and not state.get("executed_results"):
            report_text = (
                f"[Tick {tick} | Zone {zone}] ✓ STABLE — Supervisor skipped planning cycle. "
                f"Zone is stable, no active crises, no incoming offers."
            )
            print(f"  [Report] {report_text}")
            return {"tick_report": report_text}
 
        messages = [
            SystemMessage(content=(
                "You are the Report Agent for an energy zone management system.\n"
                "Role: Produce a clear, concise terminal readout explaining the AI's "
                "decision-making for this tick. Plain text only — no markdown headers "
                "or bullet symbols. Write 8-12 lines total.\n\n"
                "Structure: state the top problem(s) → what the planner proposed and why → "
                "what risk assessment decided → what was actually executed and its outcome."
            )),
            HumanMessage(content=(
                f"Tick: {tick}  |  Zone: {state['zone_id']}\n\n"
                f"SITUATION (summary):\n{state.get('situation_report', 'N/A')[:600]}\n\n"
                f"PLAN PROPOSED ({len(state.get('planned_actions', []))} action(s), "
                f"est. cost {state.get('estimated_cost', 0):.0f}):\n"
                f"{json.dumps(state.get('planned_actions', []), indent=2)[:500]}\n\n"
                f"RISK DECISION: {state.get('risk_decision', 'N/A').upper()}\n"
                f"Critique: {state.get('risk_critique', 'N/A')}\n"
                f"Retries: {state.get('retry_count', 0)}/{MAX_RETRIES}\n\n"
                f"EXECUTED ({len(state.get('executed_results', []))} action(s)):\n"
                f"{json.dumps(state.get('executed_results', []), indent=2)[:400]}\n\n"
                "Write the tick report:"
            )),
        ]
 
        response    = self.llm.invoke(messages)
        tick_report = response.content
 
        print(f"\nAI REPORT -- Tick {tick} | Zone {zone}")
        for line in tick_report.strip().splitlines():
            print(f"  {line}")
 
        return {"tick_report": tick_report}
 
    # ─────────────────────────────────────────────────────────────────────────
    # 7. COMMUNICATION AGENT  (LLM → JSON)
    # ─────────────────────────────────────────────────────────────────────────
 
    def communication(self, state: AgentState) -> dict:
        """
        Diplomatic interface for handling external zone communications.
 
        Responsibilities:
          1. Parse incoming trade offers — decide accept, reject, or counter-offer
          2. Parse information requests — respond within fog-of-war constraints
          3. Parse aid requests and broadcasts from other zones
 
        If any response commits significant resources (budget > 20 or energy > 50),
        sets comm_needs_planning=True so the full Planning→Risk pipeline reviews it first.
        Otherwise, executes low-cost responses (reject_trade, emergency_broadcast)
        directly and routes to the Report Agent.
        """
        zone_state      = state["zone_state"]
        incoming_trades = zone_state.get("incoming_trade_offers", [])
        messages        = zone_state.get("messages", [])
 
        if not incoming_trades and not messages:
            print("  [Communication] No incoming offers or messages to handle")
            return {"comm_response_actions": [], "comm_needs_planning": False}
 
        budget    = zone_state.get("budget", 0)
        stored    = zone_state.get("stored_energy", 0)
        stability = zone_state.get("stability_state", "stable")
        fill_pct  = zone_state.get("storage_fill_pct", 0)
 
        llm_messages = [
            SystemMessage(content=(
                f"You are the Communication Agent for energy zone '{state['zone_id']}'.\n"
                "Role: Handle incoming trade offers and messages diplomatically and strategically.\n\n"
                f"Zone status: stability={stability}, budget={budget:.0f}, "
                f"stored={stored:.0f} ({fill_pct:.0f}% full)\n\n"
                "For each TRADE OFFER decide:\n"
                "  accept_trade  — if the terms benefit us and we can afford it\n"
                "  reject_trade  — if terms are unfavorable or we're under stress\n"
                "  propose_trade — counter-offer with better terms for us\n\n"
                "For INFORMATION REQUESTS: only share public data (stability_state, name).\n"
                "Never share exact budget or crisis details under fog-of-war.\n\n"
                "OUTPUT FORMAT — ONLY valid JSON:\n"
                "{\n"
                '  "response_actions": [\n'
                '    {\n'
                '      "action_type": "accept_trade|reject_trade|propose_trade|emergency_broadcast",\n'
                '      "params": {"zone_id": "...", ...},\n'
                '      "estimated_cost": 0.0,\n'
                '      "rationale": "why"\n'
                '    }\n'
                '  ],\n'
                '  "needs_planning": false,\n'
                '  "diplomatic_summary": "one-sentence summary"\n'
                "}\n\n"
                "Set needs_planning=true ONLY if accepting/countering a trade would cost "
                "> 20 budget credits or transfer > 50 units of stored energy. "
                "Simple reject_trade or emergency_broadcast never needs planning."
            )),
            HumanMessage(content=(
                f"INCOMING TRADE OFFERS:\n"
                f"{json.dumps(incoming_trades, indent=2)}\n\n"
                f"RECENT MESSAGES (last 5):\n"
                f"{json.dumps(messages[-5:] if messages else [], indent=2)}\n\n"
                f"ZONE RESOURCES:\n"
                f"  budget:        {budget:.0f} credits\n"
                f"  stored_energy: {stored:.0f} units ({fill_pct:.0f}% capacity)\n"
                f"  stability:     {stability}\n\n"
                "Decide how to respond to each offer/message and output JSON:"
            )),
        ]
 
        response = self.llm.invoke(llm_messages)
 
        # ── Parse JSON response ───────────────────────────────────────────
        try:
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
 
            result           = json.loads(content)
            response_actions = result.get("response_actions", [])
            needs_planning   = bool(result.get("needs_planning", False))
            summary          = result.get("diplomatic_summary", "")
 
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(f"[Communication] JSON parse error: {exc}")
            response_actions = []
            needs_planning   = False
            summary          = "Parse error — no comm actions taken"
 
        print(
            f"  [Communication] {len(response_actions)} response(s) | "
            f"needs_planning={needs_planning} | {summary[:60]}"
        )
 
        # If no planning needed, execute low-cost actions immediately
        if not needs_planning and response_actions:
            executed = []
            print(f"  [Communication] Executing {len(response_actions)} comm action(s) directly:")
            for action in response_actions:
                result = self._dispatch_action(
                    action.get("action_type", ""),
                    dict(action.get("params", {}))
                )
                icon = "✓" if result["success"] else "✗"
                print(f"    {icon} {action.get('action_type', '?')} -> {result['result']}")
                executed.append({**action, "success": result["success"], "result": result["result"]})
 
            return {
                "comm_response_actions": executed,
                "comm_needs_planning":   False,
                "executed_results":      executed,
            }
 
        return {
            "comm_response_actions": response_actions,
            "comm_needs_planning":   needs_planning,
        }
 
    def route_communication(self, state: AgentState) -> str:
        """
        Pure routing for communication conditional edges.
 
        Returns:
          "needs_planning" → situation_awareness (resource-committing response)
          "done"           → report (responses already executed or nothing to do)
        """
        if state.get("comm_needs_planning"):
            return "needs_planning"
        return "done"



    


    