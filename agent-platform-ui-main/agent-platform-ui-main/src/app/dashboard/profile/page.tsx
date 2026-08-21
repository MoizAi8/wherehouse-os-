"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Mail, Shield, User as UserIcon, RefreshCw } from "lucide-react"

interface Profile {
  id: string
  email: string
  name: string
  role: string
  must_change_password?: boolean
}

const roleLabels: Record<string, string> = {
  ADMIN: "Admin",
  VIEWER: "Viewer",
  OPERATOR: "Operator",
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch("/api/auth/me")
      const body = await res.json()
      if (!res.ok) {
        setError(body?.error || `Request failed (${res.status})`)
        setProfile(null)
        return
      }
      setProfile(body)
    } catch {
      setError("Could not load your profile. Please try again.")
      setProfile(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Profile</h1>
        <p className="text-sm text-muted-foreground">Your account details</p>
      </div>

      {error && (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <span>{error}</span>
          <button
            onClick={() => void load()}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border/50 bg-card px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-muted transition-colors"
          >
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        </div>
      )}

      {loading && !profile && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 rounded-xl bg-muted/20 animate-pulse" />
          ))}
        </div>
      )}

      {profile && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border/50 bg-card overflow-hidden"
        >
          <div className="flex items-center gap-4 border-b border-border/30 bg-muted/20 px-6 py-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-accent to-primary shadow-lg shadow-accent/20">
              <UserIcon className="h-5 w-5 text-background" />
            </div>
            <div>
              <p className="text-base font-semibold text-foreground">{profile.name}</p>
              <p className="text-xs text-muted-foreground">{roleLabels[profile.role] || profile.role}</p>
            </div>
          </div>

          <div className="px-6 py-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex items-start gap-3 rounded-lg border border-border/40 bg-muted/10 px-4 py-3">
                <Mail className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Email</p>
                  <p className="text-sm font-medium text-foreground">{profile.email}</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-lg border border-border/40 bg-muted/10 px-4 py-3">
                <Shield className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Role</p>
                  <p className="text-sm font-medium text-foreground">{roleLabels[profile.role] || profile.role}</p>
                </div>
              </div>
            </div>

            {profile.must_change_password && (
              <p className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-xs text-amber-600">
                You should change your password.
              </p>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}