"""
run_ai_demo.py — Phase 2: LangGraph Multi-Agent Governor Demo.
 
Replaces the hardcoded governor actions in run_demo.py with autonomous
AI agents that observe, plan, assess risk, and act each tick.
 
Three zones, same crisis schedule as run_demo.py, but now governed by:
  • Supervisor Agent     — orchestrates the tick cycle
  • Situation Awareness  — analyzes telemetry + messages
  • Planning Agent       — drafts action lists (JSON)
  • Risk Assessment      — approves or rejects plans (with retry loop)
  • Report Agent         — explains AI behavior in the console
  • Communication Agent  — handles incoming trade offers diplomatically
 
Prerequisites:
  pip install langgraph langchain-anthropic langchain-core
  export ANTHROPIC_API_KEY="sk-ant-..."
 
Run with:
  python run_ai_demo.py
 
Optional flags:
  --ticks N       Number of ticks to run (default: 25)
  --zones alpha   Comma-separated list of zones to enable AI for (default: all)
  --model NAME    Anthropic model to use (default: claude-sonnet-4-6)
  --no-adversary  Disable the adversarial Crisis Agent
  --seed N        RNG seed for reproducibility (default: 42)
"""
 
import sys
import os
import argparse
import time
import logging
 
sys.path.insert(0, os.path.dirname(__file__))
 
# ── Simulation imports ────────────────────────────────────────────────────────
from models import (
    Zone, EnergySource, TradeRoute,
    Storage, Economy, EnergyType, StabilityState,
)
from engine import SimulationEngine
 
# ── Agent imports ─────────────────────────────────────────────────────────────
from graph import create_zone_graph
from state import make_initial_state
from crisis_agent import create_crisis_graph, make_crisis_hook
 
 
# ─────────────────────────────────────────────────────────────────────────────
# LOGGING CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
 
logging.basicConfig(
    level=logging.WARNING,
    format="%(name)s | %(levelname)s | %(message)s",
)
 
 
# ─────────────────────────────────────────────────────────────────────────────
# ZONE FACTORIES  (identical to run_demo.py)
# ─────────────────────────────────────────────────────────────────────────────
 
def make_zone_alpha() -> Zone:
    """Solar + wind zone in the north. High variability, exports to Gamma."""
    return Zone(
        zone_id="alpha",
        name="Alpha",
        sources=[
            EnergySource(
                source_id="alpha_solar",
                energy_type=EnergyType.SOLAR,
                low_output_rate=40.0, high_output_rate=100.0,
                resilience=0.4, degradation_rate=0.003,
            ),
            EnergySource(
                source_id="alpha_wind",
                energy_type=EnergyType.WIND,
                low_output_rate=20.0, high_output_rate=40.0,
                resilience=0.7, degradation_rate=0.001,
            ),
        ],
        storage=Storage(capacity=800.0, stored_energy=250.0),
        economy=Economy(budget_per_tick=18.0, budget=50.0),
        base_demand=52.0,
        region="north",
        morale=85.0, reputation=90.0,
    )
 
 
def make_zone_beta() -> Zone:
    """Hydro zone in the north. Reliable but drought-sensitive."""
    return Zone(
        zone_id="beta",
        name="Beta",
        sources=[
            EnergySource(
                source_id="beta_hydro",
                energy_type=EnergyType.HYDRO,
                low_output_rate=80.0, high_output_rate=100.0,
                resilience=0.9, degradation_rate=0.001,
            ),
        ],
        storage=Storage(capacity=600.0, stored_energy=190.0),
        economy=Economy(budget_per_tick=18.0, budget=50.0),
        base_demand=65.0,
        region="north",
        morale=90.0, reputation=95.0,
    )
 
 
def make_zone_gamma() -> Zone:
    """Fossil zone in the south. Demand-heavy — must import from neighbours."""
    return Zone(
        zone_id="gamma",
        name="Gamma",
        sources=[
            EnergySource(
                source_id="gamma_fossil",
                energy_type=EnergyType.FOSSIL,
                low_output_rate=35.0, high_output_rate=50.0,
                resilience=0.6, degradation_rate=0.002,
            ),
        ],
        storage=Storage(capacity=500.0, stored_energy=150.0),
        economy=Economy(budget_per_tick=18.0, budget=50.0),
        base_demand=88.0,
        region="south",
        morale=80.0, reputation=85.0,
    )
 
 
def make_routes():
    return [
        TradeRoute(
            route_id="route_alpha_gamma",
            source_zone_id="alpha", target_zone_id="gamma",
            energy_type=EnergyType.SOLAR,
            transfer_rate=30.0, latency=1,
            route_health=100.0, transmission_efficiency=0.90,
        ),
        TradeRoute(
            route_id="route_beta_gamma",
            source_zone_id="beta", target_zone_id="gamma",
            energy_type=EnergyType.HYDRO,
            transfer_rate=25.0, latency=1,
            route_health=100.0, transmission_efficiency=0.90,
        ),
    ]
 
 

# ─────────────────────────────────────────────────────────────────────────────
# GOVERNOR HOOK FACTORY
# ─────────────────────────────────────────────────────────────────────────────
 
def make_governor_hook(zone_graphs: dict, timing_log: list, ai_zone_ids: set):
    """
    Build the governor_hook callback for engine.governor_hook.
 
    The hook is called by the engine once per non-collapsed zone per tick.
    It invokes the zone's LangGraph pipeline and records timing.
 
    Args:
        zone_graphs:  dict mapping zone_id → compiled LangGraph
        timing_log:   list to append per-tick timing records to
        ai_zone_ids:  set of zone IDs that should use AI governance
    """
    def governor_hook(engine, zone):
        if zone.zone_id not in ai_zone_ids:
            return                                   # Zone not governed by AI
 
        graph = zone_graphs.get(zone.zone_id)
        if graph is None:
            return
 
        t0          = time.perf_counter()
        init_state  = make_initial_state(zone.zone_id)
 
        try:
            final_state = graph.invoke(init_state)
        except Exception as exc:
            print(f"\n  ⚠️  [Governor] Exception in zone {zone.zone_id}: {exc}")
            logging.exception(f"Governor hook error for zone {zone.zone_id}")
            return
 
        elapsed = time.perf_counter() - t0
        timing_log.append({
            "tick":    engine.tick_number,
            "zone_id": zone.zone_id,
            "elapsed": elapsed,
            "actions": len(final_state.get("executed_results", [])),
            "skipped": final_state.get("skip_planning", False),
        })
 
    return governor_hook
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
 
def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 2: Crisis Management AI — LangGraph Multi-Agent Demo"
    )
    parser.add_argument("--ticks",     type=int,   default=25,
                        help="Number of simulation ticks (default: 25)")
    parser.add_argument("--zones",     type=str,   default="alpha,beta,gamma",
                        help="Comma-separated list of zone IDs to govern with AI")
    parser.add_argument("--model",     type=str,   default="gpt-4o-mini",
                        help="OpenAI model for LLM agents")
    parser.add_argument("--seed",      type=int,   default=42,
                        help="RNG seed for reproducibility")
    parser.add_argument("--verbose",   action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--no-adversary", action="store_true",
                        help="Disable the adversarial Crisis Agent")
    return parser.parse_args()
 
 
def main():
    args = parse_args()
 
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
 
    # Verify API key early
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("  Set it with: export OPENAI_API_KEY='sk-...'")
        sys.exit(1)
 
    print("=" * 80)
    print("  Crisis Management Simulation — Phase 2: LangGraph Multi-Agent AI")
    print(f"  Model: {args.model}  |  Ticks: {args.ticks}  |  Seed: {args.seed}")
    print("=" * 80)
 
    # ── Build simulation world ────────────────────────────────────────────
    engine              = SimulationEngine(seed=args.seed)
    engine.ticks_per_season = 6
 
    engine.add_zone(make_zone_alpha())
    engine.add_zone(make_zone_beta())
    engine.add_zone(make_zone_gamma())
    for route in make_routes():
        engine.add_trade_route(route)
 
    # All crises are now dynamically injected by the adversarial Crisis Agent.
    print("\n  No pre-scheduled crises — Crisis Agent will inject all events dynamically.")
 
    # ── Build AI agent graphs ─────────────────────────────────────────────
    ai_zone_ids = set(z.strip() for z in args.zones.split(","))
    print(f"\n  Building AI governor graphs for zones: {sorted(ai_zone_ids)}")
 
    zone_graphs = {}
    for zone_id in ai_zone_ids:
        if zone_id not in engine.zones:
            print(f"  WARNING: zone '{zone_id}' not found in engine — skipping")
            continue
        print(f"    • Zone '{zone_id}' → create_zone_graph(model={args.model})")
        zone_graphs[zone_id] = create_zone_graph(
            engine, zone_id, llm_model=args.model
        )
 
    print(f"\n  {len(zone_graphs)} governor graph(s) compiled.")
 
    # ── Wire governor hook into engine ────────────────────────────────────
    timing_log            = []
    engine.governor_hook  = make_governor_hook(zone_graphs, timing_log, ai_zone_ids)

    # ── Wire adversarial Crisis Agent into engine ───────────────────────────
    if not getattr(args, 'no_adversary', False):
        print(f'\n  Building adversarial Crisis Agent (model={args.model})')
        crisis_graph       = create_crisis_graph(engine, llm_model=args.model)
        engine.crisis_hook = make_crisis_hook(crisis_graph)
        print('  Crisis Agent compiled and wired into engine.crisis_hook.')
    else:
        print('\n  Adversarial Crisis Agent DISABLED (--no-adversary).')

    # ── Print initial world state ─────────────────────────────────────────
    print("\n  Initial state:")
    engine.print_status()
 
    # ── Main simulation loop ──────────────────────────────────────────────
    print(f"\n{'═' * 80}")
    print(f"  Starting {args.ticks}-tick simulation with AI governors...")
    print(f"{'═' * 80}\n")
 
    for _ in range(args.ticks):
        # Engine.tick() handles the full physics step, then calls governor_hook
        # for each zone (which runs the LangGraph pipeline), then crisis_hook.
        engine.tick()
 
        # Print engine's own status summary after this tick
        engine.print_status()
 
        # Show engine event log entries for this tick
        tick_logs = [
            e["message"]
            for e in engine.event_log
            if e["tick"] == engine.tick_number
        ]
        for msg in tick_logs:
            print(f"  LOG: {msg}")
        if tick_logs:
            print()

        # Collapse check: exit early if any zone runs out of energy
        collapsed = [
            z for z in engine.zones.values()
            if z.stability_state == StabilityState.COLLAPSED
        ]
        if collapsed:
            names = ', '.join(z.name for z in collapsed)
            print(f"\n{'=' * 80}")
            print(f"  GAME OVER -- Zone(s) COLLAPSED: {names}")
            print(f"{'=' * 80}\n")
            break
 
    # ── Timing summary ────────────────────────────────────────────────────
    if timing_log:
        print(f"\n{'─' * 80}")
        print("  GOVERNOR TIMING SUMMARY")
        print(f"{'─' * 80}")
        print(f"  {'Tick':>5}  {'Zone':<8}  {'Actions':>7}  {'Skipped':>8}  {'Time (s)':>10}")
        print(f"  {'─'*5}  {'─'*8}  {'─'*7}  {'─'*8}  {'─'*10}")
 
        total_elapsed = 0.0
        total_actions = 0
        for rec in timing_log:
            skip_flag = "✓" if rec["skipped"] else " "
            print(
                f"  {rec['tick']:>5}  {rec['zone_id']:<8}  "
                f"{rec['actions']:>7}  {skip_flag:>8}  {rec['elapsed']:>9.2f}s"
            )
            total_elapsed += rec["elapsed"]
            total_actions += rec["actions"]
 
        print(f"  {'─'*5}  {'─'*8}  {'─'*7}  {'─'*8}  {'─'*10}")
        print(f"  {'TOTAL':>5}  {'':8}  {total_actions:>7}  {'':8}  {total_elapsed:>9.2f}s")
        avg = total_elapsed / len(timing_log) if timing_log else 0
        print(f"\n  Average latency per governor call: {avg:.2f}s")
        print(f"  Total AI actions executed: {total_actions}")
 
    print(f"\n{'═' * 80}")
    print("  Simulation complete.")
    print(f"{'═' * 80}\n")
 
 
if __name__ == "__main__":
    main()