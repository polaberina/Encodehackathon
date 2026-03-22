"""
graph.py — LangGraph StateGraph construction for the Zone AI Governor.

Builds and compiles the full multi-agent pipeline for a single zone.
Call create_zone_graph() once per zone at simulation startup, then
invoke the compiled graph each tick via graph.invoke(initial_state).

Graph topology:
                        ┌──────────────────────────────────────────────────┐
                        │                                                  │
             START      │                                                  │
               │        │                                                  │
               ▼        │                                                  │
        ┌─────────────┐ │  ┌──────────────────┐   ┌─────────────────────┐ │
        │ supervisor_ │ │  │ situation_       │   │                     │ │
        │ gate        │─┼─►│ awareness        │──►│ planning ◄──────────┼─┘
        └─────────────┘ │  └──────────────────┘   │                     │
             │   │      │                          └────────┬────────────┘
          skip   comm   │                                   │
             │   │      └──────────────────────────────────►│
             │   ▼                                          ▼
             │ ┌─────────────┐      ┌───────────────────────────────┐
             │ │ communica-  │ done │ risk_assessment               │
             │ │ tion        │─────►│ (approved / retry / forced)   │
             │ └─────────────┘      └──────────┬────────────────────┘
             │      │ needs_                    │ approved / forced_empty
             │      │ planning                  ▼
             │      │              ┌───────────────────────┐
             │      │              │ supervisor_execute     │
             │      │              └──────────┬────────────┘
             │      │                         │
             └──────┴─────────────────────────►
                                              ▼
                                      ┌───────────────┐
                                      │ report        │──► END
                                      └───────────────┘

Key design decisions:
  • One graph instance per zone (closures bind engine + zone_id).
  • communication can route back to situation_awareness when a trade
    response requires resource commitment (needs_planning=True).
  • risk_assessment loops back to planning up to MAX_RETRIES times,
    then forces an empty action list to prevent infinite looping.
  • supervisor_execute is the single point of engine action calls.
"""

from langgraph.graph import StateGraph, END

from state import AgentState
from nodes import ZoneAgentNodes


def create_zone_graph(engine, zone_id: str, llm_model: str = "gpt-4o-mini"):
    """
    Build and compile a LangGraph StateGraph for a single zone governor.

    Args:
        engine:     SimulationEngine instance (shared across zones).
        zone_id:    ID of the zone this graph will govern (e.g. "alpha").
        llm_model:  Anthropic model string (default: claude-sonnet-4-6).

    Returns:
        A compiled LangGraph that accepts AgentState and returns final AgentState.

    Usage:
        graph = create_zone_graph(engine, "alpha")
        from agents.state import make_initial_state
        final = graph.invoke(make_initial_state("alpha"))
    """
    nodes   = ZoneAgentNodes(engine=engine, zone_id=zone_id, llm_model=llm_model)
    builder = StateGraph(AgentState)

    # ── Register all nodes ────────────────────────────────────────────────
    builder.add_node("supervisor_gate",     nodes.supervisor_gate)
    builder.add_node("situation_awareness", nodes.situation_awareness)
    builder.add_node("planning",            nodes.planning)
    builder.add_node("risk_assessment",     nodes.risk_assessment)
    builder.add_node("supervisor_execute",  nodes.supervisor_execute)
    builder.add_node("report",              nodes.report)
    builder.add_node("communication",       nodes.communication)

    # ── Entry point ────────────────────────────────────────────────────────
    builder.set_entry_point("supervisor_gate")

    # ── supervisor_gate → branching ────────────────────────────────────────
    #   "plan"        → full Situation Awareness pipeline
    #   "communicate" → Communication Agent for diplomatic handling
    #   "skip"        → straight to Report (stable, nothing to do)
    builder.add_conditional_edges(
        "supervisor_gate",
        nodes.route_supervisor_gate,
        {
            "plan":        "situation_awareness",
            "communicate": "communication",
            "skip":        "report",
        },
    )

    # ── Situation Awareness → Planning (always) ───────────────────────────
    builder.add_edge("situation_awareness", "planning")

    # ── Planning → Risk Assessment (always) ───────────────────────────────
    builder.add_edge("planning", "risk_assessment")

    # ── Risk Assessment → branching ────────────────────────────────────────
    #   "approved"     → Supervisor executes the plan
    #   "retry"        → Planning Agent revises (up to MAX_RETRIES times)
    #   "forced_empty" → Supervisor executes nothing (retry limit hit)
    builder.add_conditional_edges(
        "risk_assessment",
        nodes.route_risk_assessment,
        {
            "approved":     "supervisor_execute",
            "retry":        "planning",
            "forced_empty": "supervisor_execute",
        },
    )

    # ── Supervisor Execute → Report (always) ──────────────────────────────
    builder.add_edge("supervisor_execute", "report")

    # ── Report → END (always) ─────────────────────────────────────────────
    builder.add_edge("report", END)

    # ── Communication → branching ─────────────────────────────────────────
    #   "needs_planning" → Situation Awareness (resource-committing response)
    #   "done"           → Report (low-cost responses already executed)
    builder.add_conditional_edges(
        "communication",
        nodes.route_communication,
        {
            "needs_planning": "situation_awareness",
            "done":           "report",
        },
    )

    return builder.compile()


def create_all_zone_graphs(engine, llm_model: str = "gpt-4o-mini") -> dict:
    """
    Convenience function: create one compiled graph per zone in the engine.

    Returns:
        dict mapping zone_id → compiled graph.

    Usage:
        graphs = create_all_zone_graphs(engine)
        # In governor hook:
        def governor_hook(engine, zone):
            state = make_initial_state(zone.zone_id)
            graphs[zone.zone_id].invoke(state)
    """
    return {
        zone_id: create_zone_graph(engine, zone_id, llm_model)
        for zone_id in engine.zones
    }