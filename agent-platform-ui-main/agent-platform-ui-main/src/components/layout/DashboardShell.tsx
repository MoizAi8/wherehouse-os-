"use client"

import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col pl-[240px] transition-all duration-300">
        <Topbar />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  )
}
