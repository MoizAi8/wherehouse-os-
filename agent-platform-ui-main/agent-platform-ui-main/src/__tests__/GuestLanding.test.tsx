import { expect, it, vi } from "vitest"
import Home from "@/app/page"
import FormerDemo from "@/app/demo/page"
import { guestModeEnabled } from "@/lib/demo-guest"
import { redirect } from "next/navigation"
vi.mock("@/lib/demo-guest", () => ({ guestModeEnabled: vi.fn() }))
vi.mock("@/components/hero/LazyWarehouseHero", () => ({ LazyWarehouseHero: () => null }))
vi.mock("@/components/landing/LandingSections", () => ({ LandingSections: () => null }))
vi.mock("next/navigation", () => ({ redirect: vi.fn(() => { throw new Error("redirect") }) }))
it("uses the existing dashboard as the guest entry point", async () => {
  vi.mocked(guestModeEnabled).mockResolvedValue(true)
  await expect(Home()).rejects.toThrow("redirect")
  expect(redirect).toHaveBeenCalledWith("/dashboard")
})
it("removes the separate demonstration page", () => {
  expect(() => FormerDemo()).toThrow("redirect")
  expect(redirect).toHaveBeenCalledWith("/dashboard")
})
it("preserves the original landing flow when guest mode is disabled", async () => {
  vi.mocked(guestModeEnabled).mockResolvedValue(false)
  expect(await Home()).toBeTruthy()
})
