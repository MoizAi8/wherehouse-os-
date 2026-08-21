"use client"

import { motion } from "framer-motion"
import { Package } from "lucide-react"
import Link from "next/link"

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string
  subtitle: string
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-background bg-grid-subtle bg-ambient flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <Link href="/" className="mb-8 flex items-center justify-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-primary shadow-lg shadow-accent/20">
              <Package className="h-4 w-4 text-background" />
            </div>
            <span className="text-lg font-semibold tracking-tight text-foreground">PromptBase</span>
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1], delay: 0.1 }}
          className="glass-card-strong rounded-2xl p-8"
        >
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
          </div>

          {children}
        </motion.div>

        {footer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mt-6 text-center text-sm text-muted-foreground"
          >
            {footer}
          </motion.div>
        )}
      </div>
    </div>
  )
}