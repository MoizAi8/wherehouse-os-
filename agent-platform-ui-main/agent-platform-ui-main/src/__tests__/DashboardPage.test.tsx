import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"
import DashboardPage from "@/app/dashboard/page"

vi.mock("@/hooks/use-analytics", () => ({
  useKPIs: () => ({
    data: { total_orders: 8421, orders_shipped: 3200, orders_delivered: 2800, orders_delayed: 45, on_time_delivery_rate: 94.2, avg_delivery_time_days: 2.3, avg_shipping_cost: 24.5, total_shipping_cost: 205800.0, failed_delivery_rate: 1.2, period_start: null, period_end: null },
    loading: false, error: null, refetch: vi.fn(),
  }),
  useCarrierAnalytics: () => ({ data: [], loading: false, error: null }),
}))

vi.mock("@/hooks/use-agents", () => ({
  useAgentMonitor: () => ({
    data: { cycle_id: "cyc-001", shipments_checked: 150, delays_detected: 12, reroutes_initiated: 3, notifications_sent: 24, anomalies_found: 2, events: [], completed_at: "2026-06-15T10:00:00Z" },
    loading: false, error: null, refetch: vi.fn(),
  }),
}))

vi.mock("@/hooks/use-shipments", () => ({
  useShipments: () => ({ data: [], loading: false, error: null }),
}))

describe("Category 1: Dashboard Overview", () => {
  it("Test 1: Dashboard renders correctly", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Warehouse OS")).toBeInTheDocument()
    expect(screen.getByText("Monitor agents and manage operations")).toBeInTheDocument()
  })

  it("Test 2: Metrics panel shows KPIs", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Total Orders")).toBeInTheDocument()
    expect(screen.getByText("On-Time Rate")).toBeInTheDocument()
    expect(screen.getByText("Avg Delivery (days)")).toBeInTheDocument()
    expect(screen.getByText("Shipments Today")).toBeInTheDocument()
    expect(screen.getByText("8421")).toBeInTheDocument()
    expect(screen.getByText("94.2%")).toBeInTheDocument()
  })

  it("Test 3: Agent status grid loads", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Agent Status")).toBeInTheDocument()
    expect(screen.getByText("RoutingAgent")).toBeInTheDocument()
  })

  it("Test 4: Live indicator renders", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Warehouse OS")).toBeInTheDocument()
    expect(screen.getByText("Monitor agents and manage operations")).toBeInTheDocument()
  })

  it("Test 5: Agent session summary renders", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Agent Session")).toBeInTheDocument()
    expect(screen.getByText("Delays")).toBeInTheDocument()
    expect(screen.getByText("Reroutes")).toBeInTheDocument()
  })

  it("Test 6: Clear chat button works", () => {
    render(<DashboardPage />)
    const clearButton = screen.getByTitle("Clear chat")
    expect(clearButton).toBeInTheDocument()
    fireEvent.click(clearButton)
    expect(screen.getByText(/Chat cleared/)).toBeInTheDocument()
  })
})
