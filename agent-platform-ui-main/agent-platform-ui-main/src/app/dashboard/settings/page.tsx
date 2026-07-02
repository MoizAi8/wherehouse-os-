"use client"

import { useSettings } from "@/contexts/SettingsContext"

export default function SettingsPage() {
  const { settings } = useSettings()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">Ask AI to update settings</p>
      </div>

      <div className="rounded-xl border border-border/50 bg-card p-6">
        <h2 className="text-base font-semibold text-foreground mb-4">Current Configuration</h2>
        <div className="space-y-3 text-sm">
          {[
            { label: "App Name", value: settings.appName },
            { label: "Timezone", value: settings.timezone },
            { label: "Language", value: settings.language },
            { label: "Theme", value: settings.theme },
            { label: "API Endpoint", value: settings.apiEndpoint },
          ].map((s) => (
            <div key={s.label} className="flex items-center justify-between py-1.5 border-b border-border/20 last:border-0">
              <span className="text-muted-foreground">{s.label}</span>
              <span className="text-foreground font-medium">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
