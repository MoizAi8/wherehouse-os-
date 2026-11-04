"use client"

import { cloneElement, useId, useRef, useState, type FormEvent, type ReactElement } from "react"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApi } from "@/hooks/use-api"
import { ApiError, api } from "@/lib/api"

const base = "/api/v1/inventory"
const selectStyle = "rounded-md border border-input bg-background px-3 py-2 text-sm"
const panelStyle = "space-y-3 rounded-xl border border-border/40 bg-card/50 p-4"

type Product = { sku: string; name: string }
type Center = { id: string; name: string }
type Stock = { id: string; sku: string; center_id: string; on_hand: number; reserved: number; available: number; low_stock: boolean }
type Movement = { id: string; kind: string; on_hand_delta: number; reserved_delta: number; reason: string; created_at: string }
type Reservation = { id: string; stock_id: string; quantity: number; status: "reserved" | "released" | "consumed" }
type Order = { status: string; tracking_number: string | null }

function Field({ title, children }: { title: string; children: ReactElement<{ id?: string }> }) {
  const id = useId()
  return <div className="flex flex-col gap-1 text-sm">
    <label htmlFor={id}>{title}</label>
    {cloneElement(children, { id })}
  </div>
}

function InventoryWorkspace() {
  const [stockId, setStockId] = useState("")
  const [orderId, setOrderId] = useState("")
  const [lookedUpOrder, setLookedUpOrder] = useState("")
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const changeRequest = useRef<{ signature: string; id: string } | null>(null)
  const profile = useApi(() => api.get<{ role: string }>("/api/auth/me"))
  const canWrite = profile.data?.role === "admin" || profile.data?.role === "operator"
  const products = useApi(() => api.get<Product[]>(base + "/products"), [revision])
  const centers = useApi(() => api.get<Center[]>("/api/v1/fulfillment-centers"))
  const stocks = useApi(() => api.get<Stock[]>(base + "/stock"), [revision])
  const stock = stocks.data?.find(item => item.id === stockId)
  const stockPath = base + "/stock/" + encodeURIComponent(stockId)
  const history = useApi(
    async () => ({ stockId, rows: stockId ? await api.get<Movement[]>(stockPath + "/movements") : [] }),
    [stockId, revision],
  )
  const reservations = useApi(
    async () => ({
      orderId: lookedUpOrder,
      rows: lookedUpOrder
        ? await api.get<Reservation[]>(base + "/orders/" + encodeURIComponent(lookedUpOrder) + "/reservations")
        : [],
    }),
    [lookedUpOrder, revision],
  )
  const order = useApi(async () => ({
    orderId: lookedUpOrder,
    record: lookedUpOrder ? await api.get<Order>("/api/v1/orders/" + encodeURIComponent(lookedUpOrder)) : null,
  }), [lookedUpOrder, revision])
  const orderRecord = order.data?.orderId === lookedUpOrder ? order.data.record : null
  const movements = history.data?.stockId === stockId ? history.data.rows : []
  const orderReservations = reservations.data?.orderId === lookedUpOrder ? reservations.data.rows : []

  async function submit(event: FormEvent<HTMLFormElement>, action: (data: FormData) => Promise<unknown>) {
    event.preventDefault()
    if (pending.current) return
    const data = new FormData(event.currentTarget)
    pending.current = true
    setBusy(true)
    setError("")
    try {
      await action(data)
      setRevision(value => value + 1)
    } catch (failure) {
      if (failure instanceof ApiError) {
        try {
          const { detail } = JSON.parse(failure.message)
          setError(typeof detail === "string" ? detail : "Inventory request failed. Check the submitted values.")
        } catch {
          setError("Inventory request failed.")
        }
      } else {
        setError("The server response could not be confirmed. Refresh before retrying.")
      }
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  const readError = profile.error || products.error || centers.error || stocks.error || history.error || reservations.error || order.error
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Inventory</h1>
        <p className="text-sm text-muted-foreground">Manage SKU balances, stock movements, and order reservations.</p>
      </div>
      {(error || readError) && <p role="alert" className="text-sm text-destructive">{error || "An inventory view could not load."}</p>}

      {canWrite && <div className="grid gap-4 lg:grid-cols-2">
        <form className={panelStyle} onSubmit={event => void submit(event, data => api.post(base + "/products", {
          sku: data.get("sku"), name: data.get("name"),
        }))}>
          <h2 className="font-medium">New product</h2>
          <Field title="SKU"><Input name="sku" required maxLength={80} /></Field>
          <Field title="Product name"><Input name="name" required maxLength={200} /></Field>
          <Button disabled={busy}>Add product</Button>
        </form>
        <form className={panelStyle} onSubmit={event => void submit(event, async data => {
          const created = await api.post<Stock>(base + "/stock", {
            sku: data.get("sku"), center_id: data.get("center"), low_stock_threshold: Number(data.get("threshold")),
          })
          setStockId(created.id)
        })}>
          <h2 className="font-medium">New stock location</h2>
          <Field title="Product"><select name="sku" className={selectStyle} required defaultValue="">
            <option value="" disabled>Select a SKU</option>
            {products.data?.map(product => <option key={product.sku} value={product.sku}>{product.sku} · {product.name}</option>)}
          </select></Field>
          <Field title="Fulfillment center"><select name="center" className={selectStyle} required defaultValue="">
            <option value="" disabled>Select a center</option>
            {centers.data?.map(center => <option key={center.id} value={center.id}>{center.name}</option>)}
          </select></Field>
          <Field title="Low-stock threshold"><Input name="threshold" type="number" min={0} max={1000000000} defaultValue={0} required /></Field>
          <Button disabled={busy || !products.data?.length || !centers.data?.length}>Add stock location</Button>
        </form>
      </div>}

      {canWrite && <form className={panelStyle} onSubmit={event => void submit(event, async data => {
        const created = await api.post<{ id: string }>("/api/v1/orders", {
          defer_routing: true, external_order_id: data.get("reference"), customer_email: data.get("email"),
          shipping_address: data.get("address"), shipping_zip: data.get("zip"), shipping_city: data.get("city"),
          shipping_state: data.get("state"), shipping_country: data.get("country"), total_weight_kg: Number(data.get("weight")),
        })
        setOrderId(created.id)
        setLookedUpOrder(created.id)
      })}>
        <h2 className="font-medium">Create order for allocation</h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Field title="Order reference"><Input name="reference" required maxLength={255} /></Field>
          <Field title="Customer email"><Input name="email" type="email" required /></Field>
          <Field title="Shipping address"><Input name="address" required /></Field>
          <Field title="Postal code"><Input name="zip" required minLength={5} maxLength={20} /></Field>
          <Field title="Shipping city"><Input name="city" required /></Field>
          <Field title="State or region"><Input name="state" required /></Field>
          <Field title="Shipping country"><Input name="country" required defaultValue="US" /></Field>
          <Field title="Total weight (kg)"><Input name="weight" type="number" min={0} step="any" required /></Field>
        </div>
        <Button disabled={busy}>Create pending order</Button>
      </form>}

      <section className={panelStyle}>
        <Field title="Stock location"><select className={selectStyle} value={stockId} onChange={event => setStockId(event.target.value)}>
          <option value="">{stocks.loading ? "Loading…" : "Select a location"}</option>
          {stocks.data?.map(item => (
            <option key={item.id} value={item.id}>{item.sku} · {centers.data?.find(center => center.id === item.center_id)?.name ?? item.center_id}</option>
          ))}
        </select></Field>
        {stock && <p className="text-sm" aria-live="polite">
          On hand {stock.on_hand} · Reserved {stock.reserved} · Available {stock.available}
          {stock.low_stock && <span className="ml-2 text-amber-500">Low stock</span>}
        </p>}
      </section>

      {stock && canWrite && <div className="grid gap-4 lg:grid-cols-2">
        <form className={panelStyle} onSubmit={event => void submit(event, async data => {
          const payload = { kind: data.get("kind"), quantity_delta: Number(data.get("quantity")), reason: data.get("reason") }
          const signature = JSON.stringify([stock.id, payload])
          if (changeRequest.current?.signature !== signature) {
            changeRequest.current = { signature, id: crypto.randomUUID() }
          }
          await api.post(stockPath + "/movements", { ...payload, operation_id: changeRequest.current.id })
          changeRequest.current = null
        })}>
          <h2 className="font-medium">Record stock movement</h2>
          <Field title="Movement type"><select className={selectStyle} name="kind"><option value="receipt">Receipt</option><option value="adjustment">Adjustment</option></select></Field>
          <Field title="Quantity change"><Input name="quantity" type="number" min={-1000000000} max={1000000000} required /></Field>
          <Field title="Movement reason"><Input name="reason" maxLength={250} required /></Field>
          <Button disabled={busy}>Record movement</Button>
        </form>
        <form className={panelStyle} onSubmit={event => void submit(event, async data => {
          const id = String(data.get("order") ?? "").trim()
          await api.post(stockPath + "/reservations", { order_id: id, quantity: Number(data.get("quantity")) })
          setOrderId(id)
          setLookedUpOrder(id)
        })}>
          <h2 className="font-medium">Reserve for an order</h2>
          <Field title="Allocation order ID"><Input name="order" required maxLength={36} value={orderId} onChange={event => setOrderId(event.target.value)} /></Field>
          <Field title="Reservation quantity"><Input name="quantity" type="number" min={1} max={1000000000} required /></Field>
          <Button disabled={busy}>Reserve stock</Button>
        </form>
      </div>}

      {stock && <section className={panelStyle}>
        <h2 className="font-medium">Recent movements</h2>
        <ul className="space-y-1 text-sm text-muted-foreground">
          {!history.loading && !history.error && !movements.length && <li>No movements recorded.</li>}
          {movements.map(item => <li key={item.id}>
            {new Date(item.created_at).toLocaleString()} · {item.kind} · On hand {item.on_hand_delta} · Reserved {item.reserved_delta} · {item.reason}
          </li>)}
        </ul>
      </section>}

      <section className={panelStyle}>
        <h2 className="font-medium">Order reservations</h2>
        <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
          event.preventDefault()
          setLookedUpOrder(orderId.trim())
        }}>
          <Field title="Lookup order ID"><Input required maxLength={36} value={orderId} onChange={event => setOrderId(event.target.value)} /></Field>
          <Button variant="outline">Find reservations</Button>
        </form>
        {lookedUpOrder && <p className="break-all text-sm">Order {lookedUpOrder}</p>}
        {orderRecord && <p className="text-sm" aria-live="polite">
          Status {orderRecord.status}{orderRecord.tracking_number && ` · Internal tracking ${orderRecord.tracking_number}`}
        </p>}
        {lookedUpOrder && !reservations.loading && !reservations.error && !orderReservations.length && <p className="text-sm text-muted-foreground">No reservations found.</p>}
        {canWrite && orderRecord?.status === "pending" && orderReservations.some(item => item.status === "reserved") && (
          <form onSubmit={event => void submit(event, async () => {
            await api.post("/api/v1/orders/" + encodeURIComponent(lookedUpOrder) + "/route")
          })}>
            <Button variant="outline" disabled={busy}>Route allocated order</Button>
          </form>
        )}
        {orderReservations.map(item => (
          <div key={item.id} className="space-y-2 border-t border-border/40 pt-2">
            <p className="text-sm">{stocks.data?.find(row => row.id === item.stock_id)?.sku ?? item.stock_id} · {item.quantity} units · {item.status}</p>
            {canWrite && item.status === "reserved" && <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
              const button = (event.nativeEvent as SubmitEvent).submitter
              const action = button?.getAttribute("value") === "consume" ? "consume" : "release"
              if (action === "consume" && !window.confirm("Record these reserved units as dispatched?")) {
                event.preventDefault()
                return
              }
              void submit(event, data => api.post(base + "/reservations/" + encodeURIComponent(item.id) + "/" + action, {
                reason: data.get("reason"),
              }))
            }}>
              <Field title="Reservation outcome reason"><Input name="reason" maxLength={250} required /></Field>
              <Button value="release" variant="outline" disabled={busy}>Release</Button>
              <Button value="consume" disabled={busy}>Record dispatch</Button>
            </form>}
          </div>
        ))}
      </section>
    </div>
  )
}

export default function InventoryPage() {
  const { data: session, status } = useSession()
  if (status === "loading") return <p className="text-sm text-muted-foreground">Loading session…</p>
  if (!session?.accessToken || session.demoGuest) {
    return <p className="text-sm text-muted-foreground">Sign in with a business account to view inventory.</p>
  }
  return <InventoryWorkspace key={session.user.id} />
}
