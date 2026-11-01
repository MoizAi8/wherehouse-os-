import { afterEach, expect, it, vi } from "vitest"
import { signIn } from "next-auth/react"
import { refreshSession } from "@/lib/session"

vi.mock("next-auth/react", () => ({ signIn: vi.fn() }))
afterEach(() => vi.unstubAllEnvs())

it("never signs a production user into the shared demo account on expiry", async () => {
  vi.stubEnv("NODE_ENV", "production")
  expect(await refreshSession()).toBe(false)
  expect(signIn).not.toHaveBeenCalled()
})
