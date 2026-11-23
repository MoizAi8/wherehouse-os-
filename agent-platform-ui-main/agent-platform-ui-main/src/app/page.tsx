import { LazyWarehouseHero } from "@/components/hero/LazyWarehouseHero"
import { LandingSections } from "@/components/landing/LandingSections"

import { redirect } from "next/navigation"

export const dynamic = "force-dynamic"

export default function Home() {
  if (process.env.HOSTED_INSTRUCTOR_ENABLED === "true") redirect("/dashboard")
  return (
    <>
      <LazyWarehouseHero />
      <LandingSections />
    </>
  )
}
