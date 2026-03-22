from typing import TypedDict, List, Optional 

class AgentState(TypedDict):

    zone_id: str 
    tick_number: int 
    zone_state: dict 
    situation_report: str 
    planned_actions: List[dict]
    estimated_cost: float 
    risk_decision: str 
    risk_critique: str 
    retry_count: int 
    approved_actions: List[dict]
    executed_results: List[dict] 
    tick_report: str 
    skip_planning: bool 
    comm_response_actions: List[dict] 
    comm_needs_planning:bool 
    memory_context: str

def make_initial_state(zone_id: str) -> AgentState:
    """
    Create a clean initial AgentState for a new tick cycle.
    Pass this to graph.invoke() at the start of each tick.
    """
    return AgentState(
        zone_id=zone_id,
        tick_number=0,
        zone_state={},
        situation_report="",
        planned_actions=[],
        estimated_cost=0.0,
        risk_decision="",
        risk_critique="",
        retry_count=0,
        approved_actions=[],
        executed_results=[],
        tick_report="",
        skip_planning=False,
        comm_response_actions=[],
        comm_needs_planning=False,
        memory_context="",
    )