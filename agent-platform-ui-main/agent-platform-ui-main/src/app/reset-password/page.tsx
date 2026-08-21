"use client"

import { useState, Suspense } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { Lock, Loader2, ArrowLeft, Eye, EyeOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthShell } from "@/components/auth/AuthShell"

function ResetPasswordForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token") || ""

  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | undefined>()
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token) {
      setError("This reset link is invalid or incomplete. Please request a new one.")
      return
    }
    if (!password) {
      setError("Password is required")
      return
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    if (confirm !== password) {
      setError("Passwords do not match")
      return
    }
    setLoading(true)
    setError(undefined)

    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok || !data?.ok) {
        setError(data?.error || "Unable to reset your password. Please try again.")
        return
      }
      setDone(true)
      setTimeout(() => router.push("/login"), 1500)
    } catch {
      setError("Network error. Please check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Set a new password"
      subtitle="Choose a strong password for your account"
      footer={
        <Link href="/login" className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
          <ArrowLeft className="h-3 w-3" /> Back to login
        </Link>
      }
    >
      {done ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-xl border border-accent/20 bg-accent/5 px-4 py-4 text-sm text-foreground"
        >
          <p className="font-medium text-accent">Password updated</p>
          <p className="mt-1 text-muted-foreground">Your password has been reset. Redirecting to login...</p>
        </motion.div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {error && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
            >
              {error}
            </motion.p>
          )}

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium text-foreground">
              New Password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="At least 8 characters"
                className="pl-9 pr-10"
                value={password}
                error={!!error}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-foreground transition-colors"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirm" className="text-sm font-medium text-foreground">
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
              <Input
                id="confirm"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Re-enter your password"
                className="pl-9"
                value={confirm}
                error={!!error}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" size="lg" className="w-full bg-accent text-background hover:opacity-90" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loading ? "Resetting..." : "Reset password"}
          </Button>
        </form>
      )}
    </AuthShell>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="flex h-[calc(100vh-4rem)] items-center justify-center">Loading…</div>}>
      <ResetPasswordForm />
    </Suspense>
  )
}