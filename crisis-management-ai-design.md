# Crisis Management AI — System Design Document

**Status:** Draft v0.1
**Audience:** Internal team
**Purpose:** High-level design specification for the Crisis Management AI simulation, with TODOs flagged for team resolution.

---

## Overview

This document outlines the design for a multi-agent Crisis Management AI operating within a simulated energy trade environment. The system is composed of **Zone Governor Agents** — LLM-powered agents that independently manage individual zones — and an adversarial **Crisis Agent** that introduces disruptions to stress the system. The overarching goal is a resilient, observable simulation in which Governor AIs must detect, reason about, and survive crises in real time.

The simulation is divided into two phases:
- **Phase 1** covers the environment: energy resources, stability mechanics, trade, zone actions, and the tick system.
- **Phase 2** covers the agents: the Governor AI design and the Crisis Agent design.

---

## Phase 1: Environment Design

### 1.1 Energy Resources & Zone Variables

Each zone is defined by a set of environment variables describing its energy profile.

**Energy Sources**

Each zone contains one or more energy sources (e.g., solar, hydro, fossil fuel, nuclear, wind). Each source has the following properties:

- **Type** — The category of energy it produces.
- **Output Rate** — Energy generated per tick (e.g., `solar_gain = base_solar × weather_modifier`).
- **Dependencies** — Conditions required for the source to function (e.g., solar requires sunlight hours; hydro requires water level).
- **Resilience** — A fragility score expressing how vulnerable the source is to crisis events.
- **Capacity** — The maximum energy output ceiling.

**Storage**

Each zone maintains an energy storage pool with:
- `storage_capacity` — Maximum storable energy.
- `stored_energy` — Current energy level (never exceeds capacity).

**Energy Demand**

Each zone has an energy demand that is consumed each tick:
- `base_demand` — Baseline consumption under normal conditions.
- `demand_modifier` — A multiplier adjusted by events such as population spikes or seasonal shifts.

> **TODO:** Define the full taxonomy of energy source types and their dependency parameters. Specify whether `base_demand` is static per zone or dynamically calculated over time.

---

### 1.2 State Monitoring & Stability Thresholds

Zone stability is tracked continuously using the following core equations:

```
Net Energy per Tick    = Energy Gain per Tick − Energy Loss per Tick

Energy Gain per Tick   = Σ(active_source_outputs) + Σ(incoming_trade_energy)
Energy Loss per Tick   = base_demand × demand_modifier + Σ(outgoing_trade_energy)

Projected Depletion    = stored_energy / |Net Energy per Tick|   [when Net < 0]
```

**Stability States**

| State     | Condition                                              | Severity |
|-----------|--------------------------------------------------------|----------|
| Stable    | Net ≥ 0 and `stored_energy` > `low_threshold`         | Normal   |
| Warning   | Net < 0 but Projected Depletion > `warning_window`    | Low      |
| Critical  | Projected Depletion ≤ `critical_window`               | High     |
| Collapsed | `stored_energy` ≤ 0                                   | Terminal |

> **TODO:** Define exact values for `low_threshold`, `warning_window`, and `critical_window`. Determine whether collapse triggers zone elimination or a recovery mechanic (e.g., emergency aid from other zones).

---

### 1.3 Trade System

Trade routes allow zones to exchange energy. The system must handle route negotiation, active energy flow, and failure states end-to-end.

**Route Properties**

Each trade route is characterized by:
- `source_zone` / `target_zone`
- `energy_type` — The type of energy being transferred (must match or be converted).
- `transfer_rate` — Energy units moved per tick.
- `route_health` — Route integrity on a 0–100 scale; degraded routes transfer proportionally less.
- `latency` — Number of ticks before energy arrives after a route is established.

**Trade Mechanics**

1. A zone initiates a trade request specifying energy type, requested amount, and duration.
2. The receiving zone accepts or declines based on its own surplus and current stability state.
3. Upon agreement, the route is established and energy flows automatically each tick.
4. Routes can be damaged by crises, reducing `route_health` and transfer rate until repaired.

> **TODO:** Define the negotiation protocol between Governor Agents — broadcast request vs. peer-to-peer. Specify whether energy type conversion is allowed and at what efficiency cost. Define the maximum number of concurrent trade routes per zone.

---

### 1.4 Zone Actions

Governor Agents can execute the following actions each tick:

| Action | Description |
|--------|-------------|
| `open_trade_route(target, type, rate)` | Initiate a trade request with another zone. |
| `close_trade_route(route_id)` | Terminate an existing trade route. |
| `ration_energy(level)` | Reduce zone demand by a percentage; may impact zone output or "health." |
| `upgrade_storage(amount)` | Expand storage capacity at an energy or resource cost. |
| `boost_source(source_id)` | Temporarily increase output of an energy source beyond its base rate. |
| `repair_route(route_id)` | Restore `route_health` on a damaged trade route. |
| `emergency_broadcast(message)` | Alert neighboring Governor Agents of a critical state. |

> **TODO:** Define the cost (energy, ticks, cooldown) for each action. Specify whether actions are instantaneous or resolve over multiple ticks. Define the tool-calling schema that exposes these actions to the LLM Governor Agents.

---

### 1.5 Crisis Events

The Crisis Agent periodically injects events that stress zones and trade networks. Crises fall into three broad categories:

**Supply Disruptions**
- A natural disaster reduces solar or wind gain for a zone over N ticks.
- An infrastructure failure shuts down a source entirely until repaired.
- A fuel shortage reduces fossil fuel output by a percentage.

**Demand Spikes**
- A sudden population surge or industrial event raises `demand_modifier`.
- A cold snap or heat wave elevates consumption for a fixed duration.

**Trade Route Attacks**
- A route is damaged, reducing `route_health` and transfer rate.
- A route is severed entirely, requiring zones to renegotiate.

**Cascading Failures**
- A zone collapse reduces energy availability for dependent connected zones, potentially triggering chain reactions.

> **TODO:** Define crisis severity levels and the frequency of injection per tick interval. Determine whether the Crisis Agent has full or partial visibility of all zones. Specify whether crises are drawn from a pre-scripted library, procedurally generated, or synthesized via LLM reasoning.

---

### 1.6 Game Time Tick System

The simulation runs on a discrete tick system that drives all state changes.

**Tick Execution Order (each tick):**

1. Energy sources produce their output for the tick.
2. Active trade routes transfer energy between zones.
3. Zone demand is consumed from each zone's `stored_energy`.
4. Stability metrics are recalculated for all zones.
5. Governor Agents observe their current state and select actions.
6. The Crisis Agent evaluates the global state and optionally injects an event.
7. All pending actions are resolved and state updates are committed.

> **TODO:** Define the tick duration and total simulation length. Determine whether Governor Agents act synchronously (all zones resolve at once) or sequentially. Specify the real-time clock mapping (e.g., 1 tick = 1 second of wall time, or tick-on-demand for testing).

---

## Phase 2: Agent Design

### 2.1 Zone Governor Agents (Multi-Agent System)

Each zone is managed by an independent **LLM-powered Governor Agent**. Agents operate autonomously over the deterministic board state using a structured tool-calling interface.

**Agent Inputs (Observation Space)**

Each tick, a Governor Agent receives:
- Current `stored_energy`, `energy_gain_per_tick`, `energy_loss_per_tick`.
- Stability state and projected depletion time.
- Active trade routes and their current health.
- Recent crisis events affecting this zone.
- Incoming messages or emergency broadcasts from neighboring agents.

**Agent Reasoning Loop (per tick)**

1. **Observe** — Read current telemetry and zone state.
2. **Assess** — Identify stability state; flag incoming deficits or emerging threats.
3. **Plan** — Generate a prioritized list of actions to address issues.
4. **Act** — Execute actions via the available tool interface.
5. **Report** — Optionally broadcast status to neighboring agents.

**Agent Objectives (in priority order)**

1. Prevent collapse (`stored_energy` must remain above zero).
2. Maintain stability (Net Energy per Tick ≥ 0).
3. Build surplus (maximize `stored_energy` buffer where possible).
4. Cooperate with neighbors when surplus allows.

> **TODO:** Write the system prompt and zone persona for Governor Agents. Specify the exact tool schema exposed via LLM tool-calling. Define the inter-agent communication protocol (shared memory, message passing, or broadcast channel). Determine how agents handle conflicting or competing trade requests.

---

### 2.2 Crisis Agent

The Crisis Agent is an adversarial LLM agent that monitors the simulation and injects crises to maximize systemic stress.

**Agent Inputs**

- Zone-by-zone stability state (full or partial visibility — TBD).
- History of past crises and observed Governor Agent responses.
- Current tick number and simulation phase.

**Crisis Injection Strategy**

The Crisis Agent is designed to adapt its behavior based on the simulation state:
- Target zones showing strong recovery or high surplus to prevent dominance.
- Chain crises to exploit dependencies (e.g., damage a trade route immediately after a demand spike).
- Vary crisis types and timing to prevent Governor Agents from pattern-matching predictable sequences.

**Constraints**

- Crisis injection is rate-limited (e.g., maximum N events per tick interval).
- Certain crisis types have a cooldown period before they can be reused.

> **TODO:** Define the Crisis Agent's objective function — maximize total collapses, maximize cumulative instability duration, or some other metric. Specify whether it operates with full or partial observability. Determine whether it draws from a fixed crisis library or generates novel events via LLM reasoning.

---

## Open Questions & Next Steps

| # | Question | Priority |
|---|----------|----------|
| 1 | Finalize energy source taxonomy and dependency parameters | High |
| 2 | Define stability threshold values (`low_threshold`, `warning_window`, `critical_window`) | High |
| 3 | Design Governor Agent system prompt and tool-calling schema | High |
| 4 | Specify trade negotiation protocol (broadcast vs. peer-to-peer) | High |
| 5 | Define action costs, resolution timing, and cooldowns | Medium |
| 6 | Define crisis severity levels and injection frequency | Medium |
| 7 | Finalize tick duration and real-time clock mapping | Medium |
| 8 | Define Crisis Agent observability scope and objective function | Medium |
| 9 | Design inter-agent communication architecture | Medium |
| 10 | Determine zone collapse behavior (elimination vs. recovery) | Medium |
