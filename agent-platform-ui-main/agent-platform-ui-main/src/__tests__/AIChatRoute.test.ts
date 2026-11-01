import { beforeEach, describe, expect, it, vi } from "vitest"
import type { NextRequest } from "next/server"
import { POST } from "@/app/api/ai/chat/route"
import { backendUrl, getAuthHeaders } from "@/lib/backend"

vi.mock("@/lib/backend", () => ({ backendUrl: vi.fn(), getAuthHeaders: vi.fn() }))

const request = (body: unknown) => new Request("http://localhost/api/ai/chat", {
  method: "POST", body: JSON.stringify(body),
}) as NextRequest

describe("AI chat authorization and backend failure handling", () => {
  beforeEach(() => {
    vi.mocked(backendUrl).mockReturnValue("http://api:8000")
    vi.mocked(getAuthHeaders).mockResolvedValue({ Authorization: "Bearer test-token" })
    vi.stubGlobal("fetch", vi.fn())
    vi.stubGlobal("AbortSignal", { timeout: vi.fn(() => undefined) })
  })

  it("rejects anonymous requests before contacting any provider", async () => {
    vi.mocked(getAuthHeaders).mockResolvedValue({})
    expect((await POST(request({ messages: [] }))).status).toBe(401)
    expect(fetch).not.toHaveBeenCalled()
  })

  it("preserves backend authentication rejection", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("denied", { status: 401 }))
    expect((await POST(request({ messages: [{ role: "user", content: "hello" }] }))).status).toBe(401)
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it("fails closed when the backend is unavailable", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("private connection details"))
    const response = await POST(request({ messages: [{ role: "user", content: "hello" }] }))
    expect(response.status).toBe(503)
    expect(await response.text()).not.toContain("private connection details")
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it("validates input without calling the backend", async () => {
    expect((await POST(request({ messages: "invalid" }))).status).toBe(400)
    expect(fetch).not.toHaveBeenCalled()
  })

  it("returns the authenticated backend reply using its exact route", async () => {
    vi.mocked(fetch).mockResolvedValue(Response.json({ reply: "Warehouse ready" }))
    const response = await POST(request({ messages: [{ role: "user", content: "hello" }] }))
    expect(await response.text()).toBe("Warehouse ready")
    expect(fetch).toHaveBeenCalledWith("http://api:8000/api/chat", expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
    }))
  })
})
