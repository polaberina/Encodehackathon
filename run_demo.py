"""
run_demo.py — Extended demo showcasing all v3 features.
 
Scenario (25 ticks, season length 6 = nearly a full year):
  Three zones across two regions:
    Alpha (solar + wind) — region "north"
    Beta  (hydro)        — region "north"
    Gamma (fossil)       — region "south"
 
  Crises scheduled via schedule_crisis (all with early warnings):
    Tick  3: Equipment failure on Alpha solar
    Tick  5: Drought hits Beta (hydro at 40% for 6 ticks)
    Tick  7: Political embargo freezes Beta->Gamma route for 4 ticks
    Tick  9: Cyber attack on Gamma (readings corrupted for 3 ticks)
    Tick 11: Heat wave in Gamma (demand +25%, solar at 80%)
    Tick 13: Worker strike on Alpha wind (at 50%)
    Tick 15: Storage leak in Beta (3%/tick for 5 ticks)
    Tick 17: Wildfire: Alpha solar at 30%, Alpha->Gamma route -8 health/tick
    Tick 19: Regional blackout across "north" (Alpha + Beta demand +50%)
    Tick 22: Economic recession in Gamma (income at 65% for 4 ticks)
    Tick 23: Transmission surge on Beta (20% efficiency loss for 3 ticks)
 
  Governor actions (hardcoded to demonstrate every action and both new systems):
    Tick  4: fortify_route + deploy_emergency_generator + repair_source
             (queued with latency -- effects land 1-2 ticks later)
    Tick  6: issue_conservation_order + monitor_zone
    Tick  8: sell_surplus + request_aid + emergency_broadcast
    Tick 10: emergency_broadcast + boost_source + ration_energy
    Tick 12: settle_worker_strike + build_new_route + invest_in_efficiency
 
  NEW -- Trade offer system (tick 14-15):
    Tick 14: Alpha proposes a trade to Gamma (60 energy for 80 budget)
             Beta proposes a counter-offer to Alpha (50 energy for 40 budget)
    Tick 15: Gamma accepts Alpha's offer (settlement arrives tick 16)
             Alpha rejects Beta's offer
 
  Continued governor actions:
    Tick 16: set_export_cap + repair_route + upgrade_storage
    Tick 20: open_trade_route + set_export_cap (remove) + upgrade_storage
 
Run with:  python run_demo.py
"""
 
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
 
from models import (
    Zone, EnergySource, TradeRoute, CrisisEvent,
    Storage, Economy, EnergyType, CrisisType
)
from engine import SimulationEngine
 
 
 
def make_zone_alpha() -> Zone:
    """Solar + wind zone in the north. High variability, exports to Gamma."""
    solar = EnergySource(
        source_id="alpha_solar",
        energy_type=EnergyType.SOLAR,
        low_output_rate=40.0,
        high_output_rate=100.0,
        resilience=0.4,
        degradation_rate=0.003,
    )
    wind = EnergySource(
        source_id="alpha_wind",
        energy_type=EnergyType.WIND,
        low_output_rate=20.0,
        high_output_rate=40.0,
        resilience=0.7,
        degradation_rate=0.001,
    )
    return Zone(
        zone_id="alpha",
        name="Alpha",
        sources=[solar, wind],
        storage=Storage(capacity=800.0, stored_energy=400.0),
        economy=Economy(budget_per_tick=100.0, budget=200.0),
        base_demand=40.0,
        region="north",
        morale=85.0,
        reputation=90.0,
    )
 
 
def make_zone_beta() -> Zone:
    """Hydro zone in the north. Reliable but season-sensitive."""
    hydro = EnergySource(
        source_id="beta_hydro",
        energy_type=EnergyType.HYDRO,
        low_output_rate=80.0,
        high_output_rate=100.0,
        resilience=0.9,
        degradation_rate=0.001,
    )
    return Zone(
        zone_id="beta",
        name="Beta",
        sources=[hydro],
        storage=Storage(capacity=600.0, stored_energy=300.0),
        economy=Economy(budget_per_tick=100.0, budget=200.0),
        base_demand=50.0,
        region="north",
        morale=90.0,
        reputation=95.0,
    )
 
 
def make_zone_gamma() -> Zone:
    """Fossil zone in the south. Demand exceeds local production — must import."""
    fossil = EnergySource(
        source_id="gamma_fossil",
        energy_type=EnergyType.FOSSIL,
        low_output_rate=35.0,
        high_output_rate=50.0,
        resilience=0.6,
        degradation_rate=0.002,
    )
    return Zone(
        zone_id="gamma",
        name="Gamma",
        sources=[fossil],
        storage=Storage(capacity=500.0, stored_energy=250.0),
        economy=Economy(budget_per_tick=100.0, budget=200.0),
        base_demand=70.0,
        region="south",
        morale=80.0,
        reputation=85.0,
    )


def make_zone_delta() -> Zone:
    """Nuclear baseline zone in the east. Stable output, resilience-focused."""
    nuclear = EnergySource(
        source_id="delta_nuclear",
        energy_type=EnergyType.NUCLEAR,
        low_output_rate=90.0,
        high_output_rate=120.0,
        resilience=0.95,
        degradation_rate=0.0005,
    )
    return Zone(
        zone_id="delta",
        name="Delta",
        sources=[nuclear],
        storage=Storage(capacity=700.0, stored_energy=350.0),
        economy=Economy(budget_per_tick=100.0, budget=200.0),
        base_demand=60.0,
        region="south",
        morale=88.0,
        reputation=92.0,
    )
 
 
# ─────────────────────────────────────────────
# TRADE ROUTES
# ─────────────────────────────────────────────
 
def make_routes():
    return [
        TradeRoute(
            route_id="route_alpha_gamma",
            source_zone_id="alpha",
            target_zone_id="gamma",
            energy_type=EnergyType.SOLAR,
            transfer_rate=30.0,
            latency=1,
            route_health=100.0,
            transmission_efficiency=0.90,
        ),
        TradeRoute(
            route_id="route_beta_gamma",
            source_zone_id="beta",
            target_zone_id="gamma",
            energy_type=EnergyType.HYDRO,
            transfer_rate=25.0,
            latency=1,
            route_health=100.0,
            transmission_efficiency=0.90,
        ),
    ]
 
 
# ─────────────────────────────────────────────
# CRISIS PARAMETER CONSTANTS
# Adjust these to tune difficulty. Values are designed to be challenging
# but survivable — no single crisis should be impossible to recover from.
# ─────────────────────────────────────────────
 
# DROUGHT: fraction of hydro output that remains (0.0–1.0)
DROUGHT_OUTPUT_MODIFIER       = 0.40   # 60% reduction (was 0.20 / 80%)
 
# HEAT WAVE: demand multiplier and solar efficiency during overheating
HEAT_WAVE_DEMAND_MODIFIER     = 1.25   # +25% demand (was 1.40 / +40%)
HEAT_WAVE_SOLAR_MODIFIER      = 0.80   # solar at 80% (was 0.70 / 70%)
 
# WORKER STRIKE: fraction of source output that remains during strike
WORKER_STRIKE_OUTPUT_MODIFIER = 0.50   # 50% reduction (was 0.25 / 75%)
 
# STORAGE LEAK: fraction of stored energy lost per tick
STORAGE_LEAK_RATE             = 0.03   # 3%/tick drain (was 0.04 / 4%)
 
# WILDFIRE: source output fraction + route damage per tick
WILDFIRE_OUTPUT_MODIFIER      = 0.30   # source at 30% (was 0.10 / 10%)
WILDFIRE_ROUTE_DAMAGE_PER_TICK = 8.0   # route health lost/tick (was 15.0)
 
# REGIONAL BLACKOUT: demand spike across the affected region
REGIONAL_BLACKOUT_DEMAND_MODIFIER = 1.50  # +50% demand (was 1.80 / +80%)
 
# ECONOMIC RECESSION: fraction of normal budget income earned
RECESSION_INCOME_MODIFIER     = 0.65   # 35% income cut (was 0.50 / 50%)
 
# TRANSMISSION SURGE: efficiency points lost on all routes in/out of zone
TRANSMISSION_SURGE_EFFICIENCY_REDUCTION = 0.20  # 20% loss (was 0.35 / 35%)
 
 
# ─────────────────────────────────────────────
# CRISIS FACTORY FUNCTIONS
# ─────────────────────────────────────────────
 
def c_equipment_failure():
    return CrisisEvent(
        crisis_id="c001", crisis_type=CrisisType.EQUIPMENT_FAILURE,
        target_id="alpha", duration=3, remaining_ticks=3,
        parameters={"source_id": "alpha_solar"},
        description="Alpha solar array offline (equipment failure)",
    )
 
def c_drought():
    return CrisisEvent(
        crisis_id="c002", crisis_type=CrisisType.DROUGHT,
        target_id="beta", duration=6, remaining_ticks=6,
        parameters={"output_modifier": DROUGHT_OUTPUT_MODIFIER},
        description=f"Drought: Beta hydro at {int(DROUGHT_OUTPUT_MODIFIER*100)}% for 6 ticks",
    )
 
def c_embargo():
    return CrisisEvent(
        crisis_id="c003", crisis_type=CrisisType.POLITICAL_EMBARGO,
        target_id="route_beta_gamma", duration=4, remaining_ticks=4,
        parameters={"route_id": "route_beta_gamma"},
        description="Political embargo: Beta->Gamma route frozen",
    )
 
def c_cyber_attack():
    return CrisisEvent(
        crisis_id="c004", crisis_type=CrisisType.CYBER_ATTACK,
        target_id="gamma", duration=3, remaining_ticks=3,
        parameters={},
        description="Gamma control systems hacked -- readings corrupted",
    )
 
def c_heat_wave():
    return CrisisEvent(
        crisis_id="c005", crisis_type=CrisisType.HEAT_WAVE,
        target_id="gamma", duration=4, remaining_ticks=4,
        parameters={
            "demand_modifier":    HEAT_WAVE_DEMAND_MODIFIER,
            "solar_output_modifier": HEAT_WAVE_SOLAR_MODIFIER,
        },
        description=(
            f"Heat wave: Gamma demand +{int((HEAT_WAVE_DEMAND_MODIFIER-1)*100)}%, "
            f"solar at {int(HEAT_WAVE_SOLAR_MODIFIER*100)}%"
        ),
    )
 
def c_worker_strike():
    return CrisisEvent(
        crisis_id="c006", crisis_type=CrisisType.WORKER_STRIKE,
        target_id="alpha", duration=6, remaining_ticks=6,
        parameters={"source_id": "alpha_wind", "output_modifier": WORKER_STRIKE_OUTPUT_MODIFIER},
        description=f"Wind farm strike: Alpha wind at {int(WORKER_STRIKE_OUTPUT_MODIFIER*100)}%",
    )
 
def c_storage_leak():
    return CrisisEvent(
        crisis_id="c007", crisis_type=CrisisType.STORAGE_LEAK,
        target_id="beta", duration=5, remaining_ticks=5,
        parameters={"leak_rate": STORAGE_LEAK_RATE},
        description=f"Beta storage breach: {int(STORAGE_LEAK_RATE*100)}% drain per tick",
    )
 
def c_wildfire():
    return CrisisEvent(
        crisis_id="c008", crisis_type=CrisisType.WILDFIRE,
        target_id="alpha", duration=4, remaining_ticks=4,
        parameters={
            "source_id": "alpha_solar",
            "output_modifier": WILDFIRE_OUTPUT_MODIFIER,
            "route_id": "route_alpha_gamma",
            "route_damage_per_tick": WILDFIRE_ROUTE_DAMAGE_PER_TICK,
        },
        description=(
            f"Wildfire: Alpha solar at {int(WILDFIRE_OUTPUT_MODIFIER*100)}%, "
            f"Alpha->Gamma route takes {WILDFIRE_ROUTE_DAMAGE_PER_TICK} damage/tick"
        ),
    )
 
def c_regional_blackout():
    return CrisisEvent(
        crisis_id="c009", crisis_type=CrisisType.REGIONAL_BLACKOUT,
        target_id="north", duration=3, remaining_ticks=3,
        parameters={"region": "north", "demand_modifier": REGIONAL_BLACKOUT_DEMAND_MODIFIER},
        description=(
            f"North region blackout: "
            f"{int((REGIONAL_BLACKOUT_DEMAND_MODIFIER-1)*100)}% demand surge in Alpha + Beta"
        ),
    )
 
def c_recession():
    return CrisisEvent(
        crisis_id="c010", crisis_type=CrisisType.ECONOMIC_RECESSION,
        target_id="gamma", duration=4, remaining_ticks=4,
        parameters={"income_modifier": RECESSION_INCOME_MODIFIER},
        description=f"Economic recession: Gamma income at {int(RECESSION_INCOME_MODIFIER*100)}%",
    )
 
def c_transmission_surge():
    return CrisisEvent(
        crisis_id="c011", crisis_type=CrisisType.TRANSMISSION_SURGE,
        target_id="beta", duration=3, remaining_ticks=3,
        parameters={"efficiency_reduction": TRANSMISSION_SURGE_EFFICIENCY_REDUCTION},
        description=(
            f"Transmission surge: all Beta routes lose "
            f"{int(TRANSMISSION_SURGE_EFFICIENCY_REDUCTION*100)}% efficiency"
        ),
    )
 
 
# ─────────────────────────────────────────────
# GOVERNOR ACTION HANDLERS
# ─────────────────────────────────────────────
 
def _actions_tick4(e):
    """Alpha fortifies its route + deploys emergency gen + repairs solar."""
    print("    Alpha: fortifying route to Gamma (pre-emptive hardening)")
    print(f"    fortify_route -> {e.action_fortify_route('alpha', 'route_alpha_gamma')}")
 
    print("    Alpha: deploying emergency generator (solar is offline)")
    print(f"    deploy_emergency_generator -> "
          f"{e.action_deploy_emergency_generator('alpha', output_rate=25.0, duration=5)}")
 
    print("    Alpha: sending repair crew to solar array")
    print(f"    repair_source -> {e.action_repair_source('alpha', 'alpha_solar')}")
 
 
def _actions_tick6(e):
    """Beta issues conservation order; Alpha purchases monitoring of Beta."""
    print("    Beta: issuing conservation order (30% demand cut, morale cost)")
    print(f"    issue_conservation_order -> "
          f"{e.action_issue_conservation_order('beta', reduction_pct=0.30)}")
 
    print("    Alpha: purchasing monitoring access to Beta for 6 ticks")
    print(f"    monitor_zone -> {e.action_monitor_zone('alpha', 'beta', duration=6)}")
 
    obs = e.get_zone_state("beta", observer_zone_id="alpha")
    print(f"    Alpha's view of Beta: visibility={obs.get('visibility')}, "
          f"stored={obs.get('stored_energy'):.1f}, morale={obs.get('morale'):.1f}")
 
 
def _actions_tick8(e):
    """Beta sells surplus; Gamma requests aid from Alpha; Alpha broadcasts."""
    print("    Beta: selling 80 units of surplus to cover budget shortfall")
    print(f"    sell_surplus -> {e.action_sell_surplus('beta', amount=80.0, rate=0.50)}")
 
    print("    Gamma: requesting 50 units of emergency aid from Alpha")
    print(f"    request_aid -> {e.action_request_aid('gamma', 'alpha', amount=50.0)}")
 
    print("    Alpha: broadcasting warning about embargo")
    print(f"    emergency_broadcast -> {e.action_emergency_broadcast('alpha', 'Beta->Gamma embargoed. Route traffic via Alpha.')}")
 
 
def _actions_tick10(e):
    """Gamma broadcasts about cyber readings; Alpha boosts wind; Beta rations."""
    print("    Gamma: warning neighbours about corrupted readings")
    print(f"    emergency_broadcast -> "
          f"{e.action_emergency_broadcast('gamma', 'ALERT: Gamma readings unreliable. Do not base decisions on our data.')}")
 
    print("    Alpha: boosting wind source to compensate for lost solar exports")
    print(f"    boost_source -> "
          f"{e.action_boost_source('alpha', 'alpha_wind', boost_factor=1.8)}")
 
    print("    Beta: rationing energy to extend drought reserves")
    print(f"    ration_energy -> {e.action_ration_energy('beta', reduction_pct=0.20)}")
 
 
def _actions_tick12(e):
    """Alpha settles worker strike; Beta starts building a new route; Alpha invests."""
    print("    Alpha: settling wind worker strike (budget-intensive)")
    print(f"    settle_worker_strike -> "
          f"{e.action_settle_worker_strike('alpha', 'alpha_wind')}")
 
    print("    Beta: constructing a new direct route to Gamma (4-tick build)")
    route_id = e.action_build_new_route(
        "beta", "gamma",
        energy_type=EnergyType.HYDRO,
        transfer_rate=20.0,
        construction_ticks=4,
        transmission_efficiency=0.92,
    )
    print(f"    build_new_route -> route_id={route_id}")
 
    print("    Alpha: investing in wind efficiency (+12%)")
    print(f"    invest_in_efficiency -> "
          f"{e.action_invest_in_efficiency('alpha', 'alpha_wind', improvement_pct=0.12)}")
 
 
def _actions_tick14(e):
    """Alpha proposes a spot trade to Gamma; Beta sends a counter-offer to Alpha."""
    print("    Alpha: proposing trade to Gamma -- 60 energy in exchange for 80 budget")
    offer_id_1 = e.action_propose_trade(
        from_zone_id="alpha",
        to_zone_id="gamma",
        energy_offered=60.0,
        budget_offered=0.0,
        energy_requested=0.0,
        budget_requested=80.0,
        expires_in_ticks=3,
        description="Alpha offers 60E to Gamma in exchange for 80 credits",
    )
    print(f"    propose_trade (Alpha->Gamma) -> offer_id={offer_id_1}")
    e._demo_offer_alpha_gamma = offer_id_1   # Store for acceptance at tick 15
 
    print("    Beta: proposing trade to Alpha -- 50 energy for 40 budget")
    offer_id_2 = e.action_propose_trade(
        from_zone_id="beta",
        to_zone_id="alpha",
        energy_offered=50.0,
        budget_offered=0.0,
        energy_requested=0.0,
        budget_requested=40.0,
        expires_in_ticks=3,
        description="Beta offers 50E to Alpha in exchange for 40 credits",
    )
    print(f"    propose_trade (Beta->Alpha) -> offer_id={offer_id_2}")
    e._demo_offer_beta_alpha = offer_id_2    # Store for rejection at tick 15
 
    # Show Gamma's inbox so we can see the incoming offer
    gamma_state = e.get_zone_state("gamma")
    incoming = gamma_state.get("incoming_trade_offers", [])
    print(f"    Gamma now has {len(incoming)} incoming offer(s) to decide on")
 
 
def _actions_tick15(e):
    """Gamma accepts Alpha's offer; Alpha rejects Beta's offer."""
    # Gamma accepts the offer Alpha sent
    offer_1 = getattr(e, "_demo_offer_alpha_gamma", None)
    if offer_1:
        print(f"    Gamma: accepting Alpha's trade offer {offer_1}")
        print(f"    accept_trade -> {e.action_accept_trade('gamma', offer_1)}")
    else:
        print("    [Demo] Alpha->Gamma offer not found")
 
    # Alpha rejects Beta's offer
    offer_2 = getattr(e, "_demo_offer_beta_alpha", None)
    if offer_2:
        print(f"    Alpha: rejecting Beta's trade offer {offer_2}")
        print(f"    reject_trade -> {e.action_reject_trade('alpha', offer_2)}")
    else:
        print("    [Demo] Beta->Alpha offer not found")
 
    # Show pending actions queue to illustrate latency
    pending = e._pending_actions
    if pending:
        print(f"    Pending action queue ({len(pending)} items):")
        for a in sorted(pending, key=lambda x: x["apply_at_tick"]):
            print(
                f"      {a['action_type']:<30} | zone: {a['zone_name']:<8} "
                f"| applies tick {a['apply_at_tick']}"
            )
 
 
def _actions_tick16(e):
    """Alpha caps exports under wildfire; repairs route; Beta upgrades storage."""
    print("    Alpha: capping exports to 18/tick while storage is stressed")
    print(f"    set_export_cap -> "
          f"{e.action_set_export_cap('alpha', 'route_alpha_gamma', max_rate=18.0)}")
 
    print("    Alpha: repairing wildfire damage on route to Gamma")
    print(f"    repair_route -> "
          f"{e.action_repair_route('alpha', 'route_alpha_gamma', repair_amount=35.0)}")
 
    print("    Beta: upgrading storage capacity for drought resilience")
    print(f"    upgrade_storage -> "
          f"{e.action_upgrade_storage('beta', additional_capacity=200.0)}")
 
 
def _actions_tick20(e):
    """Alpha opens new route to Beta; removes export cap; Gamma upgrades storage."""
    print("    Alpha: opening immediate direct route to Beta")
    route_id = e.action_open_trade_route(
        "alpha", "beta",
        energy_type=EnergyType.WIND,
        transfer_rate=15.0,
        route_latency=1,
        transmission_efficiency=0.88,
    )
    print(f"    open_trade_route -> route_id={route_id}")
 
    # Remove the export cap set at tick 16 (wildfire is now over)
    for rid, route in e.trade_routes.items():
        if route.source_zone_id == "alpha" and route.target_zone_id == "gamma":
            ok = e.action_set_export_cap("alpha", rid, max_rate=None)
            print(f"    set_export_cap (remove cap) -> {ok}")
            break
 
    print("    Gamma: upgrading storage for winter resilience")
    print(f"    upgrade_storage -> "
          f"{e.action_upgrade_storage('gamma', additional_capacity=200.0)}")
 
 
# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
 
def main():
    print("=" * 80)
    print("  Crisis Management Simulation -- v3 Extended Demo")
    print("  11 crisis types | bilateral trade offers | action latency | seasons | morale")
    print("=" * 80)
 
    engine = SimulationEngine(seed=42)
    engine.ticks_per_season = 6     # 4 seasons x 6 ticks = 24-tick year
 
    engine.add_zone(make_zone_alpha())
    engine.add_zone(make_zone_beta())
    engine.add_zone(make_zone_gamma())
    engine.add_zone(make_zone_delta())
    for route in make_routes():
        engine.add_trade_route(route)
 
    # Schedule crises (early warnings auto-generated 2 ticks before each)
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
 
    governor_dispatch = {
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
 
    print("\nInitial state:")
    engine.print_status()
 
    for _ in range(25):
        engine.tick()
        engine.print_status()
 
        # Print all log entries for this tick
        tick_logs = [
            e["message"]
            for e in engine.event_log
            if e["tick"] == engine.tick_number
        ]
        for msg in tick_logs:
            print(f"  LOG: {msg}")
        if tick_logs:
            print()
 
        # Run hardcoded governor actions for this tick
        if engine.tick_number in governor_dispatch:
            print(f"  [Governor actions — tick {engine.tick_number}]")
            governor_dispatch[engine.tick_number](engine)
            print()
 
        # At tick 9 demonstrate partial observability under cyber attack
        if engine.tick_number == 9:
            import json
            print("  [Partial observability demo — Gamma under cyber attack]")
            own_view     = engine.get_zone_state("gamma")
            alpha_view   = engine.get_zone_state("gamma", observer_zone_id="alpha")
            beta_view    = engine.get_zone_state("gamma", observer_zone_id="beta")
            print(f"  Own view  (full+noisy): "
                  f"stored={own_view.get('stored_energy')}, "
                  f"demand={own_view.get('energy_demand_per_tick')}, "
                  f"cyber_attacked={own_view.get('cyber_attacked')}")
            print(f"  Alpha view  (partial):  "
                  f"stored={alpha_view.get('stored_energy')}, "
                  f"stability={alpha_view.get('stability_state')}, "
                  f"visibility={alpha_view.get('visibility')}")
            print(f"  Beta view   (minimal):  "
                  f"stability={beta_view.get('stability_state')}, "
                  f"visibility={beta_view.get('visibility')}")
            print()
 
 
if __name__ == "__main__":
    main()