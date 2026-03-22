import type { 
  SimulationState, Zone, TradeRoute, GovernorAction, TradeNegotiation, 
  EnergySource, CrisisEvent, CrisisAgentState, ZoneArchetype, CrisisType,
  GovernorActionType, CrisisTier, StabilityState
} from './simulation-types'
import { ZONE_CONFIGS, ENERGY_CONFIGS, CRISIS_MENU, ACTION_COSTS, ACTION_LATENCY } from './simulation-types'

// Deterministic seeded random for consistency
function seededRandom(seed: number): () => number {
  return () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    return seed / 0x7fffffff
  }
}

// Crisis Agent budget model from crisis_agent.py
function adversaryIncome(tick: number): number {
  if (tick <= 5) return 12
  if (tick <= 10) return 22
  if (tick <= 15) return 38
  if (tick <= 20) return 58
  return 85
}

const CRISIS_AGENT_STARTING_BUDGET = 30

export function generateZoneEnergySources(archetype: ZoneArchetype, random: () => number): EnergySource[] {
  const config = ZONE_CONFIGS[archetype]
  const sources: EnergySource[] = []

  config.primaryEnergy.forEach((type, index) => {
    const energyConfig = ENERGY_CONFIGS[type]
    const isPrimary = index === 0
    const capacityMultiplier = isPrimary ? 2.5 : 1.5
    
    const lowRate = energyConfig.baseOutput * capacityMultiplier * 0.7
    const highRate = energyConfig.baseOutput * capacityMultiplier
    
    sources.push({
      sourceId: `${archetype}_${type}_${index}`,
      type,
      lowOutputRate: lowRate,
      highOutputRate: highRate,
      resilience: type === 'nuclear' ? 0.9 : type === 'hydro' ? 0.7 : type === 'solar' ? 0.5 : 0.6,
      active: true,
      outputModifier: 1.0,
      degradationModifier: 1.0 - random() * 0.1,
      seasonalModifier: 1.0,
      currentOutput: lowRate + random() * (highRate - lowRate),
    })
  })

  return sources
}

export function generateInitialZones(random: () => number): Zone[] {
  const archetypes: ZoneArchetype[] = ['alpha', 'beta', 'gamma']
  
  return archetypes.map((archetype, i) => {
    const config = ZONE_CONFIGS[archetype]
    const energySources = generateZoneEnergySources(archetype, random)
    const totalSupply = energySources.reduce((sum, s) => sum + s.currentOutput, 0)
    
    const storageMultiplier = archetype === 'gamma' ? 1.5 : archetype === 'alpha' ? 0.8 : 1
    const maxStorage = 1000 * storageMultiplier
    const baseDemand = archetype === 'gamma' ? 180 : archetype === 'beta' ? 150 : 120
    
    const storage = maxStorage * (0.4 + random() * 0.4)
    const demand = baseDemand * (0.8 + random() * 0.4)
    const netEnergy = totalSupply - demand

    return {
      id: `zone-${i}`,
      name: config.name,
      archetype,
      strategy: config.strategy,
      description: config.description,
      region: config.region,
      position: { x: 0, y: 0 }, // Will be set by map
      storage,
      maxStorage,
      budget: 200 + random() * 100,
      budgetPerTick: 100,
      incomeModifier: 1.0,
      totalSpent: 0,
      morale: 70 + random() * 25,
      reputation: 80 + random() * 15,
      baseDemand,
      demandModifier: 1.0,
      seasonalDemandModifier: 1.0,
      energySources,
      supply: totalSupply,
      demand,
      netEnergyPerTick: netEnergy,
      projectedDepletionTicks: netEnergy < 0 ? Math.floor(storage / Math.abs(netEnergy)) : null,
      stabilityState: 'stable' as StabilityState,
      cyberAttacked: false,
      fogOfWarLevel: random() * 0.3,
      activeCrises: [],
      survivalTicks: Math.floor(random() * 50) + 50,
      crisesMitigated: Math.floor(random() * 8) + 5,
      crisesTotal: Math.floor(random() * 5) + 10,
      tradeProfitability: 60 + random() * 40,
      efficiencyScore: 75 + random() * 20,
      color: config.color,
    }
  })
}

export function generateTradeRoutes(zones: Zone[], random: () => number): TradeRoute[] {
  const routes: TradeRoute[] = []
  const connections = [
    [0, 2], // alpha -> gamma
    [1, 2], // beta -> gamma
  ]

  connections.forEach(([a, b], i) => {
    const sourceZone = zones[a]
    const targetZone = zones[b]
    
    const healthBonus = 
      (sourceZone.strategy === 'aggressive' || targetZone.strategy === 'aggressive') ? -10 :
      (sourceZone.strategy === 'defensive' && targetZone.strategy === 'defensive') ? 10 : 0

    routes.push({
      id: `route_${sourceZone.archetype}_${targetZone.archetype}`,
      sourceZoneId: zones[a].id,
      targetZoneId: zones[b].id,
      transferRate: 30 + random() * 20,
      latency: Math.floor(random() * 2) + 1,
      routeHealth: Math.min(100, Math.max(50, 70 + random() * 25 + healthBonus)),
      transmissionEfficiency: 0.85 + random() * 0.1,
      exportCap: null,
      fortification: random() * 0.3,
      isEmbargoed: false,
      currentFlow: 20 + random() * 60,
      maxCapacity: 150,
      isActive: random() > 0.1,
    })
  })

  return routes
}

// Generate crisis agent state and planned attacks
function generateCrisisAgentState(tick: number, zones: Zone[], random: () => number): CrisisAgentState {
  let budget = CRISIS_AGENT_STARTING_BUDGET
  for (let t = 1; t <= tick; t++) {
    budget += adversaryIncome(t)
  }
  
  // Simulate some spending
  const totalSpent = budget * (0.3 + random() * 0.4)
  budget -= totalSpent
  
  const incomeThisTick = adversaryIncome(tick)
  
  // Determine vulnerability ranking
  const sortedZones = [...zones].sort((a, b) => {
    const aScore = (a.storage / a.maxStorage) + (a.morale / 100) + (a.netEnergyPerTick > 0 ? 0.2 : -0.3)
    const bScore = (b.storage / b.maxStorage) + (b.morale / 100) + (b.netEnergyPerTick > 0 ? 0.2 : -0.3)
    return aScore - bScore
  })
  
  // Pick affordable crises
  const affordableCrises = Object.entries(CRISIS_MENU)
    .filter(([, c]) => c.cost <= budget)
    .sort((a, b) => b[1].cost - a[1].cost)
  
  let strategy = 'Saving budget for bigger strike'
  const plannedCrises: CrisisEvent[] = []
  
  if (affordableCrises.length > 0 && random() > 0.3) {
    const [crisisKey, crisisConfig] = affordableCrises[Math.floor(random() * Math.min(3, affordableCrises.length))]
    const targetZone = sortedZones[0]
    
    strategy = `Targeting ${targetZone.name} with ${crisisKey.replace(/_/g, ' ')}`
    
    plannedCrises.push({
      crisisId: `crisis-${tick}-${random().toString(36).slice(2, 8)}`,
      crisisType: crisisConfig.crisisType,
      targetId: targetZone.id,
      duration: crisisConfig.duration,
      remainingTicks: crisisConfig.duration,
      tier: crisisConfig.tier,
      cost: crisisConfig.cost,
      description: crisisConfig.description,
      parameters: {},
    })
  }
  
  return {
    budget,
    incomeThisTick,
    totalSpent,
    plannedCrises,
    executedCrises: plannedCrises,
    strategy,
    vulnerabilityRanking: sortedZones.map(z => z.name),
  }
}

// Generate governor actions (counter-actions to crises)
function generateGovernorActions(tick: number, zones: Zone[], crisisAgent: CrisisAgentState, random: () => number): GovernorAction[] {
  const actions: GovernorAction[] = []
  
  const actionTypes: GovernorActionType[] = [
    'boost_source', 'repair_route', 'fortify_route', 'deploy_emergency_generator',
    'issue_conservation_order', 'repair_source', 'ration_energy', 'sell_surplus'
  ]
  
  // For each zone, generate 0-2 actions
  zones.forEach(zone => {
    const numActions = Math.floor(random() * 3)
    
    for (let i = 0; i < numActions; i++) {
      const actionType = actionTypes[Math.floor(random() * actionTypes.length)]
      const cost = ACTION_COSTS[actionType]
      const latency = ACTION_LATENCY[actionType]
      
      let details = ''
      const params: Record<string, unknown> = { zone_id: zone.id }
      
      switch (actionType) {
        case 'boost_source':
          const source = zone.energySources[Math.floor(random() * zone.energySources.length)]
          details = `Boosting ${source?.type || 'solar'} output by 30%`
          params.source_id = source?.sourceId
          params.boost_factor = 1.3
          break
        case 'repair_route':
          details = `Repairing trade route (+25 health)`
          params.repair_amount = 25
          break
        case 'fortify_route':
          details = `Fortifying route (+30% damage reduction)`
          break
        case 'deploy_emergency_generator':
          details = `Deploying emergency generator (~60MW for 8 ticks)`
          params.output_rate = 60
          params.duration = 8
          break
        case 'issue_conservation_order':
          details = `Conservation order: demand -20%, morale -6`
          params.reduction_pct = 0.2
          break
        case 'repair_source':
          details = `Repairing offline ${zone.energySources[0]?.type || 'solar'} source`
          break
        case 'ration_energy':
          details = `Rationing energy: demand modifier -30%`
          params.reduction_pct = 0.3
          break
        case 'sell_surplus':
          details = `Selling surplus energy for ${Math.floor(20 + random() * 30)} credits`
          break
      }
      
      // Check if it's a response to a crisis
      const isCounterAction = crisisAgent.executedCrises.some(c => c.targetId === zone.id)
      if (isCounterAction) {
        details = `[COUNTER] ${details}`
      }
      
      actions.push({
        id: `action-${tick}-${zone.archetype}-${i}`,
        agentId: `agent-${zone.archetype}`,
        zoneName: zone.name,
        type: actionType,
        cost,
        latency,
        details,
        tick: tick - Math.floor(random() * 2),
        timestamp: Date.now() - random() * 30000,
        status: random() > 0.2 ? 'completed' : random() > 0.5 ? 'executing' : 'pending',
        params,
      })
    }
  })
  
  return actions.sort((a, b) => b.tick - a.tick).slice(0, 8)
}

export function generateNegotiations(zones: Zone[]): TradeNegotiation[] {
  return [
    {
      id: 'neg-1',
      fromZoneId: zones[0].id,
      toZoneId: zones[2].id,
      energyOffered: 45,
      budgetOffered: 0,
      energyRequested: 0,
      budgetRequested: 50,
      expiresAtTick: 100,
      status: 'pending',
      description: 'Alpha selling surplus solar to Gamma',
    },
    {
      id: 'neg-2',
      fromZoneId: zones[1].id,
      toZoneId: zones[2].id,
      energyOffered: 30,
      budgetOffered: 0,
      energyRequested: 0,
      budgetRequested: 40,
      expiresAtTick: 100,
      status: 'accepted',
      description: 'Beta selling hydro power to Gamma',
    },
  ]
}

// Apply crises to zones
function applyCrisesToZones(zones: Zone[], crisisAgent: CrisisAgentState, random: () => number): Zone[] {
  return zones.map(zone => {
    const zoneCrises = crisisAgent.executedCrises.filter(c => c.targetId === zone.id)
    
    let stabilityState: StabilityState = 'stable'
    let cyberAttacked = false
    
    if (zoneCrises.length > 0) {
      // Apply crisis effects
      zoneCrises.forEach(crisis => {
        switch (crisis.crisisType) {
          case 'cyber_attack':
            cyberAttacked = true
            break
          case 'storage_leak':
            zone.storage = Math.max(0, zone.storage - zone.maxStorage * 0.05)
            break
          case 'heat_wave':
            zone.demandModifier = 1.45
            break
          case 'economic_recession':
            zone.incomeModifier = 0.35
            break
        }
      })
      
      stabilityState = zoneCrises.some(c => c.tier === 'brutal' || c.tier === 'heavy') ? 'critical' : 'warning'
    }
    
    // Check stability based on storage
    const storagePct = zone.storage / zone.maxStorage
    if (storagePct < 0.1) {
      stabilityState = 'critical'
    } else if (storagePct < 0.3) {
      stabilityState = stabilityState === 'stable' ? 'warning' : stabilityState
    }
    
    return {
      ...zone,
      activeCrises: zoneCrises,
      stabilityState,
      cyberAttacked,
    }
  })
}

export function generateSimulationState(tick: number): SimulationState {
  const random = seededRandom(tick * 12345)
  
  let zones = generateInitialZones(random)
  const tradeRoutes = generateTradeRoutes(zones, random)
  
  const crisisAgent = generateCrisisAgentState(tick, zones, random)
  
  // Apply crises to zones
  zones = applyCrisesToZones(zones, crisisAgent, random)
  
  const recentActions = generateGovernorActions(tick, zones, crisisAgent, random)
  
  const totalSupply = zones.reduce((sum, z) => sum + z.supply, 0)
  const totalDemand = zones.reduce((sum, z) => sum + z.demand, 0)
  const totalBudget = zones.reduce((sum, z) => sum + z.budget, 0)

  const seasons = ['spring', 'summer', 'autumn', 'winter'] as const
  const seasonIndex = Math.floor((tick / 8) % 4)

  const allZonesAboveThreshold = zones.every(z => (z.storage / z.maxStorage) > 0.2)
  const totalMitigated = zones.reduce((sum, z) => sum + z.crisesMitigated, 0)
  const totalCrises = zones.reduce((sum, z) => sum + z.crisesTotal, 0)
  const mitigationRate = totalCrises > 0 ? totalMitigated / totalCrises : 1

  const zonesBelowCritical = zones.filter(z => (z.storage / z.maxStorage) < 0.1)
  const isDefeat = zonesBelowCritical.length > 0 || zones.some(z => z.morale < 20)
  const defeatReason = zonesBelowCritical.length > 0 
    ? `Zone ${zonesBelowCritical[0].name} storage critical` 
    : zones.find(z => z.morale < 20) 
      ? `Zone ${zones.find(z => z.morale < 20)?.name} morale collapse`
      : undefined

  // Determine tick phase
  const tickPhases = [
    'Advance Season', 'Fire Crises', 'Apply Effects', 'Sample Outputs',
    'Energy Production', 'Economy', 'Trade Transfer', 'Demand Consumption',
    'Source Aging', 'Storage Leak', 'Morale Update', 'Monitoring Decay',
    'Pending Routes', 'Stability Check', 'Governor Agents', 'Crisis Agent', 'Expire Crises'
  ]
  const tickPhase = tickPhases[tick % tickPhases.length]

  return {
    tick,
    season: seasons[seasonIndex],
    zones,
    tradeRoutes,
    activeCrises: crisisAgent.executedCrises,
    crisisAgent,
    recentActions,
    negotiations: generateNegotiations(zones),
    globalMetrics: {
      totalSupply,
      totalDemand,
      averageMorale: zones.reduce((sum, z) => sum + z.morale, 0) / zones.length,
      averageEconomy: zones.reduce((sum, z) => sum + z.budget, 0) / zones.length,
      gridStability: Math.min(1, totalSupply / totalDemand),
      totalZoneBudget: totalBudget,
    },
    victoryConditions: {
      ticksSurvived: tick,
      targetTicks: 100,
      allZonesAboveStorageThreshold: allZonesAboveThreshold,
      storageThreshold: 20,
      crisisMitigationRate: mitigationRate * 100,
      targetMitigationRate: 80,
      isVictory: tick >= 100 && allZonesAboveThreshold && mitigationRate >= 0.8,
      isDefeat,
      defeatReason,
    },
    tickPhase,
  }
}
