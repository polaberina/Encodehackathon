"use client"

import { useState } from 'react'
import { 
  ChevronLeft, ChevronRight, Activity, Handshake, Zap, Shield, 
  AlertTriangle, DollarSign, Wrench, Flame, Cpu 
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useSimulation } from '@/lib/simulation-context'
import { ZONE_CONFIGS, CRISIS_LABELS, TIER_COLORS, ACTION_COSTS, type GovernorActionType } from '@/lib/simulation-types'
import { cn } from '@/lib/utils'

export function ActivitySidebar() {
  const { simulationState, tick } = useSimulation()
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [activeTab, setActiveTab] = useState<'all' | 'crises' | 'actions'>('all')

  if (!simulationState) return null

  const { recentActions = [], activeCrises = [], crisisAgent, negotiations = [], zones = [] } = simulationState

  const getActionIcon = (type: GovernorActionType) => {
    switch (type) {
      case 'repair_route':
      case 'repair_source':
        return Wrench
      case 'fortify_route':
        return Shield
      case 'boost_source':
      case 'deploy_emergency_generator':
        return Zap
      case 'propose_trade':
      case 'accept_trade':
        return Handshake
      case 'sell_surplus':
        return DollarSign
      default:
        return Activity
    }
  }

  const getZoneColor = (zoneName: string) => {
    const zone = zones.find(z => z.name === zoneName)
    if (zone) {
      return ZONE_CONFIGS[zone.archetype].color
    }
    return 'var(--muted-foreground)'
  }

  const getZoneNameById = (zoneId: string) => {
    const zone = zones.find(z => z.id === zoneId)
    return zone?.name || zoneId
  }

  // Calculate totals
  const totalGovernorSpent = (recentActions ?? []).reduce((sum, a) => sum + a.cost, 0)
  const totalCrisisSpent = (activeCrises ?? []).reduce((sum, c) => sum + c.cost, 0)

  return (
    <div
      className={cn(
        'absolute left-0 top-0 bottom-12 bg-card/90 backdrop-blur-md border-r border-border transition-all duration-300 flex flex-col',
        isCollapsed ? 'w-12' : 'w-80'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        {!isCollapsed && (
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-foreground">Battle Log</span>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 ml-auto"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {!isCollapsed && (
        <>
          {/* Tab selector */}
          <div className="flex p-2 gap-1 border-b border-border">
            {(['all', 'crises', 'actions'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  'flex-1 px-2 py-1.5 rounded text-xs font-medium transition-colors',
                  activeTab === tab 
                    ? tab === 'crises' ? 'bg-red-500/20 text-red-400' : 'bg-primary/20 text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
                )}
              >
                {tab === 'all' ? 'All' : tab === 'crises' ? 'Attacks' : 'Defense'}
              </button>
            ))}
          </div>

          {/* Budget Summary */}
          <div className="p-3 border-b border-border">
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 rounded-md bg-red-950/50 border border-red-500/30">
                <div className="flex items-center gap-1.5 text-red-400 text-xs mb-1">
                  <Flame className="h-3 w-3" />
                  <span>Crisis Agent</span>
                </div>
                <div className="text-lg font-semibold text-red-300">{Math.round(crisisAgent?.budget ?? 0)} cr</div>
                <div className="text-xs text-red-400/60">+{crisisAgent?.incomeThisTick ?? 0}/tick</div>
              </div>
              <div className="p-2 rounded-md bg-primary/10 border border-primary/30">
                <div className="flex items-center gap-1.5 text-primary text-xs mb-1">
                  <Shield className="h-3 w-3" />
                  <span>Zones Total</span>
                </div>
                <div className="text-lg font-semibold text-foreground">
                  {Math.round(simulationState.globalMetrics?.totalZoneBudget ?? 0)} cr
                </div>
                <div className="text-xs text-muted-foreground">4 zones</div>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-auto">
            {/* Crisis Agent Attacks */}
            {(activeTab === 'all' || activeTab === 'crises') && activeCrises.length > 0 && (
              <div className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs text-red-400 uppercase tracking-wide flex items-center gap-1.5">
                    <AlertTriangle className="h-3 w-3" />
                    Active Attacks
                  </h4>
                  <span className="text-xs text-red-400/60">{totalCrisisSpent} cr spent</span>
                </div>
                <div className="space-y-2">
                  {(activeCrises ?? []).map(crisis => (
                    <div
                      key={crisis.crisisId}
                      className="p-2 rounded-md bg-red-950/40 border border-red-500/20"
                    >
                      <div className="flex items-start gap-2">
                        <div className="w-6 h-6 rounded-md bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <Flame className="h-3 w-3 text-red-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-red-200">
                              {CRISIS_LABELS[crisis.crisisType]}
                            </span>
                            <span 
                              className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                              style={{ background: TIER_COLORS[crisis.tier], color: '#000' }}
                            >
                              {crisis.tier.toUpperCase()}
                            </span>
                          </div>
                          <div className="flex items-center justify-between mt-1 text-xs">
                            <span className="text-red-300/70">→ {getZoneNameById(crisis.targetId)}</span>
                            <span className="text-red-400/60">{crisis.cost} cr</span>
                          </div>
                          <p className="text-xs text-red-300/50 mt-1">{crisis.description}</p>
                          <div className="flex items-center justify-between mt-1">
                            <div className="h-1 flex-1 bg-red-900/50 rounded-full overflow-hidden mr-2">
                              <div 
                                className="h-full bg-red-500 transition-all"
                                style={{ width: `${(crisis.remainingTicks / crisis.duration) * 100}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-red-400/60">{crisis.remainingTicks}t</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Governor Actions */}
            {(activeTab === 'all' || activeTab === 'actions') && (
              <div className="p-3 border-t border-border">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs text-primary uppercase tracking-wide flex items-center gap-1.5">
                    <Shield className="h-3 w-3" />
                    Defense Actions
                  </h4>
                  <span className="text-xs text-muted-foreground">{totalGovernorSpent} cr spent</span>
                </div>
                <div className="space-y-2">
                  {(recentActions ?? []).slice(0, 6).map(action => {
                    const Icon = getActionIcon(action.type)
                    const zoneColor = getZoneColor(action.zoneName)
                    const isCounter = action.details.startsWith('[COUNTER]')
                    
                    return (
                      <div
                        key={action.id}
                        className={cn(
                          'p-2 rounded-md transition-colors',
                          isCounter 
                            ? 'bg-amber-950/30 border border-amber-500/20' 
                            : 'bg-secondary/50 hover:bg-secondary/80'
                        )}
                      >
                        <div className="flex items-start gap-2">
                          <div
                            className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5"
                            style={{ backgroundColor: `${zoneColor}20` }}
                          >
                            <Icon className="h-3 w-3" style={{ color: zoneColor }} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs font-medium text-foreground">{action.zoneName}</span>
                                {isCounter && (
                                  <span className="text-[10px] px-1 py-0.5 bg-amber-500/20 text-amber-400 rounded">
                                    COUNTER
                                  </span>
                                )}
                              </div>
                              <span className="text-xs text-muted-foreground">-{action.cost}cr</span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                              {action.details.replace('[COUNTER] ', '')}
                            </p>
                            <div className="flex items-center justify-between mt-1 text-[10px] text-muted-foreground/60">
                              <span className={cn(
                                'px-1.5 py-0.5 rounded',
                                action.status === 'completed' && 'bg-primary/20 text-primary',
                                action.status === 'executing' && 'bg-amber-500/20 text-amber-400',
                                action.status === 'pending' && 'bg-muted text-muted-foreground'
                              )}>
                                {action.status}
                              </span>
                              {action.latency > 0 && (
                                <span>+{action.latency}t latency</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Active Negotiations */}
            {activeTab === 'all' && (
              <div className="p-3 border-t border-border">
                <h4 className="text-xs text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <Handshake className="h-3 w-3" />
                  Trade Offers
                </h4>
                <div className="space-y-2">
                  {negotiations.map(neg => {
                    const fromZone = zones.find(z => z.id === neg.fromZoneId)
                    const toZone = zones.find(z => z.id === neg.toZoneId)
                    
                    return (
                      <div key={neg.id} className="p-2 rounded-md bg-secondary/50">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1">
                            <span style={{ color: fromZone ? ZONE_CONFIGS[fromZone.archetype].color : 'var(--foreground)' }}>
                              {fromZone?.name || 'Unknown'}
                            </span>
                            <span className="text-muted-foreground">→</span>
                            <span style={{ color: toZone ? ZONE_CONFIGS[toZone.archetype].color : 'var(--foreground)' }}>
                              {toZone?.name || 'Unknown'}
                            </span>
                          </div>
                          <span className={cn(
                            'px-1.5 py-0.5 rounded text-xs',
                            neg.status === 'accepted' && 'bg-primary/20 text-primary',
                            neg.status === 'pending' && 'bg-muted text-muted-foreground',
                            neg.status === 'rejected' && 'bg-destructive/20 text-destructive',
                            neg.status === 'expired' && 'bg-muted text-muted-foreground/50'
                          )}>
                            {neg.status}
                          </span>
                        </div>
                        <div className="mt-1 text-[10px] text-muted-foreground">
                          {neg.energyOffered > 0 && <span>{neg.energyOffered} MWh </span>}
                          {neg.budgetOffered > 0 && <span>{neg.budgetOffered} cr </span>}
                          {(neg.energyOffered > 0 || neg.budgetOffered > 0) && 'for '}
                          {neg.energyRequested > 0 && <span>{neg.energyRequested} MWh </span>}
                          {neg.budgetRequested > 0 && <span>{neg.budgetRequested} cr</span>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Footer Stats */}
          <div className="p-3 border-t border-border">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="p-2 rounded-md bg-red-950/30">
                <div className="text-lg font-semibold text-red-400">{activeCrises.length}</div>
                <div className="text-[10px] text-red-400/60">Attacks</div>
              </div>
              <div className="p-2 rounded-md bg-primary/10">
                <div className="text-lg font-semibold text-foreground">{recentActions.length}</div>
                <div className="text-[10px] text-muted-foreground">Actions</div>
              </div>
              <div className="p-2 rounded-md bg-secondary/50">
                <div className="text-lg font-semibold text-foreground">{negotiations.filter(n => n.status === 'accepted').length}</div>
                <div className="text-[10px] text-muted-foreground">Trades</div>
              </div>
            </div>
          </div>
        </>
      )}

      {isCollapsed && (
        <div className="flex-1 flex flex-col items-center py-4 gap-4">
          <div className="w-8 h-8 rounded-md bg-red-500/20 flex items-center justify-center">
            <AlertTriangle className="h-4 w-4 text-red-400" />
          </div>
          <div className="text-xs text-red-400 font-mono">{activeCrises.length}</div>
          <div className="w-8 h-8 rounded-md bg-primary/20 flex items-center justify-center">
            <Shield className="h-4 w-4 text-primary" />
          </div>
          <div className="text-xs text-muted-foreground font-mono">{recentActions.length}</div>
        </div>
      )}
    </div>
  )
}
