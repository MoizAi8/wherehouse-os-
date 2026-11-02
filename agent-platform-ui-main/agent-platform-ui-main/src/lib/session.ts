"use client"

import { signIn, signOut } from "next-auth/react"

const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL || "demo@fulfillos.com"
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "Demo1234!"

/**
 * Requires a fresh production login when authentication expires. Only the
 * development fallback may sign into the existing local demo account.
 */
let signingOut: Promise<unknown> | undefined

export async function refreshSession(): Promise<boolean> {
  if (process.env.NODE_ENV === "production") {
    // Expired/legacy cookies cannot be renewed without re-authentication.
    // Never substitute demo credentials or keep displaying a stale session.
    signingOut ??= signOut({ callbackUrl: "/api/auth/signin?callbackUrl=%2Fdashboard" })
    await signingOut
    return false
  }
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
    if (res.status !== 401 && res.status !== 403) return true
  } catch {
    // Network error — keep existing session rather than churning it.
    return Boolean(session.accessToken)
  }
  return refreshSession()
}
