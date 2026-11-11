import type { AgentRuntimeStatus } from "@/hooks/use-agents"

export const agentStatusLabel: Record<AgentRuntimeStatus, string> = {
  READY: "Ready", RUNNING: "Running", IDLE: "Idle", FAILED: "Error",
  UNAVAILABLE: "Unavailable", UNVERIFIED: "Not yet run",
}

const completedActions = new Set([
  "route_selected", "scan_complete", "delay_detected", "failure_prediction",
  "reroute_evaluated", "reroute_recommended", "reroute_executed",
  "provider_accepted", "cost_analysis", "cycle_complete",
])
const failedActions = new Set([
  "delay_check_failed", "prediction_failed", "evaluate_failed", "execute_failed",
  "delivery_failed", "delivery_unknown", "delivery_uncertain", "analysis_failed", "cycle_failed",
])

export function executionResult(eventType?: string | null): string | null {
  if (eventType && completedActions.has(eventType)) return "Completed"
  if (eventType && failedActions.has(eventType)) return "Error — review details"
  return null
}

export function agentDiagnostic(reason?: string): string | undefined {
  return reason?.replace(/unverified/gi, "Execution not confirmed")
}
