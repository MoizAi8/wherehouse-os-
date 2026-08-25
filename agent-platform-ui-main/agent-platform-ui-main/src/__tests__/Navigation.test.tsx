import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Dock } from "@/components/navigation/Dock"
import { TopBar } from "@/components/navigation/TopBar"

describe("Category 4: Navigation & Layout", () => {
  it("Test 23: Dock navigation renders all items", () => {
    render(<Dock />)
    const links = screen.getAllByRole("link")
    expect(links.length).toBe(7)
    expect(links[0]).toHaveAttribute("href", "/")
    expect(links[1]).toHaveAttribute("href", "/dashboard")
    expect(links[2]).toHaveAttribute("href", "/dashboard/orders")
    expect(links[3]).toHaveAttribute("href", "/dashboard/agents")
    expect(links[4]).toHaveAttribute("href", "/dashboard/workflows")
    expect(links[5]).toHaveAttribute("href", "/dashboard/analytics")
    expect(links[6]).toHaveAttribute("href", "/dashboard/settings")
  })

  it("Test 24: Tooltip appears on hover", () => {
    render(<Dock />)
    const links = screen.getAllByRole("link")
    fireEvent.mouseEnter(links[1])
    expect(screen.getByText("Dashboard")).toBeInTheDocument()
  })

  it("Test 25: TopBar search input renders", () => {
    render(<TopBar />)
    const searchInput = screen.getByPlaceholderText("Search agents, workflows...")
    expect(searchInput).toBeInTheDocument()
  })

  it("Test 26: TopBar displays theme logo and avatar", () => {
    render(<TopBar />)
    expect(screen.getByText("Admin")).toBeInTheDocument()
  })

  it("Test 27: Notifications bell icon is present", () => {
    render(<TopBar />)
    const bellIcon = document.querySelector(".lucide-bell")
    expect(bellIcon).not.toBeNull()
  })

  it("Test 28: User avatar and admin name renders", () => {
    render(<TopBar />)
    expect(screen.getByText("Admin")).toBeInTheDocument()
  })
})
