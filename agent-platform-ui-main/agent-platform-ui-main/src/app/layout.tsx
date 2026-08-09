import type { Metadata } from "next"
import { Sora, Barlow_Condensed } from "next/font/google"
import "./globals.css"
import { SmoothScrollProvider } from "@/components/providers/SmoothScrollProvider"
import { TooltipProvider } from "@/components/ui/tooltip"
import { NoiseOverlay } from "@/components/effects/NoiseOverlay"
import { SettingsProvider } from "@/contexts/SettingsContext"
import { SessionProvider } from "@/components/providers/SessionProvider"
import { SessionTimer } from "@/components/providers/SessionTimer"
import { ThemeToggle } from "@/components/ui/ThemeToggle"

const sora = Sora({ variable: "--font-sora", subsets: ["latin"] })
const barlowCondensed = Barlow_Condensed({ variable: "--font-barlow-condensed", subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] })

export const metadata: Metadata = {
  title: "Warehouse OS — Multi-Agent Orchestration Platform",
  description: "Deploy, monitor, and scale autonomous agents that manage inventory, optimize workflows, and predict demand in real time.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sora.variable} ${barlowCondensed.variable} dark h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full bg-background font-sans text-foreground selection:bg-accent/30 selection:text-foreground">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-white">
          Skip to main content
        </a>
        <TooltipProvider>
          <SmoothScrollProvider>
            <SettingsProvider>
              <SessionProvider>
                <SessionTimer>
                  <NoiseOverlay />
                  <ThemeToggle />
                  <main id="main-content">{children}</main>
                </SessionTimer>
              </SessionProvider>
            </SettingsProvider>
          </SmoothScrollProvider>
        </TooltipProvider>
      </body>
    </html>
  )
}
