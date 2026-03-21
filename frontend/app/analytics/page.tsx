"use client"

import { useState, useEffect } from 'react'
import { Zap, TrendingUp, Shield, Target, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSimulation } from '@/lib/simulation-context'
import { ZONE_CONFIGS, ENERGY_CONFIGS } from '@/lib/simulation-types'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'

export default function AnalyticsPage() {
  const { simulationState, tick } = useSimulation()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  if (!simulationState) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center animate-pulse">
            <Zap className="h-7 w-7 text-primary" />
          </div>
          <div className="text-sm text-muted-foreground">Loading Analytics...</div>
        </div>
      </div>
    )
  }

  const { zones, globalMetrics, victoryConditions, tradeRoutes, activeCrises } = simulationState

  // Prepare zone comparison data
  const zoneComparisonData = zones.map(zone => ({
    name: zone.name,
    storage: Math.round((zone.storage / zone.maxStorage) * 100),
    morale: Math.round(zone.morale),
    economy: Math.round(zone.economy),
    efficiency: Math.round(zone.efficiencyScore),
    color: ZONE_CONFIGS[zone.archetype].color,
  }))

  // Prepare energy mix data
  const energyMixData: { type: string; value: number; color: string }[] = []
  const energyTotals: Record<string, number> = {}
  zones.forEach(zone => {
    zone.energySources.forEach(source => {
      energyTotals[source.type] = (energyTotals[source.type] || 0) + source.output
    })
  })
  Object.entries(energyTotals).forEach(([type, value]) => {
    const config = ENERGY_CONFIGS[type as keyof typeof ENERGY_CONFIGS]
    energyMixData.push({
      type: config.label,
      value: Math.round(value),
      color: config.color,
    })
  })

  // Prepare zone production data
  const zoneProductionData = zones.map(zone => {
    const data: Record<string, number | string> = { name: zone.name }
    zone.energySources.forEach(source => {
      data[ENERGY_CONFIGS[source.type].label] = Math.round(source.output)
    })
    return data
  })

  // Radar chart data for zone performance
  const radarData = zones.map(zone => ({
    zone: zone.name,
    Storage: Math.round((zone.storage / zone.maxStorage) * 100),
    Morale: Math.round(zone.morale),
    Economy: Math.round(zone.economy),
    Efficiency: Math.round(zone.efficiencyScore),
    'Crisis Rate': Math.round((zone.crisesMitigated / Math.max(zone.crisesTotal, 1)) * 100),
  }))

  // Trade route stats
  const activeRoutes = tradeRoutes.filter(r => r.isActive).length
  const avgRouteEfficiency = tradeRoutes.reduce((sum, r) => sum + r.efficiency, 0) / tradeRoutes.length
  const totalTradeFlow = tradeRoutes.filter(r => r.isActive).reduce((sum, r) => sum + r.currentFlow, 0)

  // Clean energy calculation
  const cleanTypes = ['solar', 'wind', 'hydro', 'nuclear', 'biomass', 'geothermal']
  const totalOutput = Object.values(energyTotals).reduce((sum, val) => sum + val, 0)
  const cleanOutput = Object.entries(energyTotals)
    .filter(([type]) => cleanTypes.includes(type))
    .reduce((sum, [, val]) => sum + val, 0)
  const gridCleanliness = totalOutput > 0 ? Math.round((cleanOutput / totalOutput) * 100) : 0

  return (
    <div className="h-[calc(100vh-3.5rem)] overflow-auto bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Analytics Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Simulation performance metrics and zone analysis
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="px-3 py-1.5 rounded-md bg-secondary text-sm">
              <span className="text-muted-foreground">Tick:</span>
              <span className="ml-2 font-mono font-medium text-foreground">{tick}</span>
            </div>
          </div>
        </div>

        {/* Victory Conditions Card */}
        <Card className="border-primary/20 bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Target className="h-5 w-5 text-primary" />
              Victory Conditions
            </CardTitle>
            <CardDescription>Track your progress toward simulation victory</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-6">
              {/* Survival Ticks */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Survive 100+ Ticks</span>
                  {victoryConditions.ticksSurvived >= victoryConditions.targetTicks ? (
                    <CheckCircle className="h-4 w-4 text-primary" />
                  ) : (
                    <XCircle className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all"
                    style={{ width: `${Math.min(100, (victoryConditions.ticksSurvived / victoryConditions.targetTicks) * 100)}%` }}
                  />
                </div>
                <div className="text-sm font-mono text-foreground">
                  {victoryConditions.ticksSurvived} / {victoryConditions.targetTicks} ticks
                </div>
              </div>

              {/* Storage Threshold */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">All Zones Above 20% Storage</span>
                  {victoryConditions.allZonesAboveStorageThreshold ? (
                    <CheckCircle className="h-4 w-4 text-primary" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {zones.map(zone => {
                    const ratio = zone.storage / zone.maxStorage
                    const isAbove = ratio > 0.2
                    return (
                      <div key={zone.id} className="flex-1">
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${ratio * 100}%`,
                              backgroundColor: isAbove ? ZONE_CONFIGS[zone.archetype].color : 'var(--destructive)',
                            }}
                          />
                        </div>
                        <div className="text-xs text-center mt-1 text-muted-foreground">{zone.name}</div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Crisis Mitigation */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">80%+ Crisis Mitigation Rate</span>
                  {victoryConditions.crisisMitigationRate >= victoryConditions.targetMitigationRate ? (
                    <CheckCircle className="h-4 w-4 text-primary" />
                  ) : (
                    <XCircle className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(100, victoryConditions.crisisMitigationRate)}%`,
                      backgroundColor: victoryConditions.crisisMitigationRate >= 80 ? 'var(--primary)' : 'var(--accent)',
                    }}
                  />
                </div>
                <div className="text-sm font-mono text-foreground">
                  {Math.round(victoryConditions.crisisMitigationRate)}% / {victoryConditions.targetMitigationRate}%
                </div>
              </div>
            </div>

            {/* Victory/Defeat Status */}
            {victoryConditions.isVictory && (
              <div className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/20 text-center">
                <span className="text-primary font-semibold">Victory Achieved!</span>
              </div>
            )}
            {victoryConditions.isDefeat && (
              <div className="mt-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-center">
                <span className="text-destructive font-semibold">
                  Defeat: {victoryConditions.defeatReason}
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Key Metrics Row */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="bg-card">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Zap className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="text-2xl font-semibold text-foreground">{Math.round(globalMetrics.totalSupply)} MW</div>
                  <div className="text-sm text-muted-foreground">Total Production</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <TrendingUp className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <div className="text-2xl font-semibold text-foreground">{Math.round(globalMetrics.gridStability * 100)}%</div>
                  <div className="text-sm text-muted-foreground">Grid Stability</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Shield className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="text-2xl font-semibold text-foreground">{gridCleanliness}%</div>
                  <div className="text-sm text-muted-foreground">Clean Energy</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${activeCrises.length > 0 ? 'bg-destructive/10' : 'bg-primary/10'}`}>
                  <AlertTriangle className={`h-5 w-5 ${activeCrises.length > 0 ? 'text-destructive' : 'text-primary'}`} />
                </div>
                <div>
                  <div className="text-2xl font-semibold text-foreground">{activeCrises.length}</div>
                  <div className="text-sm text-muted-foreground">Active Crises</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-2 gap-6">
          {/* Zone Performance Comparison */}
          <Card className="bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Zone Performance Comparison</CardTitle>
              <CardDescription>Storage, morale, economy, and efficiency by zone</CardDescription>
            </CardHeader>
            <CardContent>
              <div style={{ width: '100%', height: 256 }}>
                {isMounted && (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={zoneComparisonData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="name" tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
                      <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--card)',
                          border: '1px solid var(--border)',
                          borderRadius: '8px',
                        }}
                      />
                      <Legend />
                      <Bar dataKey="storage" name="Storage %" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="morale" name="Morale %" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="economy" name="Economy %" fill="var(--chart-3)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Energy Mix Pie Chart */}
          <Card className="bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Grid Energy Mix</CardTitle>
              <CardDescription>Distribution of energy sources across all zones</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center" style={{ width: '100%', height: 256 }}>
                <div style={{ width: '60%', height: '100%' }}>
                  {isMounted && (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={energyMixData}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={2}
                          dataKey="value"
                        >
                          {energyMixData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(value: number) => [`${value} MW`, 'Output']}
                          contentStyle={{
                            backgroundColor: 'var(--card)',
                            border: '1px solid var(--border)',
                            borderRadius: '8px',
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </div>
                <div className="flex-1 space-y-1 pl-4">
                  {energyMixData.map(item => (
                    <div key={item.type} className="flex items-center gap-2 text-sm">
                      <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: item.color }} />
                      <span className="text-muted-foreground flex-1">{item.type}</span>
                      <span className="font-mono text-foreground">{item.value} MW</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Zone Radar & Trade Stats */}
        <div className="grid grid-cols-3 gap-6">
          {/* Zone Performance Radar */}
          <Card className="col-span-2 bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Zone Performance Radar</CardTitle>
              <CardDescription>Multi-dimensional performance comparison</CardDescription>
            </CardHeader>
            <CardContent>
              <div style={{ width: '100%', height: 288 }}>
                {isMounted && (
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={[
                      { metric: 'Storage', ...Object.fromEntries(radarData.map(z => [z.zone, z.Storage])) },
                      { metric: 'Morale', ...Object.fromEntries(radarData.map(z => [z.zone, z.Morale])) },
                      { metric: 'Economy', ...Object.fromEntries(radarData.map(z => [z.zone, z.Economy])) },
                      { metric: 'Efficiency', ...Object.fromEntries(radarData.map(z => [z.zone, z.Efficiency])) },
                      { metric: 'Crisis Rate', ...Object.fromEntries(radarData.map(z => [z.zone, z['Crisis Rate']])) },
                    ]}>
                      <PolarGrid stroke="var(--border)" />
                      <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} />
                      <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                      {zones.map(zone => (
                        <Radar
                          key={zone.id}
                          name={zone.name}
                          dataKey={zone.name}
                          stroke={ZONE_CONFIGS[zone.archetype].color}
                          fill={ZONE_CONFIGS[zone.archetype].color}
                          fillOpacity={0.15}
                        />
                      ))}
                      <Legend />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--card)',
                          border: '1px solid var(--border)',
                          borderRadius: '8px',
                        }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Trade Network Stats */}
          <Card className="bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Trade Network</CardTitle>
              <CardDescription>Inter-zone trade statistics</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3 rounded-lg bg-secondary/50">
                <div className="text-sm text-muted-foreground">Active Routes</div>
                <div className="text-2xl font-semibold text-foreground">{activeRoutes} / {tradeRoutes.length}</div>
              </div>
              <div className="p-3 rounded-lg bg-secondary/50">
                <div className="text-sm text-muted-foreground">Average Efficiency</div>
                <div className="text-2xl font-semibold text-foreground">{Math.round(avgRouteEfficiency * 100)}%</div>
              </div>
              <div className="p-3 rounded-lg bg-secondary/50">
                <div className="text-sm text-muted-foreground">Total Trade Flow</div>
                <div className="text-2xl font-semibold text-foreground">{Math.round(totalTradeFlow)} MW</div>
              </div>
              <div className="p-3 rounded-lg bg-secondary/50">
                <div className="text-sm text-muted-foreground">Avg Route Health</div>
                <div className="text-2xl font-semibold text-foreground">
                  {Math.round((tradeRoutes.reduce((sum, r) => sum + r.health, 0) / tradeRoutes.length) * 100)}%
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Zone Details Table */}
        <Card className="bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Zone Details</CardTitle>
            <CardDescription>Comprehensive zone-by-zone breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 text-muted-foreground font-medium">Zone</th>
                    <th className="text-left py-2 px-3 text-muted-foreground font-medium">Strategy</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Storage</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Supply</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Demand</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Morale</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Economy</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Crises</th>
                    <th className="text-center py-2 px-3 text-muted-foreground font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {zones.map(zone => {
                    const config = ZONE_CONFIGS[zone.archetype]
                    const storageRatio = zone.storage / zone.maxStorage
                    const status = storageRatio > 0.5 && zone.morale > 60 ? 'healthy' : storageRatio > 0.2 ? 'warning' : 'critical'
                    
                    return (
                      <tr key={zone.id} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                        <td className="py-2 px-3">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
                            <span className="font-medium text-foreground">{zone.name}</span>
                          </div>
                        </td>
                        <td className="py-2 px-3">
                          <span className="px-2 py-0.5 text-xs rounded-full capitalize" style={{ backgroundColor: `${config.color}20`, color: config.color }}>
                            {zone.strategy}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-foreground">{Math.round(storageRatio * 100)}%</td>
                        <td className="py-2 px-3 text-right font-mono text-foreground">{Math.round(zone.supply)} MW</td>
                        <td className="py-2 px-3 text-right font-mono text-foreground">{Math.round(zone.demand)} MW</td>
                        <td className="py-2 px-3 text-right font-mono text-foreground">{Math.round(zone.morale)}%</td>
                        <td className="py-2 px-3 text-right font-mono text-foreground">{Math.round(zone.economy)}%</td>
                        <td className="py-2 px-3 text-right font-mono text-foreground">{zone.crisesMitigated}/{zone.crisesTotal}</td>
                        <td className="py-2 px-3 text-center">
                          <span className={`inline-flex w-2 h-2 rounded-full ${
                            status === 'healthy' ? 'bg-[var(--status-healthy)]' :
                            status === 'warning' ? 'bg-[var(--status-warning)]' : 'bg-[var(--status-critical)]'
                          }`} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
