from dataclasses import dataclass, field 
from enum import Enum 
from typing import Optional 

class EnergyType(Enum):
    """ 
    Types of energy sources.
    """

    SOLAR = "solar"
    HYDRO = "hydro"
    WIND = "wind"
    FOSSIL = "fossil"
    NUCLEAR = "nuclear"

class StabilityState(Enum):
    """ 
    Stability rates. 
    """

    STABLE = "stable"
    WARNING = "warning"
    CRITICAL = "critical"
    COLLAPSED = "collapsed"

class CrisisType(Enum):
    SUPPLY_DISRUPTION   = "supply_disruption"    # Reduces a source's output modifier
    DEMAND_SPIKE        = "demand_spike"         # Raises zone demand modifier
    ROUTE_ATTACK        = "route_attack"         # Damages route health per tick
    CASCADING_FAILURE   = "cascading_failure"    # Zone-wide output collapse + spread
    DROUGHT             = "drought"              # All hydro sources cut to low output
    HEAT_WAVE           = "heat_wave"            # Higher demand + solar panels overheat
    WILDFIRE            = "wildfire"             # Burns a source AND a nearby route
    EQUIPMENT_FAILURE   = "equipment_failure"    # Source goes offline; needs manual repair
    STORAGE_LEAK        = "storage_leak"         # Stored energy bleeds per tick
    ECONOMIC_RECESSION  = "economic_recession"   # Reduces budget income
    WORKER_STRIKE       = "worker_strike"        # Reduces source output; needs settlement
    POLITICAL_EMBARGO   = "political_embargo"    # Freezes a trade route for N ticks
    CYBER_ATTACK        = "cyber_attack"         # Corrupts zone observation data
    TRANSMISSION_SURGE  = "transmission_surge"   # All routes in/out lose efficiency
    REGIONAL_BLACKOUT   = "regional_blackout"    # Demand spike across an entire region

class Season(Enum):
    """
    The four seasons. The engine advances the season every N ticks. 
    solar peeks in summer
    hydro in spring
    demand peak in winter

    """
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

@dataclass
class Storage:
    """
    A zone's energy storage tank.
 
    deposit(amount) -> returns how much was actually stored; overflow -> total_spilled.
    withdraw(amount) -> returns how much was actually withdrawn (capped at stored).
    """
    capacity: float
    stored_energy: float = 0.0
    total_spilled: float = 0.0
 
    def deposit(self, amount: float) -> float:
        if amount <= 0:
            return 0.0
        space = self.capacity - self.stored_energy
        stored = min(amount, space)
        self.stored_energy += stored
        self.total_spilled += (amount - stored)
        return stored
 
    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            return 0.0
        withdrawn = min(amount, self.stored_energy)
        self.stored_energy -= withdrawn
        return withdrawn
 
    @property
    def fill_pct(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return (self.stored_energy / self.capacity) * 100.0
    
@dataclass
class Economy:
    """
    A zone's economic system.
    """
    budget_per_tick: float = 100.0
    budget: float = 0.0
    total_earned: float = 0.0
    total_spent: float = 0.0
    income_modifier: float = 1.0    # Reduced by ECONOMIC_RECESSION crises
 
    def earn(self, amount: float):
        """Credit the zone's account. Called by the engine each tick."""
        self.budget += amount
        self.total_earned += amount
 
    def spend(self, amount: float) -> bool:
        """Attempt to spend credits. Returns True if successful."""
        if self.budget >= amount:
            self.budget -= amount
            self.total_spent += amount
            return True
        return False
    
@dataclass
class EnergySource:
    """
    A single energy-producing asset inside a zone.
 
    Output model:
        current_output = _sampled_output
                         x output_modifier       (crises / boosts)
                         x degradation_modifier  (aging)
                         x seasonal_modifier     (season + energy type)
 
    Aging:
        age increments each tick. Every 5 ticks the engine reduces
        degradation_modifier by degradation_rate (floors at efficiency_floor).
        Use action_invest_in_efficiency to permanently raise output rates and
        partially reset degradation.
 
    Temporary sources (emergency generators):
        The engine tracks these in _temp_sources and removes them after their
        duration expires. They age normally but degradation_rate is typically 0.
    """
    source_id: str
    energy_type: EnergyType
    low_output_rate: float
    high_output_rate: float
    resilience: float           # 0.0-1.0; lower = more vulnerable to crises
 
    active: bool = True
    output_modifier: float = 1.0        # Crisis/boost modifier
    degradation_modifier: float = 1.0   # Aging modifier, decreases over time
    degradation_rate: float = 0.002     # Fraction reduction per aging step (every 5 ticks)
    efficiency_floor: float = 0.60      # degradation_modifier minimum
    age: int = 0                        # Ticks since source was created
    seasonal_modifier: float = 1.0      # Set by engine from SEASONAL_SOURCE_MODIFIERS
 
    _sampled_output: float = 0.0        # Set by engine._sample_output() each tick
 
    @property
    def current_output(self) -> float:
        """
        Actual output this tick, composing all active multipliers.
        Requires engine to have called _sample_output() first.
        """
        if not self.active:
            return 0.0
        return (self._sampled_output
                * self.output_modifier
                * self.degradation_modifier
                * self.seasonal_modifier)
 
    def _sample_output(self, rng) -> float:
        """Draw a fresh random output for this tick and store it."""
        raw = rng.uniform(self.low_output_rate, self.high_output_rate)
        self._sampled_output = raw
        return raw
 
    @property
    def expected_output(self) -> float:
        """
        Mean output incorporating degradation and seasonal modifiers.
        Safe to call at any time — no sampling required.
        Used by agents for forward-looking stability projections.
        """
        base = (self.low_output_rate + self.high_output_rate) / 2.0
        return base * self.degradation_modifier * self.seasonal_modifier
    
@dataclass
class TradeRoute:
    """
    An active energy transfer agreement between two zones.
 
    export_cap:
        Optional ceiling on energy sent per tick. Set via action_set_export_cap.
        None = no cap. Allows governors to protect themselves during stress
        without fully closing the route. Respected by effective_transfer_rate.
 
    fortification:
        0.0-1.0; reduces ROUTE_ATTACK damage fraction per tick.
        Set via action_fortify_route. Represents physical hardening of
        transmission infrastructure (buried cables, redundant paths, etc.)
        A fortification of 0.5 means attacks deal only 50% of their listed damage.
    """
    route_id: str
    source_zone_id: str
    target_zone_id: str
    energy_type: EnergyType
    transfer_rate: float
    latency: int = 1
    route_health: float = 100.0
    transmission_efficiency: float = 0.90
 
    in_flight: list = field(default_factory=list)
 
    export_cap: Optional[float] = None  # None = unrestricted
    fortification: float = 0.0          # 0.0-1.0 damage reduction
 
    @property
    def effective_transfer_rate(self) -> float:
        """Energy deducted from source per tick (full sent amount, health-scaled, cap-applied)."""
        base = self.transfer_rate * (self.route_health / 100.0)
        if self.export_cap is not None:
            base = min(base, self.export_cap)
        return base
 
    @property
    def effective_received_rate(self) -> float:
        """Energy received by target per tick (after heat loss)."""
        return self.effective_transfer_rate * self.transmission_efficiency
 
    @property
    def heat_loss_rate(self) -> float:
        return self.effective_transfer_rate - self.effective_received_rate
 
    @property
    def is_severed(self) -> bool:
        return self.route_health <= 0
    
@dataclass
class Zone:
    """
    The central entity in the simulation.
 
    morale (0-100):
        Tracks public trust and zone cohesion. Falls when the zone is in Warning/
        Critical state; rises slowly when Stable. Below 50, morale raises effective
        demand (panic buying, black-market inefficiency) and reduces budget income.
        Morale degradation compounds: consecutive Critical ticks cause accelerating
        loss, making recovery harder the longer a zone stays in crisis.
 
    reputation (0-100):
        Tracks trade reliability. Falls when a trade route the zone sources delivers
        zero energy (storage ran dry mid-commitment). Rises slowly when Stable.
        Low reputation means partner zones are less willing to accept new trade
        offers (encoded as higher cost to action_open_trade_route when rep < 50).
 
    region (str):
        Tag for REGIONAL_BLACKOUT crises. All zones sharing the same region tag
        are hit simultaneously when a regional event fires.
 
    cyber_attacked (bool):
        When True, get_zone_state() returns noisy observations. The zone's own
        governor receives corrupted readings, forcing decisions under uncertainty.
 
    seasonal_demand_modifier:
        Set by engine each tick from SEASONAL_DEMAND_MODIFIERS. Winter raises
        demand; summer is neutral; spring/autumn give slight relief.
    """
    zone_id: str
    name: str
 
    sources: list = field(default_factory=list)
    storage: Storage = field(default_factory=lambda: Storage(capacity=1000.0, stored_energy=500.0))
    economy: Economy = field(default_factory=Economy)
 
    base_demand: float = 50.0
    demand_modifier: float = 1.0
 
    low_threshold: float = 100.0
    warning_window: int = 5
    critical_window: int = 2
 
    stability_state: StabilityState = StabilityState.STABLE
    net_energy_per_tick: float = 0.0
    projected_depletion_ticks: Optional[float] = None
 
    messages: list = field(default_factory=list)
 
    morale: float = 100.0
    reputation: float = 100.0
    region: str = "default"
    cyber_attacked: bool = False
    seasonal_demand_modifier: float = 1.0
    _consecutive_critical_ticks: int = 0
 
    @property
    def energy_gain_per_tick(self) -> float:
        """Total output from all active sources this tick (reads sampled values)."""
        return sum(s.current_output for s in self.sources)
 
    @property
    def expected_energy_gain(self) -> float:
        """Expected (mean) gain — safe to call without sampling."""
        return sum(s.expected_output for s in self.sources if s.active)
 
    @property
    def energy_demand_per_tick(self) -> float:
        """
        Effective demand this tick, incorporating:
          - demand_modifier        (crises, rationing, conservation orders)
          - seasonal_demand_modifier (winter peaks etc.)
          - morale_factor: below 50 morale, demand increases up to 25% at morale=0
        """
        morale_factor = 1.0 + max(0.0, (50.0 - self.morale) / 200.0)
        return self.base_demand * self.demand_modifier * self.seasonal_demand_modifier * morale_factor
 
    @property
    def stored_energy(self) -> float:
        return self.storage.stored_energy
 
    @property
    def storage_capacity(self) -> float:
        return self.storage.capacity
    
@dataclass
class CrisisEvent:
    """
    A crisis injected by the Crisis Agent (or scripted for testing).
 
    target_id: zone_id, route_id, or region name depending on crisis_type.
    parameters: flexible dict for crisis-specific data.
 
    Common parameter keys used by the engine:
        source_id           — which EnergySource is affected
        output_modifier     — modifier applied to source output
        demand_modifier     — multiplier on zone demand
        damage_per_tick     — route health lost per tick
        leak_rate           — fraction of stored energy lost per tick (STORAGE_LEAK)
        income_modifier     — fraction of budget_per_tick earned (ECONOMIC_RECESSION)
        region              — region tag for REGIONAL_BLACKOUT
        route_id            — route to freeze (POLITICAL_EMBARGO) or damage (WILDFIRE)
        route_damage_per_tick — route health lost per tick for WILDFIRE
        efficiency_reduction  — efficiency drop for TRANSMISSION_SURGE
        solar_output_modifier — solar-specific modifier for HEAT_WAVE
        spreading           — bool, CASCADING_FAILURE propagates to neighbours
        spread_modifier     — how badly neighbours are hit in CASCADING_FAILURE
 
    Internal keys (will be written by engine on first application, do not set manually):
        _originals          — saved original values for reversible effects
        _initialized        — bool, prevents re-applying one-time first-tick effects
        _spread_applied     — bool, prevents duplicate cascade spread
        _original_income_modifier — saved value for ECONOMIC_RECESSION restore
    """
    crisis_id: str
    crisis_type: CrisisType
    target_id: str
    duration: int
    remaining_ticks: int
    parameters: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class EarlyWarningSignal:
    """
    A predictive signal delivered to a zone before a scheduled crisis fires.
 
    Generated by engine.schedule_crisis() when warning_ticks > 0.
    The probability field reflects signal confidence — it is intentionally
    noisy (agents can't fully trust it). Delivered as a structured message
    in zone.messages so the governor hook can observe and act on it.
    """
    signal_id: str
    signal_type: str        # Mirrors the CrisisType value string
    target_id: str
    probability: float      # 0.0-1.0; noisy confidence estimate
    ticks_until_event: int
    description: str

@dataclass
class TradeOffer:
    """
    A bilateral trade proposal between two zones.
 
    The initiating zone (from_zone_id) proposes to:
      • Give  energy_offered  units of energy  TO   to_zone_id
      • Give  budget_offered  credits           TO   to_zone_id
      • Receive energy_requested units of energy FROM to_zone_id
      • Receive budget_requested credits        FROM to_zone_id
 
    Any of the four quantities can be 0 (e.g. a pure energy-for-budget deal
    sets energy_requested=0 and budget_offered=0).
 
    The offer must be explicitly accepted by the target zone via
    action_accept_trade() before any resources move.  Until then it sits in
    the engine's _pending_trade_offers dict and appears in the target zone's
    messages queue so its governor can inspect and decide.
 
    status lifecycle:
        "pending"  → offer is live, waiting for a response
        "accepted" → target accepted; resources were transferred atomically
        "rejected" → target explicitly declined
        "expired"  → expires_at_tick passed with no response
    """
    offer_id: str
    from_zone_id: str
    to_zone_id: str
    energy_offered: float      # Energy FROM initiator TO target
    budget_offered: float      # Budget  FROM initiator TO target
    energy_requested: float    # Energy FROM target TO initiator
    budget_requested: float    # Budget  FROM target TO initiator
    expires_at_tick: int
    status: str = "pending"    # "pending" | "accepted" | "rejected" | "expired"
    description: str = ""
    

    


