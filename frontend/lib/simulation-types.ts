export type EnergyType = 'solar' | 'wind' | 'hydro' | 'fossil' | 'nuclear'

export type Season = 'spring' | 'summer' | 'autumn' | 'winter'

export type StabilityState = 'stable' | 'warning' | 'critical' | 'collapsed'

// Crisis types from the actual game engine
export type CrisisType =
  | 'supply_disruption'
  | 'demand_spike'
  | 'route_attack'
  | 'cascading_failure'
  | 'drought'
  | 'heat_wave'
  | 'wildfire'
  | 'equipment_failure'
  | 'storage_leak'
  | 'economic_recession'
  | 'worker_strike'
  | 'political_embargo'
  | 'cyber_attack'
  | 'transmission_surge'
  | 'regional_blackout'

// Crisis tiers from crisis_agent.py
export type CrisisTier = 'light' | 'medium' | 'heavy' | 'brutal'

export type ZoneStrategy = 'aggressive' | 'defensive' | 'economic' | 'resilience'

export type ZoneArchetype = 'alpha' | 'beta' | 'gamma'

// Governor action types from engine.py ACTION_COSTS
export type GovernorActionType = 
  | 'ration_energy'
  | 'boost_source'
  | 'repair_route'
  | 'open_trade_route'
  | 'close_trade_route'
  | 'emergency_broadcast'
  | 'upgrade_storage'
  | 'fortify_route'
  | 'sell_surplus'
  | 'build_new_route'
  | 'invest_in_efficiency'
  | 'set_export_cap'
  | 'deploy_emergency_generator'
  | 'request_aid'
  | 'issue_conservation_order'
  | 'settle_worker_strike'
  | 'repair_source'
  | 'monitor_zone'
  | 'propose_trade'
  | 'accept_trade'
  | 'reject_trade'

export interface ZoneConfig {
  archetype: ZoneArchetype
  name: string
  description: string
  strategy: ZoneStrategy
  primaryEnergy: EnergyType[]
  color: string
  icon: string
  region: 'north' | 'south'
}

export interface EnergySource {
  sourceId: string
  type: EnergyType
  lowOutputRate: number
  highOutputRate: number
  resilience: number
  active: boolean
  outputModifier: number
  degradationModifier: number
  seasonalModifier: number
  currentOutput: number
}

export interface Zone {
  id: string
  name: string
  archetype: ZoneArchetype
  strategy: ZoneStrategy
  description: string
  region: 'north' | 'south'
  position: { x: number; y: number }
  // Storage
  storage: number
  maxStorage: number
  // Economy
  budget: number
  budgetPerTick: number
  incomeModifier: number
  totalSpent: number
  // Metrics
  morale: number
  reputation: number
  baseDemand: number
  demandModifier: number
  seasonalDemandModifier: number
  // Sources
  energySources: EnergySource[]
  supply: number
  demand: number
  netEnergyPerTick: number
  projectedDepletionTicks: number | null
  // State
  stabilityState: StabilityState
  cyberAttacked: boolean
  fogOfWarLevel: number
  // Crises
  activeCrises: CrisisEvent[]
  // Stats
  survivalTicks: number
  crisesMitigated: number
  crisesTotal: number
  tradeProfitability: number
  efficiencyScore: number
  color: string
}

export interface TradeRoute {
  id: string
  sourceZoneId: string
  targetZoneId: string
  transferRate: number
  latency: number
  routeHealth: number
  transmissionEfficiency: number
  exportCap: number | null
  fortification: number
  isEmbargoed: boolean
  currentFlow: number
  maxCapacity: number
  isActive: boolean
}

export interface CrisisEvent {
  crisisId: string
  crisisType: CrisisType
  targetId: string
  duration: number
  remainingTicks: number
  tier: CrisisTier
  cost: number
  description: string
  sourceId?: string
  routeId?: string
  parameters: Record<string, number | string | boolean>
}

// Crisis Agent state from crisis_agent.py
export interface CrisisAgentState {
  budget: number
  incomeThisTick: number
  totalSpent: number
  plannedCrises: CrisisEvent[]
  executedCrises: CrisisEvent[]
  strategy: string
  vulnerabilityRanking: string[]
}

// Governor Agent action from state.py
export interface GovernorAction {
  id: string
  agentId: string
  zoneName: string
  type: GovernorActionType
  cost: number
  latency: number
  details: string
  tick: number
  timestamp: number
  status: 'pending' | 'executing' | 'completed' | 'failed'
  params: Record<string, unknown>
}

export interface TradeNegotiation {
  id: string
  fromZoneId: string
  toZoneId: string
  energyOffered: number
  budgetOffered: number
  energyRequested: number
  budgetRequested: number
  expiresAtTick: number
  status: 'pending' | 'accepted' | 'rejected' | 'expired'
  description: string
}

export interface VictoryConditions {
  ticksSurvived: number
  targetTicks: number
  allZonesAboveStorageThreshold: boolean
  storageThreshold: number
  crisisMitigationRate: number
  targetMitigationRate: number
  isVictory: boolean
  isDefeat: boolean
  defeatReason?: string
}

export interface SimulationState {
  tick: number
  season: Season
  zones: Zone[]
  tradeRoutes: TradeRoute[]
  activeCrises: CrisisEvent[]
  crisisAgent: CrisisAgentState
  recentActions: GovernorAction[]
  negotiations: TradeNegotiation[]
  recentLogs?: { tick: number; message: string }[]
  globalMetrics: {
    totalSupply: number
    totalDemand: number
    averageMorale: number
    averageEconomy: number
    gridStability: number
    totalZoneBudget: number
  }
  victoryConditions: VictoryConditions
  tickPhase: string
}

export const ENERGY_CONFIGS: Record<EnergyType, { baseOutput: number; color: string; label: string }> = {
  solar: { baseOutput: 40, color: '#FBBF24', label: 'Solar' },
  wind: { baseOutput: 35, color: '#38BDF8', label: 'Wind' },
  hydro: { baseOutput: 60, color: '#3B82F6', label: 'Hydro' },
  fossil: { baseOutput: 80, color: '#78716C', label: 'Fossil' },
  nuclear: { baseOutput: 120, color: '#A855F7', label: 'Nuclear' },
}

export const ZONE_COUNTRY_CODES: Record<ZoneArchetype, string> = {
  alpha: 'DEU',
  beta: 'FRA',
  gamma: 'POL',
}

export const ZONE_CONFIGS: Record<ZoneArchetype, ZoneConfig> = {
  alpha: {
    archetype: 'alpha',
    name: 'Alpha',
    description: 'Renewable-heavy, aggressive trading',
    strategy: 'aggressive',
    primaryEnergy: ['solar', 'wind'],
    color: '#22C55E',
    icon: 'leaf',
    region: 'north',
  },
  beta: {
    archetype: 'beta',
    name: 'Beta',
    description: 'Hydro zone, defensive strategy',
    strategy: 'defensive',
    primaryEnergy: ['hydro'],
    color: '#3B82F6',
    icon: 'shield',
    region: 'north',
  },
  gamma: {
    archetype: 'gamma',
    name: 'Gamma',
    description: 'Fossil dependent, economic focus',
    strategy: 'economic',
    primaryEnergy: ['fossil'],
    color: '#F97316',
    icon: 'trending-up',
    region: 'south',
  },
}

// Crisis menu from crisis_agent.py
export const CRISIS_MENU: Record<string, { 
  cost: number
  tier: CrisisTier
  crisisType: CrisisType
  duration: number
  targetType: 'zone' | 'route' | 'region'
  requiresSource: boolean
  requiresRoute: boolean
  description: string
}> = {
  cyber_attack: {
    cost: 12,
    tier: 'light',
    crisisType: 'cyber_attack',
    duration: 3,
    targetType: 'zone',
    requiresSource: false,
    requiresRoute: false,
    description: 'Corrupts zone readings for 3 ticks',
  },
  supply_disruption: {
    cost: 20,
    tier: 'light',
    crisisType: 'supply_disruption',
    duration: 4,
    targetType: 'zone',
    requiresSource: true,
    requiresRoute: false,
    description: 'Source at 50% output',
  },
  storage_leak: {
    cost: 28,
    tier: 'medium',
    crisisType: 'storage_leak',
    duration: 6,
    targetType: 'zone',
    requiresSource: false,
    requiresRoute: false,
    description: 'Storage leaking 5%/tick',
  },
  political_embargo: {
    cost: 32,
    tier: 'medium',
    crisisType: 'political_embargo',
    duration: 4,
    targetType: 'route',
    requiresSource: false,
    requiresRoute: false,
    description: 'Trade route frozen',
  },
  worker_strike: {
    cost: 35,
    tier: 'medium',
    crisisType: 'worker_strike',
    duration: 5,
    targetType: 'zone',
    requiresSource: true,
    requiresRoute: false,
    description: 'Source at 25% output',
  },
  drought: {
    cost: 40,
    tier: 'medium',
    crisisType: 'drought',
    duration: 5,
    targetType: 'zone',
    requiresSource: false,
    requiresRoute: false,
    description: 'Hydro at 28% for 5 ticks',
  },
  equipment_failure: {
    cost: 45,
    tier: 'heavy',
    crisisType: 'equipment_failure',
    duration: 5,
    targetType: 'zone',
    requiresSource: true,
    requiresRoute: false,
    description: 'Source goes offline',
  },
  heat_wave: {
    cost: 50,
    tier: 'heavy',
    crisisType: 'heat_wave',
    duration: 4,
    targetType: 'zone',
    requiresSource: false,
    requiresRoute: false,
    description: 'Demand +45%, solar at 60%',
  },
  transmission_surge: {
    cost: 55,
    tier: 'heavy',
    crisisType: 'transmission_surge',
    duration: 4,
    targetType: 'zone',
    requiresSource: false,
    requiresRoute: false,
    description: 'All routes -35% efficiency',
  },
  wildfire: {
    cost: 60,
    tier: 'heavy',
    crisisType: 'wildfire',
    duration: 4,
    targetType: 'zone',
    requiresSource: true,
    requiresRoute: true,
    description: 'Source + route destroyed',
  },
  regional_blackout: {
    cost: 70,
    tier: 'brutal',
    crisisType: 'regional_blackout',
    duration: 3,
    targetType: 'region',
    requiresSource: false,
    requiresRoute: false,
    description: 'Region +85% demand surge',
  },
  economic_recession: {
    cost: 45,
    tier: 'heavy',
    crisisType: 'economic_recession',
    duration: 5,
    targetType: 'zone',
    requiresSource: false,
    requiresRoute: false,
    description: 'Income at 35% for 5 ticks',
  },
}

// Governor action costs from engine.py
export const ACTION_COSTS: Record<GovernorActionType, number> = {
  ration_energy: 10,
  boost_source: 50,
  repair_route: 30,
  open_trade_route: 20,
  close_trade_route: 5,
  emergency_broadcast: 0,
  upgrade_storage: 100,
  fortify_route: 40,
  sell_surplus: 0,
  build_new_route: 150,
  invest_in_efficiency: 80,
  set_export_cap: 5,
  deploy_emergency_generator: 75,
  request_aid: 0,
  issue_conservation_order: 15,
  settle_worker_strike: 60,
  repair_source: 35,
  monitor_zone: 20,
  propose_trade: 5,
  accept_trade: 0,
  reject_trade: 0,
}

// Action latencies from engine.py
export const ACTION_LATENCY: Record<GovernorActionType, number> = {
  sell_surplus: 0,
  emergency_broadcast: 0,
  monitor_zone: 0,
  set_export_cap: 0,
  ration_energy: 1,
  close_trade_route: 1,
  boost_source: 1,
  deploy_emergency_generator: 1,
  issue_conservation_order: 1,
  settle_worker_strike: 1,
  request_aid: 1,
  repair_route: 2,
  fortify_route: 2,
  repair_source: 2,
  invest_in_efficiency: 2,
  open_trade_route: 2,
  upgrade_storage: 3,
  propose_trade: 0,
  accept_trade: 1,
  reject_trade: 0,
  build_new_route: 3,
}

export const CRISIS_LABELS: Record<CrisisType, string> = {
  supply_disruption: 'Supply Disruption',
  demand_spike: 'Demand Spike',
  route_attack: 'Route Attack',
  cascading_failure: 'Cascading Failure',
  drought: 'Drought',
  heat_wave: 'Heat Wave',
  wildfire: 'Wildfire',
  equipment_failure: 'Equipment Failure',
  storage_leak: 'Storage Leak',
  economic_recession: 'Economic Recession',
  worker_strike: 'Worker Strike',
  political_embargo: 'Political Embargo',
  cyber_attack: 'Cyber Attack',
  transmission_surge: 'Transmission Surge',
  regional_blackout: 'Regional Blackout',
}

export const TIER_COLORS: Record<CrisisTier, string> = {
  light: '#FBBF24',
  medium: '#F97316',
  heavy: '#EF4444',
  brutal: '#DC2626',
}

export const STABILITY_COLORS: Record<StabilityState, string> = {
  stable: '#22C55E',
  warning: '#FBBF24',
  critical: '#EF4444',
  collapsed: '#7F1D1D',
}
