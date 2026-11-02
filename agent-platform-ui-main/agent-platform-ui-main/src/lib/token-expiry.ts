/** Read only the lifetime of a token returned by our backend. FastAPI still
 * verifies the signature, identity and permissions on every protected call. */
export function accessTokenExpiry(value: unknown): number | undefined {
  if (typeof value !== "string") return undefined
  try {
    const parts = value.split(".")
    if (parts.length !== 3) return undefined
    const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"))
    return typeof payload.exp === "number" && Number.isFinite(payload.exp)
      ? payload.exp * 1000 : undefined
  } catch {
    return undefined
  }
}
