import { describe, expect, it } from "vitest"
import { accessTokenExpiry } from "@/lib/token-expiry"

const token = (payload: unknown) => `header.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.signature`

describe("backend access token lifetime", () => {
  it("uses the backend's absolute expiry instead of extending it on session reads", () => {
    expect(accessTokenExpiry(token({ exp: 1730000000 }))).toBe(1730000000000)
  })
  it.each([undefined, "", "malformed", "header.%%.signature", token({}), token({ exp: "1730000000" })])(
    "fails closed for missing or malformed lifetime %s", value => {
      expect(accessTokenExpiry(value)).toBeUndefined()
    },
  )
})
