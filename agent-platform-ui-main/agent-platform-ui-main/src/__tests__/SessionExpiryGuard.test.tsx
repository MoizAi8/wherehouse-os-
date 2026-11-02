import { render } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { useSession } from "next-auth/react"
import { usePathname } from "next/navigation"
import { SessionExpiryGuard } from "@/components/providers/SessionProvider"
import { refreshSession } from "@/lib/session"

vi.mock("next-auth/react", () => ({ useSession: vi.fn() }))
vi.mock("next/navigation", () => ({ usePathname: vi.fn() }))
vi.mock("@/lib/session", () => ({ refreshSession: vi.fn().mockResolvedValue(false) }))
beforeEach(() => {
  vi.stubEnv("NODE_ENV", "production")
  vi.mocked(refreshSession).mockClear()
  vi.mocked(usePathname).mockReturnValue("/dashboard/orders")
})
afterEach(() => vi.unstubAllEnvs())
const setSession = (value: unknown) => vi.mocked(useSession).mockReturnValue(value as ReturnType<typeof useSession>)

it("sends an expired backend session to sign-in", () => {
  setSession({ data: { error: "SessionExpired" }, status: "authenticated" })
  render(<SessionExpiryGuard />)
  expect(refreshSession).toHaveBeenCalledOnce()
})
it("requires sign-in when the browser has already expired its session cookie", () => {
  setSession({ data: null, status: "unauthenticated" })
  render(<SessionExpiryGuard />)
  expect(refreshSession).toHaveBeenCalledOnce()
})
it("keeps public pages accessible without signing in", () => {
  vi.mocked(usePathname).mockReturnValue("/")
  setSession({ data: null, status: "unauthenticated" })
  render(<SessionExpiryGuard />)
  expect(refreshSession).not.toHaveBeenCalled()
})
it("does not interrupt an authenticated session or one still loading", () => {
  setSession({ data: { accessToken: "valid" }, status: "authenticated" })
  const view = render(<SessionExpiryGuard />)
  expect(refreshSession).not.toHaveBeenCalled()
  setSession({ data: null, status: "loading" })
  view.rerender(<SessionExpiryGuard />)
  expect(refreshSession).not.toHaveBeenCalled()
})
