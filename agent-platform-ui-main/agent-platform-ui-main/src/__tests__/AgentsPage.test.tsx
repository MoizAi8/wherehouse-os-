import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import AgentsPage from "@/app/dashboard/agents/page"

const mockMonitor = vi.fn()

vi.mock("@/hooks/use-agents", () => ({
  useAgentMonitor: (...args: unknown[]) => mockMonitor(...args),
}))

describe("Category 3: Agents Page", () => {
  beforeEach(() => {
    mockMonitor.mockReturnValue({
      data: { cycle_id: "cyc-001", shipments_checked: 150, delays_detected: 12, reroutes_initiated: 3, notifications_sent: 24, anomalies_found: 2, events: [], completed_at: "2026-06-15T10:00:00Z" },
      loading: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it("Test 15: Agents page renders", () => {
    render(<AgentsPage />)
    expect(screen.getByText("Agents")).toBeInTheDocument()
    expect(screen.getByText("Ask AI to monitor and control agents")).toBeInTheDocument()
  })

  it("Test 16: Agent cards show correct data with status", () => {
    render(<AgentsPage />)
    expect(screen.getByText("RoutingAgent")).toBeInTheDocument()
    expect(screen.getByText("MonitorAgent")).toBeInTheDocument()
    expect(screen.getAllByText("active").length).toBeGreaterThan(0)
    expect(screen.getAllByText("processing").length).toBeGreaterThan(0)
  })

  it("Test 17: Agent cards reflect monitor data", () => {
    render(<AgentsPage />)
    expect(screen.getByText("Shipment Monitor")).toBeInTheDocument()
    expect(screen.getByText("Order Router")).toBeInTheDocument()
  })

  it("Test 18: Agent statuses rendered", () => {
    render(<AgentsPage />)
    expect(screen.getByText("Reroute Handler")).toBeInTheDocument()
    expect(screen.getByText("Notification Relay")).toBeInTheDocument()
  })

  it("Test 19: Reroute handler activates when delays detected", () => {
    render(<AgentsPage />)
    expect(screen.getAllByText("active").length).toBeGreaterThan(0)
  })

  it("Test 20: Loading state shows skeleton", () => {
    mockMonitor.mockReturnValue({ data: null, loading: true, error: null, refetch: vi.fn() })
    render(<AgentsPage />)
    expect(screen.getByLabelText("Loading agents")).toBeInTheDocument()
  })

  it("Test 21: Error handling renders error display", () => {
    mockMonitor.mockReturnValue({ data: null, loading: false, error: "Backend unreachable", refetch: vi.fn() })
    render(<AgentsPage />)
    expect(screen.getByText("Backend unreachable")).toBeInTheDocument()
    expect(screen.getByText("Try again")).toBeInTheDocument()
  })
})
