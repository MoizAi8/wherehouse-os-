import { render, screen, fireEvent } from "@testing-library/react"
import { useState } from "react"
import { expect, it, vi } from "vitest"
import { useSession } from "next-auth/react"
import { SessionIdentityBoundary, useSessionIdentity } from "@/components/providers/SessionProvider"

vi.mock("next-auth/react", () => ({ useSession: vi.fn() }))
vi.mock("@/lib/session", () => ({ refreshSession: vi.fn() }))

function PrivateState() {
  const [record, setRecord] = useState("empty")
  const identity = useSessionIdentity()
  return <button onClick={() => setRecord("owner record")}>{identity}: {record}</button>
}

it("clears owner page/chat state when authentication becomes a guest session", () => {
  vi.mocked(useSession).mockReturnValue({ status: "authenticated", data: { user: { id: "owner" } } } as never)
  const view = render(<SessionIdentityBoundary><PrivateState /></SessionIdentityBoundary>)
  fireEvent.click(screen.getByRole("button"))
  expect(screen.getByText("owner: owner record")).toBeInTheDocument()
  vi.mocked(useSession).mockReturnValue({ status: "authenticated", data: { demoGuest: true } } as never)
  view.rerender(<SessionIdentityBoundary><PrivateState /></SessionIdentityBoundary>)
  expect(screen.getByText("guest: empty")).toBeInTheDocument()
  expect(screen.queryByText(/owner record/)).not.toBeInTheDocument()
})

it("does not reset guest state when only the renewable token changes", () => {
  vi.mocked(useSession).mockReturnValue({ status: "authenticated", data: { demoGuest: true, accessToken: "first" } } as never)
  const view = render(<SessionIdentityBoundary><PrivateState /></SessionIdentityBoundary>)
  fireEvent.click(screen.getByRole("button"))
  vi.mocked(useSession).mockReturnValue({ status: "authenticated", data: { demoGuest: true, accessToken: "renewed" } } as never)
  view.rerender(<SessionIdentityBoundary><PrivateState /></SessionIdentityBoundary>)
  expect(screen.getByText("guest: owner record")).toBeInTheDocument()
})
