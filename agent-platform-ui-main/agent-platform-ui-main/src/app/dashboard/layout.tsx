import { SearchProvider } from "@/contexts/SearchContext"
import { DashboardShell } from "@/components/layout/DashboardShell"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SearchProvider>
      <DashboardShell>
        <div className="min-h-full bg-grid-subtle bg-ambient">
          <div id="dashboard-content" className="outline-none" tabIndex={-1}>
            {children}
          </div>
        </div>
      </DashboardShell>
    </SearchProvider>
  )
}
