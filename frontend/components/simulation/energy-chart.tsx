'use client'

import { useMemo } from 'react'
import type { Zone } from '@/lib/simulation-types'
import { ENERGY_CONFIGS } from '@/lib/simulation-types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts'

interface EnergyChartProps {
  zones: Zone[]
}

export function EnergyChart({ zones }: EnergyChartProps) {
  const chartData = useMemo(() => {
    return zones.map(zone => {
      const data: Record<string, string | number> = { 
        name: zone.name,
        color: zone.color 
      }
      zone.energySources.forEach(source => {
        data[source.type] = Math.round(source.output)
      })
      return data
    })
  }, [zones])

  // Get all unique energy types from all zones
  const allEnergyTypes = useMemo(() => {
    const types = new Set<string>()
    zones.forEach(zone => {
      zone.energySources.forEach(source => {
        types.add(source.type)
      })
    })
    return Array.from(types)
  }, [zones])

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Energy Production by Zone</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis 
                dataKey="name" 
                tick={{ fill: '#999', fontSize: 11 }} 
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              />
              <YAxis 
                tick={{ fill: '#999', fontSize: 11 }} 
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                tickFormatter={(v) => `${v}`}
                label={{ value: 'MW', angle: -90, position: 'insideLeft', fill: '#666', fontSize: 10 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(20, 25, 40, 0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                labelStyle={{ color: '#fff', fontWeight: 'bold' }}
                formatter={(value: number, name: string) => [
                  `${value} MW`,
                  ENERGY_CONFIGS[name as keyof typeof ENERGY_CONFIGS]?.label || name
                ]}
              />
              <Legend 
                wrapperStyle={{ fontSize: '10px' }}
                formatter={(value) => ENERGY_CONFIGS[value as keyof typeof ENERGY_CONFIGS]?.label || value}
              />
              {allEnergyTypes.map(type => (
                <Bar 
                  key={type} 
                  dataKey={type} 
                  stackId="a" 
                  fill={ENERGY_CONFIGS[type as keyof typeof ENERGY_CONFIGS]?.color || '#888'} 
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
        {/* Energy Type Legend with MW values */}
        <div className="flex flex-wrap gap-2 mt-2 text-[10px]">
          {Object.entries(ENERGY_CONFIGS).map(([type, config]) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
              <span className="text-muted-foreground">{config.label}</span>
              <span className="text-foreground font-mono">{config.baseOutput}MW</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
