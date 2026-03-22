"use client"

import { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react'
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
  isTickInProgress: boolean
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
  const [isTickInProgress, setIsTickInProgress] = useState(false)
  const [simulationState, setSimulationState] = useState<SimulationState | null>(null)
  const [selectedZone, setSelectedZoneState] = useState<Zone | null>(null)

  // Track whether initial load has completed so auto-run doesn't fire too early
  const loadedRef = useRef(false)

  // Load initial state from API — retry until the backend is ready
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      while (!cancelled) {
        try {
          const state = await fetchState()
          if (!cancelled) {
            setSimulationState(state)
            setTick(state.tick)
            loadedRef.current = true
          }
          return
        } catch {
          await new Promise(r => setTimeout(r, 1000))
        }
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // Core tick executor — tracks in-flight state
  const advanceTick = useCallback(async () => {
    setIsTickInProgress(true)
    try {
      const state = await postTick()
      setSimulationState(state)
      setTick(state.tick)
    } finally {
      setIsTickInProgress(false)
    }
  }, [])

  // Auto-run loop — intentionally excludes simulationState from deps.
  // Including it would cause React to tear down and restart this effect after
  // every tick (because advanceTick updates simulationState), which kills the
  // chain by setting cancelled=true while runNext is still awaiting.
  useEffect(() => {
    if (!isRunning) return
    let cancelled = false
    const runNext = async () => {
      if (cancelled || !loadedRef.current) return
      await advanceTick()
      if (!cancelled) setTimeout(runNext, 300)
    }
    const t = setTimeout(runNext, 300)
    return () => { cancelled = true; clearTimeout(t) }
  }, [isRunning, advanceTick]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggleRunning = useCallback(() => setIsRunning(prev => !prev), [])

  // Step forward one tick — only if no tick is already in flight
  const stepForward = useCallback(() => {
    if (!isTickInProgress) advanceTick()
  }, [advanceTick, isTickInProgress])

  // Reset — stops auto-run first, then rebuilds engine on backend
  const reset = useCallback(async () => {
    setIsRunning(false)
    setIsTickInProgress(true)
    try {
      const state = await postReset()
      setSimulationState(state)
      setTick(state.tick)
    } finally {
      setIsTickInProgress(false)
    }
  }, [])

  const setSelectedZone = useCallback((zone: Zone | null) => {
    setSelectedZoneState(zone)
  }, [])

  return (
    <SimulationContext.Provider value={{
      tick, isRunning, isTickInProgress,
      simulationState, selectedZone, setSelectedZone,
      toggleRunning, stepForward, reset
    }}>
      {children}
    </SimulationContext.Provider>
  )
}

export function useSimulation() {
  const context = useContext(SimulationContext)
  if (!context) throw new Error('useSimulation must be used within a SimulationProvider')
  return context
}
