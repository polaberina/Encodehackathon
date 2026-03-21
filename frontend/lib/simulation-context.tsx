"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import type { SimulationState, Zone } from './simulation-types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchState(): Promise<SimulationState> {
  const res = await fetch(`${API_BASE}/api/state`)
  return res.json()
}

async function postTick(): Promise<SimulationState> {
  const res = await fetch(`${API_BASE}/api/tick`, { method: 'POST' })
  return res.json()
}

async function postReset(): Promise<SimulationState> {
  const res = await fetch(`${API_BASE}/api/reset`, { method: 'POST' })
  return res.json()
}

interface SimulationContextType {
  tick: number
  isRunning: boolean
  simulationState: SimulationState | null
  selectedZone: Zone | null
  setSelectedZone: (zone: Zone | null) => void
  toggleRunning: () => void
  stepForward: () => void
  reset: () => void
}

const SimulationContext = createContext<SimulationContextType | null>(null)

export function SimulationProvider({ children }: { children: ReactNode }) {
  const [tick, setTick] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const [simulationState, setSimulationState] = useState<SimulationState | null>(null)
  const [selectedZone, setSelectedZoneState] = useState<Zone | null>(null)

  // Load initial state from API
  useEffect(() => {
    fetchState().then(state => {
      setSimulationState(state)
      setTick(state.tick)
    })
  }, [])

  const advanceTick = useCallback(async () => {
    const state = await postTick()
    setSimulationState(state)
    setTick(state.tick)
  }, [])

  useEffect(() => {
    if (!isRunning || !simulationState) return
    const interval = setInterval(advanceTick, 1500)
    return () => clearInterval(interval)
  }, [isRunning, advanceTick, simulationState])

  const toggleRunning = useCallback(() => setIsRunning(prev => !prev), [])

  const stepForward = useCallback(() => { advanceTick() }, [advanceTick])

  const reset = useCallback(async () => {
    setIsRunning(false)
    const state = await postReset()
    setSimulationState(state)
    setTick(state.tick)
  }, [])

  const setSelectedZone = useCallback((zone: Zone | null) => {
    setSelectedZoneState(zone)
  }, [])

  return (
    <SimulationContext.Provider value={{ tick, isRunning, simulationState, selectedZone, setSelectedZone, toggleRunning, stepForward, reset }}>
      {children}
    </SimulationContext.Provider>
  )
}

export function useSimulation() {
  const context = useContext(SimulationContext)
  if (!context) throw new Error('useSimulation must be used within a SimulationProvider')
  return context
}
