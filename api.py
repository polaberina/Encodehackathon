"""
api.py — FastAPI server that runs the run_demo.py simulation engine
and exposes its state to the frontend.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import EnergyType, StabilityState
from engine import SimulationEngine
from run_demo import (
    make_zone_alpha, make_zone_beta, make_zone_gamma, make_zone_delta, make_routes,
    c_equipment_failure, c_drought, c_embargo, c_cyber_attack,
    c_heat_wave, c_worker_strike, c_storage_leak, c_wildfire,
    c_regional_blackout, c_recession, c_transmission_surge,
    _actions_tick4, _actions_tick6, _actions_tick8, _actions_tick10,
    _actions_tick12, _actions_tick14, _actions_tick15, _actions_tick16,
    _actions_tick20,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Engine singleton ──────────────────────────────────────────────────────────

def _build_engine() -> SimulationEngine:
    engine = SimulationEngine(seed=42)
    engine.ticks_per_season = 6

    engine.add_zone(make_zone_alpha())
    engine.add_zone(make_zone_beta())
    engine.add_zone(make_zone_gamma())
    engine.add_zone(make_zone_delta())
    for route in make_routes():
        engine.add_trade_route(route)

    engine.schedule_crisis(c_equipment_failure(), fire_at_tick=3,  warning_probability=0.80)
    engine.schedule_crisis(c_drought(),           fire_at_tick=5,  warning_probability=0.90)
    engine.schedule_crisis(c_embargo(),           fire_at_tick=7,  warning_probability=0.60)
    engine.schedule_crisis(c_cyber_attack(),      fire_at_tick=9,  warning_probability=0.50)
    engine.schedule_crisis(c_heat_wave(),         fire_at_tick=11, warning_probability=0.85)
    engine.schedule_crisis(c_worker_strike(),     fire_at_tick=13, warning_probability=0.70)
    engine.schedule_crisis(c_storage_leak(),      fire_at_tick=15, warning_probability=0.65)
    engine.schedule_crisis(c_wildfire(),          fire_at_tick=17, warning_probability=0.75)
    engine.schedule_crisis(c_regional_blackout(), fire_at_tick=19, warning_probability=0.80)
    engine.schedule_crisis(c_recession(),         fire_at_tick=22, warning_probability=0.90)
    engine.schedule_crisis(c_transmission_surge(),fire_at_tick=23, warning_probability=0.70)

    return engine


GOVERNOR_DISPATCH = {
    4:  _actions_tick4,
    6:  _actions_tick6,
    8:  _actions_tick8,
    10: _actions_tick10,
    12: _actions_tick12,
    14: _actions_tick14,
    15: _actions_tick15,
    16: _actions_tick16,
    20: _actions_tick20,
}

engine = _build_engine()

# ── Serialisation helpers ─────────────────────────────────────────────────────

def _serialize_zone(zone, eng: SimulationEngine) -> dict:
    state = eng.get_zone_state(zone.zone_id)
    sources = state.get("active_sources", [])
    active_crises = state.get("active_crises", [])
    trade_routes_raw = state.get("trade_routes", [])

    # Stability
    stability = zone.stability_state.value

    # Supply = sum of actual outputs
    supply = sum(s.get("actual_output_this_tick", 0) for s in sources)
    demand = state.get("energy_demand_per_tick", zone.base_demand)

    return {
        "id": zone.zone_id,
        "name": zone.name,
        "region": zone.region,
        "stabilityState": stability,
        "storage": round(zone.storage.stored_energy, 1),
        "maxStorage": round(zone.storage.capacity, 1),
        "budget": round(zone.economy.budget, 1),
        "budgetPerTick": zone.economy.budget_per_tick,
        "incomeModifier": zone.economy.income_modifier,
        "totalSpent": round(zone.economy.total_spent, 1),
        "morale": round(zone.morale, 1),
        "reputation": round(zone.reputation, 1),
        "baseDemand": zone.base_demand,
        "demandModifier": zone.demand_modifier,
        "seasonalDemandModifier": zone.seasonal_demand_modifier,
        "supply": round(supply, 1),
        "demand": round(demand, 1),
        "netEnergyPerTick": round(state.get("net_energy_per_tick", 0), 1),
        "projectedDepletionTicks": state.get("projected_depletion_ticks"),
        "cyberAttacked": zone.cyber_attacked,
        "energySources": [
            {
                "sourceId": s["source_id"],
                "type": s["type"],
                "lowOutputRate": s["low_rate"],
                "highOutputRate": s["high_rate"],
                "resilience": 0.0,
                "active": s["active"],
                "outputModifier": s["output_modifier"],
                "degradationModifier": s["degradation_modifier"],
                "seasonalModifier": s["seasonal_modifier"],
                "currentOutput": round(s.get("actual_output_this_tick", 0), 1),
            }
            for s in sources
        ],
        "activeCrises": [
            {
                "crisisId": c["crisis_id"],
                "crisisType": c["type"],
                "targetId": zone.zone_id,
                "duration": 0,
                "remainingTicks": c["ticks_remaining"],
                "tier": "medium",
                "cost": 0,
                "description": c["description"],
                "parameters": {},
            }
            for c in active_crises
        ],
        "tradeRoutes": trade_routes_raw,
        "messages": state.get("messages", []),
        "pendingActions": state.get("pending_actions", []),
        "incomingTradeOffers": state.get("incoming_trade_offers", []),
        "outgoingTradeOffers": state.get("outgoing_trade_offers", []),
        # Placeholder scoring fields
        "survivalTicks": eng.tick_number,
        "crisesMitigated": 0,
        "crisesTotal": len(active_crises),
        "tradeProfitability": 0,
        "efficiencyScore": 0,
        "fogOfWarLevel": 0,
        # UI helpers
        "archetype": zone.zone_id,
        "strategy": "defensive",
        "description": "",
        "color": {"alpha": "#22C55E", "beta": "#3B82F6", "gamma": "#F97316"}.get(zone.zone_id, "#A855F7"),
        "position": {"x": 0, "y": 0},
    }


def _serialize_route(route, eng: SimulationEngine) -> dict:
    return {
        "id": route.route_id,
        "sourceZoneId": route.source_zone_id,
        "targetZoneId": route.target_zone_id,
        "transferRate": round(route.effective_transfer_rate, 2),
        "latency": route.latency,
        "routeHealth": round(route.route_health, 1),
        "transmissionEfficiency": route.transmission_efficiency,
        "exportCap": route.export_cap,
        "fortification": route.fortification,
        "isEmbargoed": route.route_id in eng.embargoed_routes,
        "currentFlow": round(route.effective_received_rate, 2),
        "maxCapacity": round(route.transfer_rate, 2),
        "isActive": not route.is_severed and route.route_id not in eng.embargoed_routes,
    }


def _build_state() -> dict:
    zones = [_serialize_zone(z, engine) for z in engine.zones.values()]
    routes = [_serialize_route(r, engine) for r in engine.trade_routes.values()]

    active_crises = [
        {
            "crisisId": c.crisis_id,
            "crisisType": c.crisis_type.value,
            "targetId": c.target_id,
            "duration": c.duration,
            "remainingTicks": c.remaining_ticks,
            "tier": "medium",
            "cost": 0,
            "description": c.description,
            "parameters": {k: v for k, v in c.parameters.items() if isinstance(v, (int, float, str, bool))},
        }
        for c in engine.crisis_events
    ]

    total_supply = sum(z["supply"] for z in zones)
    total_demand = sum(z["demand"] for z in zones)
    avg_morale = sum(z["morale"] for z in zones) / max(len(zones), 1)
    avg_budget = sum(z["budget"] for z in zones) / max(len(zones), 1)
    total_budget = sum(z["budget"] for z in zones)

    # Recent log entries (last 20)
    recent_logs = engine.event_log[-20:] if engine.event_log else []

    # Pending actions as governor actions
    recent_actions = [
        {
            "id": a.get("action_id", ""),
            "agentId": f"agent-{a.get('zone_name', '').lower()}",
            "zoneName": a.get("zone_name", ""),
            "type": a.get("action_type", ""),
            "cost": 0,
            "latency": max(0, a.get("apply_at_tick", 0) - engine.tick_number),
            "details": a.get("action_type", "").replace("_", " "),
            "tick": engine.tick_number,
            "timestamp": 0,
            "status": "pending",
            "params": {},
        }
        for a in engine._pending_actions
    ]

    # Trade negotiations
    negotiations = [
        {
            "id": o.offer_id,
            "fromZoneId": o.from_zone_id,
            "toZoneId": o.to_zone_id,
            "energyOffered": o.energy_offered,
            "budgetOffered": o.budget_offered,
            "energyRequested": o.energy_requested,
            "budgetRequested": o.budget_requested,
            "expiresAtTick": o.expires_at_tick,
            "status": o.status,
            "description": o.description,
        }
        for o in engine._pending_trade_offers.values()
    ]

    all_above_threshold = all((z["storage"] / max(z["maxStorage"], 1)) > 0.2 for z in zones)
    is_defeat = any((z["storage"] / max(z["maxStorage"], 1)) < 0.1 for z in zones) or any(z["morale"] < 20 for z in zones)

    seasons = ["spring", "summer", "autumn", "winter"]

    return {
        "tick": engine.tick_number,
        "season": engine.season.value,
        "zones": zones,
        "tradeRoutes": routes,
        "activeCrises": active_crises,
        "crisisAgent": {
            "budget": 0,
            "incomeThisTick": 0,
            "totalSpent": 0,
            "plannedCrises": [],
            "executedCrises": active_crises,
            "strategy": "Scheduled scenario",
            "vulnerabilityRanking": [z["name"] for z in zones],
        },
        "recentActions": recent_actions or [],
        "negotiations": negotiations or [],
        "recentLogs": recent_logs,
        "globalMetrics": {
            "totalSupply": round(total_supply, 1),
            "totalDemand": round(total_demand, 1),
            "averageMorale": round(avg_morale, 1),
            "averageEconomy": round(avg_budget, 1),
            "gridStability": round(min(1.0, total_supply / max(total_demand, 1)), 3),
            "totalZoneBudget": round(total_budget, 1),
        },
        "victoryConditions": {
            "ticksSurvived": engine.tick_number,
            "targetTicks": 25,
            "allZonesAboveStorageThreshold": all_above_threshold,
            "storageThreshold": 20,
            "crisisMitigationRate": 0,
            "targetMitigationRate": 80,
            "isVictory": engine.tick_number >= 25 and all_above_threshold,
            "isDefeat": is_defeat,
            "defeatReason": None,
        },
        "tickPhase": "idle",
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    return _build_state()


@app.post("/api/tick")
def advance_tick():
    global engine
    if engine.tick_number >= 25:
        return _build_state()

    engine.tick()

    # Run hardcoded governor actions
    if engine.tick_number in GOVERNOR_DISPATCH:
        try:
            GOVERNOR_DISPATCH[engine.tick_number](engine)
        except Exception as e:
            pass  # Don't crash the API on demo action errors

    return _build_state()


@app.post("/api/reset")
def reset():
    global engine
    engine = _build_engine()
    return _build_state()
