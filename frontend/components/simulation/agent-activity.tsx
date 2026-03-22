'use client'

import type { AgentAction, TradeNegotiation } from '@/lib/simulation-types'
import { ZONE_CONFIGS } from '@/lib/simulation-types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  ArrowRightLeft, CheckCircle, XCircle, Gauge, AlertTriangle, Clock, Handshake,
  Hammer, Database, Wrench
} from 'lucide-react'

interface AgentActivityProps {
  actions: AgentAction[]
  negotiations: TradeNegotiation[]
}

const actionIcons: Record<string, React.ElementType> = {
  trade_request: ArrowRightLeft,
  trade_accept: CheckCircle,
  trade_reject: XCircle,
  adjust_production: Gauge,
  emergency_response: AlertTriangle,
  build_generator: Hammer,
  upgrade_storage: Database,
  repair: Wrench,
}

const actionColors: Record<string, string> = {
  trade_request: 'text-blue-400',
  trade_accept: 'text-green-400',
  trade_reject: 'text-red-400',
  adjust_production: 'text-yellow-400',
  emergency_response: 'text-orange-400',
  build_generator: 'text-cyan-400',
  upgrade_storage: 'text-purple-400',
  repair: 'text-emerald-400',
}

// Map zone names to their colors
const zoneColors: Record<string, string> = {
  Alpha: ZONE_CONFIGS.alpha.color,
  Beta: ZONE_CONFIGS.beta.color,
  Gamma: ZONE_CONFIGS.gamma.color,
}

export function AgentActivity({ actions, negotiations }: AgentActivityProps) {
  return (
    <div className="space-y-4 flex flex-col">
      {/* Recent Actions */}
      <Card className="bg-card/50 border-border backdrop-blur-sm flex-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            Governor Agent Activity
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-40">
            <div className="px-4 pb-4 space-y-2">
              {actions.map(action => {
                const Icon = actionIcons[action.type] || Gauge
                const zoneColor = zoneColors[action.zoneName] || '#888'
                return (
                  <div
                    key={action.id}
                    className="flex items-start gap-3 p-2 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                  >
                    <div className={`mt-0.5 ${actionColors[action.type] || 'text-gray-400'}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <div 
                          className="w-2 h-2 rounded-full" 
                          style={{ backgroundColor: zoneColor }}
                        />
                        <span className="text-xs font-medium">{action.zoneName}</span>
                        <Badge variant="outline" className="text-[10px] h-4 px-1">
                          T{action.tick}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{action.details}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Active Negotiations */}
      <Card className="bg-card/50 border-border backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Handshake className="h-4 w-4 text-muted-foreground" />
            Bilateral Trade Negotiations
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {negotiations.map(neg => {
            const buyerColor = zoneColors[neg.buyerZone] || '#888'
            const sellerColor = zoneColors[neg.sellerZone] || '#888'
            return (
              <div
                key={neg.id}
                className="flex items-center justify-between p-2 rounded-lg bg-secondary/30"
              >
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 text-xs">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: buyerColor }} />
                    <span className="font-medium">{neg.buyerZone}</span>
                    <ArrowRightLeft className="h-3 w-3 text-muted-foreground" />
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: sellerColor }} />
                    <span className="font-medium">{neg.sellerZone}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <div className="text-xs font-mono">{neg.amount} MWh</div>
                    <div className="text-[10px] text-muted-foreground">${neg.pricePerUnit}/unit</div>
                  </div>
                  <Badge
                    variant={
                      neg.status === 'completed'
                        ? 'default'
                        : neg.status === 'accepted'
                        ? 'secondary'
                        : neg.status === 'pending'
                        ? 'outline'
                        : 'destructive'
                    }
                    className="text-[10px] min-w-[60px] justify-center"
                  >
                    {neg.status}
                  </Badge>
                </div>
              </div>
            )
          })}
          {/* Reputation indicator */}
          <div className="text-[10px] text-muted-foreground text-center pt-1 border-t border-border">
            Reputation affects future trade acceptance rates
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
