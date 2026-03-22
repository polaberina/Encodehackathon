"use client"

import { Zap } from 'lucide-react'
import { TerritoryMap } from '@/components/simulation/territory-map'
import { ZoneInfoPanel } from '@/components/simulation/zone-info-panel'
import { LiveStatusBar } from '@/components/simulation/live-status-bar'
import { ActivitySidebar } from '@/components/simulation/activity-sidebar'
import { useSimulation } from '@/lib/simulation-context'

export default function LiveMapPage() {
  const { simulationState } = useSimulation()

  if (!simulationState) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center animate-pulse">
            <Zap className="h-7 w-7 text-primary" />
          </div>
          <div className="text-sm text-muted-foreground">Initializing R.E.A.C.T Simulation...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] relative overflow-hidden">
      {/* Activity Sidebar (left side) */}
      <ActivitySidebar />
      
      {/* Main Map */}
      <TerritoryMap />
      
      {/* Zone Info Panel (right side) */}
      <ZoneInfoPanel />
      
      {/* Bottom Status Bar */}
      <LiveStatusBar />
    </div>
  )
}
