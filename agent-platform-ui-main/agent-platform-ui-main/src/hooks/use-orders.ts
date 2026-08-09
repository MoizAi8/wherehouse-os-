"use client"

import { api } from "@/lib/api"
import { useApi } from "./use-api"

export interface Order {
  id: string
  external_order_id: string | null
  customer_email: string
  customer_phone: string | null
  shipping_address: string
  shipping_zip: string
  shipping_city: string
  shipping_state: string
  shipping_country: string
  items_json: string
  total_weight_kg: number
  status: string
  fulfillment_center_id: string | null
  carrier_id: string | null
  tracking_number: string | null
  estimated_delivery: string | null
  shipping_cost: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface OrderListResponse {
  orders: Order[]
  total: number
}

export function useOrders(params?: { status?: string; limit?: number }) {
  const query = new URLSearchParams()
  if (params?.status) query.set("status", params.status)
  if (params?.limit) query.set("limit", String(params.limit))
  const qs = query.toString()

  return useApi(() => api.get<OrderListResponse>(`/api/v1/orders${qs ? `?${qs}` : ""}`), [params?.status, params?.limit])
}
