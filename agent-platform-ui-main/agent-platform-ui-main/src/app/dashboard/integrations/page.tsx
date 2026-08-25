"use client"

import { useState, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Plug, Puzzle, Plus, TestTube, RefreshCw, Trash2, CheckCircle2,
  XCircle, Loader2, AlertTriangle, X,
} from "lucide-react"
import { api } from "@/lib/api"
import { useIntegrations, type IntegrationConnection, type SyncResult } from "@/hooks/use-integrations"

export default function IntegrationsPage() {
  const { data: connections, loading, refetch } = useIntegrations()
  const [showForm, setShowForm] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Integrations</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Connect your warehouse management system
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Connection
        </button>
      </div>

      <AnimatePresence>
        {showForm && (
          <AddConnectionForm
            onClose={() => setShowForm(false)}
            onSuccess={() => { setShowForm(false); refetch() }}
          />
        )}
      </AnimatePresence>

      <div className="space-y-3">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {!loading && (!connections || connections.length === 0) && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Puzzle className="h-12 w-12 text-muted-foreground/40 mb-4" />
            <p className="text-muted-foreground">No integrations configured</p>
            <p className="text-sm text-muted-foreground/60 mt-1">
              Connect your Odoo warehouse to get started
            </p>
          </div>
        )}

        {connections?.map((conn) => (
          <ConnectionCard
            key={conn.id}
            conn={conn}
            onDelete={() => setDeleteId(conn.id)}
            onUpdated={refetch}
          />
        ))}
      </div>

      <AnimatePresence>
        {deleteId && (
          <DeleteConfirmDialog
            onCancel={() => setDeleteId(null)}
            onConfirm={async () => {
              await api.delete(`/api/v1/integrations/connections/${deleteId}`)
              setDeleteId(null)
              refetch()
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function AddConnectionForm({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({ base_url: "", db: "", username: "", password: "", label: "" })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.post<IntegrationConnection>("/api/v1/integrations/connect", {
        provider: "odoo",
        label: form.label || `Odoo — ${form.base_url}`,
        base_url: form.base_url,
        db: form.db,
        username: form.username,
        password: form.password,
      })
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connection failed")
    } finally {
      setLoading(false)
    }
  }

  const valid = form.base_url && form.db && form.username && form.password

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="rounded-xl border border-border/40 bg-card p-6 space-y-4 relative"
    >
      <button onClick={onClose} className="absolute top-4 right-4 text-muted-foreground hover:text-foreground">
        <X className="h-4 w-4" />
      </button>
      <h2 className="text-lg font-medium flex items-center gap-2">
        <Plug className="h-5 w-5 text-primary" />
        Connect Odoo
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Odoo URL" placeholder="https://my-odoo-instance.com" value={form.base_url} onChange={(v) => setForm({ ...form, base_url: v })} />
        <Field label="Database" placeholder="odoo_db_name" value={form.db} onChange={(v) => setForm({ ...form, db: v })} />
        <Field label="Username" placeholder="admin" value={form.username} onChange={(v) => setForm({ ...form, username: v })} />
        <Field label="Password / API Key" type="password" placeholder="••••••••" value={form.password} onChange={(v) => setForm({ ...form, password: v })} />
      </div>
      <Field label="Label (optional)" placeholder="My Warehouse" value={form.label} onChange={(v) => setForm({ ...form, label: v })} />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-3">
        <button onClick={handleSubmit} disabled={loading || !valid} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
          {loading ? "Connecting..." : "Connect"}
        </button>
        <button onClick={onClose} className="rounded-lg border border-border/40 px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
          Cancel
        </button>
      </div>
    </motion.div>
  )
}

function Field({ label, placeholder, value, onChange, type = "text" }: {
  label: string; placeholder: string; value: string; onChange: (v: string) => void; type?: string
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-border/40 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
    </div>
  )
}

function ConnectionCard({ conn, onDelete, onUpdated }: {
  conn: IntegrationConnection; onDelete: () => void; onUpdated: () => void
}) {
  const [action, setAction] = useState<"idle" | "testing" | "syncing">("idle")
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editing, setEditing] = useState(false)
  const [label, setLabel] = useState(conn.label)

  const showFeedback = useCallback((type: "success" | "error", text: string) => {
    setFeedback({ type, text })
    setTimeout(() => setFeedback(null), 5000)
  }, [])

  const handleTest = async () => {
    setAction("testing")
    setFeedback(null)
    try {
      const res = await api.post<{ connected: boolean; version?: string }>(`/api/v1/integrations/connections/${conn.id}/test`)
      if (res.connected) {
        showFeedback("success", `Connected — v${res.version || "?"}`)
      } else {
        showFeedback("error", "Connection failed")
      }
      onUpdated()
    } catch (err: unknown) {
      showFeedback("error", err instanceof Error ? err.message : "Test failed")
    } finally {
      setAction("idle")
    }
  }

  const handleSync = async () => {
    setAction("syncing")
    setFeedback(null)
    try {
      const res = await api.post<SyncResult>(`/api/v1/integrations/connections/${conn.id}/sync`)
      showFeedback("success", res.message || "Sync completed")
      onUpdated()
    } catch (err: unknown) {
      showFeedback("error", err instanceof Error ? err.message : "Sync failed")
    } finally {
      setAction("idle")
    }
  }

  const handleSaveLabel = async () => {
    setEditing(false)
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border/40 bg-card p-5 space-y-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
            conn.is_connected ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
          }`}>
            {conn.is_connected ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
          </div>
          <div className="min-w-0">
            {editing ? (
              <input
                autoFocus
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                onBlur={handleSaveLabel}
                onKeyDown={(e) => e.key === "Enter" && handleSaveLabel()}
                className="rounded border border-border/40 bg-background px-2 py-1 text-sm font-medium w-full"
              />
            ) : (
              <h3
                className="font-medium text-foreground cursor-pointer hover:text-primary transition-colors truncate"
                onClick={() => setEditing(true)}
                title="Click to rename"
              >
                {conn.label || conn.base_url}
              </h3>
            )}
            <p className="text-xs text-muted-foreground mt-0.5">
              {conn.provider.toUpperCase()} &middot; {conn.base_url}
              {conn.version && <> &middot; v{conn.version}</>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <ActionButton
            icon={action === "testing" ? Loader2 : TestTube}
            label="Test"
            onClick={handleTest}
            disabled={action !== "idle"}
            spin={action === "testing"}
          />
          <ActionButton
            icon={action === "syncing" ? Loader2 : RefreshCw}
            label="Sync"
            onClick={handleSync}
            disabled={action !== "idle" || !conn.is_connected}
            spin={action === "syncing"}
            title={!conn.is_connected ? "Connect first" : "Sync data from Odoo"}
          />
          <ActionButton icon={Trash2} label="" onClick={onDelete} disabled={action !== "idle"} danger />
        </div>
      </div>

      {feedback && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
            feedback.type === "success" ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-600"
          }`}
        >
          {feedback.type === "success" ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> : <AlertTriangle className="h-3.5 w-3.5 shrink-0" />}
          {feedback.text}
        </motion.div>
      )}

      <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted-foreground">
        <StatusBadge status={conn.sync_status} />
        <span>Orders: <strong>{conn.total_orders_synced}</strong></span>
        <span>Products: <strong>{conn.total_products_synced}</strong></span>
        {conn.last_sync_at && (
          <span>Last sync: <strong>{new Date(conn.last_sync_at).toLocaleString()}</strong></span>
        )}
        {conn.error_message && (
          <span className="text-red-500 truncate max-w-[300px]" title={conn.error_message}>
            Error: {conn.error_message}
          </span>
        )}
      </div>
    </motion.div>
  )
}

function ActionButton({ icon: Icon, label, onClick, disabled, spin, danger, title }: {
  icon: typeof Loader2; label: string; onClick: () => void; disabled?: boolean; spin?: boolean; danger?: boolean; title?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-lg border border-border/40 px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
        danger ? "text-red-500 hover:bg-red-500/10 hover:border-red-500/30" : "hover:bg-muted"
      }`}
    >
      <Icon className={`h-3.5 w-3.5 ${spin ? "animate-spin" : ""}`} />
      {label}
    </button>
  )
}

function DeleteConfirmDialog({ onCancel, onConfirm }: { onCancel: () => void; onConfirm: () => void }) {
  const [loading, setLoading] = useState(false)
  const handleConfirm = async () => {
    setLoading(true)
    await onConfirm()
    setLoading(false)
  }
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onCancel}
    >
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.95 }}
        className="rounded-xl border border-border/40 bg-card p-6 w-full max-w-sm mx-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10 text-red-500">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <h3 className="font-semibold">Delete Connection</h3>
        </div>
        <p className="text-sm text-muted-foreground mb-6">
          Are you sure? This will remove the integration and all its sync history.
        </p>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} disabled={loading} className="rounded-lg border border-border/40 px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
            Cancel
          </button>
          <button onClick={handleConfirm} disabled={loading} className="inline-flex items-center gap-2 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 transition-colors disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Delete
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    success: "bg-emerald-500/10 text-emerald-600",
    error: "bg-red-500/10 text-red-600",
    connected: "bg-blue-500/10 text-blue-600",
    configured: "bg-amber-500/10 text-amber-600",
    never: "bg-muted text-muted-foreground",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] || colors.never}`}>
      {status}
    </span>
  )
}
