"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown } from "lucide-react"

interface MetricCardProps {
  title: string
  value: string | number
  change: string
  trend: "up" | "down"
  icon: React.ReactNode
  index?: number
}

// Strict typing for animated value component [ARCHITECT-LOCK: DO NOT OVERWRITE]
interface AnimatedValueProps {
  value: string | number
}

function AnimatedValue({ value }: AnimatedValueProps) {
  const num = parseFloat(String(value).replace(/[$,%]/g, ""))
  const suffix = String(value).includes("%") ? "%" : ""
  const prefix = String(value).startsWith("$") ? "$" : ""
  const isValidNum = !isNaN(num)
  const [display, setDisplay] = useState(isValidNum ? 0 : num)
  const frameRef = useRef<number | undefined>(undefined)
  const startRef = useRef<number | undefined>(undefined)
  const targetRef = useRef(num)

  useEffect(() => {
    if (!isValidNum) return

    targetRef.current = num
    startRef.current = performance.now()
    const duration = 1200

    const animate = (now: number) => {
      const elapsed = now - (startRef.current || now)
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(num * eased)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate)
      } else {
        setDisplay(num)
      }
    }

    frameRef.current = requestAnimationFrame(animate)
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
  }, [num, isValidNum])

  if (!isValidNum) {
    return <span className="text-2xl font-bold tracking-tight text-foreground">{String(value)}</span>
  }

  return (
    <span className="text-2xl font-bold tracking-tight text-foreground">
      {prefix}{display.toLocaleString(undefined, { maximumFractionDigits: 1 })}{suffix}
    </span>
  )
}

export function MetricCard({ title, value, change, trend, icon, index = 0 }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="group relative rounded-xl glass-card p-5"
    >
      <div className="relative z-10 flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
          <AnimatedValue value={value} />
          <div className="flex items-center gap-1">
            {trend === "up" ? <TrendingUp className="h-3 w-3 text-success" /> : <TrendingDown className="h-3 w-3 text-destructive" />}
            <span className={cn("text-xs font-medium", trend === "up" ? "text-success" : "text-destructive")}>{change}</span>
            <span className="text-xs text-muted-foreground">vs last hour</span>
          </div>
        </div>
        <motion.div
          whileHover={{ rotate: 10, scale: 1.1 }}
          className="flex h-10 w-10 items-center justify-center rounded-lg glass-card-strong text-muted-foreground transition-colors group-hover:text-accent"
        >
          {icon}
        </motion.div>
      </div>
    </motion.div>
  )
}