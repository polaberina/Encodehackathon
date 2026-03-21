"use client"

import { X, Zap, TrendingUp, Heart, Shield, AlertTriangle, Leaf, Flame, DollarSign, Cpu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useSimulation } from '@/lib/simulation-context'
import { 
  ZONE_CONFIGS, ENERGY_CONFIGS, CRISIS_LABELS, TIER_COLORS, STABILITY_COLORS 
} from '@/lib/simulation-types'

export function ZoneInfoPanel() {
  const { simulationState, selectedZone, setSelectedZone } = useSimulation()

  if (!selectedZone || !simulationState) return null

  const config = ZONE_CONFIGS[selectedZone.archetype]
  const activeCrises = selectedZone.activeCrises || []
  
  const cleanTypes = ['solar', 'wind', 'hydro', 'nuclear']
  const totalOutput = selectedZone.energySources.reduce((sum, s) => sum + s.currentOutput, 0)
  const cleanOutput = selectedZone.energySources
    .filter(s => cleanTypes.includes(s.type))
    .reduce((sum, s) => sum + s.currentOutput, 0)
  const cleanPercentage = totalOutput > 0 ? Math.round((cleanOutput / totalOutput) * 100) : 0
  
  const storagePercent = Math.round((selectedZone.storage / selectedZone.maxStorage) * 100)
  const supplyDemandRatio = selectedZone.demand > 0 ? selectedZone.supply / selectedZone.demand : 1

  return (
    <div className="absolute right-4 top-4 w-80 bg-card/95 backdrop-blur-md border border-border rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div 
        className="p-4 border-b border-border"
        style={{ backgroundColor: `${config.color}15` }}
      >
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: config.color }}
              />
              {selectedZone.name}
            </h3>
            <p className="text-sm text-muted-foreground mt-0.5">{config.description}</p>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-7 w-7 -mt-1 -mr-1"
            onClick={() => setSelectedZone(null)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="flex items-center gap-2 mt-3">
          <span 
            className="px-2 py-0.5 text-xs rounded-full uppercase tracking-wide font-medium"
            style={{ 
              backgroundColor: `${config.color}25`,
              color: config.color 
            }}
          >
            {selectedZone.strategy}
          </span>
          <span 
            className="px-2 py-0.5 text-xs rounded-full capitalize font-medium"
            style={{ 
              backgroundColor: `${STABILITY_COLORS[selectedZone.stabilityState]}25`,
              color: STABILITY_COLORS[selectedZone.stabilityState]
            }}
          >
            {selectedZone.stabilityState}
          </span>
          {selectedZone.cyberAttacked && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400 flex items-center gap-1">
              <Cpu className="h-3 w-3" />
              Hacked
            </span>
          )}
        </div>
      </div>

      {/* Active Crises Alert */}
      {activeCrises.length > 0 && (
        <div className="p-3 bg-red-950/30 border-b border-red-500/30">
          <div className="flex items-center gap-2 text-red-400 text-xs mb-2">
            <AlertTriangle className="h-3 w-3" />
            <span className="font-medium">Active Crises ({activeCrises.length})</span>
          </div>
          {activeCrises.slice(0, 2).map(crisis => (
            <div key={crisis.crisisId} className="flex items-center justify-between text-xs mb-1">
              <span className="text-red-300">{CRISIS_LABELS[crisis.crisisType]}</span>
              <div className="flex items-center gap-2">
                <span 
                  className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                  style={{ background: TIER_COLORS[crisis.tier], color: '#000' }}
                >
                  {crisis.tier}
                </span>
                <span className="text-red-400/60">{crisis.remainingTicks}t</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-2 gap-3">
        {/* Budget */}
        <div className="bg-primary/10 rounded-lg p-3 border border-primary/20">
          <div className="flex items-center gap-1.5 text-xs text-primary mb-1">
            <DollarSign className="h-3 w-3" />
            Budget
          </div>
          <div className="text-lg font-semibold text-foreground">{Math.round(selectedZone.budget)} cr</div>
          <div className="text-xs text-muted-foreground">
            +{Math.round(selectedZone.budgetPerTick * selectedZone.incomeModifier)}/tick
          </div>
        </div>

        {/* Storage */}
        <div className="bg-secondary/50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
            <Zap className="h-3 w-3" />
            Storage
          </div>
          <div className="text-lg font-semibold text-foreground">{storagePercent}%</div>
          <div className="mt-1 h-1.5 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full rounded-full transition-all"
              style={{ 
                width: `${storagePercent}%`,
                backgroundColor: STABILITY_COLORS[selectedZone.stabilityState]
              }}
            />
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {Math.round(selectedZone.storage)} / {selectedZone.maxStorage} MWh
          </div>
        </div>

        {/* Grid Balance */}
        <div className="bg-secondary/50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
            <TrendingUp className="h-3 w-3" />
            Net Energy
          </div>
          <div className={`text-lg font-semibold ${selectedZone.netEnergyPerTick >= 0 ? 'text-primary' : 'text-destructive'}`}>
            {selectedZone.netEnergyPerTick >= 0 ? '+' : ''}{Math.round(selectedZone.netEnergyPerTick)}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {Math.round(selectedZone.supply)} / {Math.round(selectedZone.demand)} MW
          </div>
        </div>

        {/* Morale */}
        <div className="bg-secondary/50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
            <Heart className="h-3 w-3" />
            Morale
          </div>
          <div className="text-lg font-semibold text-foreground">{Math.round(selectedZone.morale)}%</div>
          <div className="mt-1 h-1.5 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${selectedZone.morale}%` }}
            />
          </div>
        </div>
      </div>

      {/* Energy Mix */}
      <div className="px-4 pb-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium text-foreground">Energy Mix</h4>
          <div className="flex items-center gap-1.5 text-xs">
            {cleanPercentage > 60 ? (
              <Leaf className="h-3 w-3 text-primary" />
            ) : (
              <Flame className="h-3 w-3 text-accent" />
            )}
            <span className={cleanPercentage > 60 ? 'text-primary' : 'text-accent'}>
              {cleanPercentage}% Clean
            </span>
          </div>
        </div>
        
        <div className="space-y-2">
          {selectedZone.energySources.map(source => {
            const energyConfig = ENERGY_CONFIGS[source.type]
            const outputPercent = totalOutput > 0 ? (source.currentOutput / totalOutput) * 100 : 0
            
            return (
              <div key={source.sourceId} className="flex items-center gap-2">
                <div 
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: source.active ? energyConfig.color : 'var(--muted)' }}
                />
                <span className={`text-xs w-16 truncate ${!source.active ? 'text-destructive' : 'text-muted-foreground'}`}>
                  {energyConfig.label}
                </span>
                <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div 
                    className="h-full rounded-full transition-all"
                    style={{ 
                      width: `${outputPercent}%`,
                      backgroundColor: source.active ? energyConfig.color : 'var(--muted)'
                    }}
                  />
                </div>
                <span className="text-xs font-mono text-foreground w-14 text-right">
                  {source.active ? `${Math.round(source.currentOutput)} MW` : 'OFF'}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="px-4 pb-4 border-t border-border pt-3">
        <h4 className="text-sm font-medium text-foreground mb-2">Performance</h4>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="text-xs text-muted-foreground">Survival</div>
            <div className="text-sm font-semibold text-foreground">{selectedZone.survivalTicks} ticks</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Crises</div>
            <div className="text-sm font-semibold text-foreground">
              {selectedZone.crisesMitigated}/{selectedZone.crisesTotal}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Rep</div>
            <div className="text-sm font-semibold text-foreground">
              {Math.round(selectedZone.reputation)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
