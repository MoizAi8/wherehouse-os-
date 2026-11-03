"use client"

import { createContext, Fragment, useContext, useEffect } from "react"
import { usePathname } from "next/navigation"
import { SessionProvider as NextAuthSessionProvider, useSession } from "next-auth/react"
import { refreshSession } from "@/lib/session"

export function SessionExpiryGuard() {
  const { data: session, status } = useSession()
  const pathname = usePathname()
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && pathname.startsWith("/dashboard") && !session?.demoGuest && (
      session?.error === "SessionExpired" ||
      status === "unauthenticated"
    )) void refreshSession()
  }, [session?.error, session?.demoGuest, status, pathname])
  return null
}

const IdentityContext = createContext("anonymous")
export const useSessionIdentity = () => useContext(IdentityContext)

export function SessionIdentityBoundary({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const identity = status === "loading" ? "loading" : session?.demoGuest ? "guest" : session?.user?.id || "anonymous"
  // Never retain owner query/chat state when the session becomes a public guest.
  return <IdentityContext.Provider value={identity}><Fragment key={identity}>{children}</Fragment></IdentityContext.Provider>
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  return <NextAuthSessionProvider refetchInterval={60}>
    <SessionExpiryGuard />
    <SessionIdentityBoundary>{children}</SessionIdentityBoundary>
  </NextAuthSessionProvider>
}
