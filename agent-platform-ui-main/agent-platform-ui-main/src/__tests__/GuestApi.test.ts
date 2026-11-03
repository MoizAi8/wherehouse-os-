import { expect, it, vi, beforeEach } from "vitest"
import { getSession } from "next-auth/react"
import { api, ApiError } from "@/lib/api"

vi.unmock("@/lib/api")
vi.mock("next-auth/react", () => ({ getSession: vi.fn() }))
beforeEach(() => vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ orders: [], total: 0 }))))

it("maps original UI reads to the isolated guest API, including filters", async () => {
  vi.mocked(getSession).mockResolvedValue({ demoGuest: true, accessToken: "guest-scoped-token" } as never)
  await api.get("/api/v1/orders?status=pending&limit=2")
  expect(fetch).toHaveBeenCalledWith("/api/demo/guest/data?path=%2Fapi%2Fv1%2Forders&status=pending&limit=2", expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer guest-scoped-token" }) }))
})
it("keeps owner requests on the existing production endpoint", async () => {
  vi.mocked(getSession).mockResolvedValue({ accessToken: "owner-token" } as never)
  await api.get("/api/v1/orders")
  expect(fetch).toHaveBeenCalledWith("/api/v1/orders", expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer owner-token" }) }))
})
it("surfaces guest write denial instead of reporting success", async () => {
  vi.mocked(getSession).mockResolvedValue({ demoGuest: true, accessToken: "guest-scoped-token" } as never)
  vi.mocked(fetch).mockResolvedValue(Response.json({ detail: "Guest access is read-only" }, { status: 403 }))
  await expect(api.delete("/api/v1/orders/private-id")).rejects.toBeInstanceOf(ApiError)
  expect(fetch).toHaveBeenCalledOnce()
})
