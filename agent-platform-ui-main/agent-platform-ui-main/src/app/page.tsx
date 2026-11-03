import { guestModeEnabled } from "@/lib/demo-guest"
import { LazyWarehouseHero } from "@/components/hero/LazyWarehouseHero"
import { LandingSections } from "@/components/landing/LandingSections"
import { redirect } from "next/navigation"

export const dynamic = "force-dynamic"

export default async function Home() {
  if (await guestModeEnabled()) redirect("/dashboard")
  return (
    <>
      <LazyWarehouseHero />
      <LandingSections />
    </>
  )
}
