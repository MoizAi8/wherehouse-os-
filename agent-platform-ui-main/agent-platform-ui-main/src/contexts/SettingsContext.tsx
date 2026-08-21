"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { api } from "@/lib/api"

export interface AppSettings {
  theme: "dark" | "light"
  appName: string
  timezone: string
  language: string
  emailAlerts: boolean
  smsAlerts: boolean
  delayNotifications: boolean
  anomalyAlerts: boolean
  twoFactor: boolean
  sessionTimeout: number
  compactMode: boolean
  apiEndpoint: string
  webhookUrl: string
  autoCleanupDays: number
  autoBackup: boolean
}

const defaults: AppSettings = {
  theme: "dark",
  appName: "Warehouse OS",
  timezone: "UTC",
  language: "English",
  emailAlerts: true,
  smsAlerts: false,
  delayNotifications: true,
  anomalyAlerts: true,
  twoFactor: false,
  sessionTimeout: 60,
  compactMode: false,
  apiEndpoint: "",
  webhookUrl: "",
  autoCleanupDays: 90,
  autoBackup: true,
}

interface SettingsContextType {
  settings: AppSettings
  updateSetting: <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => void
  resetSettings: () => void
  hasChanges: boolean
}

const STORAGE_KEY = "warehouse-os-settings"

const SettingsContext = createContext<SettingsContextType | null>(null)

function loadLocal(): AppSettings {
  if (typeof window === "undefined") return { ...defaults }
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      return { ...defaults, ...parsed }
    }
  } catch {}
  return { ...defaults }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(defaults)
  const [loaded, setLoaded] = useState(false)
  const [savedSnapshot, setSavedSnapshot] = useState(JSON.stringify(defaults))

  useEffect(() => {
    const local = loadLocal()

    api.get<AppSettings>("/api/v1/settings")
      .then((remote) => {
        const merged = { ...defaults, ...local, ...remote }
        setSettings(merged)
        setSavedSnapshot(JSON.stringify(merged))
      })
      .catch(() => {
        setSettings(local)
        setSavedSnapshot(JSON.stringify(local))
      })
      .finally(() => setLoaded(true))
  }, [])

  useEffect(() => {
    if (!loaded) return
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    applyTheme(settings.theme)
  }, [settings, loaded])

  const updateSetting = useCallback(<K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }, [])

  const resetSettings = useCallback(() => {
    setSettings({ ...defaults })
  }, [])

  const hasChanges = JSON.stringify(settings) !== savedSnapshot

  return (
    <SettingsContext.Provider value={{ settings, updateSetting, resetSettings, hasChanges }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider")
  return ctx
}

function applyTheme(theme: string) {
  const root = document.documentElement
  if (theme === "light") {
    root.classList.remove("dark")
    root.style.setProperty("--background", "#ffffff")
    root.style.setProperty("--foreground", "#09090b")
    root.style.setProperty("--card", "#ffffff")
    root.style.setProperty("--card-foreground", "#09090b")
    root.style.setProperty("--muted", "#f4f4f5")
    root.style.setProperty("--muted-foreground", "#71717a")
    root.style.setProperty("--border", "#e4e4e7")
    root.style.setProperty("--sidebar", "#f8f8fa")
    root.style.setProperty("--sidebar-foreground", "#71717a")
    root.style.setProperty("--sidebar-border", "#e4e4e7")
    root.style.setProperty("--hero", "#fafafa")
    root.style.setProperty("--secondary", "#f4f4f5")
    root.style.setProperty("--secondary-foreground", "#09090b")
  } else {
    root.classList.add("dark")
    root.style.setProperty("--background", "#09090b")
    root.style.setProperty("--foreground", "#fafafa")
    root.style.setProperty("--card", "#111113")
    root.style.setProperty("--card-foreground", "#fafafa")
    root.style.setProperty("--muted", "#1a1a1e")
    root.style.setProperty("--muted-foreground", "#a1a1aa")
    root.style.setProperty("--border", "#27272a")
    root.style.setProperty("--sidebar", "#0a0a0d")
    root.style.setProperty("--sidebar-foreground", "#a1a1aa")
    root.style.setProperty("--sidebar-border", "#1c1c20")
    root.style.setProperty("--hero", "#0c0c12")
    root.style.setProperty("--secondary", "#1f1f23")
    root.style.setProperty("--secondary-foreground", "#fafafa")
  }
}
