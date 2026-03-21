"""
engine.py — The Simulation Engine.

This is the "physics" of the world. It owns the authoritative state of all
zones, routes, and crises, and advances time via tick().

Key design principle: The engine is the single source of truth. Agents
never modify zone state directly — they call engine action methods, which
validate, check budget, deduct cost, and apply changes atomically.

Tick execution order (v3):
  0.  Advance season calendar.
  1.  Fire any scheduled crises (and send early warnings 2 ticks ahead).
  2.  Apply active crisis effects (set modifiers before any production).
  3.  Sample random outputs for all energy sources.
  4.  Energy sources produce output -> deposited into Storage.
  5.  Economy: each zone earns budget (scaled by income_modifier and morale).
  6.  Trade routes transfer energy (respects export_cap; embargoed routes skipped).
  7.  Zone demand is consumed from Storage.
  8.  Source aging: age increments; every 5 ticks degradation_modifier decreases.
  9.  Storage leaks applied (STORAGE_LEAK crises).
  10. Morale and reputation updated based on stability state.
  11. Monitoring subscriptions ticked down.
  12. Pending route construction ticked down; completed routes go live.
  13. Stability metrics recalculated.
  14. Governor Agents observe and act.      <- Phase 2 hook
  15. Crisis Agent evaluates and injects.   <- Phase 2 hook
  16. Active crises ticked down / expired.

New in v3:
  Seasonal mechanics:
    SEASONAL_SOURCE_MODIFIERS maps (EnergyType, Season) -> multiplier.
    SEASONAL_DEMAND_MODIFIERS maps Season -> demand multiplier.
    Applied every tick by _step_advance_season().

  Source aging:
    Sources degrade slowly over time (degradation_modifier decreases every
    5 ticks). Invest in efficiency to permanently raise output rates.

  Morale and reputation:
    Tracked per zone. Both affect income and demand. Morale degradation
    compounds under consecutive Critical ticks.

  Partial observability:
    get_zone_state(zone_id, observer_zone_id) returns full, partial, or
    minimal info depending on whether the observer has a trade route or
    has spent budget on action_monitor_zone().

  Scheduled crises with early warnings:
    schedule_crisis() queues a crisis to fire at a specific tick and
    automatically sends a noisy warning signal 2 ticks before.

  New actions:
    fortify_route, sell_surplus, build_new_route, invest_in_efficiency,
    set_export_cap, deploy_emergency_generator, request_aid,
    issue_conservation_order, settle_worker_strike, repair_source,
    monitor_zone.

  New crises handled:
    DROUGHT, HEAT_WAVE, WILDFIRE, EQUIPMENT_FAILURE, STORAGE_LEAK,
    ECONOMIC_RECESSION, WORKER_STRIKE, POLITICAL_EMBARGO, CYBER_ATTACK,
    TRANSMISSION_SURGE, REGIONAL_BLACKOUT, CASCADING_FAILURE (now fully
    implemented with neighbour spread).
"""

import uuid
import random
import logging
from typing import Optional, Callable
from models import (
    Zone, EnergySource, TradeRoute, CrisisEvent, TradeOffer, Storage, Economy,
    StabilityState, EnergyType, CrisisType, Season
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# ACTION COSTS
# ─────────────────────────────────────────────────────────────

ACTION_COSTS: dict = {
    # ── Original actions ──────────────────────────────────────
    "ration_energy":              10.0,
    "boost_source":               50.0,
    "repair_route":               30.0,
    "open_trade_route":           20.0,
    "close_trade_route":           5.0,
    "emergency_broadcast":         0.0,
    "upgrade_storage":           100.0,
    # ── New actions ───────────────────────────────────────────
    "fortify_route":              40.0,   # Harden a route against attack damage
    "sell_surplus":                0.0,   # Free; energy -> credits conversion
    "build_new_route":           150.0,   # Expensive; route ready after delay
    "invest_in_efficiency":       80.0,   # Permanently raise source output rates
    "set_export_cap":              5.0,   # Limit export without closing route
    "deploy_emergency_generator": 75.0,   # Temporary fossil backup source
    "request_aid":                 0.0,   # Free for requester; donor pays energy
    "issue_conservation_order":   15.0,   # Cut demand at cost of morale
    "settle_worker_strike":       60.0,   # Resolve WORKER_STRIKE crisis
    "repair_source":              35.0,   # Restore EQUIPMENT_FAILURE offline source
    "monitor_zone":               20.0,   # Full observability of a zone for N ticks
    # ── Trade offer actions ───────────────────────────────────
    "propose_trade":               5.0,   # Small admin cost to draft an offer
    "accept_trade":                0.0,   # Acceptance is free; value is in the deal
    "reject_trade":                0.0,   # Rejection is free
}

# ─────────────────────────────────────────────────────────────
# ACTION LATENCY (in ticks)
# Budget is deducted immediately when an action is queued.
# The actual state change takes effect after this many ticks.
# 0 = immediate (applied in the same tick, no queue entry created).
# ─────────────────────────────────────────────────────────────

ACTION_LATENCY: dict = {
    # Immediate — communication or admin policy (no physical work needed)
    "sell_surplus":               0,
    "emergency_broadcast":        0,
    "monitor_zone":               0,
    "set_export_cap":             0,
    # Fast (1 tick) — quick decisions with modest ramp-up time
    "ration_energy":              1,
    "close_trade_route":          1,
    "boost_source":               1,
    "deploy_emergency_generator": 1,
    "issue_conservation_order":   1,
    "settle_worker_strike":       1,
    "request_aid":                1,
    # Moderate (2 ticks) — crew mobilization or engineering work
    "repair_route":               2,
    "fortify_route":              2,
    "repair_source":              2,
    "invest_in_efficiency":       2,
    "open_trade_route":           2,
    # Slow (3 ticks) — major infrastructure construction
    "upgrade_storage":            3,
    # Trade offers: propose is instant (message delivery); accept has 1-tick settlement
    "propose_trade":              0,
    "accept_trade":               1,
    "reject_trade":               0,
}

# ─────────────────────────────────────────────────────────────
# SEASONAL MULTIPLIERS
# ─────────────────────────────────────────────────────────────

SEASON_ORDER = [Season.SPRING, Season.SUMMER, Season.AUTUMN, Season.WINTER]

# Per (EnergyType, Season) output multiplier applied to seasonal_modifier.
SEASONAL_SOURCE_MODIFIERS: dict = {
    EnergyType.SOLAR: {
        Season.SPRING: 0.90,
        Season.SUMMER: 1.30,    # Long days, strong sun
        Season.AUTUMN: 0.70,
        Season.WINTER: 0.40,    # Short days, low angle
    },
    EnergyType.HYDRO: {
        Season.SPRING: 1.30,    # Snowmelt runoff
        Season.SUMMER: 0.85,    # Lower water levels
        Season.AUTUMN: 0.90,
        Season.WINTER: 0.60,    # Ice / low flow
    },
    EnergyType.WIND: {
        Season.SPRING: 1.10,
        Season.SUMMER: 0.80,    # Calmer summers
        Season.AUTUMN: 1.15,
        Season.WINTER: 1.30,    # Stronger winter winds
    },
    EnergyType.FOSSIL: {
        Season.SPRING: 1.00,
        Season.SUMMER: 1.00,
        Season.AUTUMN: 1.00,
        Season.WINTER: 1.00,    # Fossil unaffected by weather
    },
    EnergyType.NUCLEAR: {
        Season.SPRING: 1.00,
        Season.SUMMER: 0.95,    # Slight cooling efficiency drop in heat
        Season.AUTUMN: 1.00,
        Season.WINTER: 1.00,
    },
}

# Per-season demand multiplier applied to seasonal_demand_modifier.
SEASONAL_DEMAND_MODIFIERS: dict = {
    Season.SPRING: 0.90,
    Season.SUMMER: 1.00,
    Season.AUTUMN: 0.95,
    Season.WINTER: 1.30,    # Heating demand spike
}


class SimulationEngine:
    """
    The central engine that owns and advances all simulation state.

    Usage:
        engine = SimulationEngine(seed=42)
        engine.add_zone(zone_a)
        engine.add_zone(zone_b)
        engine.add_trade_route(route)
        engine.schedule_crisis(crisis_event, fire_at_tick=5)
        engine.tick()
    """

    def __init__(self, seed: Optional[int] = None):
        self.zones: dict = {}
        self.trade_routes: dict = {}
        self.crisis_events: list = []
        self.tick_number: int = 0

        self.rng = random.Random(seed)

        # Phase 2 hooks
        self.governor_hook: Optional[Callable] = None
        self.crisis_hook: Optional[Callable] = None

        # Event log
        self.event_log: list = []

        # ── Seasonal state ────────────────────────────────────────────────
        self.season: Season = Season.SPRING
        self._season_tick: int = 0
        self.ticks_per_season: int = 8      # Each season lasts 8 ticks by default

        # ── New v3 state ──────────────────────────────────────────────────
        self.embargoed_routes: set = set()  # Route IDs blocked by POLITICAL_EMBARGO
        self._pending_routes: list = []     # Under-construction routes (build_new_route)
        self._temp_sources: dict = {}       # gen_id -> ticks_remaining (emergency gens)
        self._monitored_zones: dict = {}    # {observer_id: {target_id: ticks_remaining}}
        self._scheduled_crises: list = []   # [{crisis, fire_tick, warning_sent, ...}]

        # ── Action latency queue ──────────────────────────────────────────
        # Actions with latency > 0 are stored here and applied when
        # apply_at_tick <= tick_number at the start of each tick.
        # Format: {action_id, action_type, zone_name, apply_at_tick, params}
        self._pending_actions: list = []

        # ── Trade offer system ────────────────────────────────────────────
        # Keyed by offer_id. Offers sit here until accepted, rejected, or expired.
        self._pending_trade_offers: dict = {}   # offer_id -> TradeOffer

    # ──────────────────────────────────────────
    # SETUP METHODS
    # ──────────────────────────────────────────

    def add_zone(self, zone: Zone):
        self.zones[zone.zone_id] = zone
        logger.info(f"Zone added: {zone.name} ({zone.zone_id})")

    def add_trade_route(self, route: TradeRoute):
        assert route.source_zone_id in self.zones, \
            f"Source zone '{route.source_zone_id}' not registered"
        assert route.target_zone_id in self.zones, \
            f"Target zone '{route.target_zone_id}' not registered"
        self.trade_routes[route.route_id] = route
        logger.info(
            f"Trade route: {route.source_zone_id} -> {route.target_zone_id} "
            f"| sent: {route.effective_transfer_rate:.1f}/tick "
            f"| received: {route.effective_received_rate:.1f}/tick "
            f"| heat loss: {route.heat_loss_rate:.1f}/tick"
        )

    def inject_crisis(self, crisis: CrisisEvent):
        """Inject a crisis immediately (fires this tick)."""
        self.crisis_events.append(crisis)
        self._log(f"CRISIS: [{crisis.crisis_type.value}] -> {crisis.target_id} -- {crisis.description}")

    def schedule_crisis(
        self,
        crisis: CrisisEvent,
        fire_at_tick: int,
        send_warning: bool = True,
        warning_probability: float = 0.75,
    ):
        """
        Queue a crisis to fire at a specific tick.

        If send_warning=True, an early warning signal is delivered 2 ticks
        before the crisis fires. The probability is intentionally noisy —
        sometimes warnings are false alarms (set warning_probability < 1.0).
        """
        self._scheduled_crises.append({
            "crisis": crisis,
            "fire_tick": fire_at_tick,
            "warning_sent": False,
            "send_warning": send_warning,
            "warning_probability": warning_probability,
        })

    # ──────────────────────────────────────────
    # MAIN TICK
    # ──────────────────────────────────────────

    def tick(self):
        """Advance the simulation by one time step."""
        self.tick_number += 1
        self._log(f"=== Tick {self.tick_number} | Season: {self.season.value.upper()} ===")

        self._step_apply_pending_actions()      # Step 0:  Apply matured deferred actions
        self._step_advance_season()             # Step 1:  Season calendar + modifiers
        self._step_scheduled_crises()           # Step 2:  Fire/warn scheduled crises
        self._apply_active_crises()             # Step 3:  Apply modifiers from active crises
        self._step_sample_outputs()             # Step 4:  Roll random outputs
        self._step_energy_production()          # Step 5:  Produce -> Storage
        self._step_economy()                    # Step 6:  Earn budget
        self._step_trade_transfer()             # Step 7:  Trade (with embargo + cap)
        self._step_demand_consumption()         # Step 8:  Consume demand
        self._step_source_aging()               # Step 9:  Age sources + expire temp gens
        self._step_storage_leak()               # Step 10: STORAGE_LEAK drains
        self._step_morale()                     # Step 11: Update morale and reputation
        self._step_monitoring_decay()           # Step 12: Tick monitoring subscriptions
        self._step_pending_routes()             # Step 13: Advance under-construction routes
        self._step_recalculate_stability()      # Step 14: Recompute stability

        # Step 15: Governor Agent hook (Phase 2)
        if self.governor_hook:
            for zone in self.zones.values():
                if zone.stability_state != StabilityState.COLLAPSED:
                    self.governor_hook(self, zone)

        # Step 16: Crisis Agent hook (Phase 2)
        if self.crisis_hook:
            self.crisis_hook(self)

        # Step 17: Expire finished crises
        self._step_expire_crises()

        # Step 18: Expire stale trade offers
        self._step_expire_trade_offers()

    # ──────────────────────────────────────────
    # TICK STEPS (private)
    # ──────────────────────────────────────────

    def _step_apply_pending_actions(self):
        """
        Step 0: Apply any deferred actions whose apply_at_tick has arrived.

        Actions are sorted by apply_at_tick so earlier-queued actions execute
        first within the same tick.  If the target zone or resource no longer
        exists (e.g. zone collapsed, source removed) the action is skipped with
        a warning log — the budget was already deducted when the action was
        queued.
        """
        ready, still_pending = [], []
        for item in self._pending_actions:
            if item["apply_at_tick"] <= self.tick_number:
                ready.append(item)
            else:
                still_pending.append(item)
        self._pending_actions = still_pending
        ready.sort(key=lambda x: x["apply_at_tick"])
        for item in ready:
            self._apply_pending_action(item)

    def _apply_pending_action(self, item: dict):
        """Dispatch and execute a single matured pending action."""
        atype = item["action_type"]
        p     = item["params"]
        zname = item.get("zone_name", "?")
        self._log(f"  [Latency] Applying deferred '{atype}' for {zname}")

        if atype == "ration_energy":
            zone = self.zones.get(p["zone_id"])
            if zone and zone.stability_state != StabilityState.COLLAPSED:
                zone.demand_modifier = max(0.1, 1.0 - p["reduction_pct"])
                self._log(
                    f"  [Action] {zone.name}: energy rationed "
                    f"(demand modifier -> {zone.demand_modifier:.2f})"
                )

        elif atype == "boost_source":
            zone = self.zones.get(p["zone_id"])
            if zone:
                for source in zone.sources:
                    if source.source_id == p["source_id"]:
                        source.output_modifier = min(p["boost_factor"], 2.0)
                        self._log(
                            f"  [Action] {zone.name}: boosted {p['source_id']} "
                            f"(modifier -> {source.output_modifier:.1f}x)"
                        )
                        break

        elif atype == "repair_route":
            route = self.trade_routes.get(p["route_id"])
            if route:
                route.route_health = min(100.0, route.route_health + p["repair_amount"])
                self._log(
                    f"  [Action] Route {p['route_id']} repaired "
                    f"-> health {route.route_health:.1f}"
                )
            else:
                self._log(f"  [Latency] repair_route: route {p['route_id']} no longer exists")

        elif atype == "open_trade_route":
            route = p["route"]
            if route.source_zone_id in self.zones and route.target_zone_id in self.zones:
                self.add_trade_route(route)
                self._log(
                    f"  [Action] Route opened: {route.source_zone_id}->{route.target_zone_id} "
                    f"| rate {route.transfer_rate:.1f}/tick "
                    f"| eff {route.transmission_efficiency*100:.0f}%"
                )
            else:
                self._log(f"  [Latency] open_trade_route: zone(s) no longer exist")

        elif atype == "close_trade_route":
            if p["route_id"] in self.trade_routes:
                del self.trade_routes[p["route_id"]]
                self._log(f"  [Action] Route {p['route_id']} closed by {zname}")
            else:
                self._log(f"  [Latency] close_trade_route: route {p['route_id']} already gone")

        elif atype == "upgrade_storage":
            zone = self.zones.get(p["zone_id"])
            if zone:
                zone.storage.capacity += p["additional_capacity"]
                self._log(
                    f"  [Action] {zone.name}: storage upgraded "
                    f"+{p['additional_capacity']:.0f} -> new capacity {zone.storage.capacity:.0f}"
                )

        elif atype == "fortify_route":
            route = self.trade_routes.get(p["route_id"])
            if route:
                old = route.fortification
                route.fortification = min(1.0, route.fortification + 0.30)
                self._log(
                    f"  [Action] Route {p['route_id']} fortified: "
                    f"{old:.2f} -> {route.fortification:.2f} "
                    f"({route.fortification*100:.0f}% damage reduction)"
                )
            else:
                self._log(f"  [Latency] fortify_route: route {p['route_id']} no longer exists")

        elif atype == "deploy_emergency_generator":
            zone = self.zones.get(p["zone_id"])
            if zone and zone.stability_state != StabilityState.COLLAPSED:
                gen_id = p["gen_id"]
                temp_source = EnergySource(
                    source_id=gen_id,
                    energy_type=EnergyType.FOSSIL,
                    low_output_rate=p["output_rate"] * 0.80,
                    high_output_rate=p["output_rate"],
                    resilience=0.3,
                    degradation_rate=0.0,
                    seasonal_modifier=1.0,
                )
                zone.sources.append(temp_source)
                self._temp_sources[gen_id] = p["duration"]
                self._log(
                    f"  [Action] {zone.name}: emergency generator online "
                    f"| ~{p['output_rate']:.0f}/tick for {p['duration']} ticks"
                )
            else:
                self._log(f"  [Latency] deploy_emergency_generator: zone unavailable")

        elif atype == "issue_conservation_order":
            zone = self.zones.get(p["zone_id"])
            if zone and zone.stability_state != StabilityState.COLLAPSED:
                zone.demand_modifier = max(0.1, zone.demand_modifier - p["reduction_pct"])
                morale_cost = p["reduction_pct"] * 30.0
                zone.morale = max(0.0, zone.morale - morale_cost)
                self._log(
                    f"  [Action] {zone.name}: conservation order applied "
                    f"(demand modifier -> {zone.demand_modifier:.2f}, "
                    f"morale -{morale_cost:.1f} -> {zone.morale:.1f})"
                )

        elif atype == "settle_worker_strike":
            zone = self.zones.get(p["zone_id"])
            if zone:
                source_id = p["source_id"]
                strike = next(
                    (c for c in self.crisis_events
                     if c.crisis_type == CrisisType.WORKER_STRIKE
                     and c.target_id == p["zone_id"]
                     and c.parameters.get("source_id") == source_id),
                    None
                )
                if strike:
                    self.crisis_events = [c for c in self.crisis_events if c is not strike]
                    for source in zone.sources:
                        if source.source_id == source_id:
                            source.output_modifier = 1.0
                            break
                    self._log(f"  [Action] {zone.name}: worker strike settled on {source_id}")
                else:
                    self._log(
                        f"  [Latency] settle_worker_strike: no active strike on "
                        f"{source_id} (may have resolved on its own)"
                    )

        elif atype == "repair_source":
            zone = self.zones.get(p["zone_id"])
            if zone:
                source_id = p["source_id"]
                for source in zone.sources:
                    if source.source_id == source_id and not source.active:
                        source.active = True
                        source.output_modifier = 1.0
                        self._log(
                            f"  [Action] {zone.name}/{source_id}: repaired and back online"
                        )
                        break
                else:
                    self._log(
                        f"  [Latency] repair_source: {source_id} already active or not found"
                    )

        elif atype == "invest_in_efficiency":
            zone = self.zones.get(p["zone_id"])
            if zone:
                for source in zone.sources:
                    if source.source_id == p["source_id"]:
                        imp = p["improvement_pct"]
                        source.low_output_rate  *= (1.0 + imp)
                        source.high_output_rate *= (1.0 + imp)
                        deg_gap = 1.0 - source.degradation_modifier
                        source.degradation_modifier = min(
                            1.0, source.degradation_modifier + deg_gap * 0.20
                        )
                        self._log(
                            f"  [Action] {zone.name}/{p['source_id']}: efficiency improved "
                            f"+{imp*100:.0f}% "
                            f"| range [{source.low_output_rate:.1f}, {source.high_output_rate:.1f}] "
                            f"| degradation restored to {source.degradation_modifier:.3f}x"
                        )
                        break

        elif atype == "request_aid":
            donor     = self.zones.get(p["donor_zone_id"])
            requester = self.zones.get(p["requesting_zone_id"])
            if donor and requester:
                available = min(p["amount"], donor.storage.stored_energy)
                if available > 0:
                    donor.storage.withdraw(available)
                    requester.storage.deposit(available)
                    donor.reputation = min(100.0, donor.reputation + 2.0)
                    self._log(
                        f"  [Aid] {donor.name} -> {requester.name}: "
                        f"emergency transfer of {available:.1f} energy (arrived)"
                    )
                else:
                    self._log(
                        f"  [Aid] {donor.name}: no energy available for aid to "
                        f"{requester.name} (situation changed)"
                    )

        elif atype == "accept_trade":
            self._execute_accepted_trade(p["offer_id"])

    def _queue_action(
        self, action_type: str, zone_name: str, params: dict, latency: int
    ):
        """
        Record a pending action for deferred application.
        Called by action methods after validation and budget deduction.
        """
        self._pending_actions.append({
            "action_id":    f"act_{uuid.uuid4().hex[:8]}",
            "action_type":  action_type,
            "zone_name":    zone_name,
            "apply_at_tick": self.tick_number + latency,
            "params":       params,
        })
        self._log(
            f"  [Queue] '{action_type}' for {zone_name} "
            f"-- effect in {latency} tick(s) (at tick {self.tick_number + latency})"
        )

    def _step_expire_trade_offers(self):
        """
        Step 18: Expire trade offers whose deadline has passed.
        Notifies both parties and marks the offer as expired.
        """
        for offer in list(self._pending_trade_offers.values()):
            if offer.status == "pending" and offer.expires_at_tick <= self.tick_number:
                offer.status = "expired"
                self._log(
                    f"  [Trade] Offer {offer.offer_id} expired "
                    f"({offer.from_zone_id} -> {offer.to_zone_id})"
                )
                # Notify both sides
                for zone_id in (offer.from_zone_id, offer.to_zone_id):
                    zone = self.zones.get(zone_id)
                    if zone:
                        zone.messages.append({
                            "from": "trade_system",
                            "type": "trade_offer_expired",
                            "offer_id": offer.offer_id,
                            "description": (
                                f"Trade offer {offer.offer_id} expired with no response."
                            ),
                            "tick": self.tick_number,
                        })

    def _step_advance_season(self):
        """
        Step 0: Advance the season calendar and apply seasonal multipliers.

        Called first so that all source.seasonal_modifier and
        zone.seasonal_demand_modifier values are correct before production
        and demand are computed this tick.
        """
        self._season_tick += 1
        if self._season_tick >= self.ticks_per_season:
            self._season_tick = 0
            idx = SEASON_ORDER.index(self.season)
            old_season = self.season
            self.season = SEASON_ORDER[(idx + 1) % 4]
            self._log(f"  [Season] {old_season.value.upper()} -> {self.season.value.upper()}")

        # Apply to all zones and sources
        demand_mult = SEASONAL_DEMAND_MODIFIERS[self.season]
        for zone in self.zones.values():
            zone.seasonal_demand_modifier = demand_mult
            for source in zone.sources:
                source.seasonal_modifier = SEASONAL_SOURCE_MODIFIERS.get(
                    source.energy_type, {}
                ).get(self.season, 1.0)

    def _step_scheduled_crises(self):
        """
        Step 1: Fire scheduled crises at their designated tick.
        Send early warnings 2 ticks before the fire tick.
        """
        still_pending = []
        for item in self._scheduled_crises:
            fire_tick = item["fire_tick"]
            crisis = item["crisis"]

            # Send warning 2 ticks before
            if item["send_warning"] and not item["warning_sent"]:
                if self.tick_number == fire_tick - 2:
                    item["warning_sent"] = True
                    prob = item["warning_probability"]
                    zone = self.zones.get(crisis.target_id)
                    if zone:
                        zone.messages.append({
                            "from": "early_warning_system",
                            "type": "early_warning",
                            "signal_type": crisis.crisis_type.value,
                            "probability": prob,
                            "ticks_until": 2,
                            "description": (
                                f"WARNING: {crisis.description} expected in ~2 ticks "
                                f"(confidence: {prob*100:.0f}%)"
                            ),
                            "tick": self.tick_number,
                        })
                        self._log(
                            f"  [Warning] Early warning -> {zone.name}: "
                            f"{crisis.crisis_type.value} ({prob*100:.0f}% confidence)"
                        )

            # Fire the crisis
            if self.tick_number >= fire_tick:
                self.inject_crisis(crisis)
            else:
                still_pending.append(item)

        self._scheduled_crises = still_pending

    def _apply_active_crises(self):
        """
        Step 2: Apply the ongoing effects of each active crisis.

        Runs before production so modifiers are in place.
        One-time setup (e.g. storing originals for restore) is guarded by
        _initialized / _originals keys in crisis.parameters.
        """
        for crisis in self.crisis_events:
            ctype = crisis.crisis_type

            # ── Original crisis types ─────────────────────────────────────

            if ctype == CrisisType.SUPPLY_DISRUPTION:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    source_id = crisis.parameters.get("source_id")
                    modifier = crisis.parameters.get("output_modifier", 0.20)
                    for source in zone.sources:
                        if source.source_id == source_id:
                            source.output_modifier = modifier

            elif ctype == CrisisType.DEMAND_SPIKE:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    zone.demand_modifier = crisis.parameters.get("demand_modifier", 2.0)

            elif ctype == CrisisType.ROUTE_ATTACK:
                route = self.trade_routes.get(crisis.target_id)
                if route:
                    damage = crisis.parameters.get("damage_per_tick", 20.0)
                    # Fortification reduces damage
                    effective_damage = damage * (1.0 - route.fortification)
                    route.route_health = max(0.0, route.route_health - effective_damage)
                    if route.is_severed:
                        self._log(
                            f"  [Route] {route.route_id} severed "
                            f"({route.source_zone_id}->{route.target_zone_id})"
                        )

            elif ctype == CrisisType.CASCADING_FAILURE:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    modifier = crisis.parameters.get("output_modifier", 0.10)
                    for source in zone.sources:
                        source.output_modifier = min(source.output_modifier, modifier)
                    # Spread to neighbours once (on first application)
                    if (crisis.parameters.get("spreading", True)
                            and not crisis.parameters.get("_spread_applied")):
                        crisis.parameters["_spread_applied"] = True
                        spread_modifier = crisis.parameters.get("spread_modifier", 0.40)
                        neighbors = self._get_neighbor_ids(crisis.target_id)
                        for nid in neighbors:
                            neighbor = self.zones.get(nid)
                            if neighbor:
                                for source in neighbor.sources:
                                    source.output_modifier = min(
                                        source.output_modifier, spread_modifier
                                    )
                                self._log(
                                    f"  [Cascade] Failure spread to {neighbor.name} "
                                    f"(output capped at {spread_modifier:.1f}x)"
                                )

            # ── Physical / environmental ──────────────────────────────────

            elif ctype == CrisisType.DROUGHT:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    modifier = crisis.parameters.get("output_modifier", 0.05)
                    for source in zone.sources:
                        if source.energy_type == EnergyType.HYDRO:
                            source.output_modifier = modifier

            elif ctype == CrisisType.HEAT_WAVE:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    zone.demand_modifier = crisis.parameters.get("demand_modifier", 1.80)
                    solar_mod = crisis.parameters.get("solar_output_modifier", 0.30)
                    for source in zone.sources:
                        if source.energy_type == EnergyType.SOLAR:
                            source.output_modifier = solar_mod

            elif ctype == CrisisType.WILDFIRE:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    source_id = crisis.parameters.get("source_id")
                    src_mod = crisis.parameters.get("output_modifier", 0.05)
                    for source in zone.sources:
                        if source.source_id == source_id:
                            source.output_modifier = src_mod
                # Also damage the associated route each tick
                route_id = crisis.parameters.get("route_id")
                if route_id:
                    route = self.trade_routes.get(route_id)
                    if route:
                        dmg = crisis.parameters.get("route_damage_per_tick", 30.0)
                        effective_dmg = dmg * (1.0 - route.fortification)
                        route.route_health = max(0.0, route.route_health - effective_dmg)

            elif ctype == CrisisType.EQUIPMENT_FAILURE:
                zone = self.zones.get(crisis.target_id)
                if zone and not crisis.parameters.get("_initialized"):
                    crisis.parameters["_initialized"] = True
                    source_id = crisis.parameters.get("source_id")
                    for source in zone.sources:
                        if source.source_id == source_id and source.active:
                            source.active = False
                            self._log(
                                f"  [Equipment] {zone.name}/{source_id}: "
                                f"equipment failure -- source offline"
                            )

            elif ctype == CrisisType.STORAGE_LEAK:
                pass    # Handled separately in _step_storage_leak()

            # ── Economic / political ──────────────────────────────────────

            elif ctype == CrisisType.ECONOMIC_RECESSION:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    if "_original_income_modifier" not in crisis.parameters:
                        crisis.parameters["_original_income_modifier"] = (
                            zone.economy.income_modifier
                        )
                    zone.economy.income_modifier = crisis.parameters.get(
                        "income_modifier", 0.15
                    )

            elif ctype == CrisisType.WORKER_STRIKE:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    source_id = crisis.parameters.get("source_id")
                    modifier = crisis.parameters.get("output_modifier", 0.10)
                    for source in zone.sources:
                        if source.source_id == source_id:
                            source.output_modifier = modifier

            elif ctype == CrisisType.POLITICAL_EMBARGO:
                route_id = crisis.parameters.get("route_id", crisis.target_id)
                self.embargoed_routes.add(route_id)
                if not crisis.parameters.get("_initialized"):
                    crisis.parameters["_initialized"] = True
                    self._log(
                        f"  [Embargo] Route {route_id} frozen "
                        f"({crisis.remaining_ticks} ticks remaining)"
                    )

            # ── Technical / systemic ──────────────────────────────────────

            elif ctype == CrisisType.CYBER_ATTACK:
                zone = self.zones.get(crisis.target_id)
                if zone:
                    zone.cyber_attacked = True
                    if not crisis.parameters.get("_initialized"):
                        crisis.parameters["_initialized"] = True
                        self._log(
                            f"  [Cyber] {zone.name}: systems compromised -- "
                            f"observations corrupted for {crisis.remaining_ticks} ticks"
                        )

            elif ctype == CrisisType.TRANSMISSION_SURGE:
                if "_originals" not in crisis.parameters:
                    # First application: store originals and apply reduction
                    originals = {}
                    reduction = crisis.parameters.get("efficiency_reduction", 0.60)
                    for route in self.trade_routes.values():
                        if (route.source_zone_id == crisis.target_id
                                or route.target_zone_id == crisis.target_id):
                            originals[route.route_id] = route.transmission_efficiency
                            route.transmission_efficiency = max(
                                0.10, route.transmission_efficiency - reduction
                            )
                    crisis.parameters["_originals"] = originals
                    self._log(
                        f"  [Surge] Transmission surge on {crisis.target_id}: "
                        f"{reduction*100:.0f}% efficiency loss on {len(originals)} routes"
                    )

            elif ctype == CrisisType.REGIONAL_BLACKOUT:
                region = crisis.parameters.get("region", crisis.target_id)
                demand_mod = crisis.parameters.get("demand_modifier", 2.50)
                for zone in self.zones.values():
                    if zone.region == region:
                        zone.demand_modifier = demand_mod
                if not crisis.parameters.get("_initialized"):
                    crisis.parameters["_initialized"] = True
                    affected = [z.name for z in self.zones.values() if z.region == region]
                    self._log(
                        f"  [Regional] Blackout across region '{region}': "
                        f"{', '.join(affected)} hit with {demand_mod:.1f}x demand"
                    )

    def _step_sample_outputs(self):
        """Step 3: Roll random output for every active energy source."""
        for zone in self.zones.values():
            if zone.stability_state == StabilityState.COLLAPSED:
                continue
            for source in zone.sources:
                if source.active:
                    sampled = source._sample_output(self.rng)
                    expected = source.expected_output
                    deviation_pct = abs(sampled - expected) / max(expected, 0.01) * 100
                    if deviation_pct > 25:
                        direction = "spike" if sampled > expected else "dip"
                        self._log(
                            f"  [Output] {zone.name}/{source.source_id}: "
                            f"output {direction} {sampled:.1f} "
                            f"(expected ~{expected:.1f}, {deviation_pct:.0f}% off)"
                        )

    def _step_energy_production(self):
        """Step 4: Each zone's active sources deposit energy into Storage."""
        for zone in self.zones.values():
            if zone.stability_state == StabilityState.COLLAPSED:
                continue
            gain = zone.energy_gain_per_tick
            stored = zone.storage.deposit(gain)
            spilled = gain - stored
            if spilled > 0.01:
                self._log(
                    f"  [Spill] {zone.name}: spilled {spilled:.1f} units "
                    f"(storage at capacity {zone.storage.capacity:.0f})"
                )

    def _step_economy(self):
        """
        Step 5: Each zone earns budget.

        Income = budget_per_tick x income_modifier (recession) x morale_factor.
        Morale below 50 reduces income: tax base shrinks, productivity drops.
        """
        for zone in self.zones.values():
            if zone.stability_state == StabilityState.COLLAPSED:
                continue
            morale_factor = max(0.50, zone.morale / 100.0)
            effective_income = (
                zone.economy.budget_per_tick
                * zone.economy.income_modifier
                * morale_factor
            )
            zone.economy.earn(effective_income)

    def _step_trade_transfer(self):
        """
        Step 6: Trade routes move energy from source to target.

        Respects:
          - export_cap: source cannot send more than the cap per tick
          - embargoed_routes: skipped entirely during embargo
          - fortification: no effect on trade; applies in crisis step
          - transmission_efficiency: applied at delivery
        """
        for route in self.trade_routes.values():
            if route.is_severed:
                continue
            if route.route_id in self.embargoed_routes:
                self._log(
                    f"  [Embargo] Route {route.route_id} skipped "
                    f"({route.source_zone_id}->{route.target_zone_id})"
                )
                continue

            source = self.zones.get(route.source_zone_id)
            target = self.zones.get(route.target_zone_id)
            if not source or not target:
                continue
            if source.stability_state == StabilityState.COLLAPSED:
                continue

            to_send = min(route.effective_transfer_rate, source.storage.stored_energy)
            if to_send <= 0:
                # Source delivered nothing this tick -> reputation penalty
                source.reputation = max(0.0, source.reputation - 1.5)
                continue

            source.storage.withdraw(to_send)
            route.in_flight.append([to_send, route.latency])

            still_flying = []
            total_sent = 0.0
            total_received = 0.0
            for packet in route.in_flight:
                sent_amount, ticks_left = packet
                ticks_left -= 1
                if ticks_left <= 0:
                    received = sent_amount * route.transmission_efficiency
                    target.storage.deposit(received)
                    total_sent += sent_amount
                    total_received += received
                else:
                    still_flying.append([sent_amount, ticks_left])
            route.in_flight = still_flying

            if total_received > 0:
                heat_loss = total_sent - total_received
                self._log(
                    f"  [Trade] {source.name}->{target.name}: "
                    f"sent {total_sent:.1f}, received {total_received:.1f}, "
                    f"loss {heat_loss:.1f} ({(1-route.transmission_efficiency)*100:.0f}%)"
                )

    def _step_demand_consumption(self):
        """Step 7: Each zone consumes energy to meet demand."""
        for zone in self.zones.values():
            if zone.stability_state == StabilityState.COLLAPSED:
                continue
            demand = zone.energy_demand_per_tick
            withdrawn = zone.storage.withdraw(demand)
            if withdrawn < demand - 0.01:
                shortfall = demand - withdrawn
                self._log(
                    f"  [Demand] {zone.name}: shortfall {shortfall:.1f} units "
                    f"(storage drained to zero)"
                )

    def _step_source_aging(self):
        """
        Step 8: Age all sources; apply degradation every 5 ticks.
        Also expire temporary emergency generators.
        """
        expired_gen_ids = []

        # Tick down temporary generators
        for gen_id in list(self._temp_sources.keys()):
            self._temp_sources[gen_id] -= 1
            if self._temp_sources[gen_id] <= 0:
                expired_gen_ids.append(gen_id)

        for gen_id in expired_gen_ids:
            del self._temp_sources[gen_id]
            for zone in self.zones.values():
                for source in zone.sources:
                    if source.source_id == gen_id:
                        zone.sources.remove(source)
                        self._log(
                            f"  [Generator] Emergency generator {gen_id} "
                            f"decommissioned in {zone.name}"
                        )
                        break

        # Age all remaining sources
        for zone in self.zones.values():
            for source in zone.sources:
                source.age += 1
                # Apply degradation every 5 ticks
                if source.age % 5 == 0:
                    old_deg = source.degradation_modifier
                    source.degradation_modifier = max(
                        source.efficiency_floor,
                        source.degradation_modifier - source.degradation_rate
                    )
                    if abs(old_deg - source.degradation_modifier) > 0.0001:
                        self._log(
                            f"  [Aging] {zone.name}/{source.source_id}: "
                            f"degradation -> {source.degradation_modifier:.3f}x "
                            f"(age {source.age})"
                        )

    def _step_storage_leak(self):
        """
        Step 9: STORAGE_LEAK crises drain stored energy each tick.

        Handled as a separate step (not in _apply_active_crises) because
        the leak is a physical drain on storage, not a modifier — it needs
        to happen after production and trade have already deposited energy.
        """
        for crisis in self.crisis_events:
            if crisis.crisis_type == CrisisType.STORAGE_LEAK:
                zone = self.zones.get(crisis.target_id)
                if zone and zone.storage.stored_energy > 0:
                    leak_rate = crisis.parameters.get("leak_rate", 0.04)
                    leaked = zone.storage.stored_energy * leak_rate
                    zone.storage.withdraw(leaked)
                    if leaked > 0.5:
                        self._log(
                            f"  [Leak] {zone.name}: storage leaking "
                            f"{leaked:.1f} units ({leak_rate*100:.0f}%/tick)"
                        )

    def _step_morale(self):
        """
        Step 10: Update morale and reputation based on stability.

        Morale:
          STABLE:    +1.5 per tick (recovery)
          WARNING:   -2.0 per tick
          CRITICAL:  compound penalty: -5 base + 0.5 per consecutive critical tick
          COLLAPSED: -10 per tick

        Reputation:
          STABLE:    +0.5 (reliable delivery track record)
          COLLAPSED: -3.0 (counterparties lose confidence)
        """
        for zone in self.zones.values():
            state = zone.stability_state
            if state == StabilityState.STABLE:
                zone.morale = min(100.0, zone.morale + 1.5)
                zone.reputation = min(100.0, zone.reputation + 0.5)
                zone._consecutive_critical_ticks = 0
            elif state == StabilityState.WARNING:
                zone.morale = max(0.0, zone.morale - 2.0)
            elif state == StabilityState.CRITICAL:
                zone._consecutive_critical_ticks += 1
                penalty = 5.0 + (zone._consecutive_critical_ticks * 0.5)
                zone.morale = max(0.0, zone.morale - penalty)
            elif state == StabilityState.COLLAPSED:
                zone.morale = max(0.0, zone.morale - 10.0)
                zone.reputation = max(0.0, zone.reputation - 3.0)

    def _step_monitoring_decay(self):
        """Step 11: Tick down monitoring subscriptions; remove expired ones."""
        for observer_id in list(self._monitored_zones.keys()):
            for target_id in list(self._monitored_zones[observer_id].keys()):
                self._monitored_zones[observer_id][target_id] -= 1
                if self._monitored_zones[observer_id][target_id] <= 0:
                    del self._monitored_zones[observer_id][target_id]
                    self._log(
                        f"  [Monitor] Monitoring expired: {observer_id} -> {target_id}"
                    )
            if not self._monitored_zones[observer_id]:
                del self._monitored_zones[observer_id]

    def _step_pending_routes(self):
        """Step 12: Advance under-construction routes; complete when ready."""
        still_pending = []
        for item in self._pending_routes:
            item["ticks_remaining"] -= 1
            if item["ticks_remaining"] <= 0:
                route = item["route"]
                if (route.source_zone_id in self.zones
                        and route.target_zone_id in self.zones):
                    self.trade_routes[route.route_id] = route
                    self._log(
                        f"  [Build] New route online: "
                        f"{route.source_zone_id}->{route.target_zone_id} "
                        f"| rate {route.transfer_rate:.1f}/tick"
                    )
            else:
                still_pending.append(item)
        self._pending_routes = still_pending

    def _step_recalculate_stability(self):
        """Step 13: Recompute stability state for every zone."""
        for zone in self.zones.values():
            trade_in = sum(
                r.effective_received_rate
                for r in self.trade_routes.values()
                if r.target_zone_id == zone.zone_id and not r.is_severed
                and r.route_id not in self.embargoed_routes
            )
            trade_out = sum(
                r.effective_transfer_rate
                for r in self.trade_routes.values()
                if r.source_zone_id == zone.zone_id and not r.is_severed
                and r.route_id not in self.embargoed_routes
            )

            expected_gain = zone.expected_energy_gain + trade_in
            loss = zone.energy_demand_per_tick + trade_out
            net = expected_gain - loss

            zone.net_energy_per_tick = net

            if net < 0 and zone.storage.stored_energy > 0:
                zone.projected_depletion_ticks = zone.storage.stored_energy / abs(net)
            else:
                zone.projected_depletion_ticks = None

            stored = zone.storage.stored_energy
            if stored <= 0:
                zone.stability_state = StabilityState.COLLAPSED
                self._log(f"  [Collapse] {zone.name} has COLLAPSED!")
            elif net >= 0 and stored > zone.low_threshold:
                zone.stability_state = StabilityState.STABLE
            elif zone.projected_depletion_ticks is not None:
                if zone.projected_depletion_ticks <= zone.critical_window:
                    zone.stability_state = StabilityState.CRITICAL
                else:
                    zone.stability_state = StabilityState.WARNING
            else:
                zone.stability_state = StabilityState.STABLE

    def _step_expire_crises(self):
        """Step 16: Decrement crisis durations, remove and reverse expired ones."""
        still_active = []
        for crisis in self.crisis_events:
            crisis.remaining_ticks -= 1
            if crisis.remaining_ticks <= 0:
                self._expire_crisis(crisis)
            else:
                still_active.append(crisis)
        self.crisis_events = still_active

    def _expire_crisis(self, crisis: CrisisEvent):
        """
        Reverse a crisis that has run its course (where reversible).

        LINGERING EFFECTS: Crises no longer fully restore to 1.0. Instead,
        output modifiers recover to 0.85 (a 15% permanent scar), demand
        modifiers settle at 1.10 (lingering panic), and morale takes a
        lasting hit. This means long or overlapping crises leave zones
        permanently weakened — recovery is never free.
        """
        LINGERING_OUTPUT_MODIFIER = 0.85      # Sources don't fully recover
        LINGERING_DEMAND_MODIFIER = 1.10      # Residual panic demand
        LINGERING_MORALE_PENALTY  = 5.0       # Flat morale loss on crisis end
        LINGERING_EFFICIENCY_LOSS = 0.05      # Permanent route efficiency scar

        self._log(f"  [Expired] Crisis ended: {crisis.description}")
        ctype = crisis.crisis_type

        # ── Reversible: restore with lingering damage ────────────────────
        if ctype == CrisisType.SUPPLY_DISRUPTION:
            zone = self.zones.get(crisis.target_id)
            if zone:
                source_id = crisis.parameters.get("source_id")
                for source in zone.sources:
                    if source.source_id == source_id:
                        source.output_modifier = LINGERING_OUTPUT_MODIFIER
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY)

        elif ctype == CrisisType.DEMAND_SPIKE:
            zone = self.zones.get(crisis.target_id)
            if zone:
                zone.demand_modifier = LINGERING_DEMAND_MODIFIER
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY)

        elif ctype == CrisisType.DROUGHT:
            zone = self.zones.get(crisis.target_id)
            if zone:
                for source in zone.sources:
                    if source.energy_type == EnergyType.HYDRO:
                        source.output_modifier = LINGERING_OUTPUT_MODIFIER
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 2)

        elif ctype == CrisisType.HEAT_WAVE:
            zone = self.zones.get(crisis.target_id)
            if zone:
                zone.demand_modifier = LINGERING_DEMAND_MODIFIER
                for source in zone.sources:
                    if source.energy_type == EnergyType.SOLAR:
                        source.output_modifier = LINGERING_OUTPUT_MODIFIER
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 2)

        elif ctype == CrisisType.WILDFIRE:
            zone = self.zones.get(crisis.target_id)
            if zone:
                source_id = crisis.parameters.get("source_id")
                for source in zone.sources:
                    if source.source_id == source_id:
                        # Wildfire leaves severe permanent damage
                        source.output_modifier = 0.60
                        source.degradation_modifier = max(
                            source.efficiency_floor,
                            source.degradation_modifier - 0.15
                        )
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 3)
            # Route health is NOT auto-restored — requires action_repair_route

        elif ctype == CrisisType.CASCADING_FAILURE:
            zone = self.zones.get(crisis.target_id)
            if zone:
                for source in zone.sources:
                    source.output_modifier = 0.70  # Severe lingering from cascade
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 3)
            if crisis.parameters.get("_spread_applied"):
                for nid in self._get_neighbor_ids(crisis.target_id):
                    neighbor = self.zones.get(nid)
                    if neighbor:
                        for source in neighbor.sources:
                            source.output_modifier = LINGERING_OUTPUT_MODIFIER
                        neighbor.morale = max(0.0, neighbor.morale - LINGERING_MORALE_PENALTY)

        elif ctype == CrisisType.WORKER_STRIKE:
            zone = self.zones.get(crisis.target_id)
            if zone:
                source_id = crisis.parameters.get("source_id")
                for source in zone.sources:
                    if source.source_id == source_id:
                        source.output_modifier = LINGERING_OUTPUT_MODIFIER
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 2)
                self._log(f"  [Strike] Worker strike resolved in {zone.name}/{source_id} (lingering effects remain)")

        elif ctype == CrisisType.POLITICAL_EMBARGO:
            route_id = crisis.parameters.get("route_id", crisis.target_id)
            self.embargoed_routes.discard(route_id)
            # Embargo leaves diplomatic damage — reputation hit on both ends
            route = self.trade_routes.get(route_id)
            if route:
                for zid in (route.source_zone_id, route.target_zone_id):
                    z = self.zones.get(zid)
                    if z:
                        z.reputation = max(0.0, z.reputation - 10.0)
            self._log(f"  [Embargo] Route {route_id} unblocked (reputation scarred)")

        elif ctype == CrisisType.CYBER_ATTACK:
            zone = self.zones.get(crisis.target_id)
            if zone:
                zone.cyber_attacked = False
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 2)
                self._log(f"  [Cyber] {zone.name}: systems restored (trust damaged)")

        elif ctype == CrisisType.TRANSMISSION_SURGE:
            originals = crisis.parameters.get("_originals", {})
            for route_id, orig_eff in originals.items():
                route = self.trade_routes.get(route_id)
                if route:
                    # Permanent efficiency scar from surge damage
                    route.transmission_efficiency = max(
                        0.10, orig_eff - LINGERING_EFFICIENCY_LOSS
                    )
            self._log(
                f"  [Surge] Transmission partially restored on "
                f"{len(originals)} routes (permanent {LINGERING_EFFICIENCY_LOSS*100:.0f}% scar)"
            )

        elif ctype == CrisisType.ECONOMIC_RECESSION:
            zone = self.zones.get(crisis.target_id)
            if zone:
                original = crisis.parameters.get("_original_income_modifier", 1.0)
                # Recession leaves lasting economic damage
                zone.economy.income_modifier = max(0.20, original - 0.20)
                zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 2)

        elif ctype == CrisisType.REGIONAL_BLACKOUT:
            region = crisis.parameters.get("region", crisis.target_id)
            for zone in self.zones.values():
                if zone.region == region:
                    zone.demand_modifier = LINGERING_DEMAND_MODIFIER
                    zone.morale = max(0.0, zone.morale - LINGERING_MORALE_PENALTY * 2)

        # EQUIPMENT_FAILURE: intentionally NOT auto-restored -- needs repair_source action
        # STORAGE_LEAK: simply stops leaking; no state to restore

    # ──────────────────────────────────────────
    # GOVERNOR AGENT ACTIONS
    # Pattern: 1) look up zone  2) check not collapsed  3) spend budget
    #          4) apply effect  5) log
    # ──────────────────────────────────────────

    def _check_and_spend(self, zone: Zone, action_name: str, cost_override: float = None) -> bool:
        cost = cost_override if cost_override is not None else ACTION_COSTS.get(action_name, 0.0)
        if not zone.economy.spend(cost):
            self._log(
                f"  [Budget] {zone.name}: insufficient for '{action_name}' "
                f"(needs {cost:.0f}, has {zone.economy.budget:.0f})"
            )
            return False
        return True

    # ── Original actions ─────────────────────────────────────────────────

    def action_ration_energy(self, zone_id: str, reduction_pct: float) -> bool:
        """
        Reduce demand by reduction_pct (0.0-1.0). Latency: 1 tick.
        Cost: {ration_energy} credits. No morale penalty (purely administrative).
        """
        zone = self.zones.get(zone_id)
        if not zone or zone.stability_state == StabilityState.COLLAPSED:
            return False
        if not self._check_and_spend(zone, "ration_energy"):
            return False
        self._queue_action("ration_energy", zone.name,
                           {"zone_id": zone_id, "reduction_pct": reduction_pct},
                           ACTION_LATENCY["ration_energy"])
        return True

    def action_boost_source(
        self, zone_id: str, source_id: str, boost_factor: float = 1.5
    ) -> bool:
        """Boost a source's output_modifier. Latency: 1 tick. Cost: {boost_source} credits. Capped at 2.0x."""
        zone = self.zones.get(zone_id)
        if not zone or zone.stability_state == StabilityState.COLLAPSED:
            return False
        # Validate source exists before spending
        if not any(s.source_id == source_id for s in zone.sources):
            self._log(f"  [Action] {zone.name}: source {source_id} not found")
            return False
        if not self._check_and_spend(zone, "boost_source"):
            return False
        self._queue_action("boost_source", zone.name,
                           {"zone_id": zone_id, "source_id": source_id, "boost_factor": boost_factor},
                           ACTION_LATENCY["boost_source"])
        return True

    def action_repair_route(self, zone_id: str, route_id: str, repair_amount: float = 20.0) -> bool:
        """
        Restore route_health on a damaged trade route. Latency: 2 ticks.
        Zone must be an endpoint. Cost: {repair_route} credits.
        """
        zone = self.zones.get(zone_id)
        route = self.trade_routes.get(route_id)
        if not zone or not route:
            return False
        if route.source_zone_id != zone_id and route.target_zone_id != zone_id:
            self._log(f"  [Action] {zone.name} cannot repair {route_id} (not an endpoint)")
            return False
        if not self._check_and_spend(zone, "repair_route"):
            return False
        self._queue_action("repair_route", zone.name,
                           {"route_id": route_id, "repair_amount": repair_amount},
                           ACTION_LATENCY["repair_route"])
        return True

    def action_open_trade_route(
        self,
        source_zone_id: str,
        target_zone_id: str,
        energy_type: EnergyType,
        transfer_rate: float,
        route_latency: int = 1,
        transmission_efficiency: float = 0.90,
    ) -> Optional[str]:
        """
        Open a new trade route. Latency: 2 ticks (setup + logistics).
        Cost: {open_trade_route} credits (+ 50% surcharge if source reputation < 50).
        Returns route_id immediately (route not yet active), None on failure.
        Use action_build_new_route for a cheaper multi-tick construction option.
        """
        source = self.zones.get(source_zone_id)
        if not source or target_zone_id not in self.zones:
            return None
        base_cost = ACTION_COSTS["open_trade_route"]
        if source.reputation < 50:
            cost = base_cost * 1.5
            self._log(
                f"  [Action] {source.name}: reputation surcharge applied "
                f"({source.reputation:.0f} rep -> {cost:.0f} credits)"
            )
        else:
            cost = base_cost
        if not self._check_and_spend(source, "open_trade_route", cost_override=cost):
            return None
        route_id = f"route_{uuid.uuid4().hex[:8]}"
        route = TradeRoute(
            route_id=route_id,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
            energy_type=energy_type,
            transfer_rate=transfer_rate,
            latency=route_latency,
            transmission_efficiency=transmission_efficiency,
        )
        self._queue_action("open_trade_route", source.name,
                           {"route": route},
                           ACTION_LATENCY["open_trade_route"])
        return route_id

    def action_close_trade_route(self, zone_id: str, route_id: str) -> bool:
        """Close an existing trade route. Latency: 1 tick. Cost: {close_trade_route} credits."""
        zone = self.zones.get(zone_id)
        if not zone or route_id not in self.trade_routes:
            return False
        if not self._check_and_spend(zone, "close_trade_route"):
            return False
        self._queue_action("close_trade_route", zone.name,
                           {"route_id": route_id},
                           ACTION_LATENCY["close_trade_route"])
        return True

    def action_emergency_broadcast(self, zone_id: str, message: str) -> bool:
        """Broadcast a message to all neighboring zones. FREE. Immediate (latency: 0)."""
        zone = self.zones.get(zone_id)
        if not zone:
            return False
        self._check_and_spend(zone, "emergency_broadcast")
        neighbors = set()
        for route in self.trade_routes.values():
            if route.source_zone_id == zone_id:
                neighbors.add(route.target_zone_id)
            elif route.target_zone_id == zone_id:
                neighbors.add(route.source_zone_id)
        for neighbor_id in neighbors:
            neighbor = self.zones.get(neighbor_id)
            if neighbor:
                neighbor.messages.append({
                    "from": zone_id,
                    "type": "broadcast",
                    "message": message,
                    "tick": self.tick_number,
                })
        self._log(
            f"  [Action] {zone.name} broadcast to {len(neighbors)} neighbors: '{message}'"
        )
        return True

    def action_upgrade_storage(self, zone_id: str, additional_capacity: float) -> bool:
        """Expand a zone's storage capacity. Latency: 3 ticks. Cost: {upgrade_storage} credits."""
        zone = self.zones.get(zone_id)
        if not zone or zone.stability_state == StabilityState.COLLAPSED:
            return False
        if not self._check_and_spend(zone, "upgrade_storage"):
            return False
        self._queue_action("upgrade_storage", zone.name,
                           {"zone_id": zone_id, "additional_capacity": additional_capacity},
                           ACTION_LATENCY["upgrade_storage"])
        return True

    # ── New actions ───────────────────────────────────────────────────────

    def action_fortify_route(self, zone_id: str, route_id: str) -> bool:
        """
        Harden a trade route against attack damage. Latency: 2 ticks.
        Increases route.fortification by 0.30 (capped at 1.0).
        Cost: {fortify_route} credits. Zone must be an endpoint.
        """
        zone = self.zones.get(zone_id)
        route = self.trade_routes.get(route_id)
        if not zone or not route:
            return False
        if route.source_zone_id != zone_id and route.target_zone_id != zone_id:
            self._log(f"  [Action] {zone.name} cannot fortify {route_id} (not an endpoint)")
            return False
        if not self._check_and_spend(zone, "fortify_route"):
            return False
        self._queue_action("fortify_route", zone.name,
                           {"route_id": route_id},
                           ACTION_LATENCY["fortify_route"])
        return True

    def action_sell_surplus(
        self, zone_id: str, amount: float, rate: float = 0.50
    ) -> bool:
        """
        DISABLED: Energy-to-cash conversion is no longer permitted.
        Zones cannot sell energy for budget credits. Energy can only be
        traded between zones via trade offers (energy-for-energy only).
        """
        zone = self.zones.get(zone_id)
        zone_name = zone.name if zone else zone_id
        self._log(
            f"  [Action] {zone_name}: sell_surplus BLOCKED — "
            f"energy-cash conversion is disabled. Use inter-zone energy trades instead."
        )
        return False

    def action_build_new_route(
        self,
        source_zone_id: str,
        target_zone_id: str,
        energy_type: EnergyType,
        transfer_rate: float,
        construction_ticks: int = 4,
        transmission_efficiency: float = 0.90,
    ) -> Optional[str]:
        """
        Begin construction of a new trade route that comes online after
        construction_ticks. Cheaper than action_open_trade_route.
        Cost: {build_new_route} credits charged immediately.
        Returns route_id on success (route not yet active), None on failure.
        """
        source = self.zones.get(source_zone_id)
        if not source or target_zone_id not in self.zones:
            return None
        if not self._check_and_spend(source, "build_new_route"):
            return None
        route_id = f"route_{uuid.uuid4().hex[:8]}"
        route = TradeRoute(
            route_id=route_id,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
            energy_type=energy_type,
            transfer_rate=transfer_rate,
            transmission_efficiency=transmission_efficiency,
        )
        self._pending_routes.append({
            "route": route,
            "ticks_remaining": construction_ticks,
        })
        self._log(
            f"  [Action] Route construction started: "
            f"{source_zone_id}->{target_zone_id} "
            f"| rate {transfer_rate:.1f}/tick "
            f"| completes in {construction_ticks} ticks"
        )
        return route_id

    def action_invest_in_efficiency(
        self, zone_id: str, source_id: str, improvement_pct: float = 0.10
    ) -> bool:
        """
        Permanently improve a source's output range by improvement_pct. Latency: 2 ticks.
        Also resets 20% of accumulated degradation (maintenance overhaul effect).
        Cost: {invest_in_efficiency} credits.
        """
        zone = self.zones.get(zone_id)
        if not zone or zone.stability_state == StabilityState.COLLAPSED:
            return False
        if not any(s.source_id == source_id for s in zone.sources):
            self._log(f"  [Action] {zone.name}: source {source_id} not found")
            return False
        if not self._check_and_spend(zone, "invest_in_efficiency"):
            return False
        self._queue_action("invest_in_efficiency", zone.name,
                           {"zone_id": zone_id, "source_id": source_id,
                            "improvement_pct": improvement_pct},
                           ACTION_LATENCY["invest_in_efficiency"])
        return True

    def action_set_export_cap(
        self, zone_id: str, route_id: str, max_rate: Optional[float]
    ) -> bool:
        """
        Set or remove an export cap on a trade route. Immediate (latency: 0).
        max_rate=None removes the cap. Zone must be the source endpoint.
        Cost: {set_export_cap} credits.
        """
        zone = self.zones.get(zone_id)
        route = self.trade_routes.get(route_id)
        if not zone or not route:
            return False
        if route.source_zone_id != zone_id:
            self._log(
                f"  [Action] {zone.name}: cannot set export cap -- "
                f"not the source of {route_id}"
            )
            return False
        if not self._check_and_spend(zone, "set_export_cap"):
            return False
        route.export_cap = max_rate
        if max_rate is None:
            self._log(f"  [Action] {zone.name}: export cap removed on {route_id}")
        else:
            self._log(
                f"  [Action] {zone.name}: export cap set to {max_rate:.1f}/tick "
                f"on {route_id}"
            )
        return True

    def action_deploy_emergency_generator(
        self, zone_id: str, output_rate: float = 30.0, duration: int = 4
    ) -> bool:
        """
        Deploy a temporary fossil-fuel backup generator for duration ticks. Latency: 1 tick.
        Only usable when the zone is in WARNING or CRITICAL state.
        Cost: {deploy_emergency_generator} credits.
        """
        zone = self.zones.get(zone_id)
        if not zone or zone.stability_state == StabilityState.COLLAPSED:
            return False
        if zone.stability_state == StabilityState.STABLE:
            self._log(
                f"  [Action] {zone.name}: emergency generator requires "
                f"WARNING or CRITICAL state"
            )
            return False
        if not self._check_and_spend(zone, "deploy_emergency_generator"):
            return False
        gen_id = f"emgen_{uuid.uuid4().hex[:6]}"
        self._queue_action("deploy_emergency_generator", zone.name,
                           {"zone_id": zone_id, "gen_id": gen_id,
                            "output_rate": output_rate, "duration": duration},
                           ACTION_LATENCY["deploy_emergency_generator"])
        return True

    def action_request_aid(
        self, requesting_zone_id: str, donor_zone_id: str, amount: float
    ) -> bool:
        """
        Request emergency energy transfer from a donor zone (a gift, not a trade).
        Latency: 1 tick (transit time). The engine approves if the donor is STABLE
        and has the requested energy at queue time. Resources arrive 1 tick later.
        No budget cost; donor pays only energy.
        """
        requester = self.zones.get(requesting_zone_id)
        donor = self.zones.get(donor_zone_id)
        if not requester or not donor:
            return False
        if donor.stability_state != StabilityState.STABLE:
            self._log(f"  [Aid] {donor.name} cannot provide aid -- not STABLE")
            return False
        if donor.storage.stored_energy < amount:
            self._log(
                f"  [Aid] {donor.name}: insufficient energy for aid "
                f"(requested {amount:.0f}, available {donor.storage.stored_energy:.0f})"
            )
            return False
        self._log(f"  [Aid] {donor.name} -> {requester.name}: aid of {amount:.1f} energy in transit")
        self._queue_action("request_aid", donor.name,
                           {"requesting_zone_id": requesting_zone_id,
                            "donor_zone_id": donor_zone_id, "amount": amount},
                           ACTION_LATENCY["request_aid"])
        return True

    def action_issue_conservation_order(
        self, zone_id: str, reduction_pct: float
    ) -> bool:
        """
        Issue a mandatory conservation order. Latency: 1 tick (policy announcement).
        Demand falls by reduction_pct; public morale also falls.
        Morale cost = reduction_pct * 30.
        Cost: {issue_conservation_order} credits.
        """
        zone = self.zones.get(zone_id)
        if not zone or zone.stability_state == StabilityState.COLLAPSED:
            return False
        if not self._check_and_spend(zone, "issue_conservation_order"):
            return False
        self._queue_action("issue_conservation_order", zone.name,
                           {"zone_id": zone_id, "reduction_pct": reduction_pct},
                           ACTION_LATENCY["issue_conservation_order"])
        return True

    def action_settle_worker_strike(self, zone_id: str, source_id: str) -> bool:
        """
        Negotiate an end to an active WORKER_STRIKE crisis. Latency: 1 tick.
        Cost: {settle_worker_strike} credits.
        """
        zone = self.zones.get(zone_id)
        if not zone:
            return False
        # Verify there is a strike to settle before spending
        strike = next(
            (c for c in self.crisis_events
             if c.crisis_type == CrisisType.WORKER_STRIKE
             and c.target_id == zone_id
             and c.parameters.get("source_id") == source_id),
            None
        )
        if not strike:
            self._log(f"  [Action] {zone.name}: no active worker strike on {source_id}")
            return False
        if not self._check_and_spend(zone, "settle_worker_strike"):
            return False
        self._queue_action("settle_worker_strike", zone.name,
                           {"zone_id": zone_id, "source_id": source_id},
                           ACTION_LATENCY["settle_worker_strike"])
        return True

    def action_repair_source(self, zone_id: str, source_id: str) -> bool:
        """
        Restore an offline EnergySource to active=True. Latency: 2 ticks.
        Does NOT work on sources with an active WORKER_STRIKE.
        Cost: {repair_source} credits.
        """
        zone = self.zones.get(zone_id)
        if not zone:
            return False
        has_strike = any(
            c.crisis_type == CrisisType.WORKER_STRIKE
            and c.target_id == zone_id
            and c.parameters.get("source_id") == source_id
            for c in self.crisis_events
        )
        if has_strike:
            self._log(
                f"  [Action] {zone.name}/{source_id}: cannot repair "
                f"-- active worker strike (use settle_worker_strike)"
            )
            return False
        # Verify source exists and is offline
        target_source = next(
            (s for s in zone.sources if s.source_id == source_id and not s.active), None
        )
        if not target_source:
            self._log(f"  [Action] {zone.name}: {source_id} not found or already active")
            return False
        if not self._check_and_spend(zone, "repair_source"):
            return False
        self._queue_action("repair_source", zone.name,
                           {"zone_id": zone_id, "source_id": source_id},
                           ACTION_LATENCY["repair_source"])
        return True

    def action_monitor_zone(
        self, observer_zone_id: str, target_zone_id: str, duration: int = 5
    ) -> bool:
        """
        Purchase full observability of a target zone for duration ticks.
        Immediate (latency: 0). Cost: {monitor_zone} credits.
        """
        observer = self.zones.get(observer_zone_id)
        if not observer or target_zone_id not in self.zones:
            return False
        if not self._check_and_spend(observer, "monitor_zone"):
            return False
        if observer_zone_id not in self._monitored_zones:
            self._monitored_zones[observer_zone_id] = {}
        self._monitored_zones[observer_zone_id][target_zone_id] = duration
        self._log(
            f"  [Action] {observer.name}: monitoring {target_zone_id} "
            f"for {duration} ticks"
        )
        return True

    # ── Trade offer actions ───────────────────────────────────────────────

    def action_propose_trade(
        self,
        from_zone_id: str,
        to_zone_id: str,
        energy_offered: float = 0.0,
        budget_offered: float = 0.0,
        energy_requested: float = 0.0,
        budget_requested: float = 0.0,
        expires_in_ticks: int = 3,
        description: str = "",
    ) -> Optional[str]:
        """
        Propose a bilateral trade deal to another zone. Immediate delivery (latency: 0).
        The offer specifies what the initiating zone will GIVE and what it WANTS in return.
        Resources are NOT committed until the target zone calls action_accept_trade().

        Parameters:
            energy_offered    -- units of energy from_zone gives to to_zone
            budget_offered    -- credits from_zone gives to to_zone
            energy_requested  -- units of energy from_zone wants from to_zone
            budget_requested  -- credits from_zone wants from to_zone

        Cost: {propose_trade} credits (admin/diplomatic fee).
        Returns offer_id on success, None on failure.
        """
        from_zone = self.zones.get(from_zone_id)
        to_zone   = self.zones.get(to_zone_id)
        if not from_zone or not to_zone:
            return None
        if from_zone.stability_state == StabilityState.COLLAPSED:
            self._log(f"  [Trade] {from_zone.name}: cannot propose trade -- collapsed")
            return None
        if not self._check_and_spend(from_zone, "propose_trade"):
            return None

        offer_id = f"offer_{uuid.uuid4().hex[:8]}"
        desc = description or (
            f"{from_zone.name} offers {energy_offered:.0f}E + {budget_offered:.0f}B "
            f"for {energy_requested:.0f}E + {budget_requested:.0f}B from {to_zone.name}"
        )
        offer = TradeOffer(
            offer_id=offer_id,
            from_zone_id=from_zone_id,
            to_zone_id=to_zone_id,
            energy_offered=energy_offered,
            budget_offered=budget_offered,
            energy_requested=energy_requested,
            budget_requested=budget_requested,
            expires_at_tick=self.tick_number + expires_in_ticks,
            description=desc,
        )
        self._pending_trade_offers[offer_id] = offer

        # Deliver as a message to the target zone so its governor can act on it
        to_zone.messages.append({
            "from": from_zone_id,
            "type": "trade_offer",
            "offer_id": offer_id,
            "energy_offered": energy_offered,
            "budget_offered": budget_offered,
            "energy_requested": energy_requested,
            "budget_requested": budget_requested,
            "expires_at_tick": offer.expires_at_tick,
            "description": desc,
            "tick": self.tick_number,
        })

        self._log(
            f"  [Trade] Offer {offer_id}: {from_zone.name} -> {to_zone.name} | "
            f"gives [{energy_offered:.0f}E, {budget_offered:.0f}B] | "
            f"wants [{energy_requested:.0f}E, {budget_requested:.0f}B] | "
            f"expires tick {offer.expires_at_tick}"
        )
        return offer_id

    def action_accept_trade(self, zone_id: str, offer_id: str) -> bool:
        """
        Accept a pending trade offer addressed to this zone. Latency: 1 tick (settlement).
        Both parties must have sufficient resources at settlement time.
        The offer's status is set to "accepted" immediately; actual resource
        transfer happens 1 tick later via the pending-action queue.
        Cost: FREE.
        """
        zone  = self.zones.get(zone_id)
        offer = self._pending_trade_offers.get(offer_id)
        if not zone or not offer:
            self._log(f"  [Trade] accept_trade: offer {offer_id} not found")
            return False
        if offer.to_zone_id != zone_id:
            self._log(
                f"  [Trade] {zone.name}: offer {offer_id} is not addressed to this zone"
            )
            return False
        if offer.status != "pending":
            self._log(
                f"  [Trade] {zone.name}: offer {offer_id} is no longer pending "
                f"(status: {offer.status})"
            )
            return False
        if offer.expires_at_tick <= self.tick_number:
            offer.status = "expired"
            self._log(f"  [Trade] {zone.name}: offer {offer_id} has expired")
            return False

        offer.status = "accepted"
        self._log(
            f"  [Trade] {zone.name} accepted offer {offer_id} -- "
            f"settlement queued for tick {self.tick_number + ACTION_LATENCY['accept_trade']}"
        )
        self._queue_action("accept_trade", zone.name,
                           {"offer_id": offer_id},
                           ACTION_LATENCY["accept_trade"])
        return True

    def action_reject_trade(self, zone_id: str, offer_id: str) -> bool:
        """
        Reject a pending trade offer addressed to this zone. Immediate. FREE.
        The initiating zone receives a rejection notification in its messages.
        """
        zone  = self.zones.get(zone_id)
        offer = self._pending_trade_offers.get(offer_id)
        if not zone or not offer:
            self._log(f"  [Trade] reject_trade: offer {offer_id} not found")
            return False
        if offer.to_zone_id != zone_id:
            self._log(
                f"  [Trade] {zone.name}: offer {offer_id} is not addressed to this zone"
            )
            return False
        if offer.status != "pending":
            self._log(
                f"  [Trade] {zone.name}: offer {offer_id} is no longer pending "
                f"(status: {offer.status})"
            )
            return False

        offer.status = "rejected"
        self._log(f"  [Trade] {zone.name} rejected offer {offer_id}")

        # Notify the initiating zone
        from_zone = self.zones.get(offer.from_zone_id)
        if from_zone:
            from_zone.messages.append({
                "from": "trade_system",
                "type": "trade_offer_rejected",
                "offer_id": offer_id,
                "rejected_by": zone_id,
                "description": f"Trade offer {offer_id} was rejected by {zone.name}.",
                "tick": self.tick_number,
            })
        return True

    def _execute_accepted_trade(self, offer_id: str):
        """
        Internal: settle an accepted trade offer (called from _apply_pending_action).
        Validates both parties still have sufficient resources; transfers atomically.
        ENERGY-ONLY: Budget components are ignored (forced to 0).
        """
        offer = self._pending_trade_offers.get(offer_id)
        if not offer or offer.status != "accepted":
            self._log(f"  [Trade] Settlement: offer {offer_id} not in accepted state — skipped")
            return

        from_zone = self.zones.get(offer.from_zone_id)
        to_zone   = self.zones.get(offer.to_zone_id)
        if not from_zone or not to_zone:
            self._log(f"  [Trade] Settlement: zone(s) for offer {offer_id} no longer exist")
            return

        # Validate both sides can honour the deal
        failures = []
        if from_zone.storage.stored_energy < offer.energy_offered:
            failures.append(
                f"{from_zone.name} lacks energy "
                f"(needs {offer.energy_offered:.0f}, has {from_zone.storage.stored_energy:.0f})"
            )
        if from_zone.economy.budget < offer.budget_offered:
            failures.append(
                f"{from_zone.name} lacks budget "
                f"(needs {offer.budget_offered:.0f}, has {from_zone.economy.budget:.0f})"
            )
        if to_zone.storage.stored_energy < offer.energy_requested:
            failures.append(
                f"{to_zone.name} lacks energy "
                f"(needs {offer.energy_requested:.0f}, has {to_zone.storage.stored_energy:.0f})"
            )
        if to_zone.economy.budget < offer.budget_requested:
            failures.append(
                f"{to_zone.name} lacks budget "
                f"(needs {offer.budget_requested:.0f}, has {to_zone.economy.budget:.0f})"
            )

        if failures:
            self._log(
                f"  [Trade] Settlement failed for offer {offer_id}: "
                + "; ".join(failures)
            )
            offer.status = "expired"
            # Notify both parties
            msg = {
                "from": "trade_system",
                "type": "trade_settlement_failed",
                "offer_id": offer_id,
                "reasons": failures,
                "description": f"Trade {offer_id} could not settle: " + "; ".join(failures),
                "tick": self.tick_number,
            }
            from_zone.messages.append(msg)
            to_zone.messages.append(msg)
            return

        # Execute atomically
        from_zone.storage.withdraw(offer.energy_offered)
        from_zone.economy.spend(offer.budget_offered)
        to_zone.storage.deposit(offer.energy_offered)
        to_zone.economy.budget += offer.budget_offered
        to_zone.economy.total_earned += offer.budget_offered

        to_zone.storage.withdraw(offer.energy_requested)
        to_zone.economy.spend(offer.budget_requested)
        from_zone.storage.deposit(offer.energy_requested)
        from_zone.economy.budget += offer.budget_requested
        from_zone.economy.total_earned += offer.budget_requested

        # Reputation boost for successful bilateral deal
        from_zone.reputation = min(100.0, from_zone.reputation + 1.0)
        to_zone.reputation   = min(100.0, to_zone.reputation   + 1.0)

        self._log(
            f"  [Trade] Settled offer {offer_id}: "
            f"{from_zone.name} gave [{offer.energy_offered:.0f}E, {offer.budget_offered:.0f}B] | "
            f"{to_zone.name} gave [{offer.energy_requested:.0f}E, {offer.budget_requested:.0f}B]"
        )

        # Success notifications
        for z, partner in ((from_zone, to_zone.name), (to_zone, from_zone.name)):
            z.messages.append({
                "from": "trade_system",
                "type": "trade_settled",
                "offer_id": offer_id,
                "partner": partner,
                "description": f"Trade {offer_id} with {partner} settled successfully.",
                "tick": self.tick_number,
            })

    # ──────────────────────────────────────────
    # OBSERVABILITY
    # ──────────────────────────────────────────

    def get_zone_state(
        self, zone_id: str, observer_zone_id: Optional[str] = None
    ) -> dict:
        """
        Return a structured snapshot of a zone's state.

        Visibility levels:
          full    — observer is the zone itself, or has an active monitor_zone
          partial — observer has an active trade route with the zone
          minimal — no connection; only name + stability visible

        If the zone is cyber_attacked, numeric values in full/partial views
        are corrupted with noise (+/-30%), simulating compromised instruments.
        The zone's own governor is also affected (cannot trust its readings).
        """
        zone = self.zones.get(zone_id)
        if not zone:
            return {}

        # Determine visibility
        if observer_zone_id is None or observer_zone_id == zone_id:
            visibility = "full"
        else:
            is_monitoring = (
                observer_zone_id in self._monitored_zones
                and zone_id in self._monitored_zones[observer_zone_id]
            )
            is_connected = any(
                (r.source_zone_id == observer_zone_id and r.target_zone_id == zone_id)
                or (r.target_zone_id == observer_zone_id and r.source_zone_id == zone_id)
                for r in self.trade_routes.values()
            )
            if is_monitoring:
                visibility = "full"
            elif is_connected:
                visibility = "partial"
            else:
                visibility = "minimal"

        # Minimal: only public-facing info
        if visibility == "minimal":
            return {
                "zone_id": zone.zone_id,
                "name": zone.name,
                "stability_state": zone.stability_state.value,
                "visibility": "minimal",
            }

        # Noise function for cyber-attacked zones
        def n(value: float) -> float:
            if zone.cyber_attacked:
                noise = self.rng.uniform(-0.30, 0.30) * abs(value)
                return round(value + noise, 2)
            return round(value, 2)

        base = {
            "zone_id": zone.zone_id,
            "name": zone.name,
            "stability_state": zone.stability_state.value,
            "stored_energy": n(zone.storage.stored_energy),
            "storage_capacity": zone.storage.capacity,
            "storage_fill_pct": n(zone.storage.fill_pct),
            "net_energy_per_tick": n(zone.net_energy_per_tick),
            "projected_depletion_ticks": (
                round(zone.projected_depletion_ticks, 1)
                if zone.projected_depletion_ticks is not None else None
            ),
            "budget": round(zone.economy.budget, 1),
            "morale": round(zone.morale, 1),
            "reputation": round(zone.reputation, 1),
            "region": zone.region,
            "season": self.season.value,
            "visibility": visibility,
        }

        if visibility == "partial":
            return base

        # Full visibility — add all details
        base.update({
            "total_spilled": round(zone.storage.total_spilled, 2),
            "energy_gain_this_tick": n(zone.energy_gain_per_tick),
            "expected_energy_gain": n(zone.expected_energy_gain),
            "energy_demand_per_tick": n(zone.energy_demand_per_tick),
            "budget_per_tick": zone.economy.budget_per_tick,
            "income_modifier": zone.economy.income_modifier,
            "total_spent": round(zone.economy.total_spent, 1),
            "cyber_attacked": zone.cyber_attacked,
            "active_sources": [
                {
                    "source_id": s.source_id,
                    "type": s.energy_type.value,
                    "low_rate": s.low_output_rate,
                    "high_rate": s.high_output_rate,
                    "expected_output": n(s.expected_output),
                    "actual_output_this_tick": n(s.current_output),
                    "output_modifier": s.output_modifier,
                    "degradation_modifier": round(s.degradation_modifier, 3),
                    "seasonal_modifier": s.seasonal_modifier,
                    "age": s.age,
                    "active": s.active,
                }
                for s in zone.sources
            ],
            "trade_routes": [
                {
                    "route_id": r.route_id,
                    "direction": "outgoing" if r.source_zone_id == zone_id else "incoming",
                    "partner": r.target_zone_id if r.source_zone_id == zone_id else r.source_zone_id,
                    "transfer_rate_sent": round(r.effective_transfer_rate, 2),
                    "transfer_rate_received": round(r.effective_received_rate, 2),
                    "heat_loss_per_tick": round(r.heat_loss_rate, 2),
                    "transmission_efficiency": r.transmission_efficiency,
                    "route_health": r.route_health,
                    "fortification": r.fortification,
                    "export_cap": r.export_cap,
                    "embargoed": r.route_id in self.embargoed_routes,
                    "latency": r.latency,
                }
                for r in self.trade_routes.values()
                if r.source_zone_id == zone_id or r.target_zone_id == zone_id
            ],
            "messages": zone.messages,
            "active_crises": [
                {
                    "crisis_id": c.crisis_id,
                    "type": c.crisis_type.value,
                    "ticks_remaining": c.remaining_ticks,
                    "description": c.description,
                }
                for c in self.crisis_events
                if c.target_id == zone_id
            ],
            # Pending (deferred) actions queued by this zone
            "pending_actions": [
                {
                    "action_id":    a["action_id"],
                    "action_type":  a["action_type"],
                    "apply_at_tick": a["apply_at_tick"],
                    "ticks_until":  max(0, a["apply_at_tick"] - self.tick_number),
                }
                for a in self._pending_actions
                if a.get("zone_name") == zone.name
            ],
            # Incoming trade offers waiting for a response from this zone
            "incoming_trade_offers": [
                {
                    "offer_id":         o.offer_id,
                    "from_zone_id":     o.from_zone_id,
                    "energy_offered":   o.energy_offered,
                    "budget_offered":   o.budget_offered,
                    "energy_requested": o.energy_requested,
                    "budget_requested": o.budget_requested,
                    "expires_at_tick":  o.expires_at_tick,
                    "description":      o.description,
                }
                for o in self._pending_trade_offers.values()
                if o.to_zone_id == zone_id and o.status == "pending"
            ],
            # Outgoing trade offers this zone has sent that are still open
            "outgoing_trade_offers": [
                {
                    "offer_id":         o.offer_id,
                    "to_zone_id":       o.to_zone_id,
                    "energy_offered":   o.energy_offered,
                    "budget_offered":   o.budget_offered,
                    "energy_requested": o.energy_requested,
                    "budget_requested": o.budget_requested,
                    "expires_at_tick":  o.expires_at_tick,
                    "status":           o.status,
                }
                for o in self._pending_trade_offers.values()
                if o.from_zone_id == zone_id
            ],
        })
        return base

    def print_status(self):
        """Print a human-readable summary of all zones and active routes."""
        print(f"\n{'─'*80}")
        print(
            f"  Tick {self.tick_number:>3} | "
            f"Season: {self.season.value.upper():<6} | "
            f"Crises active: {len(self.crisis_events)} | "
            f"Routes: {len(self.trade_routes)}"
        )
        print(f"{'─'*80}")
        icons = {
            StabilityState.STABLE: "[OK]",
            StabilityState.WARNING: "[!!]",
            StabilityState.CRITICAL: "[CRIT]",
            StabilityState.COLLAPSED: "[DEAD]",
        }
        for zone in self.zones.values():
            icon = icons[zone.stability_state]
            dep = (
                f"{zone.projected_depletion_ticks:.1f}t"
                if zone.projected_depletion_ticks is not None else "inf"
            )
            cyber = " [CYBER]" if zone.cyber_attacked else ""
            print(
                f"  {icon:<7} {zone.name:<10} | "
                f"store: {zone.storage.stored_energy:6.1f}/{zone.storage.capacity:.0f} "
                f"({zone.storage.fill_pct:.0f}%) | "
                f"net: {zone.net_energy_per_tick:+6.1f}/t | "
                f"depl: {dep:>6} | "
                f"budget: {zone.economy.budget:6.1f} | "
                f"morale: {zone.morale:5.1f} | "
                f"rep: {zone.reputation:5.1f} | "
                f"{zone.stability_state.value}{cyber}"
            )
        # Active crises summary
        if self.crisis_events:
            print(f"\n  Active crises:")
            for c in self.crisis_events:
                print(
                    f"    {c.crisis_type.value:<22} -> {c.target_id:<20} "
                    f"({c.remaining_ticks}t left) {c.description}"
                )
        # Embargoed routes
        if self.embargoed_routes:
            print(f"  Embargoed routes: {', '.join(self.embargoed_routes)}")

        # Pending (deferred) actions
        if self._pending_actions:
            print(f"\n  Pending actions ({len(self._pending_actions)}):")
            for a in sorted(self._pending_actions, key=lambda x: x["apply_at_tick"]):
                ticks_left = max(0, a["apply_at_tick"] - self.tick_number)
                print(
                    f"    {a['action_type']:<30} | zone: {a['zone_name']:<10} "
                    f"| applies in {ticks_left}t (tick {a['apply_at_tick']})"
                )

        # Pending trade offers
        pending_offers = [
            o for o in self._pending_trade_offers.values()
            if o.status == "pending"
        ]
        if pending_offers:
            print(f"\n  Pending trade offers ({len(pending_offers)}):")
            for o in pending_offers:
                print(
                    f"    {o.offer_id} | {o.from_zone_id} -> {o.to_zone_id} | "
                    f"gives [{o.energy_offered:.0f}E, {o.budget_offered:.0f}B] "
                    f"wants [{o.energy_requested:.0f}E, {o.budget_requested:.0f}B] "
                    f"| expires tick {o.expires_at_tick}"
                )
        print()

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _get_neighbor_ids(self, zone_id: str) -> set:
        """Return zone IDs connected to zone_id via any trade route."""
        neighbors = set()
        for route in self.trade_routes.values():
            if route.source_zone_id == zone_id:
                neighbors.add(route.target_zone_id)
            elif route.target_zone_id == zone_id:
                neighbors.add(route.source_zone_id)
        return neighbors

    def _log(self, message: str):
        entry = {"tick": self.tick_number, "message": message}
        self.event_log.append(entry)
        logger.debug(message)
