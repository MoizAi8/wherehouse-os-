"use client"

import { api } from "@/lib/api"
import { useApi } from "./use-api"

export interface Shipment {
  id: string
  order_id: string
  carrier_name: string
  tracking_number: string
  status: string
  estimated_delivery: string | null
  actual_delivery: string | null
  origin_zip: string
  destination_zip: string
  weight_kg: number
  shipping_cost: number | null
  carrier_status_detail: string | null
  is_delayed: boolean
  delay_reason: string | null
  created_at: string
  updated_at: string
}

export function useShipments(params?: { status?: string }) {
  const query = params?.status ? `?status=${params.status}` : ""
  return useApi(() => api.get<Shipment[]>(`/api/v1/shipments${query}`), [params?.status])
}
