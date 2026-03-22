'use client'

import type { SimulationState } from '@/lib/simulation-types'
import { CRISIS_LABELS } from '@/lib/simulation-types'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Zap, TrendingUp, Users, Activity, Sun, Snowflake, Leaf, Cloud, AlertTriangle } from 'lucide-react'

interface GlobalMetricsProps {
  state: SimulationState
}

const seasonConfig = {
  spring: { icon: Leaf, color: 'text-green-400', bg: 'bg-green-400/10', border: 'border-green-400/30' },
  summer: { icon: Sun, color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/30' },
  autumn: { icon: Cloud, color: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/30' },
  winter: { icon: Snowflake, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/30' },
}

export function GlobalMetrics({ state }: GlobalMetricsProps) {
  const { globalMetrics, tick, season, activeCrises, victoryConditions } = state
  const SeasonIcon = seasonConfig[season].icon

  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      {/* Tick Counter & Season */}
      <Card className="bg-card/50 border-border backdrop-blur-sm">
        <CardContent className="py-2 px-4 flex items-center gap-4">
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide">Tick</div>
            <div className="font-mono text-2xl font-bold text-primary">{tick.toString().padStart(4, '0')}</div>
          </div>
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border ${seasonConfig[season].bg} ${seasonConfig[season].border}`}>
            <SeasonIcon className={`h-4 w-4 ${seasonConfig[season].color}`} />
            <span className={`text-sm font-medium capitalize ${seasonConfig[season].color}`}>{season}</span>
          </div>
          {/* Victory progress mini-indicator */}
          <div className="flex flex-col items-center">
            <div className="text-[10px] text-muted-foreground">Target</div>
            <div className="font-mono text-sm">
              <span className={tick >= 100 ? 'text-primary' : 'text-foreground'}>{tick}</span>
              <span className="text-muted-foreground">/100</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Grid Status */}
      <div className="flex items-center gap-3">
        <MetricCard
          icon={Zap}
          label="Supply / Demand"
          value={`${globalMetrics.totalSupply.toFixed(0)} / ${globalMetrics.totalDemand.toFixed(0)}`}
          unit="MW"
          status={globalMetrics.totalSupply >= globalMetrics.totalDemand ? 'healthy' : 'warning'}
        />
        <MetricCard
          icon={Activity}
          label="Grid Stability"
          value={(globalMetrics.gridStability * 100).toFixed(1)}
          unit="%"
          status={globalMetrics.gridStability > 0.9 ? 'healthy' : globalMetrics.gridStability > 0.7 ? 'warning' : 'critical'}
        />
        <MetricCard
          icon={Users}
          label="Avg Morale"
          value={globalMetrics.averageMorale.toFixed(0)}
          unit="%"
          status={globalMetrics.averageMorale > 70 ? 'healthy' : globalMetrics.averageMorale > 50 ? 'warning' : 'critical'}
        />
        <MetricCard
          icon={TrendingUp}
          label="Avg Economy"
          value={globalMetrics.averageEconomy.toFixed(0)}
          unit="%"
          status={globalMetrics.averageEconomy > 70 ? 'healthy' : globalMetrics.averageEconomy > 50 ? 'warning' : 'critical'}
        />
      </div>

      {/* Active Crises / Status */}
      <div className="flex items-center gap-2">
        {victoryConditions.isVictory ? (
          <Badge className="bg-primary/20 text-primary border-primary/30 px-3 py-1">
            VICTORY ACHIEVED
          </Badge>
        ) : victoryConditions.isDefeat ? (
          <Badge variant="destructive" className="px-3 py-1 animate-pulse">
            <AlertTriangle className="h-3 w-3 mr-1" />
            SIMULATION FAILED
          </Badge>
        ) : activeCrises.length > 0 ? (
          activeCrises.map((crisis, i) => (
            <Badge key={i} variant="destructive" className="animate-pulse">
              <AlertTriangle className="h-3 w-3 mr-1" />
              {CRISIS_LABELS[crisis.type]} ({crisis.ticksRemaining}t)
            </Badge>
          ))
        ) : (
          <Badge variant="outline" className="text-primary border-primary/30">
            All Systems Nominal
          </Badge>
        )}
      </div>
    </div>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  unit,
  status,
}: {
  icon: React.ElementType
  label: string
  value: string
  unit: string
  status: 'healthy' | 'warning' | 'critical'
}) {
  const statusColors = {
    healthy: 'text-primary',
    warning: 'text-accent',
    critical: 'text-destructive',
  }

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm">
      <CardContent className="py-2 px-3 flex items-center gap-2">
        <Icon className={`h-4 w-4 ${statusColors[status]}`} />
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</div>
          <div className={`text-sm font-semibold ${statusColors[status]}`}>
            {value} <span className="text-xs font-normal text-muted-foreground">{unit}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
