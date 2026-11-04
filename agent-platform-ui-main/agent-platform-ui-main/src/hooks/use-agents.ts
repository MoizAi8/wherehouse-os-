"use client"

import { api, ApiError } from "@/lib/api"
import { useApi } from "./use-api"

export type AgentRuntimeStatus = "READY" | "RUNNING" | "IDLE" | "FAILED" | "UNAVAILABLE" | "UNVERIFIED"
export interface AgentRuntimeEvidence {
  name: string
  status: AgentRuntimeStatus
  reason: string
  event_id: string | null
  event_type: string | null
  entity_id: string | null
  observed_at: string | null
}

export interface MonitorResponse {
  agents?: AgentRuntimeEvidence[]
  cycle_id: string
  shipments_checked: number
  delays_detected: number
  reroutes_initiated: number
  notifications_sent: number
  anomalies_found: number
  events: Record<string, unknown>[]
  completed_at: string
  recorded?: boolean
}

const EMPTY_MONITOR: MonitorResponse = {
  cycle_id: "",
  shipments_checked: 0,
  delays_detected: 0,
  reroutes_initiated: 0,
  notifications_sent: 0,
  anomalies_found: 0,
  events: [],
  completed_at: new Date().toISOString(),
}

export function useAgentMonitor() {
  return useApi(async () => {
    try {
      return await api.get<MonitorResponse>("/api/v1/agents/status")
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        // Viewers can view the agent roster but cannot run a monitor cycle.
        return EMPTY_MONITOR
      }
      throw err
    }
  }, [])
}
