"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Activity, Server, Cpu, HardDrive, Wifi, CheckCircle2, AlertCircle, Clock, Zap, Sparkles } from "lucide-react"

const metrics = [
  { icon: Server, label: "API Latency", value: "47ms", pct: 20, status: "good" },
  { icon: Cpu, label: "CPU Usage", value: "34%", pct: 34, status: "good" },
  { icon: HardDrive, label: "Memory", value: "62%", pct: 62, status: "warning" },
  { icon: Wifi, label: "Network I/O", value: "1.2 Gbps", pct: 40, status: "good" },
  { icon: Activity, label: "Error Rate", value: "0.03%", pct: 3, status: "good" },
]

function GaugeMeter({ pct, color }: { pct: number; color: string }) {
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const [offset, setOffset] = useState(circumference)
  useEffect(() => {
    const timer = setTimeout(() => setOffset(circumference * (1 - pct / 100)), 300)
    return () => clearTimeout(timer)
  }, [pct, circumference])

  return (
    <svg width="72" height="72" viewBox="0 0 72 72" className="shrink-0">
      <circle cx="36" cy="36" r={radius} fill="none" stroke="currentColor" strokeWidth="5" className="text-border/30" />
      <motion.circle
        cx="36" cy="36" r={radius} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 36 36)"
        initial={false}
        transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
      />
    </svg>
  )
}

const agentIcons = [Zap, CheckCircle2, Clock, Activity, Cpu, Server]
const agentColors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f43f5e"]

export default function MonitoringPage() {
  const [liveTime, setLiveTime] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => setLiveTime((t) => t + 1), 1000)
    return () => clearInterval(interval)
  }, [])

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { transition: { staggerChildren: 0.06 } },
  }
  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { transition: { duration: 0.5, ease: "easeOut" as const } },
  }

  const agents = [
    { name: "Order Router", status: "active", uptime: "99.98%", tasks: 1243 },
    { name: "Inventory Monitor", status: "active", uptime: "99.95%", tasks: 892 },
    { name: "Cost Optimizer", status: "active", uptime: "99.99%", tasks: 567 },
    { name: "Demand Predictor", status: "active", uptime: "99.87%", tasks: 345 },
    { name: "Rerouting Agent", status: "idle", uptime: "99.91%", tasks: 78 },
    { name: "Quality Checker", status: "active", uptime: "99.93%", tasks: 2101 },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
      className="space-y-6"
    >
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <motion.div
          whileHover={{ rotate: 15, scale: 1.05 }}
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg"
        >
          <Activity className="h-4 w-4 text-white" />
        </motion.div>
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">Monitoring</h1>
          <p className="text-sm text-muted-foreground/80 mt-0.5">Real-time system health and agent performance</p>
        </div>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {metrics.map((m, i) => {
          const color = m.status === "good" ? "#10b981" : "#f59e0b"
          const Icon = m.icon
          return (
            <motion.div
              key={m.label}
              variants={cardVariants}
              whileHover={{ y: -4, scale: 1.01, transition: { duration: 0.2 } }}
              className="rounded-xl border border-border/50 bg-card p-4 hover:shadow-lg hover:shadow-accent/5 transition-all duration-300"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted transition-colors group-hover:bg-accent/10">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">{m.label}</span>
                </div>
                <motion.div
                  animate={{ scale: [1, 1.4, 1] }}
                  transition={{ duration: 2, repeat: Infinity, delay: i * 0.3 }}
                  className={`h-2 w-2 rounded-full ${m.status === "good" ? "bg-emerald-500" : "bg-amber-500"}`}
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <GaugeMeter pct={m.pct} color={color} />
                <div className="text-right">
                  <motion.p
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + i * 0.1 }}
                    className="text-xl font-bold text-foreground tabular-nums"
                  >
                    {m.value}
                  </motion.p>
                  <p className="text-[10px] text-muted-foreground">{m.pct}% capacity</p>
                </div>
              </div>
            </motion.div>
          )
        })}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.5 }}
        className="rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm overflow-hidden hover:shadow-lg hover:shadow-accent/5 transition-shadow duration-300"
      >
        <div className="border-b border-border/30 bg-muted/30 px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-foreground">Agent Status</h2>
          </div>
          <motion.span
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="text-[10px] text-emerald-500 font-medium flex items-center gap-1"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            All systems nominal
          </motion.span>
        </div>
        <div className="divide-y divide-border/30">
          {agents.map((agent, i) => {
            const Icon = agentIcons[i]
            const color = agentColors[i]
            return (
              <motion.div
                key={agent.name}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 + i * 0.05 }}
                whileHover={{ backgroundColor: "rgba(255,255,255,0.02)" }}
                className="flex items-center justify-between px-5 py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: `${color}15` }}>
                    <Icon className="h-4 w-4" style={{ color }} />
                  </div>
                  <div>
                    <span className="text-sm font-medium text-foreground">{agent.name}</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <motion.span
                        animate={agent.status === "active" ? { scale: [1, 1.3, 1] } : {}}
                        transition={{ duration: 2, repeat: Infinity }}
                        className={`h-1.5 w-1.5 rounded-full ${agent.status === "active" ? "bg-emerald-500" : "bg-gray-400"}`}
                      />
                      <span className="text-[10px] text-muted-foreground">{agent.status}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-6 text-xs text-muted-foreground">
                  <span>
                    Uptime:{" "}
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
 className="text-foreground/80 font-medium">{agent.uptime}</motion.span>
                  </span>
                  <span>
                    Tasks:{" "}
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
 className="text-foreground/80 font-medium">{agent.tasks.toLocaleString()}</motion.span>
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${agent.status === "active" ? "bg-emerald-500/10 text-emerald-500" : "bg-muted text-muted-foreground"}`}>
                    {agent.status}
                  </span>
                </div>
              </motion.div>
            )
          })}
        </div>
      </motion.div>
    </motion.div>
  )
}
