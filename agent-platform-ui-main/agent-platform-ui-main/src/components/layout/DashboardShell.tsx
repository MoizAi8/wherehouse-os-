"use client"

import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background max-md:[&:has([data-chat-layout])>aside]:w-[68px] max-md:[&:has([data-chat-layout])_[data-chat-compact-hide]]:hidden max-md:[&:has([data-chat-layout])_header]:px-3">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col pl-[240px] max-md:has-[[data-chat-layout]]:pl-[68px] transition-all duration-300">
        <Topbar />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
