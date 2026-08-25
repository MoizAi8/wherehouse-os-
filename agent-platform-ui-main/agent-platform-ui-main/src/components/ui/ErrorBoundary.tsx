"use client"

import { Component, type ReactNode, ErrorInfo } from "react"
import { RefreshCw, Bug } from "lucide-react"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  fallbackMessage?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ error, errorInfo })
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
    // Log to console for debugging
    console.error("ErrorBoundary caught:", error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <Bug className="h-6 w-6" />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium text-destructive">
              {this.props.fallbackMessage || "Something went wrong"}
            </p>
            {this.state.error && (
              <details className="text-left max-w-md text-[11px] text-muted-foreground bg-muted/50 rounded p-3">
                <summary className="cursor-pointer font-medium mb-2">Error details</summary>
                <pre className="whitespace-pre-wrap overflow-auto max-h-40">
                  {this.state.error.message}
                  {this.state.errorInfo?.componentStack && `\n\n${this.state.errorInfo.componentStack}`}
                </pre>
              </details>
            )}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// Specialized error boundaries for different parts of the app
export function DashboardErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallbackMessage="Dashboard failed to load"
      onError={(error) => console.error("Dashboard error:", error)}
    >
      {children}
    </ErrorBoundary>
  )
}

export function AgentPanelErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallbackMessage="Agent panel unavailable"
      onError={(error) => console.error("Agent panel error:", error)}
    >
      {children}
    </ErrorBoundary>
  )
}

export function ChatErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallbackMessage="Chat assistant unavailable"
      onError={(error) => console.error("Chat error:", error)}
    >
      {children}
    </ErrorBoundary>
  )
}

export function MetricsErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallbackMessage="Metrics unavailable"
      onError={(error) => console.error("Metrics error:", error)}
    >
      {children}
    </ErrorBoundary>
  )
}
