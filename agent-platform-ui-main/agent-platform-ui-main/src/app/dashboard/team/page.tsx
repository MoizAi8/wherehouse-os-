"use client"

import { motion } from "framer-motion"
import { Users, Mail, Shield, Clock, UserCheck, UserX, UserMinus } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

const members = [
  { name: "Alex Chen", email: "alex@warehouseos.com", role: "Admin", status: "active", initials: "AC" },
  { name: "Sarah Kim", email: "sarah@warehouseos.com", role: "Operator", status: "active", initials: "SK" },
  { name: "Marcus Lee", email: "marcus@warehouseos.com", role: "Engineer", status: "away", initials: "ML" },
  { name: "Priya Sharma", email: "priya@warehouseos.com", role: "Analyst", status: "active", initials: "PS" },
  { name: "James Wilson", email: "james@warehouseos.com", role: "Operator", status: "offline", initials: "JW" },
  { name: "Emily Davis", email: "emily@warehouseos.com", role: "Engineer", status: "active", initials: "ED" },
]

const statusConfig: Record<string, { dot: string; icon: typeof UserCheck; label: string }> = {
  active: { dot: "bg-emerald-500", icon: UserCheck, label: "Active" },
  away: { dot: "bg-amber-500", icon: UserMinus, label: "Away" },
  offline: { dot: "bg-gray-400", icon: UserX, label: "Offline" },
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { transition: { staggerChildren: 0.06 } },
}

const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { transition: { duration: 0.4, ease: "easeOut" as const } },
}

const rowVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.04, duration: 0.35, ease: "easeOut" as const },
  }),
}

export default function TeamPage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
      className="space-y-6"
    >
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-3">
        <motion.div
          whileHover={{ scale: 1.05, rotate: -5 }}
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg"
        >
          <Users className="h-4 w-4 text-white" />
        </motion.div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Team</h1>
          <p className="text-sm text-muted-foreground">Manage team members and permissions</p>
        </div>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {[
          { icon: Users, label: "Total Members", value: members.length, color: "from-blue-500 to-cyan-500" },
          { icon: Shield, label: "Admins", value: members.filter(m => m.role === "Admin").length, color: "from-purple-500 to-pink-500" },
          { icon: Clock, label: "Active Now", value: members.filter(m => m.status === "active").length, color: "from-emerald-500 to-teal-500" },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            variants={cardVariants}
            whileHover={{ y: -3, transition: { duration: 0.2 } }}
            className="rounded-xl border border-border/50 bg-card p-4 flex items-center gap-3 hover:shadow-lg hover:shadow-accent/5 transition-all"
          >
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${stat.color} shadow-lg`}>
              <stat.icon className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{stat.label}</p>
              <motion.p
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 15, delay: 0.2 + i * 0.1 }}
                className="text-lg font-bold text-foreground"
              >
                {stat.value}
              </motion.p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
        className="rounded-xl border border-border/50 bg-card overflow-hidden"
      >
        <div className="grid grid-cols-[1fr_1fr_100px_100px] gap-4 border-b border-border/30 bg-muted/30 px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {["Name", "Email", "Role", "Status"].map((h, i) => (
            <motion.span
              key={h}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 + i * 0.05 }}
            >
              {h}
            </motion.span>
          ))}
        </div>
        <div className="divide-y divide-border/30">
          {members.map((member, i) => {
            const sc = statusConfig[member.status]
            const StatusIcon = sc?.icon
            return (
              <motion.div
                key={member.email}
                custom={i}
                variants={rowVariants}
                initial="hidden"
                animate="visible"
                whileHover={{ backgroundColor: "rgba(255,255,255,0.02)" }}
                className="grid grid-cols-[1fr_1fr_100px_100px] gap-4 px-5 py-3 items-center cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Avatar className="h-8 w-8 ring-2 ring-border/30">
                    <AvatarFallback className="text-[11px] font-medium bg-muted text-foreground">{member.initials}</AvatarFallback>
                  </Avatar>
                  <span className="text-sm font-medium text-foreground">{member.name}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Mail className="h-3.5 w-3.5" />
                  <span>{member.email}</span>
                </div>
                <span className="text-sm text-foreground/80">{member.role}</span>
                <span className="inline-flex items-center gap-1.5 text-sm capitalize">
                  <motion.span
                    animate={member.status === "active" ? { scale: [1, 1.4, 1] } : {}}
                    transition={{ duration: 2, repeat: Infinity }}
                    className={`h-2 w-2 rounded-full ${sc?.dot || "bg-gray-400"}`}
                  />
                  {StatusIcon && <StatusIcon className="h-3.5 w-3.5 text-muted-foreground/50" />}
                  <span className="text-foreground/70">{sc?.label || member.status}</span>
                </span>
              </motion.div>
            )
          })}
        </div>
      </motion.div>
    </motion.div>
  )
}
