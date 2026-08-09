"use client"

import { Mail } from "lucide-react"

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
        <div className="px-5 py-8 flex flex-col items-center gap-2 text-center">
          <Mail className="h-6 w-6 text-muted-foreground/50" />
          <p className="text-sm font-medium text-foreground/70">No team members yet</p>
          <p className="text-xs text-muted-foreground">
            Team management is handled by the AI assistant.
          </p>
        </div>
      </div>
    </div>
  )
}