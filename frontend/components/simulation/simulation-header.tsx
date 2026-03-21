"use client"

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Zap, Play, Pause, SkipForward, RotateCcw, Map, BarChart3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useSimulation } from '@/lib/simulation-context'
import { cn } from '@/lib/utils'

export function SimulationHeader() {
  const pathname = usePathname()
  const { tick, isRunning, simulationState, toggleRunning, stepForward, reset } = useSimulation()

  const navItems = [
    { href: '/', label: 'Live Map', icon: Map },
    { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  ]

  return (
    <header className="h-14 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between px-4 sticky top-0 z-50">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-primary/20 flex items-center justify-center">
            <Zap className="h-5 w-5 text-primary" />
          </div>
          <span className="font-semibold text-foreground">R.E.A.C.T</span>
        </Link>

        <nav className="flex items-center gap-1">
          {navItems.map(item => (
            <Link key={item.href} href={item.href}>
              <Button
                variant={pathname === item.href ? 'secondary' : 'ghost'}
                size="sm"
                className={cn(
                  'gap-2',
                  pathname === item.href && 'bg-secondary text-secondary-foreground'
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Button>
            </Link>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-4">
        {simulationState && (
          <div className="flex items-center gap-3 text-sm">
            <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-secondary">
              <span className="text-muted-foreground">Tick</span>
              <span className="font-mono font-medium text-foreground">{tick}</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-secondary">
              <span className="text-muted-foreground">Season</span>
              <span className="font-medium text-foreground capitalize">{simulationState.season}</span>
            </div>
            <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-primary/10 border border-primary/20">
              <span className="text-xs text-primary/70 truncate max-w-32">{simulationState.tickPhase}</span>
            </div>
          </div>
        )}

        <div className="flex items-center gap-1 border-l border-border pl-4">
          <Button variant="ghost" size="icon" onClick={toggleRunning} className="h-8 w-8">
            {isRunning ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="icon" onClick={stepForward} disabled={isRunning} className="h-8 w-8">
            <SkipForward className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={reset} className="h-8 w-8">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
