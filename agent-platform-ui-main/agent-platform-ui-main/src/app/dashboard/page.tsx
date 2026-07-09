"use client"

import { useState, Suspense, useCallback } from "react"
import { motion } from "framer-motion"
import { MetricsPanel } from "@/components/dashboard/MetricsPanel"
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid"
import { ActivityLog } from "@/components/dashboard/ActivityLog"
import { WorkflowPanel } from "@/components/dashboard/WorkflowPanel"
import { TaskQueuePanel } from "@/components/dashboard/TaskQueuePanel"
import { AlertsPanel } from "@/components/dashboard/AlertsPanel"
import { AnalyticsCharts } from "@/components/dashboard/AnalyticsCharts"
import { InventoryZonesPanel } from "@/components/dashboard/InventoryZonesPanel"
import { FlowVisualization } from "@/components/dashboard/FlowVisualization"
import { TiltCard } from "@/components/effects/TiltCard"
import { AIInsights } from "@/components/ai/AIInsights"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"
import { LayoutDashboard, RefreshCw, Sparkles, ArrowUpRight } from "lucide-react"

function PanelSkeleton() {
  return <SkeletonCard className="h-64" />
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
}

const sectionVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] as const },
  },
}

function SectionHeader({ title, icon, badge }: { title: string; icon?: React.ReactNode; badge?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      {icon}
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      {badge}
    </div>
  )
}

export default function DashboardPage() {
  const [syncing, setSyncing] = useState(false)

  const handleSync = useCallback(() => {
    setSyncing(true)
    setTimeout(() => setSyncing(false), 2000)
  }, [])

  return (
    <motion.div
      className="space-y-6 lg:space-y-8"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      >
        <div>
          <div className="flex items-center gap-3">
            <motion.div
              whileHover={{ scale: 1.05, rotate: -5 }}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg shadow-accent/20"
            >
              <LayoutDashboard className="h-4 w-4 text-white" />
            </motion.div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-[22px] font-bold tracking-tight text-foreground">Overview</h1>
                <Badge variant="secondary" className="text-[10px] gap-1.5 font-medium px-2.5">
                  <motion.span
                    animate={{ scale: [1, 1.3, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="h-1.5 w-1.5 rounded-full bg-success"
                  />
                  Live
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground/80 mt-0.5">Real-time warehouse intelligence and agent coordination</p>
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-xs rounded-xl transition-all hover:border-accent/30 hover:text-accent"
          onClick={handleSync}
          disabled={syncing}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : "transition-transform group-hover:rotate-180"}`} />
          {syncing ? "Syncing..." : "Sync"}
        </Button>
      </motion.div>

      <motion.div variants={sectionVariants}>
        <ErrorBoundary>
          <Suspense fallback={<PanelSkeleton />}>
            <MetricsPanel />
          </Suspense>
        </ErrorBoundary>
      </motion.div>

      <motion.div variants={sectionVariants} className="grid gap-6 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <AIInsights />
            </Suspense>
          </ErrorBoundary>
        </div>
        <div className="lg:col-span-3">
          <SectionHeader
            title="Agent Status"
            icon={<Sparkles className="h-4 w-4 text-accent" />}
            badge={<Badge variant="secondary" className="text-[10px]">6 agents</Badge>}
          />
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <div className="glass-accent-border rounded-xl">
                <motion.div
                  whileHover={{ boxShadow: "0 8px 40px rgba(139, 92, 246, 0.1)" }}
                  className="rounded-xl glass-card-strong transition-shadow duration-300"
                >
                  <AgentStatusGrid />
                </motion.div>
              </div>
            </Suspense>
          </ErrorBoundary>
        </div>
      </motion.div>

      <motion.div variants={sectionVariants}>
        <SectionHeader title="Alerts" />
        <ErrorBoundary>
          <Suspense fallback={<PanelSkeleton />}>
            <TiltCard intensity={4}>
              <AlertsPanel />
            </TiltCard>
          </Suspense>
        </ErrorBoundary>
      </motion.div>

      <motion.div variants={sectionVariants} className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3 space-y-4">
          <SectionHeader title="Analytics" />
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <TiltCard intensity={3}>
                <AnalyticsCharts />
              </TiltCard>
            </Suspense>
          </ErrorBoundary>
        </div>
        <div className="lg:col-span-2 space-y-4">
          <SectionHeader title="Inventory Zones" />
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <div className="glass-accent-border rounded-xl">
                <div className="rounded-xl glass-card-strong">
                  <InventoryZonesPanel />
                </div>
              </div>
            </Suspense>
          </ErrorBoundary>
        </div>
      </motion.div>

      <motion.div variants={sectionVariants} className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-4">
          <SectionHeader title="Task Queue" />
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <TaskQueuePanel />
            </Suspense>
          </ErrorBoundary>
        </div>
        <div className="space-y-4">
          <SectionHeader title="Workflows" />
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <WorkflowPanel />
            </Suspense>
          </ErrorBoundary>
        </div>
        <div className="space-y-4">
          <SectionHeader title="Activity Log" />
          <ErrorBoundary>
            <Suspense fallback={<PanelSkeleton />}>
              <ActivityLog />
            </Suspense>
          </ErrorBoundary>
        </div>
      </motion.div>

      <motion.div variants={sectionVariants}>
        <SectionHeader
          title="Flow Map"
          icon={<ArrowUpRight className="h-4 w-4 text-muted-foreground" />}
          badge={<Badge variant="secondary" className="text-[10px] gap-1"><span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse-subtle" /> Live</Badge>}
        />
        <ErrorBoundary>
          <Suspense fallback={<PanelSkeleton />}>
            <FlowVisualization />
          </Suspense>
        </ErrorBoundary>
      </motion.div>
    </motion.div>
  )
}
