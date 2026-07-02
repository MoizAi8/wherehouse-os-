import { SearchProvider } from "@/contexts/SearchContext"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SearchProvider>
      <div className="min-h-screen bg-grid-subtle bg-ambient flex" role="region" aria-label="Dashboard">
        <div className="flex-1 flex flex-col">
          <div id="dashboard-content" className="flex-1 outline-none flex flex-col" tabIndex={-1}>
            {children}
          </div>
        </div>
      </div>
    </SearchProvider>
  )
}
