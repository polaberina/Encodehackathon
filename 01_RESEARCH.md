# Agentic Energy Grid Simulation — Research Findings

**Project:** Multi-Zone Energy Trading Simulation with Crisis & Problem-Solver Agents  
**Date:** 20 March 2026  
**Status:** Research Phase

---

## 1. Existing Open-Source Frameworks & Prior Art

### 1.1 ASSUME Framework (Primary Reference)
- **What:** Open-source agent-based simulation toolbox for European electricity markets, with integrated deep reinforcement learning (DRL).
- **Repo:** [github.com/assume-framework/assume](https://github.com/assume-framework/assume)
- **Key features:**
  - Modular architecture: generator agents, demand-side agents, bidding strategies, market configurations
  - Multi-agent DRL (MADDPG variant) with centralized training, decentralized execution
  - Market zone clearing with nodal-level information (supports redispatch)
  - Storage unit agents with learned charge/discharge strategies
  - Steel plant demand-side management unit (industrial flexibility)
  - Dashboard via TimescaleDB + Grafana
  - Colab tutorials for RL onboarding
- **Relevance:** Closest existing framework to the proposed project. Covers market trading, agent learning, and generation/demand modelling. However, it does not include crisis injection, TSO/DSO coordination logic, or a dedicated "problem-solver" agent layer.
- **Published:** SoftwareX, Volume 30, 2025. Funded by German BMWK.
- **Successor project (ADAPT, 2025–2028):** Adding an AI-driven "market agent" that acts as a regulator, a low-code RL toolbox, and distribution-level grid modelling with sector coupling.

### 1.2 PyPSA / PyPSA-Eur
- **What:** Python for Power System Analysis — open optimisation model of the European energy system.
- **Repo:** [github.com/PyPSA/pypsa-eur](https://github.com/PyPSA/pypsa-eur)
- **Key features:**
  - Full ENTSO-E area coverage (transmission network from OpenStreetMap, 220kV+)
  - Sector-coupled: power, heat, transport, hydrogen, industry, agriculture
  - Pipeline networks for gas, hydrogen, CO₂, liquid fuels
  - Renewable time series from ERA5 and SARAH-3
  - Demand time series from ENTSO-E Transparency Platform
  - Snakemake workflow, fully reproducible from open data
- **Relevance:** Not agent-based, but provides the richest open dataset and network topology for Europe. Could serve as the data backbone or scenario generator for the simulation.

### 1.3 Other Notable Frameworks

| Framework | Focus | Language | Notes |
|-----------|-------|----------|-------|
| **AMIRIS** | Agent-based, RES integration, German market | Java | DLR-developed, open since 2021 |
| **AMES** | Wholesale power market with learning traders | Java/Python | Iowa State, ERCOT test system |
| **MASCEM** | Competitive electricity markets with strategic agents | Java | Porto, multi-agent simulator |
| **Power TAC** | Retail market competition with ML brokers | Java | Annual tournament since 2012 |
| **pandapower** | Power flow, OPF, state estimation | Python | Element-based modelling, Jupyter-friendly |
| **Sienna** (NREL) | Low-inertia power system simulation | Julia | Open-source, handles inverter-based resources |
| **INTERPLAN** | TSO-DSO coordination methodology | Multi | EU Horizon 2020, control functions for grid planning |
| **Building Energy Storage Sim** | OpenAI Gym environment for BESS RL | Python | Lightweight playground for storage control |
| **SCooDER** (LBNL) | DER simulation models | Modelica | Smart inverters, BESS, EV, transformers |

### 1.4 Key Academic References

- Harder et al. (2023) — "Fit for purpose: Modelling wholesale electricity markets realistically with multi-agent deep reinforcement learning" (Energy and AI)
- Denmark 160-household feeder study (2025) — Second-by-second multi-agent simulation of DER adoption, transformer overload dynamics, DSO/TSO agent coordination (MDPI Electronics)
- INTERPLAN methodology (ScienceDirect, 2022) — Formalised TSO-DSO operation planning with control functions, grid equivalents, and co-simulation
- Springer (2025) — Assessment of TSO-DSO coordination: TSO-managed, DSO-managed, and hybrid models with six market schemes for flexibility procurement

---

## 2. Open Data Sources

### 2.1 Generation, Demand & Market Data

| Source | Coverage | Resolution | Access |
|--------|----------|------------|--------|
| **ENTSO-E Transparency Platform** | 36 European countries, 43 TSOs | Hourly+ (from 2015) | RESTful API, free |
| **Open Power System Data (OPSD)** | 39 European countries | Hourly time series, annual capacity | CSV/JSON, open |
| **Renewables.ninja** | Global PV and wind capacity factors | Hourly, simulated | API, open |
| **Eurostat nrg_105m** | EU monthly electricity consumption/generation by fuel | Monthly | CSV, open |
| **IEA Monthly Electricity Statistics** | OECD countries | Monthly | Restricted |
| **Global Power Plant Database** | Worldwide power plants | Static (annually updated) | Open |

### 2.2 Grid Topology & Network Data

| Source | Coverage | Notes |
|--------|----------|-------|
| **PyPSA-Eur dataset** | ENTSO-E area, 220kV+ | OpenStreetMap-based, fully automated pipeline |
| **GridKit** | European transmission network | Extracted from ENTSO-E interactive map |
| **ELMOD-DE** | German HV grid (438 nodes, 697 lines) | 380kV and 220kV, with 2012 load/weather |
| **Open Infrastructure Map** | Global energy infrastructure | OpenStreetMap-based |
| **sci2grid** | European electricity transmission and gas transport | Open, geographically accurate |
| **PUDL (US)** | US electricity system (FERC, EIA, EPA) | Python pipeline, open |

### 2.3 Weather & Renewable Resource Data

| Source | Coverage | Notes |
|--------|----------|-------|
| **ERA5 (ECMWF)** | Global reanalysis | Hourly, 0.25° resolution |
| **SARAH-3** | European surface radiation | Satellite-derived |
| **MERRA-2 (NASA)** | Global | 0.625° × 0.5° resolution |
| **atlite** (PyPSA tool) | Converts weather to renewable availability | Python, integrates with ERA5/SARAH |

---

## 3. TSO-DSO Coordination Models (Crisis Management Context)

### 3.1 Three Principal Coordination Models

1. **TSO-managed model** — TSO procures all flexibility, including from distribution-connected DERs. DSO has a passive/informational role.
2. **DSO-managed model** — DSO manages local flexibility, aggregates and offers services to TSO. DSO acts as a local market operator.
3. **Hybrid TSO-DSO model** — Shared responsibility. Both operators procure flexibility through coordinated markets. Requires shared interfaces for emergency data exchange, resource activation, and market clearing.

### 3.2 Critical TSO-DSO Interfaces (for Crisis Simulation)

Based on EU research and ENTSO-E/DSO Entity frameworks:

- **Direct TSO-DSO interface:** Fast data exchange for emergency situations, structural information, forecasts, and resource activation
- **Shared resources interface:** DERs providing services to both TSO and DSO, with structural information, baselines, and measurements
- **Market interfaces:** Flexibility providers offering services; TSO and DSO purchasing. Must prevent double-bid selection and harmful cross-grid activations.

### 3.3 Crisis Feedback Communication Models

From the literature on TSO-DSO emergency coordination:

- **Centralised emergency model:** TSO detects substation/line failure → communicates to DSO → DSO redirects power via DERMS to affected DERs
- **Decentralised feedback model:** Individual TSO power stations communicate with DSO apart from integrated regional TSO. Solo network points subsidise normal DER ranges during high grid activity.
- **Forecast futures model:** TSO provides day-ahead power flow availability estimates based on substation data and "last known" averages

### 3.4 Grid Resilience Framework (Terna "Resilience 2.0")

Italian TSO Terna developed a probabilistic methodology:
- Map assets → create vulnerability curves and risk heat maps → model detailed grid-impact scenarios
- Iteratively test using advanced analytics simulation with uncertainty ranges
- Identify network sections with highest mitigation need (based on energy not served, number of affected users)
- Supports climate-change grid resilience investment planning

---

## 4. Energy Source Properties & Dependencies (Simulation Input Variables)

### 4.1 Generation Source Properties

| Property | Nuclear | Gas CCGT | Wind (Onshore) | Wind (Offshore) | Solar PV | Hydro (Reservoir) |
|----------|---------|----------|-----------------|-----------------|----------|-------------------|
| Typical capacity (GW) | 0.5–1.6 per unit | 0.3–0.9 | 0.002–0.015 per turbine | 0.006–0.015 per turbine | Varies | 0.1–2.0 |
| Capacity factor (%) | 85–93 | 40–60 | 25–45 | 35–55 | 10–25 | 20–60 |
| Ramp rate | Very slow (hours) | Fast (minutes) | Weather-dependent | Weather-dependent | Weather-dependent | Fast (seconds–minutes) |
| Dispatchability | Baseload | Flexible/peaking | Non-dispatchable | Non-dispatchable | Non-dispatchable | Dispatchable |
| Inertia contribution | High (synchronous) | High (synchronous) | None (inverter-based) | None (inverter-based) | None (inverter-based) | High (synchronous) |
| Fuel dependency | Uranium supply chain | Gas pipeline/LNG | None | None | None | Water/rainfall |
| Start-up time | 24–72 hours (cold) | 0.5–4 hours | Immediate (wind permitting) | Immediate (wind permitting) | Immediate (sun permitting) | Minutes |
| Marginal cost (£/MWh) | 5–15 | 30–80 (gas price dependent) | 0–5 | 0–5 | 0–5 | 0–10 |

### 4.2 Storage Properties

| Property | Li-ion BESS | Pumped Hydro | Hydrogen (Electrolyser + Fuel Cell) | Compressed Air |
|----------|-------------|--------------|--------------------------------------|----------------|
| Round-trip efficiency (%) | 85–95 | 70–85 | 30–45 | 40–70 |
| Discharge duration | 1–4 hours (grid-scale) | 6–20 hours | Hours–seasonal | 4–24 hours |
| Response time | Milliseconds | Seconds–minutes | Minutes | Minutes |
| Degradation | Cycle-dependent, calendar aging | Minimal | Catalyst degradation | Minimal |
| Energy density | High | Low (needs geography) | Very high (seasonal) | Low |
| Capital cost trend | Rapidly declining | Mature, site-specific | Declining | Moderate |
| Grid services | Frequency response, peak shaving, arbitrage | Load shifting, reserve | Seasonal balancing, sector coupling | Peak shaving |

### 4.3 Demand-Side Variables

| Variable | Description | Impact on Simulation |
|----------|-------------|---------------------|
| Base load | Minimum continuous demand (industrial, always-on) | Floor of demand curve |
| Peak demand | Maximum system demand (typically winter evenings UK, summer afternoons elsewhere) | Triggers peaking generation, storage discharge, DSR |
| Demand flexibility | % of load that can be shifted in time (e.g., EV charging, heat pumps, industrial) | Determines DSR potential |
| Demand response speed | How fast flexible load can be curtailed/shifted | Crisis response capability |
| Electrification growth | EV uptake, heat pump adoption, industrial electrification | Drives demand growth and profile change |
| Weather sensitivity | Heating degree days, cooling degree days | Demand forecasting input |
| Time-of-use tariff response | Consumer response to price signals | Shapes demand curve |

### 4.4 Distribution & Grid Variables

| Variable | Description | Impact on Simulation |
|----------|-------------|---------------------|
| Transmission capacity (MW) | Maximum power flow per line/interconnector | Congestion bottleneck |
| Distribution transformer capacity | Local capacity limit at substation level | DER hosting capacity |
| Grid losses (%) | Typically 2–8% depending on distance and voltage level | Reduces delivered energy |
| System inertia (GW·s) | Total rotational inertia from synchronous generators | Frequency stability |
| Frequency (Hz) | 50Hz (EU/UK), must stay within ±0.5Hz | System stability metric |
| Interconnector capacity | Cross-border/cross-zone transfer capacity | Energy trading constraint |
| Grid intelligence/automation | SCADA, PMU coverage, smart meter penetration | Observability and control speed |
| DSO operational efficiency | Fault detection speed, switching automation | Crisis response time |
| BESS grid connection | Location in network (transmission vs distribution) | Congestion relief capability |

---

## 5. Crisis Scenarios for the Crisis Agent

### 5.1 Supply-Side Crises

| Scenario | Trigger | Cascading Effects | Problem-Solver Actions |
|----------|---------|-------------------|----------------------|
| Nuclear trip (sudden loss of 1–3 GW) | Equipment failure, safety shutdown | Frequency drop, reserve activation, price spike | Activate BESS, ramp gas, demand curtailment, interconnector imports |
| Gas supply disruption | Pipeline failure, geopolitical event | Gas CCGT unavailable, price shock, fuel switching | Maximise renewables, storage dispatch, demand response, coal/oil backup |
| Wind drought (Dunkelflaute) | Sustained high-pressure weather system | Days of low wind + solar output | Storage depletion, fossil ramp-up, imports, demand curtailment |
| Solar eclipse/extreme cloud | Rapid solar generation drop | Fast frequency transient | BESS fast response, gas peakers, demand reduction |
| Transmission line failure | Storm, equipment failure | Congestion, islanding risk, price separation between zones | Redispatch, topology switching, BESS at constrained nodes |
| Cyber attack on SCADA | Malicious actor | Loss of observability, uncontrolled switching | Manual overrides, islanding, physical switching |

### 5.2 Demand-Side Crises

| Scenario | Trigger | Cascading Effects | Problem-Solver Actions |
|----------|---------|-------------------|----------------------|
| Cold snap (sudden demand surge) | Extreme winter weather | Heating demand spike, potential supply shortfall | Demand response, storage discharge, emergency imports, voltage reduction |
| Heat wave | Extreme summer temperatures | Cooling demand surge, thermal plant derating, transmission line sag | Demand curtailment, storage, imports |
| Industrial demand spike | Unforecasted large industrial load | Local transformer overload | DSO load management, local BESS, dynamic line rating |
| EV charging synchronisation | Mass simultaneous charging (e.g., after commute) | Distribution transformer overload within hours | Smart charging signals, local BESS, ToU price adjustment |

### 5.3 System-Level Crises

| Scenario | Trigger | Cascading Effects | Problem-Solver Actions |
|----------|---------|-------------------|----------------------|
| Cascading blackout | Initial fault + protection failures | Progressive line/generator tripping, system separation | Islanding, black-start procedure, load restoration sequencing |
| Market failure | Extreme price spike or negative prices | Generator withdrawal, demand distortion | Price caps, emergency dispatch, bilateral contracts |
| Interconnector loss | Subsea cable failure, political action | Loss of import/export capacity, frequency deviation | Reserve activation, demand reduction, re-routing via other interconnectors |

---

## 6. Problem-Solver Agent Toolbox

The problem-solver agent needs a defined set of actions it can take. Based on real TSO/DSO operations:

### 6.1 Supply-Side Actions
- Activate spinning reserve
- Ramp dispatchable generation (gas, hydro)
- Dispatch BESS (charge/discharge)
- Activate pumped hydro
- Request emergency interconnector flows
- Curtail renewable generation (last resort)
- Black-start sequence (post-blackout)

### 6.2 Demand-Side Actions
- Activate demand response contracts (industrial, commercial)
- Send dynamic price signals (ToU adjustment)
- Voltage reduction (conservation voltage reduction, ~2–5% demand reduction)
- Rolling blackouts / load shedding (last resort)
- Smart charging override for EVs
- Heat pump pre-heating/cooling to shift load

### 6.3 Network Actions
- Redispatch generation
- Topology switching (open/close breakers)
- Dynamic line rating activation
- Transformer tap changing
- Islanding of microgrids
- Emergency interconnector re-routing

### 6.4 Market Actions
- Activate balancing market
- Call emergency reserve tenders
- Implement price caps
- Cross-zone trading adjustments

---

## 7. Gaps & Original Contributions

What the proposed project adds beyond existing work:

1. **Crisis Agent:** No existing framework has an adversarial agent that injects realistic, multi-dimensional crisis scenarios into a running simulation. ASSUME and others test static scenarios.
2. **Problem-Solver Agent:** A dedicated agentic layer that detects crises, evaluates options from a constrained toolbox, and acts. This could use RL, LLM reasoning, or rule-based approaches.
3. **TSO-DSO coordination as first-class simulation logic:** Most frameworks model either transmission or distribution. The proposed system models the communication and decision-making interface between TSO and DSO during crises.
4. **Multi-zone energy trading under stress:** Existing frameworks model trading in normal conditions. The proposed system tests how trading patterns change, break, or adapt under crisis conditions.
5. **Unified environment:** Bringing together generation physics, storage dynamics, demand profiles, grid constraints, market mechanisms, and crisis management into one simulation environment.

---

## 8. Recommended Architecture Approach

Based on the research, the recommended approach is:

1. **Data layer:** Use ENTSO-E Transparency Platform + OPSD + PyPSA-Eur datasets for realistic European grid topology, generation mix, and demand profiles. Simplify to a manageable number of zones (e.g., 5–10 representing different energy mixes).

2. **Simulation engine:** Build in Python. Consider using ASSUME's architecture as a reference (agent-based, modular) but design a simpler, purpose-built engine focused on the crisis/response loop rather than full market clearing.

3. **Agent framework:** Use an LLM-based or RL-based agent framework. The crisis agent generates scenarios; the problem-solver agent reasons about responses.

4. **Time resolution:** Hourly for market/energy balance, sub-hourly (5-minute or 1-minute) for crisis response dynamics.

5. **Iterative build:** Start with a minimal viable simulation (2–3 zones, 3–4 generation types, 1 storage type, simple demand curve) and add complexity incrementally.

---

## References & Links

- ASSUME Framework: https://github.com/assume-framework/assume
- ASSUME Docs: https://assume.readthedocs.io/
- PyPSA-Eur: https://github.com/PyPSA/pypsa-eur
- ENTSO-E Transparency Platform: https://transparency.entsoe.eu/
- Open Power System Data: https://open-power-system-data.org/
- Renewables.ninja: https://www.renewables.ninja/
- Open Energy System Models (Wikipedia): https://en.wikipedia.org/wiki/Open_energy_system_models
- Open Energy System Databases (Wikipedia): https://en.wikipedia.org/wiki/Open_energy_system_databases
- INTERPLAN Methodology: https://www.sciencedirect.com/science/article/abs/pii/S0378779622005879
- TSO-DSO Coordination Assessment (2025): https://link.springer.com/article/10.1007/s40518-025-00269-6
- Denmark MABS Study: https://www.mdpi.com/2079-9292/14/20/4001
- Sienna (NREL): https://nrel.gov/news/program/2021/nrel-open-source-modeling-approach-cracks-the-code-of-simulating-low-inertia-power-systems.html
- SCooDER (LBNL): https://github.com/LBNL-ETA/SCooDER
- Building Energy Storage Sim: https://github.com/tobirohrer/building-energy-storage-simulation
- ACM SIGENERGY Resources: https://energy.acm.org/resources/
