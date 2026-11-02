import { afterEach, expect, it, vi } from "vitest"
import { signIn, signOut } from "next-auth/react"
import { refreshSession } from "@/lib/session"

vi.mock("next-auth/react", () => ({ signIn: vi.fn(), signOut: vi.fn().mockResolvedValue(undefined) }))
afterEach(() => vi.unstubAllEnvs())

it("never signs a production user into the shared demo account on expiry", async () => {
  vi.stubEnv("NODE_ENV", "production")
  expect(await refreshSession()).toBe(false)
  expect(signIn).not.toHaveBeenCalled()
  expect(signOut).toHaveBeenCalledWith({ callbackUrl: "/api/auth/signin?callbackUrl=%2Fdashboard" })
})
