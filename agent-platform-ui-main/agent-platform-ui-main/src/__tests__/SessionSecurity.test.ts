import { afterEach, expect, it, vi } from "vitest"
import { signIn, signOut } from "next-auth/react"
import { refreshSession } from "@/lib/session"

vi.mock("next-auth/react", () => ({ signIn: vi.fn().mockResolvedValue(undefined), signOut: vi.fn() }))
afterEach(() => vi.unstubAllEnvs())

it("opens normal production sign-in once without demo credentials or a CSRF-sensitive sign-out", async () => {
  vi.stubEnv("NODE_ENV", "production")
  expect(await Promise.all([refreshSession(), refreshSession()])).toEqual([false, false])
  expect(signIn).toHaveBeenCalledExactlyOnceWith(undefined, { callbackUrl: "/dashboard" })
  expect(signOut).not.toHaveBeenCalled()
})
