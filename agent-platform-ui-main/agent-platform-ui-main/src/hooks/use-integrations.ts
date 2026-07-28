"use client"

import { api } from "@/lib/api"
import { useApi } from "./use-api"
import { useCallback, useState } from "react"

export interface IntegrationConnection {
  id: string
  provider: string
  label: string
  base_url: string
  db_name: string | null
  username: string | null
  is_connected: boolean
  last_sync_at: string | null
  sync_status: string
  error_message: string | null
  version: string | null
  total_orders_synced: number
  total_products_synced: number
  created_at: string
  updated_at: string
}

export interface ConnectRequest {
  provider: string
  label: string
  base_url: string
  db: string
  username: string
  password: string
  verify_ssl?: boolean
}

export interface ConnectionStatus {
  connected: boolean
  version?: string
  uid?: number
  error?: string
}

export interface SyncResult {
  success: boolean
  message: string
  orders_created: number
  orders_updated: number
  products_synced: number
  partners_synced: number
}

export function useIntegrations() {
  return useApi(() => api.get<IntegrationConnection[]>("/api/v1/integrations/connections"), [])
}

export function useConnectIntegration() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connect = useCallback(async (req: ConnectRequest): Promise<IntegrationConnection | null> => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.post<IntegrationConnection>("/api/v1/integrations/connect", req)
      return result
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connection failed"
      setError(msg)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { connect, loading, error }
}

export function useTestConnection() {
  const [loading, setLoading] = useState(false)

  const test = useCallback(async (id: string): Promise<ConnectionStatus> => {
    setLoading(true)
    try {
      return await api.post<ConnectionStatus>(`/api/v1/integrations/connections/${id}/test`)
    } finally {
      setLoading(false)
    }
  }, [])

  return { test, loading }
}

export function useSyncConnection() {
  const [loading, setLoading] = useState(false)

  const sync = useCallback(async (id: string): Promise<SyncResult> => {
    setLoading(true)
    try {
      return await api.post<SyncResult>(`/api/v1/integrations/connections/${id}/sync`)
    } finally {
      setLoading(false)
    }
  }, [])

  return { sync, loading }
}

export function useDeleteConnection() {
  const [loading, setLoading] = useState(false)

  const remove = useCallback(async (id: string): Promise<boolean> => {
    setLoading(true)
    try {
      await api.delete(`/api/v1/integrations/connections/${id}`)
      return true
    } catch {
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  return { remove, loading }
}
