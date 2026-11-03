import { expect, it, vi } from "vitest"
import Home from "@/app/page"
import FormerDemo from "@/app/demo/page"
import { LazyWarehouseHero } from "@/components/hero/LazyWarehouseHero"
import { LandingSections } from "@/components/landing/LandingSections"
import { redirect } from "next/navigation"
vi.mock("@/components/hero/LazyWarehouseHero", () => ({ LazyWarehouseHero: () => null }))
vi.mock("@/components/landing/LandingSections", () => ({ LandingSections: () => null }))
vi.mock("next/navigation", () => ({ redirect: vi.fn(() => { throw new Error("redirect") }) }))
it("preserves the original landing hero and information sections at root", () => {
  const page = Home()
  expect(page.props.children[0].type).toBe(LazyWarehouseHero)
  expect(page.props.children[1].type).toBe(LandingSections)
  expect(redirect).not.toHaveBeenCalled()
})
it("keeps the separate demonstration page disabled", () => {
  expect(() => FormerDemo()).toThrow("redirect")
  expect(redirect).toHaveBeenCalledWith("/dashboard")
})
