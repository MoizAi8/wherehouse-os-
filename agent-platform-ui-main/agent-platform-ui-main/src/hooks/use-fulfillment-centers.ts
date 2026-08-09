"use client"

import { api } from "@/lib/api"
import { useApi } from "./use-api"

export interface FulfillmentCenter {
  id: string
  name: string
  address: string
  zip_code: string
  city: string
  state: string
  country: string
  latitude: number | null
  longitude: number | null
  is_active: boolean
  capacity_pct: number
  max_daily_orders: number
  current_daily_orders: number
}

export function useFulfillmentCenters() {
  return useApi(() => api.get<FulfillmentCenter[]>("/api/v1/fulfillment-centers"), [])
}
