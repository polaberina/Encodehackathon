'use client'

import type { Zone } from '@/lib/simulation-types'
import { 
  ENERGY_CONFIGS, ZONE_CONFIGS, CRISIS_LABELS, TIER_COLORS, STABILITY_COLORS 
} from '@/lib/simulation-types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { 
  Sun, Droplets, Wind, Factory, Atom, AlertTriangle, Zap, Users, TrendingUp,
  Shield, Target, Swords, DollarSign, Cpu
} from 'lucide-react'

interface ZoneDetailProps {
  zone: Zone | null
}

const energyIcons: Record<string, React.ElementType> = {
  solar: Sun,
  wind: Wind,
  hydro: Droplets,
  fossil: Factory,
  nuclear: Atom,
}

const strategyIcons: Record<string, React.ElementType> = {
  aggressive: Swords,
  defensive: Shield,
  economic: TrendingUp,
  resilience: Target,
}

const strategyDescriptions: Record<string, string> = {
  aggressive: 'Prioritizes expansion and trading volume',
  defensive: 'Focuses on stability and reserves',
  economic: 'Maximizes profit margins and efficiency',
  resilience: 'Emphasizes crisis recovery and durability',
}

export function ZoneDetail({ zone }: ZoneDetailProps) {
  if (!zone) {
    return (
      <Card className="bg-card/50 border-border backdrop-blur-sm h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Zone Details</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-48">
          <p className="text-sm text-muted-foreground">Select a zone on the map to view details</p>
        </CardContent>
      </Card>
    )
  }

  const storagePercent = (zone.storage / zone.maxStorage) * 100
  const supplyDemandRatio = zone.supply / zone.demand
  const config = ZONE_CONFIGS[zone.archetype]
  const StrategyIcon = strategyIcons[zone.strategy]

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm h-full overflow-auto">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: zone.color }}
            />
            <CardTitle className="text-lg font-semibold">Zone {zone.name}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge 
              variant="outline" 
              className="text-xs capitalize"
              style={{ 
                borderColor: STABILITY_COLORS[zone.stabilityState], 
                color: STABILITY_COLORS[zone.stabilityState] 
              }}
            >
              {zone.stabilityState}
            </Badge>
            <Badge variant="outline" className="text-xs" style={{ borderColor: zone.color, color: zone.color }}>
              {zone.archetype.toUpperCase()}
            </Badge>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-1">{zone.description}</p>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Active Crises */}
        {zone.activeCrises.length > 0 && (
          <div className="space-y-2">
            {zone.activeCrises.map(crisis => (
              <div 
                key={crisis.crisisId}
                className="flex items-center gap-2 p-2 rounded-md bg-red-950/30 border border-red-500/30"
              >
                <AlertTriangle className="h-4 w-4 text-red-400" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-red-300">
                      {CRISIS_LABELS[crisis.crisisType]}
                    </span>
                    <span 
                      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                      style={{ background: TIER_COLORS[crisis.tier], color: '#000' }}
                    >
                      {crisis.tier.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-red-400/70 mt-0.5">{crisis.description}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="h-1 flex-1 bg-red-900/50 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-red-500 transition-all"
                        style={{ width: `${(crisis.remainingTicks / crisis.duration) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-red-400/60">{crisis.remainingTicks}t left</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cyber Attack Warning */}
        {zone.cyberAttacked && (
          <div className="flex items-center gap-2 p-2 rounded-md bg-amber-950/30 border border-amber-500/30">
            <Cpu className="h-4 w-4 text-amber-400" />
            <div>
              <span className="text-xs font-medium text-amber-300">CYBER ATTACK ACTIVE</span>
              <p className="text-xs text-amber-400/70">Zone readings may be corrupted</p>
            </div>
          </div>
        )}

        {/* Strategy */}
        <div className="flex items-center gap-3 p-2 rounded-md bg-secondary/30">
          <StrategyIcon className="h-5 w-5" style={{ color: zone.color }} />
          <div>
            <div className="text-xs font-medium capitalize">{zone.strategy} Strategy</div>
            <div className="text-[10px] text-muted-foreground">{strategyDescriptions[zone.strategy]}</div>
          </div>
        </div>

        {/* Budget */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-primary/10 rounded-lg p-3 border border-primary/20">
            <div className="flex items-center gap-1.5 text-xs text-primary mb-1">
              <DollarSign className="h-3 w-3" />
              Budget
            </div>
            <div className="text-lg font-semibold text-foreground">{Math.round(zone.budget)} cr</div>
            <div className="text-xs text-muted-foreground">
              +{zone.budgetPerTick * zone.incomeModifier}/tick
            </div>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground mb-1">Total Spent</div>
            <div className="text-lg font-semibold text-foreground">{Math.round(zone.totalSpent)} cr</div>
            <div className="text-xs text-muted-foreground">this session</div>
          </div>
        </div>

        {/* Storage */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Zap className="h-3.5 w-3.5" /> Storage
            </span>
            <span>{zone.storage.toFixed(0)} / {zone.maxStorage.toFixed(0)} MWh</span>
          </div>
          <Progress value={storagePercent} className="h-2.5" />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Critical &lt;20%</span>
            <span className={storagePercent > 50 ? 'text-primary' : storagePercent > 20 ? 'text-accent' : 'text-destructive'}>
              {storagePercent.toFixed(0)}%
            </span>
          </div>
        </div>

        {/* Supply vs Demand */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-secondary/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground mb-1">Supply</div>
            <div className="text-lg font-semibold text-primary">{zone.supply.toFixed(0)} MW</div>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground mb-1">Demand</div>
            <div className="text-lg font-semibold text-accent">{zone.demand.toFixed(0)} MW</div>
            {zone.demandModifier !== 1.0 && (
              <div className="text-xs text-amber-400">x{zone.demandModifier.toFixed(2)} modifier</div>
            )}
          </div>
        </div>

        {/* Net Energy */}
        <div className="flex items-center justify-between text-sm p-2 rounded-md bg-secondary/30">
          <span className="text-muted-foreground">Net Energy:</span>
          <span className={zone.netEnergyPerTick >= 0 ? 'text-primary font-medium' : 'text-destructive font-medium'}>
            {zone.netEnergyPerTick >= 0 ? '+' : ''}{zone.netEnergyPerTick.toFixed(1)} MWh/tick
          </span>
        </div>

        {zone.projectedDepletionTicks !== null && (
          <div className="flex items-center gap-2 p-2 rounded-md bg-destructive/10 border border-destructive/20">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <span className="text-xs text-destructive">
              Storage depletes in ~{zone.projectedDepletionTicks} ticks
            </span>
          </div>
        )}

        {/* Energy Sources */}
        <div>
          <div className="text-sm font-medium mb-2">Energy Sources ({zone.energySources.length})</div>
          <div className="space-y-2">
            {zone.energySources.map((source) => {
              const Icon = energyIcons[source.type] || Zap
              const energyConfig = ENERGY_CONFIGS[source.type]
              const outputPercent = source.highOutputRate > 0 
                ? (source.currentOutput / source.highOutputRate) * 100 
                : 0
              return (
                <div key={source.sourceId} className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 w-20">
                    <Icon className="h-4 w-4 shrink-0" style={{ color: energyConfig.color }} />
                    <span className="text-xs truncate">{energyConfig.label}</span>
                  </div>
                  <div className="flex-1">
                    <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                      <div 
                        className="h-full rounded-full transition-all"
                        style={{ 
                          width: `${outputPercent}%`,
                          backgroundColor: source.active ? energyConfig.color : 'var(--muted)' 
                        }}
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                      <span className={!source.active ? 'text-destructive' : ''}>
                        {source.active ? `${source.currentOutput.toFixed(0)} MW` : 'OFFLINE'}
                      </span>
                      {source.outputModifier !== 1.0 && (
                        <span className="text-amber-400">x{source.outputModifier.toFixed(2)}</span>
                      )}
                      <span>Res: {(source.resilience * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Performance Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Users className="h-3 w-3" /> Morale
            </div>
            <div className="flex items-center gap-2">
              <Progress value={zone.morale} className="h-1.5 flex-1" />
              <span className="text-xs font-medium">{zone.morale.toFixed(0)}%</span>
            </div>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Shield className="h-3 w-3" /> Reputation
            </div>
            <div className="flex items-center gap-2">
              <Progress value={zone.reputation} className="h-1.5 flex-1" />
              <span className="text-xs font-medium">{zone.reputation.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Strategic Metrics */}
        <div className="pt-2 border-t border-border">
          <div className="text-xs font-medium mb-2">Strategic Performance</div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 rounded-md bg-secondary/30">
              <div className="text-lg font-bold text-primary">{zone.survivalTicks}</div>
              <div className="text-[10px] text-muted-foreground">Ticks Survived</div>
            </div>
            <div className="p-2 rounded-md bg-secondary/30">
              <div className="text-lg font-bold" style={{ color: zone.color }}>
                {zone.crisesMitigated}/{zone.crisesTotal}
              </div>
              <div className="text-[10px] text-muted-foreground">Crises Handled</div>
            </div>
            <div className="p-2 rounded-md bg-secondary/30">
              <div className="text-lg font-bold text-accent">{zone.tradeProfitability.toFixed(0)}%</div>
              <div className="text-[10px] text-muted-foreground">Trade Profit</div>
            </div>
          </div>
        </div>

        {/* Region */}
        <div className="text-xs text-muted-foreground flex items-center justify-between">
          <span>Region:</span>
          <span className="capitalize">{zone.region}</span>
        </div>
      </CardContent>
    </Card>
  )
}
