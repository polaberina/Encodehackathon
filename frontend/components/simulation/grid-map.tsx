'use client'

import { useRef, useEffect, useState } from 'react'
import type { Zone, TradeRoute } from '@/lib/simulation-types'
import { ENERGY_CONFIGS, ZONE_CONFIGS } from '@/lib/simulation-types'

interface GridMapProps {
  zones: Zone[]
  tradeRoutes: TradeRoute[]
  selectedZone: string | null
  onSelectZone: (id: string | null) => void
  tick: number
}

export function GridMap({ zones, tradeRoutes, selectedZone, onSelectZone, tick }: GridMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [animationFrame, setAnimationFrame] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setAnimationFrame(f => f + 1)
    }, 50)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height

    // Clear canvas with dark background
    ctx.fillStyle = '#080a12'
    ctx.fillRect(0, 0, width, height)

    // Draw hex grid background pattern
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)'
    ctx.lineWidth = 1
    const hexSize = 40
    for (let row = 0; row < height / hexSize + 1; row++) {
      for (let col = 0; col < width / hexSize + 1; col++) {
        const x = col * hexSize * 1.5
        const y = row * hexSize * Math.sqrt(3) + (col % 2 ? hexSize * Math.sqrt(3) / 2 : 0)
        drawHexagon(ctx, x, y, hexSize / 2)
      }
    }

    // Draw trade routes with animated flow
    tradeRoutes.forEach(route => {
      const sourceZone = zones.find(z => z.id === route.sourceZoneId)
      const targetZone = zones.find(z => z.id === route.targetZoneId)
      if (!sourceZone || !targetZone) return

      const x1 = (sourceZone.position.x / 100) * width
      const y1 = (sourceZone.position.y / 100) * height
      const x2 = (targetZone.position.x / 100) * width
      const y2 = (targetZone.position.y / 100) * height

      // Route line with gradient
      const gradient = ctx.createLinearGradient(x1, y1, x2, y2)
      if (route.isActive) {
        const alpha = route.health * 0.6 + 0.2
        gradient.addColorStop(0, `${sourceZone.color}${Math.floor(alpha * 255).toString(16).padStart(2, '0')}`)
        gradient.addColorStop(1, `${targetZone.color}${Math.floor(alpha * 255).toString(16).padStart(2, '0')}`)
        ctx.strokeStyle = gradient
        ctx.lineWidth = 2 + (route.currentFlow / 80)
      } else {
        ctx.strokeStyle = 'rgba(60, 60, 80, 0.4)'
        ctx.lineWidth = 1
      }
      
      ctx.beginPath()
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()

      // Animated flow particles
      if (route.isActive && route.currentFlow > 0) {
        const numParticles = Math.ceil(route.currentFlow / 30)
        for (let p = 0; p < numParticles; p++) {
          const progress = ((animationFrame / 40 + p / numParticles) % 1)
          const px = x1 + (x2 - x1) * progress
          const py = y1 + (y2 - y1) * progress
          
          ctx.beginPath()
          ctx.arc(px, py, 3, 0, Math.PI * 2)
          ctx.fillStyle = route.health > 0.7 ? '#34D399' : route.health > 0.5 ? '#FBBF24' : '#EF4444'
          ctx.fill()
        }
      }

      // Route health indicator at midpoint
      if (route.isActive) {
        const midX = (x1 + x2) / 2
        const midY = (y1 + y2) / 2
        ctx.font = '9px monospace'
        ctx.fillStyle = route.health > 0.7 ? '#34D399' : route.health > 0.5 ? '#FBBF24' : '#EF4444'
        ctx.textAlign = 'center'
        ctx.fillText(`${Math.floor(route.health * 100)}%`, midX, midY - 8)
      }
    })

    // Draw zones with personalized styling
    zones.forEach(zone => {
      const x = (zone.position.x / 100) * width
      const y = (zone.position.y / 100) * height
      const baseRadius = 50
      const isSelected = selectedZone === zone.id
      const config = ZONE_CONFIGS[zone.archetype]

      // Outer glow based on zone status
      const glowRadius = baseRadius * 1.8
      const glowGradient = ctx.createRadialGradient(x, y, baseRadius * 0.8, x, y, glowRadius)
      
      if (zone.isUnderCrisis) {
        glowGradient.addColorStop(0, 'rgba(239, 68, 68, 0.4)')
        glowGradient.addColorStop(0.5, 'rgba(239, 68, 68, 0.15)')
        glowGradient.addColorStop(1, 'rgba(239, 68, 68, 0)')
      } else if (isSelected) {
        glowGradient.addColorStop(0, `${zone.color}66`)
        glowGradient.addColorStop(0.5, `${zone.color}22`)
        glowGradient.addColorStop(1, `${zone.color}00`)
      } else {
        glowGradient.addColorStop(0, `${zone.color}22`)
        glowGradient.addColorStop(1, `${zone.color}00`)
      }
      
      ctx.beginPath()
      ctx.arc(x, y, glowRadius, 0, Math.PI * 2)
      ctx.fillStyle = glowGradient
      ctx.fill()

      // Zone shape based on archetype
      drawZoneShape(ctx, x, y, baseRadius, zone.archetype, zone.color, isSelected, zone.isUnderCrisis)

      // Energy mix ring (outer)
      const totalCapacity = zone.energySources.reduce((s, e) => s + e.capacity, 0)
      let startAngle = -Math.PI / 2
      const ringRadius = baseRadius - 8
      zone.energySources.forEach(source => {
        const angle = (source.capacity / totalCapacity) * Math.PI * 2
        ctx.beginPath()
        ctx.arc(x, y, ringRadius, startAngle, startAngle + angle)
        ctx.strokeStyle = ENERGY_CONFIGS[source.type].color
        ctx.lineWidth = 5
        ctx.stroke()
        startAngle += angle
      })

      // Storage indicator bar
      const storagePercent = zone.storage / zone.maxStorage
      const barWidth = 40
      const barHeight = 6
      const barX = x - barWidth / 2
      const barY = y + baseRadius - 18
      
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)'
      ctx.fillRect(barX - 1, barY - 1, barWidth + 2, barHeight + 2)
      ctx.fillStyle = 'rgba(30, 30, 40, 0.8)'
      ctx.fillRect(barX, barY, barWidth, barHeight)
      ctx.fillStyle = storagePercent > 0.5 ? '#34D399' : storagePercent > 0.2 ? '#FBBF24' : '#EF4444'
      ctx.fillRect(barX, barY, barWidth * storagePercent, barHeight)

      // Zone name with archetype badge
      ctx.fillStyle = '#fff'
      ctx.font = 'bold 14px system-ui'
      ctx.textAlign = 'center'
      ctx.fillText(zone.name, x, y - 8)

      // Strategy label
      ctx.font = '9px system-ui'
      ctx.fillStyle = zone.color
      ctx.fillText(zone.strategy.toUpperCase(), x, y + 6)

      // Storage percentage
      ctx.font = '10px monospace'
      ctx.fillStyle = storagePercent > 0.5 ? '#34D399' : storagePercent > 0.2 ? '#FBBF24' : '#EF4444'
      ctx.fillText(`${Math.floor(storagePercent * 100)}%`, x, y + baseRadius - 5)

      // Crisis indicator with pulsing animation
      if (zone.isUnderCrisis && zone.crisisType) {
        const pulseScale = 1 + Math.sin(animationFrame / 10) * 0.1
        ctx.save()
        ctx.translate(x, y - baseRadius - 10)
        ctx.scale(pulseScale, pulseScale)
        ctx.font = 'bold 10px system-ui'
        ctx.fillStyle = '#EF4444'
        ctx.textAlign = 'center'
        ctx.fillText('CRISIS', 0, 0)
        ctx.restore()
      }

      // Performance indicators (small badges)
      const badgeY = y + baseRadius + 15
      
      // Morale indicator
      ctx.beginPath()
      ctx.arc(x - 20, badgeY, 8, 0, Math.PI * 2)
      ctx.fillStyle = zone.morale > 70 ? '#22C55E33' : zone.morale > 50 ? '#FBBF2433' : '#EF444433'
      ctx.fill()
      ctx.font = '8px system-ui'
      ctx.fillStyle = zone.morale > 70 ? '#22C55E' : zone.morale > 50 ? '#FBBF24' : '#EF4444'
      ctx.textAlign = 'center'
      ctx.fillText(`${Math.floor(zone.morale)}`, x - 20, badgeY + 3)

      // Economy indicator
      ctx.beginPath()
      ctx.arc(x, badgeY, 8, 0, Math.PI * 2)
      ctx.fillStyle = zone.economy > 70 ? '#3B82F633' : zone.economy > 50 ? '#FBBF2433' : '#EF444433'
      ctx.fill()
      ctx.fillStyle = zone.economy > 70 ? '#3B82F6' : zone.economy > 50 ? '#FBBF24' : '#EF4444'
      ctx.fillText(`${Math.floor(zone.economy)}`, x, badgeY + 3)

      // Efficiency indicator
      ctx.beginPath()
      ctx.arc(x + 20, badgeY, 8, 0, Math.PI * 2)
      ctx.fillStyle = zone.efficiencyScore > 80 ? '#A855F733' : zone.efficiencyScore > 60 ? '#FBBF2433' : '#EF444433'
      ctx.fill()
      ctx.fillStyle = zone.efficiencyScore > 80 ? '#A855F7' : zone.efficiencyScore > 60 ? '#FBBF24' : '#EF4444'
      ctx.fillText(`${Math.floor(zone.efficiencyScore)}`, x + 20, badgeY + 3)
    })

    // Legend for performance badges
    ctx.font = '8px system-ui'
    ctx.fillStyle = 'rgba(255,255,255,0.4)'
    ctx.textAlign = 'left'
    ctx.fillText('M: Morale  E: Economy  F: Efficiency', 10, height - 10)

  }, [zones, tradeRoutes, selectedZone, animationFrame, tick])

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100

    const clickedZone = zones.find(zone => {
      const dx = zone.position.x - x
      const dy = zone.position.y - y
      return Math.sqrt(dx * dx + dy * dy) < 10
    })

    onSelectZone(clickedZone?.id ?? null)
  }

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full cursor-pointer"
      onClick={handleClick}
    />
  )
}

function drawHexagon(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
  ctx.beginPath()
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 6
    const hx = x + size * Math.cos(angle)
    const hy = y + size * Math.sin(angle)
    if (i === 0) ctx.moveTo(hx, hy)
    else ctx.lineTo(hx, hy)
  }
  ctx.closePath()
  ctx.stroke()
}

function drawZoneShape(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  archetype: string,
  color: string,
  isSelected: boolean,
  isUnderCrisis: boolean
) {
  ctx.save()
  
  // Background shape based on archetype
  ctx.beginPath()
  
  switch (archetype) {
    case 'alpha': // Leaf-like shape for renewable
      ctx.ellipse(x, y, radius, radius * 0.85, 0, 0, Math.PI * 2)
      break
    case 'beta': // Shield shape for defensive
      ctx.moveTo(x, y - radius)
      ctx.quadraticCurveTo(x + radius, y - radius * 0.5, x + radius * 0.8, y + radius * 0.3)
      ctx.quadraticCurveTo(x, y + radius, x, y + radius)
      ctx.quadraticCurveTo(x, y + radius, x - radius * 0.8, y + radius * 0.3)
      ctx.quadraticCurveTo(x - radius, y - radius * 0.5, x, y - radius)
      break
    case 'gamma': // Diamond for economic
      ctx.moveTo(x, y - radius)
      ctx.lineTo(x + radius * 0.85, y)
      ctx.lineTo(x, y + radius)
      ctx.lineTo(x - radius * 0.85, y)
      ctx.closePath()
      break
    case 'delta': // Hexagon for nuclear/tech
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 2
        const px = x + radius * 0.9 * Math.cos(angle)
        const py = y + radius * 0.9 * Math.sin(angle)
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      }
      ctx.closePath()
      break
    default:
      ctx.arc(x, y, radius, 0, Math.PI * 2)
  }

  // Fill
  const fillGradient = ctx.createRadialGradient(x, y - radius * 0.3, 0, x, y, radius)
  fillGradient.addColorStop(0, 'rgba(30, 35, 50, 0.95)')
  fillGradient.addColorStop(1, 'rgba(20, 25, 40, 0.98)')
  ctx.fillStyle = fillGradient
  ctx.fill()

  // Border
  ctx.strokeStyle = isUnderCrisis ? '#EF4444' : isSelected ? color : `${color}88`
  ctx.lineWidth = isSelected ? 3 : 2
  ctx.stroke()

  ctx.restore()
}
