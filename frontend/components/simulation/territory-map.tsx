"use client"

import { useEffect, useState, useMemo } from 'react'
import { ComposableMap, Geographies, Geography, Line, Marker } from 'react-simple-maps'
import { useSimulation } from '@/lib/simulation-context'
import { 
  ZONE_CONFIGS, ZONE_COUNTRY_CODES, CRISIS_LABELS, TIER_COLORS, STABILITY_COLORS,
  type Zone, type CrisisEvent 
} from '@/lib/simulation-types'

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json"

// Country centroids for labels and connections
const COUNTRY_CENTROIDS: Record<string, [number, number]> = {
  DEU: [10.5, 51.2],
  FRA: [2.5, 46.5],
  POL: [19.4, 52.0],
  UKR: [31.2, 48.8],
}

// Info box positions — placed so the box edge touches the centroid (route endpoint)
// Each box is 130px wide, 24px tall in SVG units; offset so it sits just outside the country
const LABEL_OFFSETS: Record<string, { dx: number; dy: number }> = {
  DEU: { dx: -8, dy: -8 },   // above-left
  FRA: { dx: -8, dy:  8 },   // below-left
  POL: { dx:  8, dy: -8 },   // above-right
  UKR: { dx:  8, dy:  8 },   // below-right
}

// Trade route connections
const TRADE_CONNECTIONS: [string, string][] = [
  ['DEU', 'FRA'],
  ['DEU', 'POL'],
  ['POL', 'UKR'],
  ['FRA', 'DEU'],
  ['DEU', 'UKR'],
  ['FRA', 'POL'],
]

// Crisis agent attack origin (off-screen menace)
const CRISIS_AGENT_ORIGIN: [number, number] = [40, 65]

interface TradeFlowParticle {
  id: string
  routeIndex: number
  progress: number
  speed: number
}

interface AttackParticle {
  id: string
  crisisId: string
  progress: number
  speed: number
}

export function TerritoryMap() {
  const { simulationState, selectedZone, setSelectedZone, tick } = useSimulation()
  const [hoveredZone, setHoveredZone] = useState<string | null>(null)
  const [particles, setParticles] = useState<TradeFlowParticle[]>([])
  const [attackParticles, setAttackParticles] = useState<AttackParticle[]>([])

  const getArchetypeByCode = (code: string) => {
    return Object.entries(ZONE_COUNTRY_CODES).find(([_, c]) => c === code)?.[0] as keyof typeof ZONE_CONFIGS | undefined
  }

  const codeToZoneId = useMemo(() => {
    if (!simulationState) return {}
    const map: Record<string, string> = {}
    ;(simulationState.zones ?? []).forEach(zone => {
      const code = ZONE_COUNTRY_CODES[zone.archetype]
      if (code) map[code] = zone.id
    })
    return map
  }, [simulationState])

  // Initialize trade particles
  useEffect(() => {
    if (!simulationState) return

    const activeRoutes = (simulationState.tradeRoutes ?? []).filter(r => r.isActive)
    const newParticles: TradeFlowParticle[] = []
    
    activeRoutes.forEach((route, index) => {
      const particleCount = Math.ceil(route.currentFlow / 40)
      for (let i = 0; i < particleCount; i++) {
        newParticles.push({
          id: `${route.id}-${i}`,
          routeIndex: index,
          progress: (i / particleCount) * 100,
          speed: 0.6 + Math.random() * 0.3,
        })
      }
    })
    setParticles(newParticles)
  }, [simulationState?.tradeRoutes, tick])

  // Initialize attack particles for active crises
  useEffect(() => {
    if (!simulationState) return

    const newAttackParticles: AttackParticle[] = []
    ;(simulationState.activeCrises ?? []).forEach(crisis => {
      for (let i = 0; i < 3; i++) {
        newAttackParticles.push({
          id: `attack-${crisis.crisisId}-${i}`,
          crisisId: crisis.crisisId,
          progress: (i / 3) * 100,
          speed: 0.8 + Math.random() * 0.4,
        })
      }
    })
    setAttackParticles(newAttackParticles)
  }, [simulationState?.activeCrises, tick])

  // Animate particles
  useEffect(() => {
    const interval = setInterval(() => {
      setParticles(prev =>
        prev.map(p => ({
          ...p,
          progress: (p.progress + p.speed) % 100,
        }))
      )
      setAttackParticles(prev =>
        prev.map(p => ({
          ...p,
          progress: (p.progress + p.speed) % 100,
        }))
      )
    }, 50)
    return () => clearInterval(interval)
  }, [])

  if (!simulationState) return null

  const targetCountryCodes = Object.values(ZONE_COUNTRY_CODES)

  const getZoneByCode = (code: string): Zone | undefined => {
    const archetype = getArchetypeByCode(code)
    if (!archetype) return undefined
    return (simulationState.zones ?? []).find(z => z.archetype === archetype)
  }

  const getZoneById = (id: string): Zone | undefined => {
    return (simulationState.zones ?? []).find(z => z.id === id)
  }

  const interpolate = (from: [number, number], to: [number, number], t: number): [number, number] => {
    return [
      from[0] + (to[0] - from[0]) * t,
      from[1] + (to[1] - from[1]) * t,
    ]
  }

  // Get zone centroid by zone ID
  const getZoneCentroid = (zoneId: string): [number, number] | null => {
    const zone = getZoneById(zoneId)
    if (!zone) return null
    const code = ZONE_COUNTRY_CODES[zone.archetype]
    return COUNTRY_CENTROIDS[code] || null
  }

  return (
    <div className="relative w-full h-full bg-background overflow-hidden">
      {/* Grid background */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: `
            linear-gradient(to right, var(--border) 1px, transparent 1px),
            linear-gradient(to bottom, var(--border) 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
        }}
      />

      {/* Crisis Agent Status Panel */}
      <div className="absolute top-4 right-4 bg-red-950/90 backdrop-blur-sm rounded-lg p-3 text-xs border border-red-500/50 z-10 w-56">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="font-semibold text-red-400">CRISIS AGENT</span>
        </div>
        <div className="space-y-1 text-red-200/80">
          <div className="flex justify-between">
            <span>Budget:</span>
            <span className="font-mono text-red-400">{Math.round(simulationState.crisisAgent?.budget ?? 0)} cr</span>
          </div>
          <div className="flex justify-between">
            <span>Income/tick:</span>
            <span className="font-mono text-red-300">+{simulationState.crisisAgent?.incomeThisTick ?? 0} cr</span>
          </div>
          <div className="flex justify-between">
            <span>Total Spent:</span>
            <span className="font-mono">{Math.round(simulationState.crisisAgent?.totalSpent ?? 0)} cr</span>
          </div>
          <div className="mt-2 pt-2 border-t border-red-500/30 text-[10px]">
            <div className="text-red-300/60 mb-1">STRATEGY:</div>
            <div className="text-red-200 italic">{simulationState.crisisAgent?.strategy}</div>
          </div>
          {(simulationState.crisisAgent?.vulnerabilityRanking ?? []).length > 0 && (
            <div className="mt-2 pt-2 border-t border-red-500/30 text-[10px]">
              <div className="text-red-300/60 mb-1">TARGET PRIORITY:</div>
              {(simulationState.crisisAgent?.vulnerabilityRanking ?? []).slice(0, 3).map((name, i) => (
                <div key={name} className="flex items-center gap-1">
                  <span className="text-red-500">{i + 1}.</span>
                  <span>{name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="absolute bottom-24 left-4 bg-card/90 backdrop-blur-sm rounded-lg p-3 text-xs border border-border z-10">
        <div className="font-semibold mb-2 text-foreground">Legend</div>
        <div className="space-y-1.5 text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-8 h-0.5 bg-primary opacity-60" />
            <span>Trade Route</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-0.5 bg-red-500 opacity-60" style={{ background: 'linear-gradient(90deg, #EF4444 50%, transparent 50%)', backgroundSize: '8px 1px' }} />
            <span>Crisis Attack</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary opacity-80" />
            <span>Energy Flow</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500 opacity-80" />
            <span>Attack Wave</span>
          </div>
          <div className="mt-2 pt-2 border-t border-border">
            <div className="text-muted-foreground mb-1">Zone Status:</div>
            {Object.entries(STABILITY_COLORS).map(([state, color]) => (
              <div key={state} className="flex items-center gap-2 mt-1">
                <div className="w-3 h-3 rounded-full" style={{ background: color }} />
                <span className="capitalize">{state}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Active Crises List */}
      {(simulationState.activeCrises ?? []).length > 0 && (
        <div className="absolute bottom-24 right-4 bg-red-950/80 backdrop-blur-sm rounded-lg p-3 text-xs border border-red-500/30 z-10 max-w-64">
          <div className="font-semibold mb-2 text-red-400 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            Active Crises ({(simulationState.activeCrises ?? []).length})
          </div>
          <div className="space-y-2 max-h-40 overflow-auto">
            {(simulationState.activeCrises ?? []).map(crisis => {
              const targetZone = getZoneById(crisis.targetId)
              return (
                <div key={crisis.crisisId} className="bg-red-900/50 rounded p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-red-200">{CRISIS_LABELS[crisis.crisisType]}</span>
                    <span 
                      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                      style={{ background: TIER_COLORS[crisis.tier], color: '#000' }}
                    >
                      {crisis.tier.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-red-300/70 mt-1">
                    Target: {targetZone?.name || crisis.targetId}
                  </div>
                  <div className="flex justify-between text-red-400/60 mt-1">
                    <span>Cost: {crisis.cost} cr</span>
                    <span>{crisis.remainingTicks}t remaining</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <ComposableMap
        projection="geoMercator"
        projectionConfig={{
          center: [14, 50],
          scale: 1400,
        }}
        className="w-full h-full"
      >
        {/* Background countries */}
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map(geo => {
              const countryCode = geo.properties?.ISO_A3 || geo.id
              const isTargetCountry = targetCountryCodes.includes(countryCode)
              if (isTargetCountry) return null

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill="rgba(30, 41, 59, 0.6)"
                  stroke="rgba(71, 85, 105, 0.4)"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: 'none' },
                    hover: { outline: 'none' },
                    pressed: { outline: 'none' },
                  }}
                />
              )
            })
          }
        </Geographies>

        {/* Crisis attack lines */}
        {(simulationState.activeCrises ?? []).map(crisis => {
          const targetCentroid = getZoneCentroid(crisis.targetId)
          if (!targetCentroid) return null

          return (
            <g key={`attack-line-${crisis.crisisId}`}>
              <Line
                from={CRISIS_AGENT_ORIGIN}
                to={targetCentroid}
                stroke={TIER_COLORS[crisis.tier]}
                strokeWidth={2}
                strokeOpacity={0.5}
                strokeDasharray="8 4"
                strokeLinecap="round"
              />
              
              {/* Attack particles */}
              {attackParticles
                .filter(p => p.crisisId === crisis.crisisId)
                .map(particle => {
                  const pos = interpolate(CRISIS_AGENT_ORIGIN, targetCentroid, particle.progress / 100)
                  return (
                    <Marker key={particle.id} coordinates={pos}>
                      <circle r="5" fill={TIER_COLORS[crisis.tier]} opacity={0.9}>
                        <animate
                          attributeName="r"
                          values="3;6;3"
                          dur="0.5s"
                          repeatCount="indefinite"
                        />
                      </circle>
                    </Marker>
                  )
                })}

              {/* Attack label */}
              <Marker coordinates={interpolate(CRISIS_AGENT_ORIGIN, targetCentroid, 0.3)}>
                <rect
                  x="-45"
                  y="-10"
                  width="90"
                  height="20"
                  rx="4"
                  fill="rgba(127, 29, 29, 0.95)"
                  stroke={TIER_COLORS[crisis.tier]}
                  strokeWidth="1"
                />
                <text
                  textAnchor="middle"
                  y="4"
                  fontSize="9"
                  fill="#FCA5A5"
                  fontWeight="500"
                >
                  {CRISIS_LABELS[crisis.crisisType].substring(0, 15)}
                </text>
              </Marker>
            </g>
          )
        })}

        {/* Trade routes */}
        {(simulationState.tradeRoutes ?? []).map((route, index) => {
          const conn = TRADE_CONNECTIONS[index]
          if (!conn) return null

          const from = COUNTRY_CENTROIDS[conn[0]]
          const to = COUNTRY_CENTROIDS[conn[1]]
          if (!from || !to) return null

          const isEmbargoed = route.isEmbargoed

          return (
            <g key={route.id}>
              <Line
                from={from}
                to={to}
                stroke={isEmbargoed ? '#EF4444' : route.isActive ? 'var(--primary)' : 'var(--muted)'}
                strokeWidth={route.isActive ? 2 : 0.5}
                strokeOpacity={route.isActive ? 0.6 : 0.2}
                strokeDasharray={isEmbargoed ? '4 4' : route.isActive ? undefined : '4 4'}
              />

              {route.isActive && !isEmbargoed && (
                <Marker coordinates={interpolate(from, to, 0.5)}>
                  <rect
                    x="-18"
                    y="-10"
                    width="36"
                    height="16"
                    rx="4"
                    fill="rgba(15, 23, 42, 0.95)"
                    stroke="var(--border)"
                    strokeWidth="1"
                  />
                  <text
                    textAnchor="middle"
                    y="3"
                    fontSize="10"
                    fill="var(--primary)"
                    fontFamily="monospace"
                    fontWeight="600"
                  >
                    {Math.round(route.transmissionEfficiency * 100)}%
                  </text>
                </Marker>
              )}

              {isEmbargoed && (
                <Marker coordinates={interpolate(from, to, 0.5)}>
                  <rect x="-30" y="-8" width="60" height="16" rx="3" fill="#7F1D1D" stroke="#EF4444" strokeWidth="1" />
                  <text textAnchor="middle" y="4" fontSize="8" fill="#FCA5A5" fontWeight="600">EMBARGOED</text>
                </Marker>
              )}

              {route.isActive && !isEmbargoed &&
                particles
                  .filter(p => p.routeIndex === index)
                  .map(particle => {
                    const pos = interpolate(from, to, particle.progress / 100)
                    return (
                      <Marker key={particle.id} coordinates={pos}>
                        <circle r="4" fill="var(--primary)" opacity={0.9}>
                          <animate attributeName="opacity" values="0.5;1;0.5" dur="0.8s" repeatCount="indefinite" />
                        </circle>
                      </Marker>
                    )
                  })}
            </g>
          )
        })}

        {/* Target countries */}
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map(geo => {
              const countryCode = geo.properties?.ISO_A3 || geo.id
              if (!targetCountryCodes.includes(countryCode)) return null

              const zone = getZoneByCode(countryCode)
              if (!zone) return null

              const config = ZONE_CONFIGS[zone.archetype]
              const isSelected = selectedZone?.id === zone.id
              const isHovered = hoveredZone === zone.id
              const hasActiveCrisis = zone.activeCrises.length > 0

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={hasActiveCrisis ? 'rgba(239, 68, 68, 0.35)' : isSelected ? `${config.color}55` : isHovered ? `${config.color}40` : `${config.color}25`}
                  stroke={STABILITY_COLORS[zone.stabilityState]}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  style={{
                    default: { outline: 'none', cursor: 'pointer' },
                    hover: { outline: 'none', cursor: 'pointer' },
                    pressed: { outline: 'none' },
                  }}
                  onClick={() => setSelectedZone(isSelected ? null : zone)}
                  onMouseEnter={() => setHoveredZone(zone.id)}
                  onMouseLeave={() => setHoveredZone(null)}
                />
              )
            })
          }
        </Geographies>

        {/* Zone labels */}
        {(simulationState.zones ?? []).map(zone => {
          const code = ZONE_COUNTRY_CODES[zone.archetype]
          const centroid = COUNTRY_CENTROIDS[code]
          const offset = LABEL_OFFSETS[code]
          if (!centroid || !offset) return null

          const config = ZONE_CONFIGS[zone.archetype]
          const hasActiveCrisis = zone.activeCrises.length > 0

          return (
            <g key={zone.id}>
              <Marker coordinates={centroid}>
                <text textAnchor="middle" y="-6" fontSize="12" fontWeight="600" fill="var(--foreground)">
                  {zone.name}
                </text>
                <text
                  textAnchor="middle"
                  y="8"
                  fontSize="8"
                  fill={config.color}
                  letterSpacing="0.05em"
                >
                  {zone.strategy.toUpperCase()}
                </text>

                {hasActiveCrisis && (
                  <g transform="translate(25, -10)">
                    <circle r="8" fill="#EF4444" opacity={0.9}>
                      <animate attributeName="r" values="6;10;6" dur="1s" repeatCount="indefinite" />
                    </circle>
                    <text textAnchor="middle" y="4" fontSize="10" fontWeight="bold" fill="white">!</text>
                  </g>
                )}

                {zone.cyberAttacked && (
                  <g transform="translate(-25, -10)">
                    <rect x="-20" y="-8" width="40" height="16" rx="3" fill="#7F1D1D" stroke="#EF4444" strokeWidth="1">
                      <animate attributeName="opacity" values="0.7;1;0.7" dur="0.5s" repeatCount="indefinite" />
                    </rect>
                    <text textAnchor="middle" y="4" fontSize="7" fill="#FCA5A5" fontWeight="600">HACKED</text>
                  </g>
                )}
              </Marker>

              <Marker coordinates={centroid}>
                {/* Info box anchored at centroid — offset box to the side so it doesn't cover the country label */}
                <g transform={`translate(${offset.dx > 0 ? 6 : -136}, -12)`}>
                  <rect
                    x="0"
                    y="0"
                    width="130"
                    height="24"
                    rx="5"
                    fill="rgba(15, 23, 42, 0.92)"
                    stroke={STABILITY_COLORS[zone.stabilityState]}
                    strokeWidth="1.5"
                  />
                  <text x="17" y="16" fontSize="10" fill="var(--foreground)" fontFamily="monospace" fontWeight="500">
                    {Math.round(zone.supply)} MW
                  </text>
                  <text x="57" y="16" fontSize="10" fill="var(--muted-foreground)">|</text>
                  <text x="65" y="16" fontSize="10" fill="var(--primary)" fontFamily="monospace" fontWeight="500">
                    {Math.round(zone.budget)}cr
                  </text>
                  <text x="100" y="16" fontSize="10" fill="var(--muted-foreground)">|</text>
                  <text x="108" y="16" fontSize="9" fill="var(--muted-foreground)" fontFamily="monospace">
                    {Math.round(zone.morale)}
                  </text>
                </g>
              </Marker>
            </g>
          )
        })}
      </ComposableMap>
    </div>
  )
}
