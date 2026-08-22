"use client"

import { signIn } from "next-auth/react"

const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL || "demo@fulfillos.com"
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "Demo1234!"

/**
 * Silently (re)establishes the NextAuth session with the demo credentials.
 * Used when no session exists or the stored backend token is invalid/expired.
 */
export async function refreshSession(): Promise<boolean> {
  try {
    const result = await signIn("credentials", {
      email: DEMO_EMAIL,
      password: DEMO_PASSWORD,
      redirect: false,
    })
    return Boolean(result && !result.error)
  } catch {
    return false
  }
}

/**
 * Ensures a session exists AND its backend token is currently accepted.
 * Returns true when a valid access token is available afterwards.
 */
export async function ensureValidSession(): Promise<boolean> {
  const { getSession } = await import("next-auth/react")
  const session = await getSession()
  if (!session?.accessToken) {
    return refreshSession()
  }

  try {
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    })
    if (res.ok) return true
  } catch {
    // Network error — keep existing session rather than churning it.
    return Boolean(session.accessToken)
  }
  return refreshSession()
}
