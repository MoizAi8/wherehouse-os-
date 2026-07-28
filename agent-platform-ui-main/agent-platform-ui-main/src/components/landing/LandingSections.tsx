"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { motion } from "framer-motion"
import { Package, Bot, TrendingUp, Shield, Zap } from "lucide-react"
import { AnimatedCounter } from "@/components/effects/AnimatedCounter"
import { Button } from "@/components/ui/button"
import { ScrollAnimations } from "@/components/effects/ScrollAnimations"

gsap.registerPlugin(ScrollTrigger)

const stats = [
  { end: 24, label: "Active Agents", icon: Bot },
  { end: 99.97, suffix: "%", decimals: 2, label: "System Uptime", icon: Shield },
  { end: 84200, suffix: "+", label: "Items Managed", icon: Package },
  { end: 47, suffix: "ms", label: "Avg Response", icon: Zap },
]

const features = [
  {
    icon: Bot,
    title: "Multi-Agent Orchestration",
    description: "Deploy autonomous agents that collaborate in real-time. Each agent specializes in inventory, routing, quality, or forecasting.",
  },
  {
    icon: TrendingUp,
    title: "Predictive Intelligence",
    description: "ML-driven demand forecasting and anomaly detection. Anticipate stockouts, optimize replenishment, and prevent bottlenecks before they happen.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description: "Role-based access, audit trails, and end-to-end encryption. SOC 2 compliant with granular permission controls.",
  },
]

export function LandingSections() {
  const router = useRouter()
  useEffect(() => {
    const ctx = gsap.context(() => {
      const cards = gsap.utils.toArray<HTMLElement>(".feature-card")
      cards.forEach((card) => {
        gsap.fromTo(card, { y: 60, opacity: 0 }, {
          y: 0, opacity: 1, duration: 1, ease: "power3.out",
          scrollTrigger: { trigger: card, start: "top 80%", toggleActions: "play none none reverse" },
        })
      })
    })
    return () => ctx.revert()
  }, [])

  return (
    <>
      <section className="relative border-t border-border/30 py-24">
        <div className="absolute inset-0 bg-gradient-to-b from-accent/[0.02] to-transparent" />
        <div className="relative z-10 mx-auto max-w-6xl px-6">
          <ScrollAnimations animation="fadeUp">
            <div className="text-center mb-16">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent/5 px-3 py-1 text-xs font-medium text-accent">
                <Zap className="h-3 w-3" /> Real-time metrics
              </span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                Trusted by <span className="gradient-text">enterprise</span> warehouses
              </h2>
              <p className="mt-3 text-muted-foreground max-w-lg mx-auto">
                Our platform processes millions of transactions daily across global fulfillment networks.
              </p>
            </div>
          </ScrollAnimations>

          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1, duration: 0.6 }}
                className="group relative rounded-2xl border border-border/50 bg-card/50 p-8 text-center transition-all duration-300 hover:border-accent/30 hover:shadow-[0_0_40px_-10px_rgba(6,214,160,0.15)]"
              >
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent transition-all group-hover:scale-110 group-hover:bg-accent/20">
                  <stat.icon className="h-6 w-6" />
                </div>
                <AnimatedCounter end={stat.end} suffix={stat.suffix || ""} decimals={stat.decimals || 0} label={stat.label} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative py-32 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-hero to-background" />
        <div className="absolute inset-0 shimmer opacity-30" />
        <div className="relative z-10 mx-auto max-w-6xl px-6">
          <ScrollAnimations animation="fadeUp">
            <div className="text-center mb-20">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent/5 px-3 py-1 text-xs font-medium text-accent">
                <Package className="h-3 w-3" /> Platform capabilities
              </span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-5xl">
                Intelligence at every <span className="gradient-text">layer</span>
              </h2>
            </div>
          </ScrollAnimations>

          <div className="grid gap-8 lg:grid-cols-3">
            {features.map((feat) => (
              <div key={feat.title} className="feature-card group relative rounded-2xl border border-border/50 bg-card/40 p-8 transition-all duration-500 hover:border-accent/30 hover:bg-card/80 hover:shadow-[0_0_50px_-15px_rgba(6,214,160,0.12)]">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent transition-all duration-300 group-hover:scale-110 group-hover:bg-accent/20">
                  <feat.icon className="h-6 w-6" />
                </div>
                <h3 className="mb-3 text-lg font-semibold text-foreground">{feat.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{feat.description}</p>
                <div className="mt-6 flex items-center gap-1 text-xs font-medium text-accent opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  Learn more <TrendingUp className="h-3 w-3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative border-t border-border/30 py-24">
        <div className="absolute inset-0 bg-gradient-to-b from-accent/[0.02] via-transparent to-accent/[0.02]" />
        <div className="relative z-10 mx-auto max-w-4xl px-6 text-center">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ duration: 0.8 }}
            className="rounded-3xl border border-border/50 bg-card/50 p-12 backdrop-blur-sm"
          >
            <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Ready to transform your warehouse?</h2>
            <p className="mt-4 text-muted-foreground max-w-lg mx-auto">Deploy your first agent in minutes. No credit card required.</p>
            <div className="mt-8 flex items-center justify-center gap-4">
              <Button size="xl" className="gap-2" onClick={() => router.push("/dashboard")}>Start Free Trial <ArrowRight /></Button>
              <Button variant="glass" size="xl" onClick={() => router.push("/dashboard")}>Book a Demo</Button>
            </div>
          </motion.div>
        </div>
      </section>
    </>
  )
}

function ArrowRight({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
    </svg>
  )
}
