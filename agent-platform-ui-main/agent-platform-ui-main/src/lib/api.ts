export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = "ApiError"
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {}

  try {
    const { getSession } = await import("next-auth/react")
    const session = await getSession()
    if (session?.accessToken) {
      return { Authorization: `Bearer ${session.accessToken}` }
    }
  } catch {
    // No active session — requests proceed without auth (server rejects with 401).
  }
  return {}
}

async function request<T>(path: string, options?: RequestInit, retried = false): Promise<T> {
  const authHeaders = await getAuthHeaders()

  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
  })

  if (res.status === 401 && !retried && typeof window !== "undefined") {
    const { refreshSession } = await import("@/lib/session")
    if (await refreshSession()) {
      return request<T>(path, options, true)
    }
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new ApiError(res.status, body || res.statusText)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
}
