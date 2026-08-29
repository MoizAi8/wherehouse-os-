"use client"

import { useLayoutEffect, useState } from "react"
import { SmoothScrollProvider as OriginalSmoothScrollProvider } from "@/components/providers/SmoothScrollProvider"
import { NoiseOverlay as OriginalNoiseOverlay } from "@/components/effects/NoiseOverlay"
import { ThemeToggle as OriginalThemeToggle } from "@/components/ui/ThemeToggle"

export function ClientProviders({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false)

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useLayoutEffect(() => {
    setMounted(true)
  }, [])

  return (
    <>
      {mounted && (
        <OriginalSmoothScrollProvider>
          <OriginalNoiseOverlay />
          <OriginalThemeToggle />
        </OriginalSmoothScrollProvider>
      )}
      {children}
    </>
  )
}