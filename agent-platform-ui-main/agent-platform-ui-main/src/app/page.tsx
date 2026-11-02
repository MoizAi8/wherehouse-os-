import { LazyWarehouseHero } from "@/components/hero/LazyWarehouseHero"
import { LandingSections } from "@/components/landing/LandingSections"
import { redirect } from "next/navigation"

export default async function Home() {
  let demoEnabled = false
  if (process.env.BACKEND_URL) {
    try {
      const response = await fetch(`${process.env.BACKEND_URL}/api/demo/status`, {
        cache: "no-store", signal: AbortSignal.timeout(1500),
      })
      demoEnabled = response.ok && (await response.json()).enabled === true
    } catch { /* Preserve the normal landing page when the backend is unavailable. */ }
  }
  if (demoEnabled) redirect("/demo")
  return (
    <>
      <LazyWarehouseHero />
      <LandingSections />
    </>
  )
}
