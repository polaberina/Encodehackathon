'use client'

import { useState } from 'react'
import { useSimulation } from '@/lib/simulation-context'
import { GridMap } from './grid-map'
import { ZoneDetail } from './zone-detail'
import { AgentActivity } from './agent-activity'
import { GlobalMetrics } from './global-metrics'
import { EnergyChart } from './energy-chart'
import { TickLifecycle } from './tick-lifecycle'
import { VictoryTracker } from './victory-tracker'
import { Button } from '@/components/ui/button'
import { Play, Pause, SkipForward, RotateCcw, Zap } from 'lucide-react'

export function SimulationDashboard() {
  const { tick, isRunning, simulationState, toggleRunning, stepForward, reset } = useSimulation()
  const [selectedZone, setSelectedZone] = useState<string | null>(null)

  // Show loading state until API responds
  if (!simulationState) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center animate-pulse">
            <Zap className="h-7 w-7 text-primary" />
          </div>
          <div className="text-sm text-muted-foreground">Connecting to R.E.A.C.T Engine...</div>
        </div>
      </div>
    )
  }

  const selectedZoneData = (simulationState.zones ?? []).find(z => z.id === selectedZone) ?? null

  return (
    <div className="h-screen flex flex-col bg-background text-foreground overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-card/30 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
              <Zap className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">R.E.A.C.T</h1>
              <p className="text-[10px] text-muted-foreground -mt-0.5">Resilient Energy Autonomous Crisis Taskforce</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={reset} title="Reset Simulation">
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={stepForward} disabled={isRunning} title="Step Forward">
            <SkipForward className="h-4 w-4" />
          </Button>
          <Button variant={isRunning ? 'secondary' : 'default'} size="sm" onClick={toggleRunning}>
            {isRunning ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            <span className="ml-1.5">{isRunning ? 'Pause' : 'Run'}</span>
          </Button>
        </div>
      </header>

      {/* Global Metrics Bar */}
      <div className="px-6 py-3 border-b border-border bg-card/20">
        <GlobalMetrics state={simulationState} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Grid Map */}
        <div className="flex-1 p-4 flex flex-col gap-4 min-w-0">
          <div className="flex-1 rounded-lg border border-border overflow-hidden bg-card/20">
            <GridMap
              zones={simulationState.zones ?? []}
              tradeRoutes={simulationState.tradeRoutes ?? []}
              selectedZone={selectedZone}
              onSelectZone={setSelectedZone}
              tick={tick}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <EnergyChart zones={simulationState.zones ?? []} />
            <TickLifecycle currentTick={tick} />
          </div>
        </div>

        {/* Right Panel - Details */}
        <div className="w-[420px] border-l border-border p-4 flex flex-col gap-4 overflow-y-auto">
          {/* Victory Conditions Tracker */}
          <VictoryTracker 
            conditions={simulationState.victoryConditions ?? []} 
            zones={simulationState.zones ?? []}
          />
          
          {/* Zone Detail */}
          <ZoneDetail zone={selectedZoneData} />
          
          {/* Agent Activity */}
          <AgentActivity
            actions={simulationState.recentActions ?? []}
            negotiations={simulationState.negotiations ?? []}
          />
        </div>
      </div>

      {/* Event Log */}
      {simulationState.recentLogs && simulationState.recentLogs.length > 0 && (
        <div className="px-6 py-2 border-t border-border bg-card/10 max-h-24 overflow-y-auto">
          {[...simulationState.recentLogs].reverse().map((entry: { tick: number; message: string }, i: number) => (
            <div key={i} className="text-[10px] text-muted-foreground font-mono leading-4">
              <span className="text-primary/60 mr-2">[t{entry.tick}]</span>{entry.message}
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      <footer className="px-6 py-2 border-t border-border bg-card/30 text-xs text-muted-foreground flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span>Tick {tick} / 25</span>
          <span>Season: {simulationState.season?.toUpperCase()}</span>
          <span>Active Crises: {(simulationState.activeCrises ?? []).length}</span>
          <span>Routes: {(simulationState.tradeRoutes ?? []).length}</span>
        </div>
        <span>R.E.A.C.T Engine — Live Data</span>
      </footer>
    </div>
  )
}
