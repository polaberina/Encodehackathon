# Agentic Energy Grid Simulation — Requirements Specification

**Project:** Multi-Zone Energy Trading Simulation with Crisis & Problem-Solver Agents  
**Date:** 20 March 2026  
**Version:** 0.1 (Draft)  
**Status:** Requirements Gathering

---

## 1. Project Overview

### 1.1 Vision
Build a simulation environment where zones/entities with different energy generation mixes trade energy based on their needs, while a Crisis Agent injects disruptive scenarios and a Problem-Solver Agent detects and responds to crises using a constrained toolbox of real-world TSO/DSO actions.

### 1.2 Core Objectives
- Simulate realistic multi-zone energy systems with heterogeneous generation, storage, and demand profiles
- Model energy distribution through TSO/DSO infrastructure with realistic constraints and dependencies
- Enable agent-based energy trading between zones based on supply, demand, and price signals
- Inject crisis scenarios that stress-test the system across supply, demand, and network dimensions
- Deploy a problem-solver agent that reasons about and executes crisis response strategies
- Observe emergent behaviours: cascading failures, market distortions, resilience patterns

### 1.3 Success Criteria
- Simulation runs end-to-end for a configurable time horizon (e.g., 1 week at hourly resolution)
- At least 3 distinct crisis scenarios can be injected and resolved
- Problem-solver agent demonstrably reduces energy-not-served compared to no-intervention baseline
- System state is observable via dashboard or log output at each time step

---

## 2. Functional Requirements

### 2.1 Zone/Entity Model

**FR-2.1.1** Each zone shall be configurable with a generation mix (nuclear, gas CCGT, coal, biomass/biofuel, wind onshore/offshore, solar PV, hydro).

**FR-2.1.2** Each generation source shall have the following configurable properties:
- Installed capacity (MW)
- Current available capacity (MW, may differ due to outages, weather)
- Capacity factor (%, time-varying for renewables)
- Ramp rate (MW/minute or MW/hour)
- Start-up time (cold start, warm start, hot start)
- Marginal cost (£/MWh)
- Inertia contribution (MW·s)
- Fuel dependency (e.g., gas supply, coal stockpile, biomass feedstock availability)
- Minimum stable generation (MW)
- Emissions intensity (gCO₂/kWh)
- Key constraints (e.g., carbon pricing impact, phase-out policies, feedstock logistics, sustainability certification)

**FR-2.1.3** Each zone shall have a demand profile with:
- Base load (MW, continuous)
- Peak demand (MW, time-dependent)
- Demand flexibility (% of total, with response time)
- Weather sensitivity coefficients (heating/cooling degree days)
- Electrification growth factor (EV, heat pump uptake curves)

**FR-2.1.4** Each zone shall optionally include storage assets:
- Type (Li-ion BESS, pumped hydro, hydrogen, compressed air)
- Capacity (MWh)
- Power rating (MW charge/discharge)
- State of charge (%, time-varying)
- Round-trip efficiency (%)
- Degradation model (cycle count, calendar aging)
- Response time (milliseconds to minutes)

**FR-2.1.5** Each zone shall have a grid connection characterised by:
- Transmission interconnector capacity to other zones (MW)
- Distribution transformer capacity (MW)
- Grid losses (%)
- Automation level (affects crisis detection and response speed)

### 2.2 Energy Distribution Model

**FR-2.2.1** Energy flow between generation, storage, demand, and interconnectors shall be balanced at each time step (conservation of energy).

**FR-2.2.2** Transmission constraints shall be enforced: power flow on any interconnector cannot exceed its rated capacity.

**FR-2.2.3** Grid losses shall be modelled as a percentage of power flow, varying by distance and voltage level.

**FR-2.2.4** System frequency shall be modelled as an aggregate metric influenced by the balance of generation and demand, and the total system inertia.

**FR-2.2.5** Distribution constraints shall be modelled at the zone level: total demand within a zone cannot exceed distribution capacity plus local generation and storage.

### 2.3 Energy Trading Model

**FR-2.3.1** Zones shall trade energy through a simplified market mechanism:
- Day-ahead market (hourly clearing, merit-order dispatch)
- Intraday/balancing market (shorter-term adjustments)

**FR-2.3.2** Trade volumes shall be constrained by interconnector capacity and available surplus/deficit.

**FR-2.3.3** Clearing price shall be set by the marginal unit dispatched (merit-order principle).

**FR-2.3.4** Each zone shall have a trading strategy (can be rule-based, optimisation-based, or RL-based).

### 2.4 Crisis Agent

**FR-2.4.1** The Crisis Agent shall be able to inject the following scenario categories:
- Supply-side: generator trip, fuel supply disruption (gas pipeline, coal supply chain, biomass feedstock shortage), prolonged renewable drought (Dunkelflaute), carbon price shock (renders coal uneconomic mid-dispatch)
- Demand-side: cold snap, heat wave, EV charging synchronisation
- Network: transmission line failure, interconnector loss, cascading blackout trigger
- Market: extreme price event

**FR-2.4.2** Each crisis shall be parameterised by:
- Severity (magnitude of impact)
- Duration (time steps affected)
- Onset speed (sudden vs. gradual)
- Spatial scope (single zone, multi-zone, system-wide)
- Cascading probability (chance of triggering secondary failures)

**FR-2.4.3** The Crisis Agent shall operate on a configurable schedule:
- Random injection within a simulation run
- Scenario-driven (predefined sequence)
- Adaptive (escalating if system appears stable)

**FR-2.4.4** The Crisis Agent shall log all injected events with timestamps and parameters.

### 2.5 Problem-Solver Agent

**FR-2.5.1** The Problem-Solver Agent shall monitor system state at each time step, including:
- Generation-demand balance per zone
- Frequency deviation
- Interconnector utilisation
- Storage state of charge
- Price signals

**FR-2.5.2** The Problem-Solver Agent shall detect anomalies by comparing observed state to normal operating bounds (configurable thresholds).

**FR-2.5.3** The Problem-Solver Agent shall have access to the following action toolbox:

*Supply-side:*
- Activate spinning reserve
- Ramp dispatchable generation
- Dispatch BESS (charge/discharge)
- Request emergency interconnector imports
- Black-start sequence (post-blackout)

*Demand-side:*
- Activate demand response contracts
- Send dynamic price signals
- Conservation voltage reduction
- Rolling blackouts / load shedding (last resort)

*Network:*
- Redispatch generation
- Dynamic line rating activation
- Islanding of microgrids

*Market:*
- Activate balancing market
- Emergency reserve tenders
- Price cap implementation

**FR-2.5.4** Each action shall have:
- Execution time (how long to take effect)
- Capacity/magnitude
- Cost
- Side effects (e.g., load shedding causes economic loss)
- Constraints (e.g., BESS cannot discharge below 10% SoC)

**FR-2.5.5** The Problem-Solver Agent shall be implementable as:
- Rule-based (deterministic priority ordering)
- Optimisation-based (minimise energy-not-served or total cost)
- RL-based (learned policy)
- LLM-based (reasoning over state and toolbox)

### 2.6 Observability & Output

**FR-2.6.1** The simulation shall output time-series data for all key variables at each time step.

**FR-2.6.2** A dashboard or log viewer shall display:
- Per-zone generation mix, demand, storage SoC, price
- Inter-zone power flows
- System frequency
- Crisis events and problem-solver actions
- Energy-not-served (ENS) metric

**FR-2.6.3** Summary metrics per simulation run:
- Total ENS (MWh)
- Total cost
- Number of crises injected
- Number of actions taken
- System reliability (% of time within normal operating bounds)
- Crisis detection latency (time steps between crisis onset and agent response)

---

## 3. Non-Functional Requirements

**NFR-3.1** The simulation shall be written in Python 3.10+.

**NFR-3.2** The simulation shall run a 168-time-step (1-week, hourly) scenario in under 60 seconds on a standard laptop.

**NFR-3.3** Configuration shall be via YAML or JSON files (no hardcoded parameters).

**NFR-3.4** The simulation shall be deterministic given a fixed random seed.

**NFR-3.5** The codebase shall be modular: zone model, market model, crisis agent, problem-solver agent, and simulation engine shall be separable components.

**NFR-3.6** Output data shall be exportable to CSV or Parquet for analysis.

**NFR-3.7** The system shall support adding new generation types, storage types, or crisis scenarios without modifying core simulation logic.

---

## 4. Data Requirements

### 4.1 Input Data (Minimum Viable)
- Zone configuration files (generation mix, storage, demand profile, grid properties)
- Time-series: hourly demand profile (at least 1 week)
- Time-series: hourly renewable capacity factor (wind, solar) — can use Renewables.ninja or synthetic
- Interconnector topology (which zones connect, with capacity limits)
- Crisis scenario definitions

### 4.2 Stretch Input Data (Realistic)
- ENTSO-E Transparency Platform actual generation/demand data
- PyPSA-Eur network topology (simplified to zone level)
- ERA5 weather data driving renewable output
- Historical price data for market calibration

### 4.3 Output Data
- Time-series per zone: generation by type, demand, storage SoC, price, ENS
- Time-series system-level: frequency, total trade volume, total ENS
- Event log: crisis injections, agent actions, state transitions

---

## 5. Constraints & Assumptions

### 5.1 Simplifications for MVP
- DC power flow approximation (no reactive power, no voltage magnitudes)
- Single bus per zone (no intra-zone network modelling)
- Simplified market clearing (merit order, single clearing price per zone)
- Deterministic demand profiles (no stochastic demand modelling in v1)
- No financial settlement or credit risk modelling

### 5.2 Key Assumptions
- Each zone operates as a self-contained balancing area that can trade with connected zones
- The TSO/DSO distinction is modelled as response time and automation level rather than separate entities
- Renewable output is weather-driven and non-dispatchable (curtailment is an action, not a default)
- Storage degradation is tracked but does not cause mid-simulation failure in v1

---

## 6. Open Questions

1. **Agent framework:** Should the problem-solver use LangChain/LangGraph agents, or a simpler RL/rule-based approach for v1?
2. **Scope:** Start with UK-only zones (e.g., Scotland, North England, South England, Wales) or abstract/fictional zones?
3. **Market design:** Simple merit-order clearing, or include more sophisticated auction mechanisms?
4. **Visualisation:** React dashboard (real-time), or post-simulation analysis in Jupyter/Streamlit?
5. **Crisis complexity:** How many concurrent crises should the system handle?
6. **Hackathon alignment:** Is this being designed for the Cactus Compute or LangChain hackathon, or as a standalone project?
