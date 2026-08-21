"use client"

import { useEffect, useState } from "react"
import { getSession, signIn } from "next-auth/react"

const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL || "demo@fulfillos.com"
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "Demo1234!"

export function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function ensureSession() {
      try {
        const session = await getSession()
        if (!session?.accessToken) {
          await signIn("credentials", {
            email: DEMO_EMAIL,
            password: DEMO_PASSWORD,
            redirect: false,
          })
        }
      } catch {
        // Proceed without session — API calls surface errors as before.
      }
      if (!cancelled) setReady(true)
    }

    ensureSession()
    return () => {
      cancelled = true
    }
  }, [])

  if (!ready) return null
  return <>{children}</>
}
