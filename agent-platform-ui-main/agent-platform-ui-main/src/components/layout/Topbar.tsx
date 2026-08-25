"use client"

import { motion } from "framer-motion"
import { usePathname, useRouter } from "next/navigation"
import { Bell, Search, ChevronRight, Maximize2, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

const breadcrumbMap: Record<string, string> = {
  dashboard: "Dashboard",
  chat: "Chat",
  agents: "Agents",
  workflows: "Workflows",
  orders: "Orders",
  monitoring: "Monitoring",
  integrations: "Integrations",
  analytics: "Analytics",
  team: "Team",
  notifications: "Notifications",
  settings: "Settings",
  profile: "Profile",
}

export function Topbar() {
  const pathname = usePathname()
  const router = useRouter()
  const segments = pathname.split("/").filter(Boolean)

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1], delay: 0.1 }}
      className="glass-topbar sticky top-0 z-30 flex h-14 items-center justify-between px-6"
    >
      <div className="flex items-center gap-4">
        {segments.length > 0 && (
          <nav className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground/60 text-xs">/</span>
            {segments.map((seg, i) => {
              const label = breadcrumbMap[seg] || seg.charAt(0).toUpperCase() + seg.slice(1)
              const isLast = i === segments.length - 1
              return (
                <span key={seg} className="flex items-center gap-1.5">
                  <span className={isLast ? "text-foreground font-medium" : "text-muted-foreground text-xs"}>{label}</span>
                  {!isLast && <ChevronRight className="h-3 w-3 text-muted-foreground/40" />}
                </span>
              )
            })}
          </nav>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/60" />
          <input
            type="text"
            placeholder="Search anything..."
            className="glass-input h-8 w-56 rounded-lg pl-9 pr-3 text-xs text-foreground placeholder:text-muted-foreground/50 focus:w-72 transition-all outline-none"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden sm:inline-flex h-4 items-center gap-0.5 rounded border border-border/40 bg-muted/50 px-1.5 text-[10px] text-muted-foreground/50">
            ⌘K
          </kbd>
        </div>

        <Button variant="ghost" size="icon" className="relative h-8 w-8">
          <Bell className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-accent ring-2 ring-background" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Maximize2 className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
        <div className="h-5 w-px bg-border/40" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 px-2 h-8">
              <Avatar className="h-6 w-6">
                <AvatarImage src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=64&h=64&fit=crop&crop=face" />
                <AvatarFallback className="text-[10px]">AD</AvatarFallback>
              </Avatar>
              <span className="text-xs font-medium">Admin</span>
              <ChevronDown className="h-3 w-3 text-muted-foreground/60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56 glass-card-strong border-border/60">
            <div className="px-2.5 py-2">
              <p className="text-sm font-medium">Admin</p>
              <p className="text-xs text-muted-foreground">admin@warehouse.io</p>
            </div>
            <DropdownMenuSeparator className="bg-border/30" />
            <DropdownMenuItem className="text-xs" onSelect={() => router.push("/dashboard/profile")}>Profile</DropdownMenuItem>
            <DropdownMenuItem className="text-xs">Preferences</DropdownMenuItem>
            <DropdownMenuItem className="text-xs">API Keys</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </motion.header>
  )
}
