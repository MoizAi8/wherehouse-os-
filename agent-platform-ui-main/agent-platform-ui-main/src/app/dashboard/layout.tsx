import { SearchProvider } from "@/contexts/SearchContext"
import { DashboardShell } from "@/components/layout/DashboardShell"
import { AuthBootstrap } from "@/components/providers/AuthBootstrap"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SearchProvider>
      <DashboardShell>
        <AuthBootstrap>
          <div className="min-h-full bg-grid-subtle bg-ambient">
            <div id="dashboard-content" className="outline-none" tabIndex={-1}>
              {children}
            </div>
          </div>
        </AuthBootstrap>
      </DashboardShell>
    </SearchProvider>
  )
}
