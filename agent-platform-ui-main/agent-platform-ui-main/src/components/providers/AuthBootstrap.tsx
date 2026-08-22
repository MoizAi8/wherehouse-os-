"use client"

import { useEffect, useState } from "react"
import { ensureValidSession } from "@/lib/session"

export function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        await ensureValidSession()
      } catch {
        // Proceed without session — API calls surface errors as before.
      }
      if (!cancelled) setReady(true)
    }

    bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  if (!ready) return null
  return <>{children}</>
}
