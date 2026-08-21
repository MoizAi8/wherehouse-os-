"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Mail, Loader2, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthShell } from "@/components/auth/AuthShell"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | undefined>()
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || loading) {
      setError(!email.trim() ? "Email is required" : undefined)
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email address")
      return
    }
    setLoading(true)
    setError(undefined)

    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok || !data?.ok) {
        setError(data?.error || "Something went wrong. Please try again.")
        return
      }
      setSent(true)
    } catch {
      setError("Network error. Please check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Forgot password"
      subtitle="Enter your email and we'll send you a reset link"
      footer={
        <Link href="/login" className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
          <ArrowLeft className="h-3 w-3" /> Back to login
        </Link>
      }
    >
      {sent ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-xl border border-accent/20 bg-accent/5 px-4 py-4 text-sm text-foreground"
        >
          <p className="font-medium text-accent">Reset link sent</p>
          <p className="mt-1 text-muted-foreground">
            If an account exists for <span className="font-medium text-foreground">{email}</span>, a password reset link has been sent.
            Check your inbox.
          </p>
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
            <label htmlFor="email" className="text-sm font-medium text-foreground">
              Email
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="pl-9"
                value={email}
                error={!!error}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" size="lg" className="w-full bg-accent text-background hover:opacity-90" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loading ? "Sending..." : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthShell>
  )
}