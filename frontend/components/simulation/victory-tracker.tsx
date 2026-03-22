'use client'

import type { VictoryConditions, Zone } from '@/lib/simulation-types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Trophy, Target, Shield, TrendingUp, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'

interface VictoryTrackerProps {
  conditions: VictoryConditions
  zones: Zone[]
}

export function VictoryTracker({ conditions, zones }: VictoryTrackerProps) {
  const survivalProgress = Math.min(100, (conditions.ticksSurvived / conditions.targetTicks) * 100)
  const mitigationProgress = Math.min(100, (conditions.crisisMitigationRate / conditions.targetMitigationRate) * 100)

  // Calculate zone survival statuses
  const zoneStatuses = zones.map(zone => ({
    name: zone.name,
    archetype: zone.archetype,
    storagePercent: (zone.storage / zone.maxStorage) * 100,
    isHealthy: (zone.storage / zone.maxStorage) > 0.2,
    isCritical: (zone.storage / zone.maxStorage) < 0.1,
    color: zone.color,
  }))

  const allZonesHealthy = zoneStatuses.every(z => z.isHealthy)

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Trophy className="h-4 w-4 text-accent" />
            Victory Conditions
          </CardTitle>
          {conditions.isVictory ? (
            <Badge className="bg-primary/20 text-primary border-primary/30">
              <CheckCircle2 className="h-3 w-3 mr-1" /> Victory
            </Badge>
          ) : conditions.isDefeat ? (
            <Badge variant="destructive">
              <XCircle className="h-3 w-3 mr-1" /> Defeat
            </Badge>
          ) : (
            <Badge variant="outline" className="text-xs">In Progress</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Defeat warning */}
        {conditions.isDefeat && conditions.defeatReason && (
          <div className="flex items-center gap-2 p-2 rounded-md bg-destructive/10 border border-destructive/20">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <span className="text-xs text-destructive">{conditions.defeatReason}</span>
          </div>
        )}

        {/* Condition 1: Survive 100+ ticks */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Target className="h-3.5 w-3.5" />
              Survive {conditions.targetTicks}+ Ticks
            </span>
            <span className={survivalProgress >= 100 ? 'text-primary' : 'text-foreground'}>
              {conditions.ticksSurvived} / {conditions.targetTicks}
            </span>
          </div>
          <Progress value={survivalProgress} className="h-2" />
        </div>

        {/* Condition 2: All zones above 20% storage */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              All Zones {'>'} {conditions.storageThreshold}% Storage
            </span>
            {allZonesHealthy ? (
              <CheckCircle2 className="h-4 w-4 text-primary" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive" />
            )}
          </div>
          <div className="flex gap-1.5">
            {zoneStatuses.map((zone) => (
              <div
                key={zone.name}
                className="flex-1 relative"
                title={`${zone.name}: ${zone.storagePercent.toFixed(0)}%`}
              >
                <div className="h-4 rounded-sm bg-secondary/50 overflow-hidden">
                  <div
                    className="h-full transition-all duration-300"
                    style={{
                      width: `${zone.storagePercent}%`,
                      backgroundColor: zone.isCritical ? '#EF4444' : zone.isHealthy ? zone.color : '#FBBF24',
                    }}
                  />
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[9px] font-medium text-foreground drop-shadow-sm">
                    {zone.name[0]}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Condition 3: Crisis mitigation rate > 80% */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              Crisis Mitigation {'>'} {conditions.targetMitigationRate}%
            </span>
            <span className={conditions.crisisMitigationRate >= conditions.targetMitigationRate ? 'text-primary' : 'text-foreground'}>
              {conditions.crisisMitigationRate.toFixed(0)}%
            </span>
          </div>
          <Progress 
            value={mitigationProgress} 
            className="h-2"
          />
        </div>

        {/* Zone Performance Summary */}
        <div className="pt-2 border-t border-border">
          <div className="text-xs text-muted-foreground mb-2">Zone Performance</div>
          <div className="grid grid-cols-2 gap-2">
            {zones.map((zone) => (
              <div
                key={zone.id}
                className="flex items-center gap-2 p-1.5 rounded-md bg-secondary/30"
              >
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: zone.color }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">{zone.name}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {zone.crisesMitigated}/{zone.crisesTotal} crises
                  </div>
                </div>
                <div className="text-[10px] font-mono">
                  {zone.tradeProfitability.toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
