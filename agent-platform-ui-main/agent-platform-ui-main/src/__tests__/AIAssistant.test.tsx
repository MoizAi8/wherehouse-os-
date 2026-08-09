import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { AIAssistant } from "@/components/ai/AIAssistant"

describe("Category 5: Chat & AI Assistant", () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it("Test 29: AI Assistant renders with greeting", () => {
    render(<AIAssistant />)
    expect(screen.getByText(/Welcome to Warehouse OS/)).toBeInTheDocument()
    expect(screen.getByText("Warehouse OS AI")).toBeInTheDocument()
  })

  it("Test 30: Send message processes input", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reply: "Hello from AI" }),
    })

    render(<AIAssistant />)
    const input = screen.getByPlaceholderText("Ask anything about your warehouse...")
    fireEvent.change(input, { target: { value: "Hello" } })
    fireEvent.submit(input.closest("form")!)

    await waitFor(() => {
      expect(screen.getByText("Hello from AI")).toBeInTheDocument()
    })
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({ method: "POST" }),
    )
  })

  it("Test 31: Suggestion buttons render", () => {
    render(<AIAssistant />)
    expect(screen.getByText("Summarize agent health")).toBeInTheDocument()
    expect(screen.getByText("What's our top priority?")).toBeInTheDocument()
    expect(screen.getByText("Suggest optimizations")).toBeInTheDocument()
    expect(screen.getByText("Explain current metrics")).toBeInTheDocument()
  })

  it("Test 32: Greeting message shows when chat opens", () => {
    render(<AIAssistant />)
    expect(screen.getAllByText(/Welcome to Warehouse OS/).length).toBeGreaterThan(0)
  })

  it("Test 33: Input and send button present", () => {
    render(<AIAssistant />)
    expect(screen.getByPlaceholderText("Ask anything about your warehouse...")).toBeInTheDocument()
    const submitButtons = screen.getAllByRole("button", { name: "" })
    expect(submitButtons.length).toBeGreaterThanOrEqual(1)
  })
})
