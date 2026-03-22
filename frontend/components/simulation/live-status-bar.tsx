"use client"

import { Zap, Activity, TrendingUp, Shield, AlertTriangle, Leaf, DollarSign, Flame } from 'lucide-react'
import { useSimulation } from '@/lib/simulation-context'
import { CRISIS_LABELS, TIER_COLORS, STABILITY_COLORS } from '@/lib/simulation-types'

export function LiveStatusBar() {
  const { simulationState } = useSimulation()

  if (!simulationState) return null

  const { zones = [], globalMetrics, activeCrises, victoryConditions, crisisAgent } = simulationState
  
  // Calculate grid cleanliness
  const cleanTypes = ['solar', 'wind', 'hydro', 'nuclear']
  let totalOutput = 0
  let cleanOutput = 0
  zones.forEach(zone => {
    zone.energySources.forEach(source => {
      totalOutput += source.currentOutput
      if (cleanTypes.includes(source.type)) {
        cleanOutput += source.currentOutput
      }
    })
  })
  const gridCleanliness = totalOutput > 0 ? Math.round((cleanOutput / totalOutput) * 100) : 0

  // Count zones by stability state
  const stableZones = zones.filter(z => z.stabilityState === 'stable').length
  const warningZones = zones.filter(z => z.stabilityState === 'warning').length
  const criticalZones = zones.filter(z => z.stabilityState === 'critical').length

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-card/90 backdrop-blur-md border-t border-border">
      <div className="flex items-center justify-end gap-6 px-6 py-2.5">
        {/* Zone Status */}
        <div className="flex items-center gap-3 mr-auto">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: STABILITY_COLORS.stable }} />
            <span className="text-sm text-muted-foreground">{stableZones}</span>
          </div>
          {warningZones > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: STABILITY_COLORS.warning }} />
              <span className="text-sm text-muted-foreground">{warningZones}</span>
            </div>
          )}
          {criticalZones > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: STABILITY_COLORS.critical }} />
              <span className="text-sm text-foreground font-medium">{criticalZones}</span>
            </div>
          )}

          {/* Crisis Agent Budget */}
          <div className="w-px h-4 bg-border mx-2" />
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-950/50 border border-red-500/30">
            <Flame className="h-3 w-3 text-red-400" />
            <span className="text-xs text-red-300 font-mono">{Math.round(crisisAgent.budget)} cr</span>
          </div>
        </div>

        {/* Key Metrics - Right aligned */}
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Zone Budget</span>
            <span className="text-sm font-mono font-semibold text-foreground">
              {Math.round(globalMetrics.totalZoneBudget)} cr
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Production</span>
            <span className="text-sm font-mono font-semibold text-foreground">
              {Math.round(globalMetrics.totalSupply)} MW
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Demand</span>
            <span className="text-sm font-mono font-semibold text-foreground">
              {Math.round(globalMetrics.totalDemand)} MW
            </span>
          </div>

          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Stability</span>
            <span className={`text-sm font-mono font-semibold ${globalMetrics.gridStability >= 0.95 ? 'text-primary' : globalMetrics.gridStability >= 0.8 ? 'text-accent' : 'text-destructive'}`}>
              {Math.round(globalMetrics.gridStability * 100)}%
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Leaf className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Clean</span>
            <span className={`text-sm font-mono font-semibold ${gridCleanliness >= 60 ? 'text-primary' : 'text-accent'}`}>
              {gridCleanliness}%
            </span>
          </div>
        </div>

        {/* Divider */}
        <div className="w-px h-6 bg-border" />

        {/* Active Crises & Victory Progress */}
        <div className="flex items-center gap-3">
          {activeCrises.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-destructive/15 border border-destructive/30">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              <span className="text-sm text-destructive font-semibold">
                {activeCrises.length} Attack{activeCrises.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary border border-border">
            <Shield className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Victory</span>
            <span className="text-sm font-mono font-semibold text-foreground">
              {victoryConditions.ticksSurvived}/{victoryConditions.targetTicks}
            </span>
          </div>
        </div>
      </div>

      {/* Active Crisis Details */}
      {activeCrises.length > 0 && (
        <div className="flex items-center justify-end gap-3 px-6 py-1.5 border-t border-border bg-destructive/5">
          <span className="text-xs text-muted-foreground mr-auto">Active Attacks:</span>
          {activeCrises.map(crisis => {
            const zone = zones.find(z => z.id === crisis.targetId)
            return (
              <div key={crisis.crisisId} className="flex items-center gap-2">
                <span 
                  className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                  style={{ background: TIER_COLORS[crisis.tier], color: '#000' }}
                >
                  {crisis.tier}
                </span>
                <span className="text-xs text-destructive font-medium">
                  {CRISIS_LABELS[crisis.crisisType]} → {zone?.name || 'Unknown'}
                </span>
                <span className="text-xs text-destructive/60">({crisis.remainingTicks}t)</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
