import { guestFetch } from "@/lib/demo-guest"
import { backendUrl, getAuthHeaders } from "@/lib/backend"

export async function POST() {
  const base = backendUrl()
  if (!base) {
    return Response.json({ error: "Backend not configured: BACKEND_URL is unset" }, { status: 503 })
  }

  try {
    const authHeaders = await getAuthHeaders()
    if (!authHeaders.Authorization) {
      const sample = await guestFetch("data?path=%2Fapi%2Fv1%2Fanalytics%2Fkpis")
      if (!sample.ok) return sample
      const metrics = await sample.json()
      return Response.json({ insights: [{ metric: "Sample warehouse", agent: "Sample warehouse", action: "Review the sample delayed shipment; guest access cannot dispatch.", priority: "medium", insight: `${metrics.orders_delayed} sample shipment is delayed. Guest access is read-only.`, severity: "info" }] })
    }
    const backendRes = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message: "Give me current insights and recommendations for the warehouse system." }),
      signal: AbortSignal.timeout(10000),
    })
    if (!backendRes.ok) {
      return Response.json({ error: "Insight generation failed" }, { status: 500 })
    }
    const data = await backendRes.json()
    return Response.json({ insights: [{ metric: "AI Insight", insight: data.reply, severity: "info" }] })
  } catch {
    return Response.json({ error: "Insight generation failed" }, { status: 500 })
  }
}