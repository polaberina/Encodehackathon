'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface TickLifecycleProps {
  currentTick: number
}

// 9-Step Game Loop from README
const lifecycleSteps = [
  { id: 1, name: 'Demand Calc', description: 'Compute zone energy needs', phase: 'compute' },
  { id: 2, name: 'Generation', description: 'Produce energy from sources', phase: 'compute' },
  { id: 3, name: 'Storage Mgmt', description: 'Charge/discharge batteries', phase: 'execute' },
  { id: 4, name: 'Trade Exec', description: 'Process energy transfers', phase: 'execute' },
  { id: 5, name: 'Crisis Events', description: 'Trigger and resolve crises', phase: 'crisis' },
  { id: 6, name: 'Action Proc', description: 'Execute Governor decisions', phase: 'action' },
  { id: 7, name: 'State Update', description: 'Recalculate zone conditions', phase: 'update' },
  { id: 8, name: 'Margin Det', description: 'Identify threshold violations', phase: 'update' },
  { id: 9, name: 'Log & Score', description: 'Record performance metrics', phase: 'score' },
]

const phaseConfig = {
  compute: { color: 'bg-blue-500', label: 'Compute', borderColor: 'border-blue-500/50', bgColor: 'bg-blue-500/15' },
  execute: { color: 'bg-emerald-500', label: 'Execute', borderColor: 'border-emerald-500/50', bgColor: 'bg-emerald-500/15' },
  crisis: { color: 'bg-red-500', label: 'Crisis', borderColor: 'border-red-500/50', bgColor: 'bg-red-500/15' },
  action: { color: 'bg-amber-500', label: 'Action', borderColor: 'border-amber-500/50', bgColor: 'bg-amber-500/15' },
  update: { color: 'bg-purple-500', label: 'Update', borderColor: 'border-purple-500/50', bgColor: 'bg-purple-500/15' },
  score: { color: 'bg-cyan-500', label: 'Score', borderColor: 'border-cyan-500/50', bgColor: 'bg-cyan-500/15' },
}

export function TickLifecycle({ currentTick }: TickLifecycleProps) {
  const currentStep = (currentTick % 9) + 1

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center justify-between">
          <span>9-Step Game Loop</span>
          <span className="text-xs font-mono text-primary">Step {currentStep}/9</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2">
          {lifecycleSteps.map((step) => {
            const config = phaseConfig[step.phase as keyof typeof phaseConfig]
            const isActive = step.id === currentStep
            const isPast = step.id < currentStep

            return (
              <div
                key={step.id}
                className={`
                  relative p-2 rounded-lg border transition-all
                  ${config.bgColor} ${config.borderColor}
                  ${isActive ? 'ring-2 ring-primary scale-[1.02] z-10' : ''}
                  ${isPast ? 'opacity-40' : ''}
                `}
              >
                {/* Phase indicator */}
                <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ${config.color}`} />
                
                {/* Step number */}
                <div className="text-[10px] font-mono text-muted-foreground mb-0.5">
                  {step.id.toString().padStart(2, '0')}
                </div>
                
                {/* Step name */}
                <div className="text-xs font-semibold truncate">
                  {step.name}
                </div>
                
                {/* Description on hover/active */}
                {isActive && (
                  <div className="text-[9px] text-muted-foreground mt-1 line-clamp-2">
                    {step.description}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        
        {/* Phase Legend */}
        <div className="flex flex-wrap justify-center gap-3 mt-3 text-[10px] text-muted-foreground">
          {Object.entries(phaseConfig).map(([key, config]) => (
            <span key={key} className="flex items-center gap-1">
              <span className={`w-2 h-2 rounded-full ${config.color}`} />
              {config.label}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
