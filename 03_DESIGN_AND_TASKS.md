# Agentic Energy Grid Simulation — Design & Task List

**Project:** Multi-Zone Energy Trading Simulation with Crisis & Problem-Solver Agents  
**Date:** 20 March 2026  
**Version:** 0.1 (Draft)  
**Status:** Design Phase

---

## 1. System Architecture

### 1.1 High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                    SIMULATION ENGINE                         │
│  (Orchestrates time steps, enforces physics, logs state)     │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Zone A   │  │  Zone B   │  │  Zone C   │  │  Zone N   │  │
│  │ Gen|Stor  │  │ Gen|Stor  │  │ Gen|Stor  │  │ Gen|Stor  │  │
│  │ Demand    │  │ Demand    │  │ Demand    │  │ Demand    │  │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘   │
│        │              │              │              │         │
│  ┌─────┴──────────────┴──────────────┴──────────────┴────┐  │
│  │              GRID / TRANSMISSION NETWORK               │  │
│  │     (Interconnectors, constraints, losses, frequency)  │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │                    MARKET ENGINE                       │  │
│  │   (Merit order, clearing price, trade settlement)     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────┐          ┌──────────────────────┐     │
│  │   CRISIS AGENT    │          │  PROBLEM-SOLVER AGENT │    │
│  │ (Injects events)  │◄────────►│ (Detects & responds)  │   │
│  └──────────────────┘          └──────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  STATE LOGGER / DASHBOARD              │  │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Simulation Loop (Per Time Step)

```
1. CRISIS AGENT evaluates → may inject crisis event(s)
2. Apply crisis effects to zone/grid state
3. Update renewable generation based on weather/capacity factors
4. Calculate demand per zone (base + weather + growth + flexibility)
5. MARKET ENGINE runs merit-order dispatch per zone
6. MARKET ENGINE clears inter-zone trades (constrained by interconnectors)
7. Calculate power balance per zone
8. PROBLEM-SOLVER AGENT observes state
9. If anomaly detected → select and execute action(s)
10. Apply action effects to state
11. Calculate final state: ENS, frequency, prices, SoC
12. Log all state variables and events
13. Advance to next time step
```

### 1.3 Data Model

```
Zone:
  id: str
  name: str
  generators: List[Generator]
  storage_assets: List[Storage]
  demand_profile: DemandProfile
  grid_properties: GridProperties
  interconnectors: List[Interconnector]

Generator:
  id: str
  type: enum (NUCLEAR, GAS_CCGT, COAL, BIOMASS, WIND_ONSHORE, WIND_OFFSHORE, SOLAR_PV, HYDRO)
  installed_capacity_mw: float
  available_capacity_mw: float  # time-varying
  capacity_factor: float  # for renewables, time-varying
  ramp_rate_mw_per_hour: float
  min_stable_generation_mw: float
  start_up_time_hours: float
  marginal_cost_per_mwh: float
  inertia_mws: float
  fuel_dependency: Optional[str]
  emissions_intensity_gco2_kwh: float
  key_constraints: Optional[str]  # e.g., carbon pricing, phase-out policy, feedstock certification
  status: enum (ONLINE, OFFLINE, STARTING, TRIPPED)

Storage:
  id: str
  type: enum (LI_ION_BESS, PUMPED_HYDRO, HYDROGEN, COMPRESSED_AIR)
  capacity_mwh: float
  power_rating_mw: float
  soc_pct: float  # 0-100
  min_soc_pct: float
  max_soc_pct: float
  round_trip_efficiency_pct: float
  response_time_minutes: float
  degradation_cycles: int
  status: enum (IDLE, CHARGING, DISCHARGING)

DemandProfile:
  base_load_mw: float
  hourly_profile: List[float]  # multiplier on base_load
  flexibility_pct: float
  flexibility_response_time_hours: float
  weather_sensitivity: WeatherCoefficients
  current_demand_mw: float  # computed at runtime

GridProperties:
  distribution_capacity_mw: float
  grid_losses_pct: float
  automation_level: float  # 0-1, affects response speed
  scada_coverage_pct: float

Interconnector:
  id: str
  from_zone: str
  to_zone: str
  capacity_mw: float
  current_flow_mw: float  # positive = from→to
  losses_pct: float
  status: enum (OPERATIONAL, DEGRADED, FAILED)

CrisisEvent:
  id: str
  type: enum (GENERATOR_TRIP, FUEL_DISRUPTION_GAS, FUEL_DISRUPTION_COAL, FUEL_DISRUPTION_BIOMASS,
              CARBON_PRICE_SHOCK, DUNKELFLAUTE, COLD_SNAP,
              HEAT_WAVE, LINE_FAILURE, INTERCONNECTOR_LOSS, DEMAND_SPIKE)
  severity: float  # 0-1
  duration_hours: int
  onset_speed: enum (SUDDEN, GRADUAL)
  affected_zones: List[str]
  affected_assets: List[str]  # specific generator/line IDs
  cascading_probability: float
  timestamp: int  # time step of injection

AgentAction:
  id: str
  type: enum (ACTIVATE_RESERVE, RAMP_GENERATION, DISPATCH_BESS,
              REQUEST_IMPORTS, DEMAND_RESPONSE, PRICE_SIGNAL,
              VOLTAGE_REDUCTION, LOAD_SHEDDING, REDISPATCH,
              DYNAMIC_LINE_RATING, ISLANDING, BALANCING_MARKET)
  target_zone: str
  target_asset: Optional[str]
  magnitude_mw: float
  execution_time_hours: float
  cost: float
  timestamp: int

SimulationState:
  timestep: int
  zones: Dict[str, ZoneState]
  system_frequency_hz: float
  total_ens_mwh: float
  active_crises: List[CrisisEvent]
  actions_taken: List[AgentAction]
  market_clearing_prices: Dict[str, float]
  inter_zone_flows: Dict[str, float]
```

---

## 2. Component Design

### 2.1 Zone Model
- Each zone is a self-contained balancing area
- At each time step, the zone calculates: total available generation, total demand, net surplus/deficit
- Surplus zones offer energy to the market; deficit zones bid for imports
- Storage is dispatched based on the zone's internal strategy or the problem-solver agent

### 2.2 Market Engine
- **Merit-order dispatch:** Stack all generators by marginal cost, dispatch from cheapest to most expensive until demand is met
- **Inter-zone clearing:** After intra-zone dispatch, surplus/deficit zones trade through interconnectors. Trades flow from lower-price zones to higher-price zones, constrained by interconnector capacity.
- **Clearing price:** Set by the marginal unit dispatched (last unit needed to meet demand)
- **Balancing market:** Activated by the problem-solver agent during crises; faster clearing with premium pricing

### 2.3 Grid Model (Simplified)
- Zones connected by interconnectors (graph topology)
- Power flow constrained by interconnector capacity (transport model, not full power flow)
- Grid losses applied as a percentage of flow
- System frequency modelled as: Δf ∝ (generation - demand) / total_inertia
- Frequency thresholds trigger automatic load shedding or generator disconnection

### 2.4 Crisis Agent Design
- Operates independently of the simulation physics
- Has a "scenario library" of crisis templates with configurable parameters
- Can be configured in three modes:
  - **Random:** Poisson-distributed events with configurable intensity
  - **Scripted:** Predefined sequence of events at specific time steps
  - **Adaptive:** Monitors system stability; injects crises when system is most stable (adversarial)
- Crisis effects are applied as modifications to zone/grid state (e.g., set generator status to TRIPPED, reduce interconnector capacity to 0)

### 2.5 Problem-Solver Agent Design
- Observes the full simulation state at each time step
- Maintains awareness of normal operating bounds for all key variables
- Detection pipeline:
  1. Compare observed state to thresholds (frequency, ENS, price, utilisation)
  2. Classify severity (WATCH → WARNING → EMERGENCY → CRITICAL)
  3. Identify root cause (which zone, which asset, which constraint)
- Response pipeline:
  1. Enumerate feasible actions from toolbox (filtered by current state)
  2. Rank actions by effectiveness vs. cost vs. execution time
  3. Select and execute top action(s)
  4. Monitor effect in subsequent time steps
- Implementable as interchangeable strategies:
  - `RuleBasedSolver`: priority-ordered if-then rules
  - `OptimisationSolver`: minimise total ENS subject to action constraints
  - `RLSolver`: trained policy network
  - `LLMSolver`: prompt with state description, receive action selection

---

## 3. MVP Zone Configuration (Suggested)

For the minimum viable simulation, use 4 zones loosely inspired by GB grid regions:

| Zone | Generation Mix | Storage | Demand Character | Interconnectors |
|------|---------------|---------|-----------------|-----------------|
| **Zone A (North)** | 3 GW wind, 1.2 GW nuclear, 0.5 GW gas, 0.8 GW coal (mothballed, emergency recall) | 200 MWh BESS | Industrial + residential, moderate | → B (2 GW), → D (0.5 GW) |
| **Zone B (Midlands)** | 2 GW gas CCGT, 1 GW solar, 0.3 GW wind, 0.4 GW biomass | 100 MWh BESS | High industrial demand, peaks in daytime | → A (2 GW), → C (3 GW) |
| **Zone C (South)** | 3 GW nuclear, 2 GW gas, 1.5 GW solar, 0.3 GW biomass | 500 MWh BESS, 1 GW pumped hydro | Highest population density, residential peaks | → B (3 GW), → D (1 GW), → Import (2 GW) |
| **Zone D (West)** | 2 GW wind (onshore + offshore), 0.5 GW hydro, 0.3 GW gas, 0.5 GW coal | 50 MWh BESS | Low demand, net exporter | → A (0.5 GW), → C (1 GW) |

---

## 4. Task List

### Phase 1: Foundation (Weeks 1–2)

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T1.1 | Project setup | Python project structure, pyproject.toml, linting, git init | ☐ |
| T1.2 | Data models | Implement all dataclasses/Pydantic models (Zone, Generator, Storage, etc.) | ☐ |
| T1.3 | Configuration loader | YAML config parser for zone definitions, interconnector topology | ☐ |
| T1.4 | Time-series loader | Load hourly demand profiles and renewable capacity factors from CSV | ☐ |
| T1.5 | Zone balancing logic | Per-zone merit-order dispatch, surplus/deficit calculation | ☐ |
| T1.6 | Basic simulation loop | Iterate through time steps, calculate state, log output | ☐ |
| T1.7 | Output logger | Write time-series state to CSV/Parquet per time step | ☐ |
| T1.8 | MVP config files | Create YAML configs for 4-zone setup | ☐ |
| T1.9 | Unit tests (foundation) | Test merit-order dispatch, energy balance, constraint enforcement | ☐ |

### Phase 2: Grid & Trading (Weeks 3–4)

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T2.1 | Interconnector model | Power flow between zones, capacity constraints, losses | ☐ |
| T2.2 | Inter-zone market clearing | Surplus/deficit trading, constrained by interconnectors | ☐ |
| T2.3 | Frequency model | Aggregate frequency calculation based on gen-demand balance and inertia | ☐ |
| T2.4 | Storage dispatch logic | Charge/discharge based on price signals and SoC constraints | ☐ |
| T2.5 | Energy-not-served (ENS) calculation | Track unmet demand per zone per time step | ☐ |
| T2.6 | Clearing price computation | Marginal price per zone, spread between zones | ☐ |
| T2.7 | Unit tests (grid & trading) | Test flow constraints, price clearing, storage cycling | ☐ |

### Phase 3: Crisis Agent (Weeks 5–6)

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T3.1 | Crisis event model | CrisisEvent dataclass, severity/duration/scope parameters | ☐ |
| T3.2 | Crisis scenario library | Implement 9+ crisis templates (generator trip, gas/coal/biomass fuel disruption, carbon price shock, line failure, cold snap, Dunkelflaute, interconnector loss, demand spike) | ☐ |
| T3.3 | Crisis injection engine | Apply crisis effects to simulation state (trip generator, reduce capacity, etc.) | ☐ |
| T3.4 | Random injection mode | Poisson-distributed crisis injection with configurable rate | ☐ |
| T3.5 | Scripted injection mode | Predefined crisis sequence from config file | ☐ |
| T3.6 | Cascading failure logic | Probability-based secondary failures triggered by initial crisis | ☐ |
| T3.7 | Crisis event logging | Full audit trail of injected events | ☐ |
| T3.8 | Unit tests (crisis) | Test each crisis type's effect on state, cascading logic | ☐ |

### Phase 4: Problem-Solver Agent (Weeks 7–8)

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T4.1 | State observer | Extract key metrics from simulation state for anomaly detection | ☐ |
| T4.2 | Anomaly detection | Threshold-based detection with severity classification | ☐ |
| T4.3 | Action toolbox | Implement all actions with effects, costs, execution times, constraints | ☐ |
| T4.4 | Rule-based solver | Priority-ordered response strategy | ☐ |
| T4.5 | Action execution engine | Apply selected actions to simulation state | ☐ |
| T4.6 | Agent decision logging | Full audit trail of observations, detections, and actions | ☐ |
| T4.7 | LLM solver (stretch) | LLM-based reasoning over state + toolbox | ☐ |
| T4.8 | RL solver (stretch) | RL-trained policy for crisis response | ☐ |
| T4.9 | Unit tests (solver) | Test detection, action selection, state effects | ☐ |

### Phase 5: Visualisation & Analysis (Weeks 9–10)

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T5.1 | Post-simulation analysis notebook | Jupyter notebook with key charts and metrics | ☐ |
| T5.2 | Zone dashboard | Streamlit or React dashboard showing per-zone state over time | ☐ |
| T5.3 | Crisis timeline view | Visual timeline of crisis events and agent responses | ☐ |
| T5.4 | Comparative analysis | Run baseline (no agent) vs. agent scenarios, compare ENS/cost | ☐ |
| T5.5 | Documentation | README, architecture doc, configuration guide | ☐ |

### Phase 6: Extensions (Ongoing)

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T6.1 | Real data integration | Load ENTSO-E actual generation/demand data | ☐ |
| T6.2 | Weather-driven renewables | ERA5 / Renewables.ninja integration | ☐ |
| T6.3 | Multi-agent trading | Each zone as an independent trading agent with learned strategies | ☐ |
| T6.4 | Adversarial crisis agent | Crisis agent learns to find system weaknesses (RL-based) | ☐ |
| T6.5 | Full power flow | Replace transport model with DC-OPF or AC power flow | ☐ |
| T6.6 | TSO-DSO split | Model TSO and DSO as separate agents with communication latency | ☐ |
| T6.7 | Additional storage types | Hydrogen seasonal storage, V2G (vehicle-to-grid) | ☐ |
| T6.8 | Carbon intensity tracking | Emissions per MWh per zone, carbon cost in market | ☐ |

---

## 5. Technology Stack (Proposed)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.11+ | Ecosystem, libraries, agent frameworks |
| Data models | Pydantic v2 | Validation, serialisation, type safety |
| Configuration | YAML (via PyYAML/ruamel.yaml) | Human-readable, widely used |
| Data storage | Parquet (via pyarrow) | Columnar, fast, compact |
| Numerical | NumPy, pandas | Standard scientific Python |
| Visualisation | Plotly, Streamlit | Interactive, web-based |
| Agent framework (LLM) | LangGraph or Claude API | Reasoning over state + toolbox |
| Agent framework (RL) | Stable-Baselines3, Gymnasium | Standard RL toolkit |
| Testing | pytest | Standard Python testing |
| Version control | Git + GitHub | Standard |

---

## 6. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Scope creep (too many features in v1) | High | High | Strict MVP definition, Phase 1-4 only for first iteration |
| Unrealistic simulation parameters | Medium | Medium | Calibrate against ENTSO-E/OPSD data early |
| Agent doesn't learn meaningful strategies | Medium | Medium | Start with rule-based solver, add RL/LLM incrementally |
| Performance (slow simulation) | Low | Low | Hourly resolution is computationally light; profile if needed |
| Data quality issues | Medium | Medium | Use synthetic data for MVP, real data in Phase 6 |

---

## 7. Decision Log

| Date | Decision | Rationale | Owner |
|------|----------|-----------|-------|
| 20 Mar 2026 | Start with 4-zone GB-inspired topology | Manageable scope, familiar grid, good data availability | FCO |
| 20 Mar 2026 | Use simplified transport model (not full power flow) | MVP focus; DC-OPF adds complexity without core value for crisis testing | FCO |
| 20 Mar 2026 | Rule-based solver first, LLM/RL as stretch | Get end-to-end working before adding AI complexity | FCO |
| | | | |
