"use client"

import { Suspense } from "react"
import { motion } from "framer-motion"
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid"

import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"
import { AIAssistant } from "@/components/ai/AIAssistant"
import { Bot, Sparkles, Package } from "lucide-react"

function PanelSkeleton() {
  return <SkeletonCard className="h-64" />
}

function AgentCountDisplay() {
  return (
    <div className="px-6 py-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg shadow-accent/20">
          <Package className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight text-foreground">Warehouse OS</h1>

          </div>
          <p className="text-sm text-muted-foreground">Ask the AI to manage your warehouse</p>
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <div className="flex flex-1 flex-col h-screen overflow-hidden">
      <AgentCountDisplay />
      <div className="flex-1 flex overflow-hidden min-h-0">
        <div className="w-1/3 border-r border-border/20 flex flex-col min-h-0">
          <div className="flex items-center gap-2 px-4 pt-4 pb-2 shrink-0">
            <Sparkles className="h-4 w-4 text-accent animate-pulse" />
            <h2 className="text-sm font-semibold text-foreground">Agent Status</h2>
          </div>
          <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
            <ErrorBoundary>
              <Suspense fallback={<PanelSkeleton />}>
                <AgentStatusGrid />
              </Suspense>
            </ErrorBoundary>
          </div>
        </div>
        <div className="flex-1 flex flex-col min-h-0">
          <AIAssistant />
        </div>
      </div>
    </div>
  )
}
