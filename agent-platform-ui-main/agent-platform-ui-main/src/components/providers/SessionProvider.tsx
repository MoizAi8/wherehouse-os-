"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"
import { SessionProvider as NextAuthSessionProvider, useSession } from "next-auth/react"
import { refreshSession } from "@/lib/session"

export function SessionExpiryGuard() {
  const { data: session, status } = useSession()
  const pathname = usePathname()
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && (
      session?.error === "SessionExpired" ||
      (status === "unauthenticated" && pathname.startsWith("/dashboard"))
    )) void refreshSession()
  }, [session?.error, status, pathname])
  return null
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  return <NextAuthSessionProvider refetchInterval={60}>
    <SessionExpiryGuard />
    {children}
  </NextAuthSessionProvider>
}
