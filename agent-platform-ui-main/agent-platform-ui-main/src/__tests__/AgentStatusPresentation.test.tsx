import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AgentCard } from '@/components/dashboard/AgentCard'
import type { AgentRuntimeStatus } from '@/hooks/use-agents'
import { executionResult } from '@/lib/agent-status'

const base = { id: 'routing', name: 'RoutingAgent', role: 'Order Router', uptime: '--', tasksCompleted: 0, workload: null, accuracy: null }

describe('Customer-facing operational state', () => {
  it.each<[AgentRuntimeStatus, string]>([
    ['UNVERIFIED', 'Not yet run'], ['READY', 'Ready'], ['RUNNING', 'Running'],
    ['IDLE', 'Idle'], ['FAILED', 'Error'], ['UNAVAILABLE', 'Unavailable'],
  ])('presents %s without changing backend evidence', (status, label) => {
    const { container } = render(<AgentCard index={0} agent={{ ...base, status, evidence: 'unverified runtime detail' }} />)
    expect(screen.getByText(label)).toBeVisible()
    expect(container.innerHTML.toLowerCase()).not.toContain('unverified')
    expect(screen.queryByText(/Result: Completed/)).not.toBeInTheDocument()
  })
  it('retains a failed execution and its diagnostic details', () => {
    render(<AgentCard index={0} agent={{ ...base, status: 'FAILED', execution: {
      name: 'RoutingAgent', status: 'FAILED', reason: 'Provider rejected', event_id: 'failure-1',
      event_type: 'delivery_failed', observed_at: '2026-11-11T12:00:00Z', entity_id: 'order-1',
    } }} />)
    expect(screen.getByText('Result: Error — review details')).toBeVisible()
    expect(screen.queryByText('Result: Completed')).not.toBeInTheDocument()
  })
  it('requires a qualifying event before declaring an execution completed', () => {
    expect(executionResult('delivery_claimed')).toBeNull()
    expect(executionResult(undefined)).toBeNull()
    expect(executionResult('provider_accepted')).toBe('Completed')
  })
})
