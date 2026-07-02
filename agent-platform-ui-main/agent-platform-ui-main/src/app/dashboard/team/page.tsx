"use client"

import { Mail } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

const members = [
  { name: "Alex Chen", email: "alex@warehouseos.com", role: "Admin", status: "active", initials: "AC" },
  { name: "Sarah Kim", email: "sarah@warehouseos.com", role: "Operator", status: "active", initials: "SK" },
  { name: "Marcus Lee", email: "marcus@warehouseos.com", role: "Engineer", status: "away", initials: "ML" },
  { name: "Priya Sharma", email: "priya@warehouseos.com", role: "Analyst", status: "active", initials: "PS" },
  { name: "James Wilson", email: "james@warehouseos.com", role: "Operator", status: "offline", initials: "JW" },
  { name: "Emily Davis", email: "emily@warehouseos.com", role: "Engineer", status: "active", initials: "ED" },
]

export default function TeamPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Team</h1>
        <p className="text-sm text-muted-foreground">Ask AI to manage team members</p>
      </div>

      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <div className="grid grid-cols-[1fr_1fr_100px_100px] gap-4 border-b border-border/30 bg-muted/30 px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {["Name", "Email", "Role", "Status"].map((h) => (
            <span key={h}>{h}</span>
          ))}
        </div>
        <div className="divide-y divide-border/30">
          {members.map((member) => (
            <div key={member.email} className="grid grid-cols-[1fr_1fr_100px_100px] gap-4 px-5 py-3 items-center">
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
              <span className="text-sm capitalize text-foreground/70">{member.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
