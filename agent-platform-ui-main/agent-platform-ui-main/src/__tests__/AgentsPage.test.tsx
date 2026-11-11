import { fireEvent, render, screen } from "@testing-library/react"
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
    expect(screen.getAllByText("Not yet run")).toHaveLength(7)
    expect(screen.queryByText("active")).not.toBeInTheDocument()
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

  it("Test 19: Delays do not fabricate a rerouting agent runtime state", () => {
    render(<AgentsPage />)
    expect(screen.getAllByText("Not yet run")).toHaveLength(7)
  })

  it("Test 20: Loading state shows skeleton", () => {
    mockMonitor.mockReturnValue({ data: null, loading: true, error: null, refetch: vi.fn() })
    render(<AgentsPage />)
    expect(screen.getByLabelText("Loading agents")).toBeInTheDocument()
  })

  it("Displays individual backend evidence without inferring other agents", () => {
    mockMonitor.mockReturnValue({ data: { agents: [
      { name: "RoutingAgent", status: "IDLE", reason: "Completed route" },
      { name: "CommunicationAgent", status: "FAILED", reason: "Provider rejected" },
    ] }, loading: false, error: null, refetch: vi.fn() })
    render(<AgentsPage />)
    expect(screen.getByText("Idle")).toHaveAttribute("title", "Completed route")
    expect(screen.getByText("Error")).toHaveAttribute("title", "Provider rejected")
    expect(screen.getAllByText("Not yet run")).toHaveLength(5)
  })

  it("Test 21: Error handling renders error display", () => {
    mockMonitor.mockReturnValue({ data: null, loading: false, error: "Backend unreachable", refetch: vi.fn() })
    render(<AgentsPage />)
    expect(screen.getByText("Backend unreachable")).toBeInTheDocument()
    expect(screen.getByText("Try again")).toBeInTheDocument()
  })

  it("refreshes the evidence and shows the persisted event and its outcome", () => {
    const refetch = vi.fn()
    mockMonitor.mockReturnValue({ data: { agents: [{
      name: "RoutingAgent", status: "IDLE", event_type: "route_selected",
      observed_at: "2026-11-10T12:00:00Z", event_id: "route-event-1",
      outcome: { carrier: "Fixture A", shipping_cost: 11 },
    }] }, loading: false, error: null, refetch })
    render(<AgentsPage />)
    fireEvent.click(screen.getByRole("button", { name: "Refresh agent status" }))
    expect(refetch).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByText("Execution details"))
    expect(screen.getByText("Event route-event-1")).toBeVisible()
    expect(screen.getByText("carrier: Fixture A")).toBeVisible()
    expect(screen.getByText("2026-11-10T12:00:00Z")).toBeVisible()
  })
})
